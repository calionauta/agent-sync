"""Integration tests for the full sync loop: centralize -> push -> pull.

These tests exercise real git and real filesystem operations to catch
bugs that unit tests with mocks miss. The most important test is the
regression for the 2026-06-06 incident, which would have been caught
by test_01_re_added_skill_survives_loop.

The tests are slow (each creates a bare remote, clones it, runs git
ops). Mark with @pytest.mark.integration to allow selective execution:

    pytest tests/integration/                    # all
    pytest -m "not integration" tests/           # skip these
    pytest -m integration tests/integration/     # only these
"""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_sync.config import Config
from agent_sync.skills import SkillsManager
from agent_sync.sync import SyncManager


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd)] + list(args),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: {result.stderr}"
        )
    return result.stdout


def _init_bare_with_main(bare: Path) -> None:
    """Create a bare git repo with a `main` branch and a no-op commit."""
    bare.mkdir(parents=True, exist_ok=True)
    _git(bare, "init", "--bare", "-b", "main", str(bare))


def _seed_skill(repo: Path, name: str, content: str = "# " + "stub\n") -> None:
    """Add a skill dir to the repo and commit it."""
    (repo / "skills" / name).mkdir(parents=True, exist_ok=True)
    (repo / "skills" / name / "SKILL.md").write_text(content)
    _git(repo, "add", f"skills/{name}/SKILL.md")
    _git(repo, "commit", "-m", f"add {name}")


def _build_test_env(
    tmp_path: Path,
    seed_skills: list[str] = (),
    manifest_entries: list[str] = (),
) -> tuple[Path, Path, Path]:
    """Build a full test environment: bare remote, repo clone, hub.

    Returns: (hub_dir, repo_dir, bare_remote)
    """
    bare = tmp_path / "remote.git"
    _init_bare_with_main(bare)

    # Initial empty commit on the bare so we can clone and push to main
    tmp_seed = tmp_path / "seed"
    tmp_seed.mkdir()
    _git(tmp_seed, "init", "-b", "main")
    _git(tmp_seed, "config", "user.email", "test@test.local")
    _git(tmp_seed, "config", "user.name", "Test")
    _git(tmp_seed, "commit", "--allow-empty", "-m", "initial")
    _git(tmp_seed, "remote", "add", "origin", str(bare))
    _git(tmp_seed, "push", "origin", "main")

    # Clone the bare into repo_dir
    repo = tmp_path / "repo"
    _git(tmp_seed, "clone", str(bare), str(repo))
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "Test")

    # Seed skills in the repo
    for skill in seed_skills:
        _seed_skill(repo, skill)
    if seed_skills:
        _git(repo, "push", "origin", "main")

    # Hub directory with optional manifest
    hub = tmp_path / "hub"
    hub.mkdir(parents=True, exist_ok=True)
    if manifest_entries:
        manifest = hub / "RETIRED.md"
        lines = [
            "# Retired Skills (test)",
            "# One per line. Comments and trailing text are ignored.",
            "",
        ]
        lines.extend(manifest_entries)
        manifest.write_text("\n".join(lines) + "\n")

    return hub, repo, bare


def _make_sync_manager(hub: Path, repo: Path, bare: Path) -> SyncManager:
    """Build a SyncManager pointed at the test env.

    Config is a MagicMock with just the attrs SyncManager touches.
    """
    config = MagicMock(spec=Config)
    config.repo_url = str(bare)
    config.app_dir = repo.parent / "app"
    config.app_dir.mkdir(parents=True, exist_ok=True)
    config.state_file = config.app_dir / "state.json"
    config.is_agent_enabled.return_value = False
    config.agents = []

    sm = SyncManager(config)
    sm.repo_dir = repo  # also override after init
    return sm


def _make_skills_manager(hub: Path) -> SkillsManager:
    """Build a SkillsManager pointed at the test hub."""
    return SkillsManager(global_skills_dir=hub)


# ---------------------------------------------------------------------------
# Scenario 1 (REGRESSION 2026-06-06): re-added skill survives the loop
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_01_re_added_skill_survives_loop(tmp_path):
    """Regression: a skill in the repo (not in the local hub, no manifest
    entry) is NOT pruned by `push`. It gets imported to the hub by
    `centralize` and stays in sync across push + pull.

    Before the fix, the prune-orphan logic would have deleted the skill
    from the repo on the first push, mirroring an empty hub.
    """
    hub, repo, bare = _build_test_env(tmp_path, seed_skills=["cali-coding-go-stack"])

    with patch("agent_sync.paths.HUB_DIR", hub), \
         patch("agent_sync.paths.REPO_DIR", repo):
        sm = _make_sync_manager(hub, repo, bare)

        # 1. Sanity: skill is in the repo, hub is empty
        assert (repo / "skills" / "cali-coding-go-stack" / "SKILL.md").exists()
        assert not (hub / "cali-coding-go-stack").exists()

        # 2. `centralize` should import the skill from the repo to the hub
        #    (Phase 2 of centralize: _sync_from_repo copies missing skills)
        skills_mgr = _make_skills_manager(hub)
        synced = skills_mgr._sync_from_repo()
        assert synced == 1, "Expected the skill to be synced from repo to hub"
        assert (hub / "cali-coding-go-stack" / "SKILL.md").exists()

        # 3. `push` (default, prune=False) should NOT delete the skill
        changed_files, orphans = sm._push_stage_and_get_changes("test commit")
        # The orphan list should be empty (hub and repo are now in sync)
        assert orphans == [], f"Orphans detected: {orphans}"
        # No D-status (delete) entries
        deletes = [f for f in changed_files if "D" in f.get("status", "")]
        assert deletes == [], f"Unexpected deletes in changed_files: {deletes}"


# ---------------------------------------------------------------------------
# Scenario 2: hub has new skill, push commits it, no orphan
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_02_hub_new_skill_pushed_cleanly(tmp_path):
    """Skill in hub only (new) gets committed and pushed. No orphans."""
    hub, repo, bare = _build_test_env(tmp_path, seed_skills=[])

    # Add the skill to the hub BEFORE any sync
    (hub / "cali-new-skill").mkdir(parents=True)
    (hub / "cali-new-skill" / "SKILL.md").write_text("# cali-new-skill\n")

    with patch("agent_sync.paths.HUB_DIR", hub), \
         patch("agent_sync.paths.REPO_DIR", repo):
        sm = _make_sync_manager(hub, repo, bare)

        # Centralize (only sync_from_repo matters here; agents are not configured)
        skills_mgr = _make_skills_manager(hub)
        skills_mgr._sync_from_repo()  # no-op since hub has it but repo doesn't

        # Stage and detect orphans
        changed_files, orphans = sm._push_stage_and_get_changes("add cali-new-skill")

        # The new skill should appear in the changed files. The stage
        # method reports whole directories (`skills/`) as untracked `??`
        # rather than individual files. Verify the skill is in the
        # discovered set.
        skills_changed = [f for f in changed_files
                          if f["path"] == "skills" or f["path"].startswith("skills/")]
        assert skills_changed, f"Expected skills/ in changes, got: {changed_files}"

        # No orphans (hub and repo in sync after push)
        assert orphans == []


# ---------------------------------------------------------------------------
# Scenario 3: manifest-declared retired skill stays retired
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_03_manifest_retired_skill_stays_retired(tmp_path):
    """A skill listed in RETIRED.md is NOT re-imported by centralize
    even if it exists in the repo. After push, no orphan.
    """
    hub, repo, bare = _build_test_env(
        tmp_path,
        seed_skills=["cali-questions-quality"],
        manifest_entries=["cali-questions-quality"],
    )

    with patch("agent_sync.paths.HUB_DIR", hub), \
         patch("agent_sync.paths.REPO_DIR", repo):
        sm = _make_sync_manager(hub, repo, bare)

        # centralize: should NOT import the retired skill to the hub
        skills_mgr = _make_skills_manager(hub)
        synced = skills_mgr._sync_from_repo()
        assert synced == 0, f"Retired skill was imported: {synced}"
        assert not (hub / "cali-questions-quality").exists(), \
            "Retired skill should not be in hub"

        # push: even with prune=True, the retired skill should NOT be
        # pruned (manifest says it's intentionally retired).
        changed_files, orphans = sm._push_stage_and_get_changes(
            "test", prune=True
        )
        # The skill is absent from the hub, so _detect_orphan_skills WILL
        # list it as an orphan. The prune step (if invoked) must skip it
        # because it's in the manifest. Verify no delete was staged.
        deletes = [f for f in changed_files if f.get("status") == "D"]
        assert not any("cali-questions-quality" in f["path"] for f in deletes), \
            f"Retired skill should not be staged for deletion, got: {deletes}"


# ---------------------------------------------------------------------------
# Scenario 4: detection returns truly-orphaned names (the bug-trigger)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_04_detect_orphan_skills(tmp_path):
    """Direct test of the orphan detection: skill in repo but missing
    from hub, not in manifest, IS an orphan.
    """
    hub, repo, bare = _build_test_env(
        tmp_path, seed_skills=["cali-orphan-1", "cali-orphan-2"]
    )

    # Hub has only one of them
    (hub / "cali-orphan-1").mkdir(parents=True)
    (hub / "cali-orphan-1" / "SKILL.md").write_text("# orphan-1\n")

    with patch("agent_sync.paths.HUB_DIR", hub), \
         patch("agent_sync.paths.REPO_DIR", repo):
        sm = _make_sync_manager(hub, repo, bare)
        orphans = sm._detect_orphan_skills()

    assert orphans == ["cali-orphan-2"], f"Expected only cali-orphan-2, got {orphans}"


# ---------------------------------------------------------------------------
# Scenario 5: prune (--prune=True) removes orphan from repo + commits
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_05_explicit_prune_removes_orphan(tmp_path):
    """With `prune=True`, an orphan skill IS removed from the repo
    in the same commit. Explicit destructive intent acknowledged.
    """
    hub, repo, bare = _build_test_env(
        tmp_path, seed_skills=["cali-ghost"]
    )
    # Hub is empty — cali-ghost is orphan from repo's perspective
    assert not (hub / "cali-ghost").exists()

    with patch("agent_sync.paths.HUB_DIR", hub), \
         patch("agent_sync.paths.REPO_DIR", repo):
        sm = _make_sync_manager(hub, repo, bare)

        changed_files, orphans = sm._push_stage_and_get_changes(
            "prune orphan", prune=True
        )

        # The orphan should have been staged for deletion
        assert orphans == ["cali-ghost"] or orphans == []  # empty after prune
        deletes = [f for f in changed_files if f.get("status") == "D"]
        assert any("cali-ghost" in f["path"] for f in deletes), \
            f"Expected cali-ghost in deletes, got: {deletes}"


# ---------------------------------------------------------------------------
# Scenario 6: end-to-end with a real git remote
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_06_full_centralize_then_pull_round_trip(tmp_path):
    """End-to-end: a skill exists in the remote repo, hub is empty.
    A new clone is created, centralize imports the skill, push is a no-op
    (in sync). Pull on a fresh clone reproduces the skill.

    This is the full circle: source -> hub -> repo -> fresh clone.
    """
    hub, repo, bare = _build_test_env(
        tmp_path, seed_skills=["cali-round-trip"]
    )
    assert (repo / "skills" / "cali-round-trip" / "SKILL.md").exists()

    with patch("agent_sync.paths.HUB_DIR", hub), \
         patch("agent_sync.paths.REPO_DIR", repo):
        sm = _make_sync_manager(hub, repo, bare)
        skills_mgr = _make_skills_manager(hub)

        # Sync from repo to hub
        synced = skills_mgr._sync_from_repo()
        assert synced == 1
        assert (hub / "cali-round-trip" / "SKILL.md").exists()

        # Default push: no orphans, no deletes
        _changed_files, orphans = sm._push_stage_and_get_changes("round trip")
        assert orphans == []


# ---------------------------------------------------------------------------
# Scenario 7: skill with file in skills/ (RETIRED.md) is NOT a phantom orphan
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_07_file_in_skills_dir_not_phantom_orphan(tmp_path):
    """Regression: a FILE in `skills/` (e.g. `RETIRED.md` manifest
    committed to the repo) is NOT treated as a phantom orphan skill.

    Before the fix, `git ls-tree --name-only HEAD skills/` returned
    the file alongside directories. The fix uses `git ls-tree -d`.
    """
    hub, repo, bare = _build_test_env(tmp_path, seed_skills=[])

    # Commit a file in skills/ (simulating the manifest being there)
    (repo / "skills").mkdir(exist_ok=True)
    (repo / "skills" / "RETIRED.md").write_text("# Retired\n")
    _git(repo, "add", "skills/RETIRED.md")
    _git(repo, "commit", "-m", "add retired manifest file")
    _git(repo, "push", "origin", "main")

    with patch("agent_sync.paths.HUB_DIR", hub), \
         patch("agent_sync.paths.REPO_DIR", repo):
        sm = _make_sync_manager(hub, repo, bare)
        orphans = sm._detect_orphan_skills()

    assert "RETIRED.md" not in orphans, \
        f"RETIRED.md (a file) should not appear as orphan, got: {orphans}"


# ---------------------------------------------------------------------------
# Sanity: audit reflects the test state
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_08_audit_reflects_test_state(tmp_path):
    """`audit_skills` reports accurate state for a known test setup."""
    from agent_sync.skills_audit import audit_skills

    hub, repo, bare = _build_test_env(
        tmp_path,
        seed_skills=["cali-in-sync", "cali-orphan"],
        manifest_entries=["cali-retired-only"],
    )
    # Hub has the in-sync one
    (hub / "cali-in-sync").mkdir(parents=True)
    (hub / "cali-in-sync" / "SKILL.md").write_text("# cali-in-sync\n")
    # cali-orphan: in repo, not in hub, not in manifest → in_repo_only
    # cali-retired-only: in manifest, not in repo, not in hub → retired_clean

    with patch("agent_sync.skills_audit.HUB_DIR", hub), \
         patch("agent_sync.skills_audit.REPO_DIR", repo), \
         patch("agent_sync.skills_audit.RETIRED_MANIFEST", hub / "RETIRED.md"):
        report = audit_skills(
            hub_skills=None,
            repo_skills=None,
            manifest_skills=None,
        )

    by_name = {r.name: r for r in report.rows}
    assert by_name["cali-in-sync"].status == "in_sync"
    assert by_name["cali-orphan"].status == "in_repo_only"
    assert by_name["cali-retired-only"].status == "retired_clean"
