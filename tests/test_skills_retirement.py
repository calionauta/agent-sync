"""Regression tests for skill retirement and active-set detection.

Retirement is now manifest-based: a skill is retired if and only if it
appears in `~/.agents/skills/RETIRED.md` (or `repo/skills/RETIRED.md`).
`active = HEAD - manifest` (KISS, AD-1, AD-4).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_sync.skills import SkillsManager
from agent_sync.sync import SyncManager


# --- Manifest parser tests (no git, no repo) -------------------------------


def test_manifest_empty_file(tmp_path):
    """An empty manifest yields an empty retired set."""
    manifest = tmp_path / "RETIRED.md"
    manifest.write_text("")
    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    assert sm._parse_retired_manifest(manifest) == set()


def test_manifest_missing_file(tmp_path):
    """A missing manifest yields an empty retired set."""
    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    assert sm._parse_retired_manifest(tmp_path / "nonexistent.md") == set()


def test_manifest_simple(tmp_path):
    """One skill per line, parsed correctly."""
    manifest = tmp_path / "RETIRED.md"
    manifest.write_text(
        "# Retired skills\n"
        "cali-old-skill\n"
        "cali-another-old\n"
    )
    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    assert sm._parse_retired_manifest(manifest) == {"cali-old-skill", "cali-another-old"}


def test_manifest_with_inline_comments_and_dates(tmp_path):
    """Trailing text after the skill name is ignored."""
    manifest = tmp_path / "RETIRED.md"
    manifest.write_text(
        "cali-old-skill   # renamed to cali-new  2026-05-01\n"
        "cali-another     # replaced\n"
    )
    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    assert sm._parse_retired_manifest(manifest) == {"cali-old-skill", "cali-another"}


def test_manifest_blank_lines_and_comments_ignored(tmp_path):
    manifest = tmp_path / "RETIRED.md"
    manifest.write_text(
        "\n"
        "# Header comment\n"
        "\n"
        "cali-real-retired\n"
        "  \n"
        "# Another comment\n"
        "cali-second\n"
    )
    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    assert sm._parse_retired_manifest(manifest) == {"cali-real-retired", "cali-second"}


def test_manifest_skips_dotfiles(tmp_path):
    """Hidden skill names (starting with `.`) are ignored."""
    manifest = tmp_path / "RETIRED.md"
    manifest.write_text(
        "cali-visible\n"
        ".cali-internal\n"
    )
    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    assert sm._parse_retired_manifest(manifest) == {"cali-visible"}


def test_manifest_malformed_line_doesnt_crash(tmp_path):
    """A line with only whitespace is skipped; a `#`-only line is skipped."""
    manifest = tmp_path / "RETIRED.md"
    manifest.write_text("   \n#\ncali-good\n")
    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    assert sm._parse_retired_manifest(manifest) == {"cali-good"}


# --- _get_retired_skill_names with git + manifest ---------------------------


def _git(cwd: Path, *args: str) -> str:
    import subprocess
    result = subprocess.run(
        ["git", "-C", str(cwd)] + list(args),
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def _commit_file(repo: Path, relpath: str, content: str, msg: str) -> None:
    full = repo / relpath
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    _git(repo, "add", relpath)
    _git(repo, "commit", "-m", msg)


def _init_repo_with_skills(tmp_path: Path, names: list[str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "Test")
    for name in names:
        _commit_file(repo, f"skills/{name}/SKILL.md", f"# {name}\n", f"add {name}")
    return repo


def test_retired_skill_from_manifest(tmp_path):
    """A skill in the manifest IS retired, regardless of HEAD state."""
    repo = _init_repo_with_skills(tmp_path, ["alive", "old"])
    manifest = tmp_path / "hub" / "RETIRED.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("old\n")

    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch("agent_sync.paths.REPO_DIR", repo):
        retired = sm._get_retired_skill_names()
    assert retired == {"old"}


def test_retired_uses_hub_manifest_over_repo_manifest(tmp_path):
    """If both `~/.agents/skills/RETIRED.md` and `repo/skills/RETIRED.md`
    exist, the hub one wins (local edits take precedence)."""
    repo = _init_repo_with_skills(tmp_path, ["a", "b"])
    _commit_file(repo, "skills/RETIRED.md", "a\n", "manifest in repo")
    (tmp_path / "hub").mkdir(parents=True)
    (tmp_path / "hub" / "RETIRED.md").write_text("b\n")

    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch("agent_sync.paths.REPO_DIR", repo):
        retired = sm._get_retired_skill_names()
    assert retired == {"b"}


def test_active_excludes_retired(tmp_path):
    """`_get_active_skill_names()` = HEAD - manifest."""
    repo = _init_repo_with_skills(tmp_path, ["alive", "old", "new"])
    manifest = tmp_path / "hub" / "RETIRED.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("old\n")

    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch("agent_sync.paths.REPO_DIR", repo):
        active = sm._get_active_skill_names()
    assert active == {"alive", "new"}


def test_active_unretire_by_removing_from_manifest(tmp_path):
    """Removing a skill from the manifest re-activates it immediately."""
    repo = _init_repo_with_skills(tmp_path, ["alive", "old"])
    manifest = tmp_path / "hub" / "RETIRED.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("old\n")

    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch("agent_sync.paths.REPO_DIR", repo):
        assert "old" not in sm._get_active_skill_names()

    # Unretire by editing manifest
    manifest.write_text("")
    with patch("agent_sync.paths.REPO_DIR", repo):
        assert "old" in sm._get_active_skill_names()


def test_active_returns_empty_set_without_repo(tmp_path):
    """A non-git repo yields an empty active set (defensive)."""
    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch("agent_sync.paths.REPO_DIR", tmp_path / "no-repo"):
        active = sm._get_active_skill_names()
    assert active == set()


# --- Regression: 2026-06-06 incident ----------------------------------------
#
# The original bug: a skill was deleted in a past commit, re-added in a
# later commit, and `git log --all --diff-filter=D` flagged it as retired
# permanently. After this refactor, a skill that exists in HEAD is active
# regardless of past deletions — IF it is not in the manifest.


def test_regression_2026_06_06_re_added_skill_is_active(tmp_path):
    """A skill deleted then re-added in HEAD is ACTIVE (not retired)."""
    repo = _init_repo_with_skills(tmp_path, ["cali-resurrected"])
    _git(repo, "rm", "-r", "skills/cali-resurrected")
    _git(repo, "commit", "-m", "temp delete")
    _commit_file(
        repo, "skills/cali-resurrected/SKILL.md", "# cali-resurrected\n", "re-add"
    )

    sm = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch("agent_sync.paths.REPO_DIR", repo):
        active = sm._get_active_skill_names()
        retired = sm._get_retired_skill_names()

    assert "cali-resurrected" in active
    assert "cali-resurrected" not in retired
