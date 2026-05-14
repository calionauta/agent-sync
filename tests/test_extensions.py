"""Tests for extension subdirectory and symlink support.

Tests for the feature that allows skills in agent CLI subdirectories
with symlinks pointing to them (e.g., opencode/superpowers/skills/).
"""

from unittest.mock import Mock, patch

from agent_sync.skills import MANIFEST_FILENAME, SkillsManager
from agent_sync.sync import SyncManager


class TestIsExtensionSymlink:
    """Test _is_extension_symlink() detection logic."""

    def test_extension_symlink_points_inside_config(self, tmp_path):
        """Symlink pointing inside agent config dir should be preserved."""
        # Setup: ~/.config/opencode/ structure
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Create extension subdirectory with skills
        superpowers_dir = config_dir / "superpowers"
        superpowers_skills = superpowers_dir / "skills"
        superpowers_skills.mkdir(parents=True)

        # Create skills directory
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        # Create symlink: skills/superpowers -> ../superpowers/skills
        symlink_path = skills_dir / "superpowers"
        symlink_path.symlink_to("../superpowers/skills")

        # Create mock agent
        mock_agent = Mock()
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        # Test
        skills_manager = SkillsManager()
        result = skills_manager._is_extension_symlink(symlink_path, mock_agent)

        assert result is True, "Extension symlink should be detected"

    def test_user_symlink_points_outside_config(self, tmp_path):
        """Symlink pointing outside agent config dir should be removed."""
        # Setup: ~/.config/opencode/ structure
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Create skills directory
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        # Create external target (e.g., ~/.agents/skills/)
        external_dir = tmp_path / "external" / "skills"
        external_dir.mkdir(parents=True)

        # Create symlink: skills/my-skill -> ~/.agents/skills/my-skill
        symlink_path = skills_dir / "my-skill"
        symlink_path.symlink_to(external_dir)

        # Create mock agent
        mock_agent = Mock()
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        # Test
        skills_manager = SkillsManager()
        result = skills_manager._is_extension_symlink(symlink_path, mock_agent)

        assert result is False, "User symlink should not be detected as extension"

    def test_broken_symlink(self, tmp_path):
        """Broken symlink should not crash and should return False."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        # Create broken symlink
        symlink_path = skills_dir / "broken"
        symlink_path.symlink_to("/nonexistent/path")

        mock_agent = Mock()
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        skills_manager = SkillsManager()
        result = skills_manager._is_extension_symlink(symlink_path, mock_agent)

        assert result is False, "Broken symlink should return False"


class TestScanExtensionSubdirs:
    """Test _scan_extension_subdirs() functionality."""

    def test_finds_extension_subdirectory(self, tmp_path):
        """Should find skills in subdirectories like superpowers/skills/."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Create extension subdirectory with skills
        superpowers_dir = config_dir / "superpowers"
        superpowers_skills = superpowers_dir / "skills"
        superpowers_skills.mkdir(parents=True)

        # Create a valid skill
        skill_dir = superpowers_skills / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test Skill")

        # Create main skills directory (empty)
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        # Create mock agent
        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        # Test
        skills_manager = SkillsManager()
        result = skills_manager._scan_extension_subdirs(mock_agent)

        assert "opencode-superpowers" in result
        assert result["opencode-superpowers"]["agent"] == "opencode"
        assert result["opencode-superpowers"]["extension"] == "superpowers"
        assert result["opencode-superpowers"]["skills_dir"] == str(superpowers_skills)

    def test_multiple_extensions(self, tmp_path):
        """Should find multiple extension subdirectories."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Create two extensions
        for ext_name in ["superpowers", "my-extension"]:
            ext_dir = config_dir / ext_name
            ext_skills = ext_dir / "skills"
            ext_skills.mkdir(parents=True)

            skill_dir = ext_skills / f"{ext_name}-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"# {ext_name} Skill")

        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        skills_manager = SkillsManager()
        result = skills_manager._scan_extension_subdirs(mock_agent)

        assert "opencode-superpowers" in result
        assert "opencode-my-extension" in result

    def test_skips_hidden_directories(self, tmp_path):
        """Should skip hidden subdirectories."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Create hidden directory with skills
        hidden_dir = config_dir / ".hidden"
        hidden_skills = hidden_dir / "skills"
        hidden_skills.mkdir(parents=True)
        (hidden_skills / "skill").mkdir()

        # Create visible extension
        visible_dir = config_dir / "visible"
        visible_skills = visible_dir / "skills"
        visible_skills.mkdir(parents=True)
        (visible_skills / "skill").mkdir()

        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        skills_manager = SkillsManager()
        result = skills_manager._scan_extension_subdirs(mock_agent)

        assert "opencode-.hidden" not in result
        assert "opencode-visible" in result

    def test_skips_main_skills_directory(self, tmp_path):
        """Should skip the main skills/ directory."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Main skills directory should not be detected as extension
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "skill").mkdir()

        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        skills_manager = SkillsManager()
        result = skills_manager._scan_extension_subdirs(mock_agent)

        assert "opencode-skills" not in result

    def test_no_extensions(self, tmp_path):
        """Should return empty dict when no extensions exist."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        skills_manager = SkillsManager()
        result = skills_manager._scan_extension_subdirs(mock_agent)

        assert result == {}


class TestCleanupUserSymlinks:
    """Test _cleanup_user_symlinks() preserves extension symlinks."""

    def test_preserves_extension_symlink(self, tmp_path):
        """Extension symlinks should be preserved."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Create extension
        superpowers_dir = config_dir / "superpowers"
        superpowers_skills = superpowers_dir / "skills"
        superpowers_skills.mkdir(parents=True)

        # Create extension symlink
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()
        symlink_path = skills_dir / "superpowers"
        symlink_path.symlink_to("../superpowers/skills")

        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        skills_manager = SkillsManager()

        with patch('agent_sync.skills.get_all_agents', return_value=[mock_agent]):
            removed = skills_manager._cleanup_user_symlinks(preserve_extension_symlinks=True)

        assert removed == 0, "Extension symlink should not be removed"
        assert symlink_path.exists(), "Extension symlink should still exist"

    def test_removes_user_symlink(self, tmp_path):
        """User symlinks should be removed."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Create external target
        external_dir = tmp_path / "external"
        external_dir.mkdir()

        # Create user symlink
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()
        symlink_path = skills_dir / "my-skill"
        symlink_path.symlink_to(external_dir)

        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        skills_manager = SkillsManager()

        with patch('agent_sync.skills.get_all_agents', return_value=[mock_agent]):
            removed = skills_manager._cleanup_user_symlinks(preserve_extension_symlinks=True)

        assert removed == 1, "User symlink should be removed"
        assert not symlink_path.exists(), "User symlink should be gone"

    def test_mixed_symlinks(self, tmp_path):
        """Should preserve extension symlinks and remove user symlinks."""
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        # Create extension
        superpowers_dir = config_dir / "superpowers"
        superpowers_skills = superpowers_dir / "skills"
        superpowers_skills.mkdir(parents=True)

        # Create external target
        external_dir = tmp_path / "external"
        external_dir.mkdir()

        # Create both types of symlinks
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        ext_symlink = skills_dir / "superpowers"
        ext_symlink.symlink_to("../superpowers/skills")

        user_symlink = skills_dir / "my-skill"
        user_symlink.symlink_to(external_dir)

        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(config_dir)
        mock_agent.skills_path = skills_dir

        skills_manager = SkillsManager()

        with patch('agent_sync.skills.get_all_agents', return_value=[mock_agent]):
            removed = skills_manager._cleanup_user_symlinks(preserve_extension_symlinks=True)

        assert removed == 1, "Only user symlink should be removed"
        assert ext_symlink.exists(), "Extension symlink should remain"
        assert not user_symlink.exists(), "User symlink should be removed"


class TestManifestOperations:
    """Test manifest creation, saving, and loading."""

    def test_save_and_load_manifest(self, tmp_path):
        """Should save and load manifest correctly."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        sync_manager = SyncManager.__new__(SyncManager)
        sync_manager.repo_dir = repo_dir

        manifest = {
            "version": 1,
            "extensions": {
                "opencode-superpowers": {
                    "agent": "opencode",
                    "extension_dir": "superpowers"
                }
            },
            "global_skills": ["skill1", "skill2"]
        }

        sync_manager._save_manifest(manifest)

        manifest_path = repo_dir / MANIFEST_FILENAME
        assert manifest_path.exists(), "Manifest file should be created"

        loaded = sync_manager._load_manifest()
        assert loaded == manifest

    def test_load_nonexistent_manifest(self, tmp_path):
        """Should return None when manifest doesn't exist."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        sync_manager = SyncManager.__new__(SyncManager)
        sync_manager.repo_dir = repo_dir

        result = sync_manager._load_manifest()
        assert result is None


class TestRestoreExtensionSkills:
    """Test _restore_extension_skills() functionality."""

    def test_restores_extension_skills(self, tmp_path):
        """Should restore extension skills from repo to original location."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        # Create skills in repo
        ext_skills_repo = repo_dir / "skills" / "opencode-superpowers"
        ext_skills_repo.mkdir(parents=True)

        skill_dir = ext_skills_repo / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test Skill")

        # Create config dir structure
        config_dir = tmp_path / "config" / "opencode"
        config_dir.mkdir(parents=True)

        manifest = {
            "extensions": {
                "opencode-superpowers": {
                    "agent": "opencode",
                    "extension_dir": "superpowers"
                }
            }
        }

        sync_manager = SyncManager.__new__(SyncManager)
        sync_manager.repo_dir = repo_dir

        with patch('agent_sync.agents.get_agent') as mock_get_agent:
            mock_agent = Mock()
            mock_agent.config_dir = str(config_dir)
            mock_get_agent.return_value = mock_agent

            restored = sync_manager._restore_extension_skills(manifest)

        assert restored == 1

        # Check skills were restored
        restored_skill = config_dir / "superpowers" / "skills" / "test-skill"
        assert restored_skill.exists()
        assert (restored_skill / "SKILL.md").read_text() == "# Test Skill"

    def test_skips_missing_extension_in_repo(self, tmp_path, capsys):
        """Should skip extensions not found in repo."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        manifest = {
            "extensions": {
                "opencode-missing": {
                    "agent": "opencode",
                    "extension_dir": "missing"
                }
            }
        }

        sync_manager = SyncManager.__new__(SyncManager)
        sync_manager.repo_dir = repo_dir

        with patch('agent_sync.agents.get_agent') as mock_get_agent:
            mock_agent = Mock()
            mock_agent.config_dir = str(tmp_path / "config" / "opencode")
            mock_get_agent.return_value = mock_agent

            restored = sync_manager._restore_extension_skills(manifest)

        assert restored == 0
        captured = capsys.readouterr()
        assert "not found in repo" in captured.out


class TestRestoreSymlinks:
    """Test _restore_symlinks_from_backup() functionality."""

    def test_restores_symlinks(self, tmp_path):
        """Should restore symlinks from backup."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        # Create symlink backup
        backup_dir = repo_dir / "configs" / "opencode" / "skills"
        backup_dir.mkdir(parents=True)

        symlink_backup = backup_dir / "superpowers"
        symlink_backup.symlink_to("../superpowers/skills")

        # Create agent skills directory
        skills_dir = tmp_path / "config" / "opencode" / "skills"
        skills_dir.mkdir(parents=True)

        sync_manager = SyncManager.__new__(SyncManager)
        sync_manager.repo_dir = repo_dir

        mock_agent = Mock()
        mock_agent.name = "opencode"
        mock_agent.config_dir = str(tmp_path / "config" / "opencode")
        mock_agent.skills_path = skills_dir

        with patch('agent_sync.agents.get_all_agents', return_value=[mock_agent]):
            restored = sync_manager._restore_symlinks_from_backup()

        assert restored == 1

        # Check symlink was restored
        restored_symlink = skills_dir / "superpowers"
        assert restored_symlink.is_symlink()
        # Check symlink target (may be absolute or relative)
        target = restored_symlink.readlink()
        assert "superpowers/skills" in str(target)
