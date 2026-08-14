"""Tests for skill drift detection and interactive confirmation.

These test the core comparison logic, dataclass behavior, and integration
with PullSummary / _apply_synced_skills. Regression-critical: any change
to _same_content, _compare_skill_dirs, or _detect_skill_drifts must keep
these passing.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from agent_sync.sync import SkillDrift, PullSummary, SyncManager
from agent_sync.config import Config


class TestSkillDrift:
    """Tests for SkillDrift dataclass."""

    def test_display_name(self):
        """display_name returns the skill name."""
        drift = SkillDrift(
            name="cali-ops-github-releases",
            files_changed=2,
            local_path=Path("/home/.agents/skills/cali-ops-github-releases"),
            repo_path=Path("/repo/skills/cali-ops-github-releases"),
        )
        assert drift.display_name == "cali-ops-github-releases"

    def test_diff_summary_single_file(self):
        """diff_summary shows file count."""
        drift = SkillDrift(
            name="test-skill",
            files_changed=1,
            local_path=Path("/a"),
            repo_path=Path("/b"),
        )
        assert "1 file(s) modified" in drift.diff_summary

    def test_diff_summary_multiple_files(self):
        """diff_summary shows correct count for multiple files."""
        drift = SkillDrift(
            name="test-skill",
            files_changed=3,
            local_path=Path("/a"),
            repo_path=Path("/b"),
            file_details=[{"path": "a.md"}, {"path": "b.md"}, {"path": "c.md"}],
        )
        assert "3 file(s) modified" in drift.diff_summary


class TestPullSummarySkillDrifts:
    """Tests for PullSummary integration with SkillDrift."""

    def test_has_skill_drifts_false_by_default(self):
        """PullSummary without drifts reports false."""
        summary = PullSummary()
        assert summary.has_skill_drifts is False

    def test_has_skill_drifts_true_with_drifts(self):
        """PullSummary with drifts reports true."""
        drift = SkillDrift(
            name="test", files_changed=1,
            local_path=Path("/a"), repo_path=Path("/b"),
        )
        summary = PullSummary(skill_drifts=[drift])
        assert summary.has_skill_drifts is True

    def test_total_changes_includes_skill_drifts(self):
        """total_changes accounts for skill_drifts count."""
        drift = SkillDrift(
            name="test", files_changed=1,
            local_path=Path("/a"), repo_path=Path("/b"),
        )
        summary = PullSummary(skill_drifts=[drift], new_files=3)
        assert summary.total_changes == 4  # 1 drift + 3 new files


class TestCompareSkillDirs:
    """Tests for _compare_skill_dirs — the core comparison logic."""

    @pytest.fixture
    def manager(self, tmp_path):
        """SyncManager with minimal mock config."""
        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"
        return SyncManager(mock_config)

    def test_identical_dirs_returns_none(self, tmp_path, manager):
        """Directories with same files and same content = no drift."""
        local = tmp_path / "local"
        repo = tmp_path / "repo"
        local.mkdir(); repo.mkdir()
        (local / "SKILL.md").write_text("hello")
        (repo / "SKILL.md").write_text("hello")

        result = manager._compare_skill_dirs(local, repo)
        assert result is None

    def test_different_content_detects_change(self, tmp_path, manager):
        """Different file content returns file_details."""
        local = tmp_path / "local"
        repo = tmp_path / "repo"
        local.mkdir(); repo.mkdir()
        (local / "SKILL.md").write_text("hello")
        (repo / "SKILL.md").write_text("hello world")

        result = manager._compare_skill_dirs(local, repo)
        assert result is not None
        assert result["files_changed"] == 1
        assert result["file_details"][0]["path"] == "SKILL.md"

    def test_extra_file_local_only(self, tmp_path, manager):
        """File only in local shows as change."""
        local = tmp_path / "local"
        repo = tmp_path / "repo"
        local.mkdir(); repo.mkdir()
        # SKILL.md exists in both with same content (not a change)
        (local / "SKILL.md").write_text("shared")
        (repo / "SKILL.md").write_text("shared")
        # extra.py only in local (counts as change)
        (local / "extra.py").write_text("extra")

        result = manager._compare_skill_dirs(local, repo)
        assert result is not None
        assert result["files_changed"] == 1
        assert result["file_details"][0]["path"] == "extra.py"
        assert result["file_details"][0]["repo"] is None

    def test_extra_file_repo_only(self, tmp_path, manager):
        """File only in repo shows as change."""
        local = tmp_path / "local"
        repo = tmp_path / "repo"
        local.mkdir(); repo.mkdir()
        (local / "SKILL.md").write_text("content")
        (repo / "SKILL.md").write_text("content")
        (repo / "helper.py").write_text("helper")

        result = manager._compare_skill_dirs(local, repo)
        assert result is not None
        assert result["files_changed"] == 1
        assert result["file_details"][0]["path"] == "helper.py"
        assert result["file_details"][0]["local"] is None

    def test_ignores_hidden_files(self, tmp_path, manager):
        """Files starting with '.' are skipped."""
        local = tmp_path / "local"
        repo = tmp_path / "repo"
        local.mkdir(); repo.mkdir()
        (local / "SKILL.md").write_text("same")
        (repo / "SKILL.md").write_text("same")
        (local / ".DS_Store").write_bytes(b"\x00")
        (repo / ".DS_Store").write_bytes(b"\xff")

        result = manager._compare_skill_dirs(local, repo)
        assert result is None  # .DS_Store ignored

    def test_nested_subdirectories(self, tmp_path, manager):
        """Files in subdirs are compared recursively."""
        local = tmp_path / "local"
        repo = tmp_path / "repo"
        local.mkdir(); repo.mkdir()
        (local / "SKILL.md").write_text("same")
        (repo / "SKILL.md").write_text("same")
        Path(local / "tools").mkdir(); Path(repo / "tools").mkdir()
        (local / "tools" / "build.py").write_text("old")
        (repo / "tools" / "build.py").write_text("new version")

        result = manager._compare_skill_dirs(local, repo)
        assert result is not None
        assert result["files_changed"] == 1
        assert result["file_details"][0]["path"] == "tools/build.py"


class TestDetectSkillDrifts:
    """Tests for _detect_skill_drifts — integration with file system."""

    @pytest.fixture
    def manager_with_dirs(self, tmp_path):
        """SyncManager with real repo/skills and ~/.agents/skills dirs."""
        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"

        mgr = SyncManager(mock_config)

        # Set up repo/skills dir (aligned with SyncManager.repo_dir convention)
        mgr.repo_dir = tmp_path / "test-repo"
        mgr.repo_dir.mkdir(parents=True)

        # Set up ~/.agents/skills (via tmp_path + patching home)
        return mgr, tmp_path

    def test_no_skills_no_drifts(self, manager_with_dirs):
        """No skills directories at all = no drifts."""
        mgr, tmp = manager_with_dirs
        assert mgr._detect_skill_drifts() == []

    def test_no_drifts_when_identical(self, tmp_path):
        """Skills identical in repo and local = no drifts."""
        repo_skills = tmp_path / "repo" / "skills"
        local_skills = tmp_path / "local" / ".agents" / "skills"
        repo_skills.mkdir(parents=True)
        local_skills.mkdir(parents=True)

        (repo_skills / "my-skill").mkdir()
        (repo_skills / "my-skill" / "SKILL.md").write_text("same")
        (local_skills / "my-skill").mkdir()
        (local_skills / "my-skill" / "SKILL.md").write_text("same")

        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"

        mgr = SyncManager(mock_config)
        mgr.repo_dir = tmp_path / "repo"

        with patch("agent_sync.paths.HUB_DIR", tmp_path / "local" / ".agents" / "skills"):
            drifts = mgr._detect_skill_drifts()
            assert drifts == []

    def test_drift_detected_when_different(self, tmp_path):
        """Different content between repo and local = drift detected."""
        repo_skills = tmp_path / "repo" / "skills"
        local_skills = tmp_path / "local" / ".agents" / "skills"
        repo_skills.mkdir(parents=True)
        local_skills.mkdir(parents=True)

        (repo_skills / "my-skill").mkdir()
        (repo_skills / "my-skill" / "SKILL.md").write_text("remote version")
        (local_skills / "my-skill").mkdir()
        (local_skills / "my-skill" / "SKILL.md").write_text("local edit")

        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"

        mgr = SyncManager(mock_config)
        mgr.repo_dir = tmp_path / "repo"

        with patch("agent_sync.paths.HUB_DIR", tmp_path / "local" / ".agents" / "skills"):
            drifts = mgr._detect_skill_drifts()
            assert len(drifts) == 1
            assert drifts[0].name == "my-skill"
            assert drifts[0].files_changed == 1
            assert drifts[0].local_path == local_skills / "my-skill"
            assert drifts[0].repo_path == repo_skills / "my-skill"

    def test_orphan_skills_ignored(self, tmp_path):
        """Skills existing in only one location are not reported as drifts."""
        repo_skills = tmp_path / "repo" / "skills"
        local_skills = tmp_path / "local" / ".agents" / "skills"
        repo_skills.mkdir(parents=True)
        local_skills.mkdir(parents=True)

        # Only in repo
        (repo_skills / "repo-only").mkdir()
        (repo_skills / "repo-only" / "SKILL.md").write_text("repo")

        # Only in local
        (local_skills / "local-only").mkdir()
        (local_skills / "local-only" / "SKILL.md").write_text("local")

        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"

        mgr = SyncManager(mock_config)
        mgr.repo_dir = tmp_path / "repo"

        with patch("agent_sync.paths.HUB_DIR", tmp_path / "local" / ".agents" / "skills"):
            drifts = mgr._detect_skill_drifts()
            assert drifts == []

    def test_filter_limits_detected_skills(self, tmp_path):
        """skills_filter restricts which skills are checked."""
        repo_skills = tmp_path / "repo" / "skills"
        local_skills = tmp_path / "local" / ".agents" / "skills"
        repo_skills.mkdir(parents=True)
        local_skills.mkdir(parents=True)

        for name in ["skill-a", "skill-b"]:
            (repo_skills / name).mkdir()
            (repo_skills / name / "SKILL.md").write_text("remote")
            (local_skills / name).mkdir()
            (local_skills / name / "SKILL.md").write_text("local edit")

        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"

        mgr = SyncManager(mock_config)
        mgr.repo_dir = tmp_path / "repo"

        with patch("agent_sync.paths.HUB_DIR", tmp_path / "local" / ".agents" / "skills"):
            drifts = mgr._detect_skill_drifts(skills_filter=["skill-a"])
            assert len(drifts) == 1
            assert drifts[0].name == "skill-a"

    def test_exclude_skips_skills(self, tmp_path):
        """skills_exclude skips specific skills."""
        repo_skills = tmp_path / "repo" / "skills"
        local_skills = tmp_path / "local" / ".agents" / "skills"
        repo_skills.mkdir(parents=True)
        local_skills.mkdir(parents=True)

        for name in ["skill-a", "skill-b"]:
            (repo_skills / name).mkdir()
            (repo_skills / name / "SKILL.md").write_text("remote")
            (local_skills / name).mkdir()
            (local_skills / name / "SKILL.md").write_text("local edit")

        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"

        mgr = SyncManager(mock_config)
        mgr.repo_dir = tmp_path / "repo"

        with patch("agent_sync.paths.HUB_DIR", tmp_path / "local" / ".agents" / "skills"):
            drifts = mgr._detect_skill_drifts(skills_exclude=["skill-a"])
            assert len(drifts) == 1
            assert drifts[0].name == "skill-b"

    def test_config_exclude_patterns_skip_matching_skills(self, tmp_path):
        """Config-level fnmatch patterns (e.g. 'stelow*') are always applied,
        even without CLI flags, and merge with CLI exclusions."""
        repo_skills = tmp_path / "repo" / "skills"
        local_skills = tmp_path / "local" / ".agents" / "skills"
        repo_skills.mkdir(parents=True)
        local_skills.mkdir(parents=True)

        for name in ["stelow-product-ads", "stelow-entry", "cali-degustia-x", "skill-b"]:
            (repo_skills / name).mkdir()
            (repo_skills / name / "SKILL.md").write_text("remote")
            (local_skills / name).mkdir()
            (local_skills / name / "SKILL.md").write_text("local edit")

        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"
        mock_config.skills_exclude = ["stelow*", "cali-degustia*"]

        mgr = SyncManager(mock_config)
        mgr.repo_dir = tmp_path / "repo"

        with patch("agent_sync.paths.HUB_DIR", tmp_path / "local" / ".agents" / "skills"):
            # No CLI flags: config patterns alone skip stelow*/cali-degustia*
            drifts = mgr._detect_skill_drifts()
            assert len(drifts) == 1
            assert drifts[0].name == "skill-b"

            # CLI flags merge with config patterns
            drifts = mgr._detect_skill_drifts(skills_exclude=["skill-b"])
            assert drifts == []


class TestApplySyncedSkillsWithDrifts:
    """Tests for _apply_synced_skills with drift-related params."""

    @pytest.fixture
    def manager_with_skills(self, tmp_path):
        """SyncManager with actual skill dirs in repo and local."""
        repo_dir = tmp_path / "repo"
        local_home = tmp_path / "home"

        # Set up repo/skills
        skills_repo = repo_dir / "skills"
        skills_repo.mkdir(parents=True)
        (skills_repo / "my-skill").mkdir()
        (skills_repo / "my-skill" / "SKILL.md").write_text("remote version")

        # Set up local ~/.agents/skills with DIFFERENT content
        skills_local = local_home / ".agents" / "skills"
        skills_local.mkdir(parents=True)
        (skills_local / "my-skill").mkdir()
        (skills_local / "my-skill" / "SKILL.md").write_text("local edit")

        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path / "app"
        mock_config.app_dir.mkdir(parents=True, exist_ok=True)
        mock_config.state_file = mock_config.app_dir / "state.json"
        mock_config.is_agent_enabled.return_value = False

        mgr = SyncManager(mock_config)
        mgr.repo_dir = repo_dir

        # Suppress console output
        with patch("agent_sync.sync.console"):
            yield mgr, local_home

    def test_force_overwrites_local(self, manager_with_skills):
        """With force=True, remote version is applied over local edit."""
        mgr, local_home = manager_with_skills
        local_skill = local_home / ".agents" / "skills" / "my-skill" / "SKILL.md"

        with patch("agent_sync.paths.HUB_DIR", local_home / ".agents" / "skills"):
            with patch("agent_sync.sync.console"):
                changes = mgr._apply_synced_skills(force=True)

        # Remote content overwrote local
        assert local_skill.read_text() == "remote version"
        assert any("my-skill" in c for c in changes)

    def test_no_interactive_keeps_local(self, manager_with_skills):
        """With interactive=False, local version is preserved (current behavior)."""
        mgr, local_home = manager_with_skills
        local_skill = local_home / ".agents" / "skills" / "my-skill" / "SKILL.md"

        with patch("agent_sync.paths.HUB_DIR", local_home / ".agents" / "skills"):
            with patch("agent_sync.sync.console"):
                changes = mgr._apply_synced_skills(interactive=False)

        assert local_skill.read_text() == "local edit"
        # No change recorded because we kept local
        assert not any("my-skill" in c for c in changes)

    def test_keep_local_skills_preserves_local(self, manager_with_skills):
        """Passing keep_local_skills set skips those skills from overwrite."""
        mgr, local_home = manager_with_skills
        local_skill = local_home / ".agents" / "skills" / "my-skill" / "SKILL.md"

        with patch("agent_sync.paths.HUB_DIR", local_home / ".agents" / "skills"):
            with patch("agent_sync.sync.console"):
                changes = mgr._apply_synced_skills(
                    keep_local_skills={"my-skill"},
                )

        assert local_skill.read_text() == "local edit"
        assert not any("my-skill" in c for c in changes)

    def test_no_drift_identical_content(self, tmp_path):
        """When content is identical, no drift and no overwrite needed."""
        repo_dir = tmp_path / "repo"
        local_home = tmp_path / "home"
        skills_repo = repo_dir / "skills"
        skills_repo.mkdir(parents=True)
        (skills_repo / "my-skill").mkdir()
        (skills_repo / "my-skill" / "SKILL.md").write_text("same content")
        skills_local = local_home / ".agents" / "skills"
        skills_local.mkdir(parents=True)
        (skills_local / "my-skill").mkdir()
        (skills_local / "my-skill" / "SKILL.md").write_text("same content")

        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path / "app"
        mock_config.app_dir.mkdir(parents=True, exist_ok=True)
        mock_config.state_file = mock_config.app_dir / "state.json"
        mock_config.is_agent_enabled.return_value = False

        mgr = SyncManager(mock_config)
        mgr.repo_dir = repo_dir

        with patch("agent_sync.paths.HUB_DIR", local_home / ".agents" / "skills"):
            with patch("agent_sync.sync.console"):
                changes = mgr._apply_synced_skills(force=True)

        # Still same content, no unintended change
        local_skill = skills_local / "my-skill" / "SKILL.md"
        assert local_skill.read_text() == "same content"


class TestHandleSkillDriftsInteractive:
    """Tests for _handle_skill_drifts_interactive prompt."""

    @pytest.fixture
    def drifts(self, tmp_path):
        """Sample skill drifts for testing."""
        local_file = tmp_path / "local" / "SKILL.md"
        repo_file = tmp_path / "repo" / "SKILL.md"
        local_file.parent.mkdir(parents=True)
        repo_file.parent.mkdir(parents=True)
        local_file.write_text("local version content")
        repo_file.write_text("remote version content with changes")

        return [
            SkillDrift(
                name="test-skill",
                files_changed=2,
                local_path=local_file.parent,
                repo_path=repo_file.parent,
                file_details=[
                    {"path": "SKILL.md", "local": local_file, "repo": repo_file},
                ],
            ),
        ]

    def test_accept_returns_true(self, drifts):
        """User typing 'a' returns True (apply remote)."""
        mock_config = Mock(spec=Config)
        mgr = SyncManager(mock_config)

        with patch("rich.prompt.Prompt.ask", return_value="a"):
            with patch("agent_sync.sync.console"):
                result = mgr._handle_skill_drifts_interactive(drifts)
                assert result is True

    def test_keep_returns_false(self, drifts):
        """User pressing Enter returns False (keep local)."""
        mock_config = Mock(spec=Config)
        mgr = SyncManager(mock_config)

        with patch("rich.prompt.Prompt.ask", return_value=""):
            with patch("agent_sync.sync.console"):
                result = mgr._handle_skill_drifts_interactive(drifts)
                assert result is False

    def test_abort_raises(self, drifts):
        """User typing 'q' raises RuntimeError."""
        mock_config = Mock(spec=Config)
        mgr = SyncManager(mock_config)

        with patch("rich.prompt.Prompt.ask", return_value="q"):
            with pytest.raises(RuntimeError, match="Pull aborted by user"):
                mgr._handle_skill_drifts_interactive(drifts)

    def test_empty_drifts_returns_false_immediately(self):
        """Empty drifts returns False without prompt (guard clause)."""
        mock_config = Mock(spec=Config)
        mgr = SyncManager(mock_config)

        result = mgr._handle_skill_drifts_interactive([])
        assert result is False

    def test_view_diff_without_pager_fallback(self, drifts):
        """When pager (less) is not available, fallback prints inline without crashing."""
        mock_config = Mock(spec=Config)
        mgr = SyncManager(mock_config)

        with patch.object(mgr, "_run_git", return_value=""):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                # Should not raise: catches FileNotFoundError and prints inline
                mgr._show_skill_diff(drifts)

    def test_view_diff_calls_pager(self, drifts):
        """User typing 'v' calls _show_skill_diff and re-prompts."""
        mock_config = Mock(spec=Config)
        mgr = SyncManager(mock_config)

        with patch.object(mgr, "_show_skill_diff") as mock_show:
            # First 'v' calls show, second asks for action again → simulate 'a'
            with patch("rich.prompt.Prompt.ask", side_effect=["v", "a"]):
                with patch("agent_sync.sync.console"):
                    result = mgr._handle_skill_drifts_interactive(drifts)
                    assert result is True
                    mock_show.assert_called_once_with(drifts)
