"""Tests for the unified publish command in CLI."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_sync.cli import main


class TestPublishCLI:
    """Tests for agent-sync publish command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_all_dry_run(self, mock_scan, mock_get_agents, mock_get_skills, runner):
        """Test --all --dry-run shows summary and security scan."""
        skill1_path = MagicMock(spec=Path)
        skill1_path.is_dir.return_value = True
        skill1_path.rglob.return_value = []

        skill2_path = MagicMock(spec=Path)
        skill2_path.is_dir.return_value = True
        skill2_path.rglob.return_value = []

        mock_get_skills.return_value = [
            {"name": "skill1", "path": skill1_path},
            {"name": "skill2", "path": skill2_path},
        ]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
            {"agent": "pi.dev", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--dry-run"], input="\n")

        assert result.exit_code == 0, result.output
        assert "Publishing Summary" in result.output
        assert "DRY RUN" in result.output

    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.scan_file")
    def test_publish_skills_only_shows_summary(self, mock_scan, mock_get_skills, mock_get_agents, runner):
        """Test --skills shows skills summary."""
        skill1_path = MagicMock(spec=Path)
        skill1_path.is_dir.return_value = False
        skill1_path.is_file.return_value = True

        mock_get_skills.return_value = [{"name": "skill1", "path": skill1_path}]
        mock_get_agents.return_value = []
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--skills", "--dry-run"], input="\n")

        assert "DRY RUN" in result.output
        assert "0 agent" in result.output.lower()

    @patch("agent_sync.cli.Config")
    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_agents_only_shows_summary(self, mock_scan, mock_get_agents, mock_get_skills, mock_config, runner):
        """Test --agents shows agents summary with security."""
        # Clear saved selections
        mock_config.return_value.published_skills = []
        mock_config.return_value.published_agents = []
        
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
    
        result = runner.invoke(main, ["publish", "--agents", "--dry-run"], input="\n")
    
        assert "DRY RUN" in result.output
        assert "0 skill" in result.output.lower()
        assert "Security: 1 safe" in result.output

    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish._interactive_flagged_selection")
    @patch("rich.prompt.Confirm.ask", return_value=False)
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.get_available_skills")
    def test_publish_cancelled_by_user(self, mock_get_skills, mock_get_agents, mock_confirm, mock_interactive, mock_scan, runner):
        """Test user can cancel publishing."""
        skill_path = MagicMock(spec=Path)
        skill_path.is_dir.return_value = False
        mock_get_skills.return_value = [{"name": "skill1", "path": skill_path}]
        mock_get_agents.return_value = []
        mock_scan.return_value = MagicMock(safe=False, issues=[])
        mock_interactive.return_value = ([], False)

        result = runner.invoke(main, ["publish", "--skills"], input="\n")

        assert result.exit_code == 0, result.output
        assert "cancelled" in result.output.lower() or "aborted" in result.output.lower()

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    def test_publish_nothing_found(self, mock_get_agents, mock_get_skills, runner):
        """Test when nothing to publish."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = []

        result = runner.invoke(main, ["publish"], input="\n")

        assert result.exit_code == 0
        assert "Nothing found to publish" in result.output

    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish._interactive_flagged_selection")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.get_available_skills")
    def test_publish_security_warning_for_agents(self, mock_get_skills, mock_get_agents, mock_interactive, mock_scan, runner):
        """Test security warning shows agent-specific info when --agents."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        mock_interactive.return_value = ([], True)
        result = runner.invoke(main, ["publish", "--agents", "--dry-run"], input="\n")
        assert result.exit_code == 0, result.output
        # Check for unified security warning
        assert "Public Disclosure" in result.output
        assert "What will be scanned" in result.output or "scanned" in result.output.lower()
        assert "agent instructions" in result.output.lower()

    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish._interactive_flagged_selection")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.get_available_skills")
    def test_publish_both_shows_contextual_warning(self, mock_get_skills, mock_get_agents, mock_interactive, mock_scan, runner):
        """Test --all shows BOTH skills and agents warning."""
        skill_path = MagicMock(spec=Path)
        skill_path.is_dir.return_value = True
        skill_path.rglob.return_value = []

        mock_get_skills.return_value = [{"name": "skill1", "path": skill_path}]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        mock_interactive.return_value = ([], True)
        result = runner.invoke(main, ["publish", "--dry-run"], input="\n")
        assert result.exit_code == 0, result.output
        assert "What will be scanned" in result.output.lower() or "scanned" in result.output.lower()

    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.get_available_skills")
    def test_publish_shows_security_status_table(self, mock_get_skills, mock_get_agents, mock_scan, runner):
        """Test summary shows security counts in dry-run."""
        path1 = MagicMock(spec=Path)
        path2 = MagicMock(spec=Path)

        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": path1},
            {"agent": "pi.dev", "filename": "AGENTS.md", "path": path2},
        ]

        mock_scan.side_effect = [
            MagicMock(safe=True, issues=[]),
            MagicMock(safe=False, issues=[{"rule": "TEST", "severity": "high", "snippet": "test"}]),
        ]

        result = runner.invoke(main, ["publish", "--agents", "--dry-run"], input="\n")

        assert result.exit_code == 0, result.output
        # Security summary should still be shown
        assert "Security: 1 safe" in result.output
        assert "Warnings: 1 flagged" in result.output
        # Should show dry-run completion
        assert "DRY RUN" in result.output

    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.get_available_skills")
    def test_publish_shows_security_warning_in_summary(self, mock_get_skills, mock_get_agents, mock_scan, runner):
        """Test flagged files reflected in security summary."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "pi.dev", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(
            safe=False,
            issues=[{"rule": "TOKEN_OPENAI", "severity": "critical", "snippet": "sk-123..."}]
        )

        # Use 'a' to select all in interactive mode (bypasses saved selection)
        result = runner.invoke(main, ["publish", "--agents", "--dry-run"], input="a\n")

        assert result.exit_code == 0, result.output
        # Should show in security summary
        assert "Security: 0 safe" in result.output
        assert "Warnings: 1 flagged" in result.output
        # Should complete dry-run
        assert "DRY RUN" in result.output