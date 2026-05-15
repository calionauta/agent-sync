"""Tests for agent-sync CLI."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agent_sync.cli import main


class TestCLI:
    """Test CLI commands."""

    def test_cli_version(self):
        """Test version command."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "agent-sync" in result.output

    def test_cli_help(self):
        """Test help command."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "agent-sync" in result.output
        assert "Sync configs and skills" in result.output

    def test_agents_command(self):
        """Test agents list command."""
        runner = CliRunner()
        result = runner.invoke(main, ["agents"])

        assert result.exit_code == 0
        assert "opencode" in result.output or "Supported Agents" in result.output

    @patch('agent_sync.cli.Config')
    @patch('agent_sync.cli.SyncManager')
    def test_status_command(self, mock_sync_mgr, mock_config):
        """Test status command."""
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance

        mock_sync_instance = MagicMock()
        mock_sync_instance.get_status.return_value = {
            "opencode": {
                "status": "configured",
                "last_sync": "2024-01-01T00:00:00",
                "changes": None,
            }
        }
        mock_sync_mgr.return_value = mock_sync_instance

        runner = CliRunner()
        result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "Sync Status" in result.output

    @patch('agent_sync.cli.Config')
    def test_generate_config_command(self, mock_config):
        """Test generate-config command."""
        mock_config_instance = MagicMock()
        mock_config_instance.generate_default.return_value = "/tmp/config.yaml"
        mock_config.return_value = mock_config_instance

        runner = CliRunner()
        result = runner.invoke(main, ["generate-config"])

        assert result.exit_code == 0
        mock_config_instance.generate_default.assert_called_once()

    @patch('agent_sync.cli.Config')
    @patch('agent_sync.cli.SyncManager')
    def test_pull_command(self, mock_sync_mgr, mock_config):
        """Test pull command."""
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        mock_sync_instance = MagicMock()
        mock_sync_instance.pull.return_value = ["config1.json", "skill1.py"]
        mock_sync_mgr.return_value = mock_sync_instance

        runner = CliRunner()
        result = runner.invoke(main, ["pull"])

        assert result.exit_code == 0
        mock_sync_instance.pull.assert_called_once()

    @patch('agent_sync.cli.Config')
    @patch('agent_sync.cli.SyncManager')
    def test_push_command(self, mock_sync_mgr, mock_config):
        """Test push command."""
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        mock_sync_instance = MagicMock()
        mock_sync_instance.push.return_value = [
            {'path': 'config1.json', 'status': 'M', 'label': 'modified', 'directory_count': None},
        ]
        mock_sync_mgr.return_value = mock_sync_instance

        runner = CliRunner()
        result = runner.invoke(main, ["push", "-m", "test commit"])

        assert result.exit_code == 0
        mock_sync_instance.push.assert_called_once()

    def test_config_show_command(self):
        """Test config show command."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "show"])

        assert result.exit_code == 0
        assert "Config" in result.output or "Repository" in result.output

    def test_init_command_help(self):
        """Test init command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--help"])

        assert result.exit_code == 0
        assert "Repository name" in result.output or "wizard" in result.output

    def test_skills_list_command(self):
        """Test skills list command."""
        runner = CliRunner()
        result = runner.invoke(main, ["skills", "list"])

        assert result.exit_code == 0

    @patch('agent_sync.cli.Config')
    def test_diff_command(self, mock_config):
        """Test diff command."""
        mock_config_instance = MagicMock()
        mock_config_instance.repo_url = "https://github.com/test/repo.git"
        mock_config.return_value = mock_config_instance

        runner = CliRunner()
        result = runner.invoke(main, ["skills", "diff"])

        assert result.exit_code == 0
        assert "Local and remote are in sync" in result.output or "remote" in result.output

    def test_centralize_help(self):
        """Test centralize command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["skills", "centralize", "--help"])

        assert result.exit_code == 0
        assert "centralize" in result.output.lower()

    def test_secrets_list_command(self):
        """Test secrets list command."""
        runner = CliRunner()
        result = runner.invoke(main, ["secrets", "list"])

        assert result.exit_code == 0

    def test_mcp_help(self):
        """Test mcp command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--help"])

        assert result.exit_code == 0
        assert "MCP" in result.output or "mcp" in result.output
