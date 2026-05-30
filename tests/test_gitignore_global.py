"""Tests for .gitignore_global sync (push backup + pull apply)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from agent_sync.sync import SyncManager


# ---------------------------------------------------------------------------
# _get_global_gitignore_path
# ---------------------------------------------------------------------------


class TestGetGlobalGitignorePath:
    """Tests for locating the user's global gitignore."""

    def test_returns_configured_path(self, tmp_path):
        """git config points to existing file → returns that path."""
        gitignore = tmp_path / "global.gitignore"
        gitignore.write_text("*.log\n")

        sm = SyncManager.__new__(SyncManager)

        fake_result = MagicMock()
        fake_result.returncode = 0
        fake_result.stdout = str(gitignore) + "\n"

        with patch("agent_sync.sync.subprocess.run", return_value=fake_result):
            result = sm._get_global_gitignore_path()

        assert result == gitignore

    def test_falls_back_to_home_default(self, tmp_path, monkeypatch):
        """git config not set → falls back to ~/.gitignore_global."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        gitignore = home_dir / ".gitignore_global"
        gitignore.write_text("*.log\n")

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))

        sm = SyncManager.__new__(SyncManager)

        fake_result = MagicMock()
        fake_result.returncode = 1
        fake_result.stdout = ""

        with patch("agent_sync.sync.subprocess.run", return_value=fake_result):
            result = sm._get_global_gitignore_path()

        assert result == gitignore

    def test_returns_none_when_nothing_found(self, tmp_path, monkeypatch):
        """No git config and no default file → returns None."""
        empty_home = tmp_path / "empty_home"
        empty_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: empty_home))

        sm = SyncManager.__new__(SyncManager)

        fake_result = MagicMock()
        fake_result.returncode = 1
        fake_result.stdout = ""

        with patch("agent_sync.sync.subprocess.run", return_value=fake_result):
            result = sm._get_global_gitignore_path()

        assert result is None


# ---------------------------------------------------------------------------
# _stage_gitignore_global
# ---------------------------------------------------------------------------


class TestStageGitignoreGlobal:
    """Tests for backing up .gitignore_global to the repo."""

    def _make_sm(self, tmp_path):
        sm = SyncManager.__new__(SyncManager)
        sm.repo_dir = tmp_path / "repo"
        sm.repo_dir.mkdir()
        sm.config = MagicMock()
        return sm

    def test_stages_when_file_exists(self, tmp_path):
        """If local gitignore_global exists, it gets copied to repo."""
        sm = self._make_sm(tmp_path)
        gitignore = tmp_path / ".gitignore_global"
        gitignore.write_text("*.log\n.env\n")

        with patch.object(sm, "_get_global_gitignore_path", return_value=gitignore):
            result = sm._stage_gitignore_global()

        assert result == "configs/gitignore_global"
        assert (sm.repo_dir / "configs" / "gitignore_global").read_text() == "*.log\n.env\n"

    def test_skips_when_identical(self, tmp_path):
        """If repo already has identical content, returns None (no change)."""
        sm = self._make_sm(tmp_path)
        gitignore = tmp_path / ".gitignore_global"
        gitignore.write_text("*.log\n")

        dest = sm.repo_dir / "configs"
        dest.mkdir(parents=True)
        (dest / "gitignore_global").write_text("*.log\n")

        with patch.object(sm, "_get_global_gitignore_path", return_value=gitignore):
            result = sm._stage_gitignore_global()

        assert result is None

    def test_skips_when_no_gitignore(self, tmp_path):
        """If no global gitignore exists, returns None."""
        sm = self._make_sm(tmp_path)

        with patch.object(sm, "_get_global_gitignore_path", return_value=None):
            result = sm._stage_gitignore_global()

        assert result is None


# ---------------------------------------------------------------------------
# _apply_gitignore_global
# ---------------------------------------------------------------------------


class TestApplyGitignoreGlobal:
    """Tests for applying .gitignore_global from the synced repo."""

    def _make_sm_with_repo(self, tmp_path):
        sm = SyncManager.__new__(SyncManager)
        sm.repo_dir = tmp_path / "repo"
        sm.repo_dir.mkdir()
        configs = sm.repo_dir / "configs"
        configs.mkdir()
        sm.config = MagicMock()
        return sm

    def _make_sm_with_gitignore(self, tmp_path, local_content=None):
        sm = self._make_sm_with_repo(tmp_path)

        # Write remote version
        (sm.repo_dir / "configs" / "gitignore_global").write_text("*.log\n.env\n")

        # Write local version if provided
        if local_content is not None:
            gitignore_local = tmp_path / ".gitignore_global"
            gitignore_local.write_text(local_content)
            with patch.object(sm, "_get_global_gitignore_path", return_value=gitignore_local):
                pass  # Just setup
            sm._local_gitignore = gitignore_local
        else:
            sm._local_gitignore = None

        return sm

    def test_no_repo_file_returns_empty(self, tmp_path):
        """If repo doesn't have gitignore_global, returns empty."""
        sm = self._make_sm_with_repo(tmp_path)
        changes = sm._apply_gitignore_global()
        assert changes == []

    def test_force_merges_new_patterns(self, tmp_path):
        """Force mode: adds missing patterns to local, keeps existing."""
        sm = self._make_sm_with_repo(tmp_path)

        remote = "*.log\n.env\nsecrets/\n"
        (sm.repo_dir / "configs" / "gitignore_global").write_text(remote)

        local = tmp_path / ".gitignore_global"
        local.write_text("*.log\n.DS_Store\n")

        with patch.object(sm, "_get_global_gitignore_path", return_value=local):
            changes = sm._apply_gitignore_global(force=True)

        content = local.read_text()
        assert "*.log" in content
        assert ".DS_Store" in content
        assert "secrets/" in content
        assert any("gitignore_global" in c for c in changes)

    def test_force_creates_when_missing(self, tmp_path):
        """Force mode: creates local file when it doesn't exist."""
        sm = self._make_sm_with_repo(tmp_path)

        remote = "*.log\n.env\n"
        (sm.repo_dir / "configs" / "gitignore_global").write_text(remote)

        local = tmp_path / ".gitignore_global"
        assert not local.exists()

        with patch.object(sm, "_get_global_gitignore_path", return_value=None):
            with patch.object(sm, "_run_git") as mock_git:
                with patch.object(Path, "home", classmethod(lambda cls: tmp_path)):
                    changes = sm._apply_gitignore_global(force=True)

        assert local.exists()
        assert local.read_text() == remote
        mock_git.assert_called_once()

    def test_dry_run_creates_when_missing(self, tmp_path):
        """Dry run + force + missing: reports without writing."""
        sm = self._make_sm_with_repo(tmp_path)

        remote = "*.log\n.env\n"
        (sm.repo_dir / "configs" / "gitignore_global").write_text(remote)

        local = tmp_path / ".gitignore_global"
        assert not local.exists()

        with patch.object(sm, "_get_global_gitignore_path", return_value=None):
            with patch.object(Path, "home", classmethod(lambda cls: tmp_path)):
                changes = sm._apply_gitignore_global(force=True, dry_run=True)

        assert not local.exists()  # Not written in dry-run
        assert len(changes) == 1
        assert "created" in changes[0]

    def test_dry_run_does_not_write(self, tmp_path):
        """Dry run mode: computes changes but doesn't write files."""
        sm = self._make_sm_with_repo(tmp_path)

        remote = "*.log\n.env\nsecrets/\n"
        (sm.repo_dir / "configs" / "gitignore_global").write_text(remote)

        local = tmp_path / ".gitignore_global"
        local.write_text("*.log\n")

        with patch.object(sm, "_get_global_gitignore_path", return_value=local):
            changes = sm._apply_gitignore_global(force=True, dry_run=True)

        # Content should be unchanged
        assert local.read_text() == "*.log\n"
        assert len(changes) == 1  # Change is reported but not applied

    def test_identical_files_returns_empty(self, tmp_path):
        """If local and remote are identical, no changes reported."""
        sm = self._make_sm_with_repo(tmp_path)

        content = "*.log\n.env\n"
        (sm.repo_dir / "configs" / "gitignore_global").write_text(content)

        local = tmp_path / ".gitignore_global"
        local.write_text(content)

        with patch.object(sm, "_get_global_gitignore_path", return_value=local):
            changes = sm._apply_gitignore_global(force=True)

        assert changes == []


class TestGitignoreGlobalConflictDetection:
    """Tests for _detect_conflicts including gitignore_global."""

    def test_detect_conflicts_includes_gitignore_global(self, tmp_path):
        """When local gitignore_global differs from repo, conflict is detected."""
        sm = SyncManager.__new__(SyncManager)
        sm.repo_dir = tmp_path / "repo"
        sm.repo_dir.mkdir()
        configs = sm.repo_dir / "configs"
        configs.mkdir()
        (configs / "gitignore_global").write_text("*.log\n.env\n")

        # Create local gitignore_global with different content
        local = tmp_path / ".gitignore_global"
        local.write_text("*.log\n.DS_Store\n")

        sm.config = MagicMock()
        sm.config.is_agent_enabled.return_value = True

        with patch.object(sm, "_get_global_gitignore_path", return_value=local):
            with patch.object(sm, "_run_git", return_value="M configs/gitignore_global"):
                with patch.object(sm, "_get_file_diff_stats", return_value={"added": 1, "removed": 1}):
                    conflicts = sm._detect_conflicts()

        gitignore_conflicts = [c for c in conflicts if c.filename == "gitignore_global"]
        assert len(gitignore_conflicts) == 1
        assert gitignore_conflicts[0].agent_name == "git"

    def test_detect_conflicts_skips_gitignore_when_agents_only(self, tmp_path):
        """agents_only flag should skip gitignore_global detection."""
        sm = SyncManager.__new__(SyncManager)
        sm.repo_dir = tmp_path / "repo"
        sm.repo_dir.mkdir()
        configs = sm.repo_dir / "configs"
        configs.mkdir()
        (configs / "gitignore_global").write_text("*.log\n")

        local = tmp_path / ".gitignore_global"
        local.write_text("*.log\n.DS_Store\n")

        sm.config = MagicMock()

        with patch.object(sm, "_get_global_gitignore_path", return_value=local):
            with patch.object(sm, "_run_git", return_value="M configs/gitignore_global"):
                conflicts = sm._detect_conflicts(agents_only=True)

        gitignore_conflicts = [c for c in conflicts if c.filename == "gitignore_global"]
        assert len(gitignore_conflicts) == 0


class TestApplyGitignoreInteractive:
    """Tests for interactive menu (Prompt.ask)."""

    def _make_sm(self, tmp_path):
        sm = SyncManager.__new__(SyncManager)
        sm.repo_dir = tmp_path / "repo"
        sm.repo_dir.mkdir()
        configs = sm.repo_dir / "configs"
        configs.mkdir()
        sm.config = MagicMock()
        return sm

    def test_interactive_replace(self, tmp_path):
        """User picks 1 → replaces local with remote."""
        sm = self._make_sm(tmp_path)

        remote = "*.log\n.env\nsecrets/\n"
        (sm.repo_dir / "configs" / "gitignore_global").write_text(remote)

        local = tmp_path / ".gitignore_global"
        local.write_text("*.log\n")

        with patch.object(sm, "_get_global_gitignore_path", return_value=local):
            with patch("rich.prompt.Prompt.ask", return_value="1"):
                changes = sm._apply_gitignore_global()

        assert local.read_text() == remote
        assert any("replaced" in c for c in changes)

    def test_interactive_keep(self, tmp_path):
        """User picks 2 → keeps local version."""
        sm = self._make_sm(tmp_path)

        remote = "*.log\n.env\nsecrets/\n"
        (sm.repo_dir / "configs" / "gitignore_global").write_text(remote)

        local = tmp_path / ".gitignore_global"
        local.write_text("*.log\n")

        with patch.object(sm, "_get_global_gitignore_path", return_value=local):
            with patch("rich.prompt.Prompt.ask", return_value="2"):
                changes = sm._apply_gitignore_global()

        assert local.read_text() == "*.log\n"  # Unchanged
        assert any("kept" in c for c in changes)

    def test_interactive_merge(self, tmp_path):
        """User picks 3 → merges missing patterns into local."""
        sm = self._make_sm(tmp_path)

        remote = "*.log\n.env\nsecrets/\n"
        (sm.repo_dir / "configs" / "gitignore_global").write_text(remote)

        local = tmp_path / ".gitignore_global"
        local.write_text("*.log\n")

        with patch.object(sm, "_get_global_gitignore_path", return_value=local):
            with patch("rich.prompt.Prompt.ask", return_value="3"):
                changes = sm._apply_gitignore_global()

        content = local.read_text()
        assert "*.log" in content
        assert ".env" in content
        assert "secrets/" in content
        assert any("merged" in c for c in changes)
