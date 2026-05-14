"""Tests for skills diff utilities."""

from pathlib import Path
from agent_sync.skills_diff import scan_skills_dir, SkillsDiff


class TestScanSkillsDir:
    """Test scan_skills_dir utility."""

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        """Non-existent directory returns empty set."""
        assert scan_skills_dir(tmp_path / "nope") == set()

    def test_returns_empty_for_empty_dir(self, tmp_path):
        """Empty directory returns empty set."""
        assert scan_skills_dir(tmp_path) == set()

    def test_detects_skill_with_skill_md(self, tmp_path):
        """Directory containing SKILL.md is a valid skill."""
        (tmp_path / "my-skill").mkdir()
        (tmp_path / "my-skill" / "SKILL.md").write_text("# My Skill")
        assert scan_skills_dir(tmp_path) == {"my-skill"}

    def test_skips_hidden_directories(self, tmp_path):
        """Hidden directories (dot-prefixed) are not valid skills."""
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "SKILL.md").write_text("# Hidden")
        assert scan_skills_dir(tmp_path) == set()

    def test_skips_files_in_root(self, tmp_path):
        """Files directly in the skills directory are not skills."""
        (tmp_path / "readme.md").write_text("# Readme")
        assert scan_skills_dir(tmp_path) == set()

    def test_returns_multiple_skills(self, tmp_path):
        """Multiple skill directories are all returned."""
        for name in ["skill-a", "skill-b", "skill-c"]:
            (tmp_path / name).mkdir()
            (tmp_path / name / "SKILL.md").write_text(f"# {name}")
        assert scan_skills_dir(tmp_path) == {"skill-a", "skill-b", "skill-c"}

    def test_skips_dirs_without_skill_md(self, tmp_path):
        """Directories without SKILL.md are not valid skills."""
        (tmp_path / "not-a-skill").mkdir()
        assert scan_skills_dir(tmp_path) == set()


class TestSkillsDiff:
    """Test SkillsDiff diff logic."""

    def setup_diff(self, local_dir: Path, repo_dir: Path) -> SkillsDiff:
        """Create a SkillsDiff instance with controlled directories."""
        diff = SkillsDiff.__new__(SkillsDiff)
        diff.global_skills_dir = local_dir
        diff.repo_dir = repo_dir
        return diff

    def test_diff_no_differences(self, tmp_path):
        """Both local and remote have same skills."""
        local = tmp_path / "local"; local.mkdir()
        repo = tmp_path / "repo"; (repo / "skills").mkdir(parents=True)
        for name in ["a", "b"]:
            (local / name).mkdir(); (local / name / "SKILL.md").write_text("")
            (repo / "skills" / name).mkdir(); (repo / "skills" / name / "SKILL.md").write_text("")

        diff = self.setup_diff(local, repo)
        result = diff.diff()
        assert result["local_only"] == []
        assert result["remote_only"] == []
        assert set(result["both"]) == {"a", "b"}

    def test_diff_local_only(self, tmp_path):
        """Skills only present locally."""
        local = tmp_path / "local"; local.mkdir()
        repo = tmp_path / "repo"; (repo / "skills").mkdir(parents=True)
        (local / "local-only").mkdir(); (local / "local-only" / "SKILL.md").write_text("")
        diff = self.setup_diff(local, repo)
        result = diff.diff()
        assert result["local_only"] == ["local-only"]
        assert result["remote_only"] == []

    def test_diff_remote_only(self, tmp_path):
        """Skills only present remotely."""
        local = tmp_path / "local"; local.mkdir()
        repo = tmp_path / "repo"; (repo / "skills").mkdir(parents=True)
        (repo / "skills" / "remote-only").mkdir(); (repo / "skills" / "remote-only" / "SKILL.md").write_text("")
        diff = self.setup_diff(local, repo)
        result = diff.diff()
        assert result["local_only"] == []
        assert result["remote_only"] == ["remote-only"]

    def test_diff_empty_dirs(self, tmp_path):
        """Empty directories produce no differences."""
        diff = self.setup_diff(tmp_path / "local", tmp_path / "repo")
        (tmp_path / "local").mkdir()
        (tmp_path / "repo" / "skills").mkdir(parents=True)
        result = diff.diff()
        assert result["local_only"] == []
        assert result["remote_only"] == []
        assert result["both"] == []

    def test_get_local_skills(self, tmp_path):
        """get_local_skills uses scan_skills_dir internally."""
        (tmp_path / "local" / "skill-x").mkdir(parents=True)
        (tmp_path / "local" / "skill-x" / "SKILL.md").write_text("")
        diff = self.setup_diff(tmp_path / "local", tmp_path / "repo")
        assert diff.get_local_skills() == {"skill-x"}

    def test_get_remote_skills_nonexistent_repo(self, tmp_path):
        """get_remote_skills returns empty when repo doesn't exist."""
        diff = self.setup_diff(tmp_path / "local", tmp_path / "nonexistent")
        assert diff.get_remote_skills() == set()


class TestSkillsReconcile:
    """Test SkillsReconcile.apply_decisions logic."""

    def setup_reconcile(self) -> SkillsDiff:
        from agent_sync.skills_reconcile import SkillsReconcile
        rec = SkillsReconcile.__new__(SkillsReconcile)
        rec.global_skills_dir = Path("/nonexistent/local")
        rec.repo_dir = Path("/nonexistent/repo")
        return rec

    def test_apply_decisions_local(self):
        """'local' action increments added_to_remote."""
        rec = self.setup_reconcile()
        stats = rec.apply_decisions({"skill-a": "local"}, dry_run=True)
        assert stats["added_to_remote"] == 1
        assert stats["downloaded_to_local"] == 0
        assert stats["skipped"] == 0

    def test_apply_decisions_remote_skipped_dry_run(self):
        """'remote' action with dry_run=True and missing repo dir is skipped."""
        rec = self.setup_reconcile()
        stats = rec.apply_decisions({"skill-a": "remote"}, dry_run=True)
        assert stats["added_to_remote"] == 0
        assert stats["downloaded_to_local"] == 0
        assert stats["skipped"] == 1  # remote_skill doesn't exist

    def test_apply_decisions_skip(self):
        """'skip' action increments skipped."""
        rec = self.setup_reconcile()
        stats = rec.apply_decisions({"skill-a": "skip"}, dry_run=True)
        assert stats["skipped"] == 1

    def test_apply_decisions_multiple(self):
        """Multiple decisions with mixed actions."""
        rec = self.setup_reconcile()
        stats = rec.apply_decisions({
            "a": "local",
            "b": "skip",
            "c": "remote",
        }, dry_run=True)
        assert stats["added_to_remote"] == 1
        assert stats["skipped"] == 2  # remote (not found) + skip = 2
        assert stats["downloaded_to_local"] == 0
