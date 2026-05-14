"""Tests for the unified publish command in CLI."""

import json
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_sync.cli import main


class TestPublishCLI:
    """Tests for agent-sync publish command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch("agent_sync.cli.publish_agents")
    @patch("agent_sync.cli.publish_skills")
    @patch("agent_sync.cli.get_available_skills")
    @patch("agent_sync.cli.get_available_agents")
    @patch("agent_sync.cli.scan_file")
    @patch("agent_sync.cli.format_issues_for_display")
    def test_publish_all_dry_run(
        self, mock_format, mock_scan, mock_get_agents, mock_get_skills,
        mock_publish_skills, mock_publish_agents, runner
    ):
        """Test --all --dry-run shows summary and security scan."""
        # Setup mocks
        mock_get_skills.return_value = [
            {"name": "skill1", "path": MagicMock(spec=Path)},
            {"name": "skill2", "path": MagicMock(spec=Path)},
        ]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
            {"agent": "pi.dev", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        mock_format.return_value = "  No issues detected."

        # Execute
        result = runner.invoke(main, ["publish", "--dry-run"])

        # Verify
        assert result.exit_code == 0
        assert "Publishing Summary" in result.output
        assert "Skills: 2 found" in result.output
        assert "Agents: 2 found" in result.output
        assert "DRY RUN" in result.output
        
        # Should NOT call actual publish functions in dry-run
        mock_publish_skills.assert_not_called()
        mock_publish_agents.assert_not_called()

    @patch("agent_sync.cli.publish_agents")
    @patch("agent_sync.cli.publish_skills")
    @patch("agent_sync.cli.get_available_skills")
    @patch("agent_sync.cli.get_available_agents")
    @patch("agent_sync.cli.scan_file")
    @patch("agent_sync.cli.Confirm.ask")
    def test_publish_skills_only(
        self, mock_confirm, mock_scan, mock_get_agents, mock_get_skills,
        mock_publish_skills, mock_publish_agents, runner
    ):
        """Test --skills only publishes skills."""
        mock_get_skills.return_value = [
            {"name": "skill1", "path": MagicMock(spec=Path)},
        ]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        mock_confirm.return_value = True
        mock_publish_skills.return_value = True

        # Execute
        result = runner.invoke(main, ["publish", "--skills"])

        # Verify
        assert result.exit_code == 0
        assert "Skills: 1 found" in result.output
        assert "Agents: 0 found" in result.output  # No agents should be published
        
        mock_publish_skills.assert_called_once()
        mock_publish_agents.assert_not_called()

    @patch("agent_sync.cli.publish_agents")
    @patch("agent_sync.cli.publish_skills")
    @patch("agent_sync.cli.get_available_skills")
    @patch("agent_sync.cli.get_available_agents")
    @patch("agent_sync.cli.scan_file")
    @patch("agent_sync.cli.Confirm.ask")
    def test_publish_agents_only(
        self, mock_confirm, mock_scan, mock_get_agents, mock_get_skills,
        mock_publish_skills, mock_publish_agents, runner
    ):
        """Test --agents only publishes agents."""
        mock_get_skills.return_value = [
            {"name": "skill1", "path": MagicMock(spec=Path)},
        ]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        mock_confirm.return_value = True
        mock_publish_agents.return_value = True

        # Execute
        result = runner.invoke(main, ["publish", "--agents"])

        # Verify
        assert result.exit_code == 0
        assert "Skills: 0 found" in result.output  # No skills should be published
        assert "Agents: 1 found" in result.output
        
        mock_publish_skills.assert_not_called()
        mock_publish_agents.assert_called_once()

    @patch("agent_sync.cli.publish_agents")
    @patch("agent_sync.cli.publish_skills")
    @patch("agent_sync.cli.get_available_skills")
    @patch("agent_sync.cli.get_available_agents")
    @patch("agent_sync.cli.scan_file")
    @patch("agent_sync.cli.Confirm.ask")
    def test_publish_cancelled_by_user(
        self, mock_confirm, mock_scan, mock_get_agents, mock_get_skills,
        mock_publish_skills, mock_publish_agents, runner
    ):
        """Test user can cancel publishing."""
        mock_get_skills.return_value = [{"name": "skill1", "path": MagicMock(spec=Path)}]
        mock_get_agents.return_value = []
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        mock_confirm.return_value = False  # User says no

        # Execute
        result = runner.invoke(main, ["publish", "--skills"])

        # Verify
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()
        mock_publish_skills.assert_not_called()
        mock_publish_agents.assert_not_called()

    @patch("agent_sync.cli.get_available_skills")
    @patch("agent_sync.cli.get_available_agents")
    def test_publish_nothing_found(self, mock_get_agents, mock_get_skills, runner):
        """Test when nothing to publish."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = []

        # Execute
        result = runner.invoke(main, ["publish"])

        # Verify
        assert result.exit_code == 0
        assert "Nothing found to publish" in result.output

    @patch("agent_sync.cli.publish_agents")
    @patch("agent_sync.cli.publish_skills")
    @patch("agent_sync.cli.get_available_skills")
    @patch("agent_sync.cli.get_available_agents")
    @patch("agent_sync.cli.scan_file")
    @patch("agent_sync.cli.Confirm.ask")
    def test_publish_security_warning_for_agents(
        self, mock_confirm, mock_scan, mock_get_agents, mock_get_skills,
        mock_publish_skills, mock_publish_agents, runner
    ):
        """Test security warning shows agent-specific info when --agents."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        mock_confirm.return_value = True
        mock_publish_agents.return_value = True

        # Execute
        result = runner.invoke(main, ["publish", "--agents"])

        # Verify
        assert result.exit_code == 0
        assert "Scanned for sensitive patterns" in result.output
        assert "publishing agent instructions" in result.output

    @patch("agent_sync.cli.publish_agents")
    @patch("agent_sync.cli.publish_skills")
    @patch("agent_sync.cli.get_available_skills")
    @patch("agent_sync.cli.get_available_agents")
    @patch("agent_sync.cli.scan_file")
    @patch("agent_sync.cli.Confirm.ask")
    def test_publish_both_shows_contextual_warning(
        self, mock_confirm, mock_scan, mock_get_agents, mock_get_skills,
        mock_publish_skills, mock_publish_agents, runner
    ):
        """Test --all shows BOTH skills and agents warning."""
        mock_get_skills.return_value = [{"name": "skill1", "path": MagicMock(spec=Path)}]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        mock_confirm.return_value = True
        mock_publish_skills.return_value = True
        mock_publish_agents.return_value = True

        # Execute (default is --all)
        result = runner.invoke(main, ["publish"])

        # Verify
        assert result.exit_code == 0
        assert "BOTH skills AND agent instructions" in result.output
        assert "📚 Skills" in result.output
        assert "🤖 Agent Instructions" in result.output

    @patch("agent_sync.cli.publish_agents")
    @patch("agent_sync.cli.publish_skills")
    @patch("agent_sync.cli.get_available_skills")
    @patch("agent_sync.cli.get_available_agents")
    @patch("agent_sync.cli.scan_file")
    @patch("agent_sync.cli.Confirm.ask")
    def test_publish_shows_security_status_table(
        self, mock_confirm, mock_scan, mock_get_agents, mock_get_skills,
        mock_publish_skills, mock_publish_agents, runner
    ):
        """Test agents table shows security status."""
        path1 = MagicMock(spec=Path)
        path2 = MagicMock(spec=Path)
        
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": path1},
            {"agent": "pi.dev", "filename": "AGENTS.md", "path": path2},
        ]
        
        # One safe, one with warning
        mock_scan.side_effect = [
            MagicMock(safe=True, issues=[]),
            MagicMock(safe=False, issues=[{"rule": "TEST", "severity": "high", "snippet": "test"}]),
        ]
        mock_confirm.return_value = True
        mock_publish_agents.return_value = True

        # Execute
        result = runner.invoke(main, ["publish", "--agents"])

        # Verify
        assert result.exit_code == 0
        assert "✓ Safe" in result.output
        assert "⚠️ Warning" in result.output
        assert "Security: 1 safe" in result.output
        assert "Warnings: 1 flagged" in result.output