"""Real behavior tests for sync commands (push, pull)."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_sync.cli import main


class TestPushCommand:
    """Real behavior tests for push command."""

    def test_push_not_linked_shows_error(self, tmp_path, monkeypatch):
        """Push without link should show clear error message."""
        # Setup isolated environment
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        
        runner = CliRunner()
        result = runner.invoke(main, ["push"])
        
        # Should fail with non-zero exit
        assert result.exit_code != 0
        # Error should mention something about repository/link
        assert "link" in result.output.lower() or "repository" in result.output.lower() or "abort" in result.output.lower()

    @patch('agent_sync.cli.SyncManager')
    @patch('agent_sync.cli.Config')
    def test_push_calls_sync_push(self, mock_config, mock_sync_mgr):
        """Push should call SyncManager.push with correct args."""
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance
        
        mock_sync_instance = MagicMock()
        mock_sync_instance.push.return_value = [
            {'path': 'configs/opencode/settings.json', 'status': 'M', 'label': 'modified', 'directory_count': None}
        ]
        mock_sync_mgr.return_value = mock_sync_instance
        
        runner = CliRunner()
        result = runner.invoke(main, ["push", "-m", "test message"])
        
        assert result.exit_code == 0
        mock_sync_instance.push.assert_called_once()
        call_args = mock_sync_instance.push.call_args
        assert call_args[1]['message'] == "test message"

    @patch('agent_sync.cli.SyncManager')
    @patch('agent_sync.cli.Config')
    def test_push_skills_only_flag(self, mock_config, mock_sync_mgr):
        """Push --skills-only should pass correct flag to SyncManager."""
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance
        
        mock_sync_instance = MagicMock()
        mock_sync_instance.push.return_value = []
        mock_sync_mgr.return_value = mock_sync_instance
        
        runner = CliRunner()
        result = runner.invoke(main, ["push", "--skills-only", "-m", "skills"])
        
        assert result.exit_code == 0
        mock_sync_instance.push.assert_called_once()
        call_args = mock_sync_instance.push.call_args[1]
        assert call_args['skills_only'] is True

    @patch('agent_sync.cli.SyncManager')
    @patch('agent_sync.cli.Config')
    def test_push_configs_only_flag(self, mock_config, mock_sync_mgr):
        """Push --configs-only should pass correct flag to SyncManager."""
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance
        
        mock_sync_instance = MagicMock()
        mock_sync_instance.push.return_value = []
        mock_sync_mgr.return_value = mock_sync_instance
        
        runner = CliRunner()
        result = runner.invoke(main, ["push", "--configs-only", "-m", "configs"])
        
        assert result.exit_code == 0
        mock_sync_instance.push.assert_called_once()
        call_args = mock_sync_instance.push.call_args[1]
        assert call_args['configs_only'] is True

    @patch('agent_sync.cli.SyncManager')
    @patch('agent_sync.cli.Config')
    def test_push_returns_file_list(self, mock_config, mock_sync_mgr):
        """Push output should show list of pushed files."""
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance
        
        mock_sync_instance = MagicMock()
        mock_sync_instance.push.return_value = [
            {'path': 'configs/opencode/settings.json', 'status': 'M', 'label': 'modified'},
            {'path': 'skills/my-skill/SKILL.md', 'status': 'A', 'label': 'added'},
        ]
        mock_sync_mgr.return_value = mock_sync_instance
        
        runner = CliRunner()
        result = runner.invoke(main, ["push", "-m", "test"])
        
        assert result.exit_code == 0
        # Should show files in output
        assert "settings.json" in result.output or "modified" in result.output.lower()


class TestPullCommand:
    """Real behavior tests for pull command."""

    def test_pull_not_linked_shows_error(self, tmp_path, monkeypatch):
        """Pull without link should show clear error message."""
        # Setup isolated environment  
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull"])
        
        # Should fail with non-zero exit
        assert result.exit_code != 0
        # Error should mention something about link/repository or local changes
        assert "link" in result.output.lower() or "repository" in result.output.lower() or "abort" in result.output.lower()

    @patch('agent_sync.cli.SyncManager')
    @patch('agent_sync.cli.Config')
    def test_pull_calls_sync_pull(self, mock_config, mock_sync_mgr):
        """Pull should call SyncManager.pull with correct args."""
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance
        
        mock_sync_instance = MagicMock()
        mock_sync_instance.pull.return_value = ["config1.json"]
        mock_sync_mgr.return_value = mock_sync_instance
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull"])
        
        assert result.exit_code == 0
        mock_sync_instance.pull.assert_called_once()
        call_args = mock_sync_instance.pull.call_args
        assert call_args[1]['force'] is False

    @patch('agent_sync.cli.SyncManager')
    @patch('agent_sync.cli.Config')
    def test_pull_force_flag(self, mock_config, mock_sync_mgr):
        """Pull --force should pass force=True to SyncManager."""
        mock_config_instance = MagicMock()
        mock_sync_instance = MagicMock()
        mock_sync_instance.pull.return_value = []
        mock_sync_mgr.return_value = mock_sync_instance
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--force"])
        
        assert result.exit_code == 0
        mock_sync_instance.pull.assert_called_once()
        call_args = mock_sync_instance.pull.call_args[1]
        assert call_args['force'] is True

    @patch('agent_sync.cli.SyncManager')
    @patch('agent_sync.cli.Config')
    def test_pull_skills_only_flag(self, mock_config, mock_sync_mgr):
        """Pull --skills-only should pass skills_only=True."""
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance
        
        mock_sync_instance = MagicMock()
        mock_sync_instance.pull.return_value = ["skill1/SKILL.md"]
        mock_sync_mgr.return_value = mock_sync_instance
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--skills-only"])
        
        assert result.exit_code == 0
        call_args = mock_sync_instance.pull.call_args[1]
        assert call_args['skills_only'] is True

    @patch('agent_sync.cli.SyncManager')
    @patch('agent_sync.cli.Config')
    def test_pull_returns_applied_files(self, mock_config, mock_sync_mgr):
        """Pull output should show list of applied files."""
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance
        
        mock_sync_instance = MagicMock()
        mock_sync_instance.pull.return_value = [
            'configs/opencode/settings.json',
            'skills/my-skill/SKILL.md'
        ]
        mock_sync_mgr.return_value = mock_sync_instance
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull"])
        
        assert result.exit_code == 0
        # Should show applied files or count
        assert "settings" in result.output.lower() or "2" in result.output