"""Tests for mirror-pull prune behavior.

Verifies that `agent-sync pull --prune` removes local skills that exist
in the hub (~/.agents/skills/) but are missing from the local clone of
the private repo. Default pull (no --prune) is additive only.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_hub_with(tmp_path: Path, skill_names: list[str]) -> Path:
    """Create a fake ~/.agents/skills/ with the given skill dirs."""
    hub = tmp_path / ".agents" / "skills"
    hub.mkdir(parents=True)
    for name in skill_names:
        (hub / name).mkdir()
        (hub / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    return hub


def _make_privado_with(tmp_path: Path, skill_names: list[str]) -> Path:
    """Create a fake local clone of the private repo (repo_dir/skills/)."""
    repo_dir = tmp_path / "agent-sync-repo"
    skills = repo_dir / "skills"
    skills.mkdir(parents=True)
    for name in skill_names:
        (skills / name).mkdir()
        (skills / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    return repo_dir


def _make_sync_manager(hub_path: Path, repo_dir: Path):
    """Build a SyncManager with a mocked repo_dir + home pointing at hub_path."""
    from agent_sync.sync import SyncManager

    sm = SyncManager.__new__(SyncManager)  # bypass __init__ (no real config needed)
    sm.repo_dir = repo_dir
    sm.config = MagicMock()
    return sm


class TestDetectLocalOrphanSkills:
    """Tests for the read-only detection helper used in preview + prune."""

    def test_no_orphans_returns_empty(self, tmp_path):
        """Local hub == privado (skill names) → no orphans."""
        _make_hub_with(tmp_path, ["cali-coding-go-stack", "cali-coding-starhtml"])
        repo_dir = _make_privado_with(tmp_path, ["cali-coding-go-stack", "cali-coding-starhtml"])

        sm = _make_sync_manager(tmp_path / ".agents" / "skills", repo_dir)
        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            orphans = sm._detect_local_orphan_skills()

        assert orphans == []

    def test_orphans_detected(self, tmp_path):
        """Local-only skills (in hub but not in privado) are returned."""
        _make_hub_with(tmp_path, ["cali-coding-go-stack", "cali-go-stack", "cali-starhtml"])
        repo_dir = _make_privado_with(tmp_path, ["cali-coding-go-stack"])

        sm = _make_sync_manager(tmp_path / ".agents" / "skills", repo_dir)
        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            orphans = sm._detect_local_orphan_skills()

        assert sorted(orphans) == ["cali-go-stack", "cali-starhtml"]

    def test_missing_local_hub_returns_empty(self, tmp_path):
        """If ~/.agents/skills/ doesn't exist, no orphans."""
        repo_dir = _make_privado_with(tmp_path, ["cali-coding-go-stack"])
        sm = _make_sync_manager(tmp_path / ".agents" / "skills", repo_dir)

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            orphans = sm._detect_local_orphan_skills()

        assert orphans == []

    def test_missing_repo_skills_dir_returns_empty(self, tmp_path):
        """If the local clone of privado has no skills/, no orphans."""
        _make_hub_with(tmp_path, ["cali-coding-go-stack", "cali-go-stack"])
        repo_dir = tmp_path / "agent-sync-repo"
        repo_dir.mkdir()  # no skills/ subdir

        sm = _make_sync_manager(tmp_path / ".agents" / "skills", repo_dir)
        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            orphans = sm._detect_local_orphan_skills()

        assert orphans == []

    def test_hidden_dirs_ignored(self, tmp_path):
        """Hidden dirs in hub (like .cali-product-workflow) are NOT orphans."""
        hub = tmp_path / ".agents" / "skills"
        hub.mkdir(parents=True)
        (hub / "cali-coding-go-stack").mkdir()
        (hub / "cali-coding-go-stack" / "SKILL.md").write_text("x")
        (hub / ".cali-product-workflow").mkdir()

        repo_dir = _make_privado_with(tmp_path, ["cali-coding-go-stack"])

        sm = _make_sync_manager(hub, repo_dir)
        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            orphans = sm._detect_local_orphan_skills()

        # .cali-product-workflow is hidden state, not a skill
        assert orphans == []


class TestPruneLocalOrphanSkills:
    """Tests for the actual deletion helper."""

    def test_no_orphans_returns_empty(self, tmp_path):
        """Local hub == privado → no deletion."""
        _make_hub_with(tmp_path, ["cali-coding-go-stack"])
        repo_dir = _make_privado_with(tmp_path, ["cali-coding-go-stack"])

        sm = _make_sync_manager(tmp_path / ".agents" / "skills", repo_dir)
        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            pruned = sm._prune_local_orphan_skills()

        assert pruned == []
        assert (tmp_path / ".agents" / "skills" / "cali-coding-go-stack").exists()

    def test_orphans_removed(self, tmp_path):
        """Local-only skills are deleted from disk."""
        _make_hub_with(tmp_path, ["cali-coding-go-stack", "cali-go-stack", "cali-starhtml"])
        repo_dir = _make_privado_with(tmp_path, ["cali-coding-go-stack"])

        sm = _make_sync_manager(tmp_path / ".agents" / "skills", repo_dir)
        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            pruned = sm._prune_local_orphan_skills()

        # Verify the return shape
        assert len(pruned) == 2
        for entry in pruned:
            assert entry["status"] == "D"
            assert "deleted" in entry["label"].lower()
            assert "prune" in entry["label"].lower()

        # Verify filesystem
        hub = tmp_path / ".agents" / "skills"
        assert (hub / "cali-coding-go-stack").exists()  # kept
        assert not (hub / "cali-go-stack").exists()      # removed
        assert not (hub / "cali-starhtml").exists()     # removed

    def test_missing_hub_returns_empty(self, tmp_path):
        """Missing ~/.agents/skills/ → no-op."""
        repo_dir = _make_privado_with(tmp_path, ["cali-coding-go-stack"])
        sm = _make_sync_manager(tmp_path / ".agents" / "skills", repo_dir)

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            pruned = sm._prune_local_orphan_skills()

        assert pruned == []


class TestPullPruneParameter:
    """Tests for the prune parameter on SyncManager.pull()."""

    def test_pull_default_prune_false(self):
        """Default prune=False on pull() — safety by default."""
        import inspect
        from agent_sync.sync import SyncManager

        sig = inspect.signature(SyncManager.pull)
        assert sig.parameters["prune"].default is False
