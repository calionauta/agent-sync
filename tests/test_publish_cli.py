"""Tests for the unified publish command in CLI."""

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

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
        mock_get_skills.return_value = [
            {"name": "skill1", "path": MagicMock(spec=Path)},
            {"name": "skill2", "path": MagicMock(spec=Path)},
        ]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
            {"agent": "pi.dev", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "Publishing Summary" in result.output
        assert "Skills: 2 found" in result.output
        assert "Agents: 2 found" in result.output
        assert "DRY RUN" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_skills_only_shows_summary(self, mock_scan, mock_get_agents, mock_get_skills, runner):
        """Test --skills shows skills summary."""
        mock_get_skills.return_value = [{"name": "skill1", "path": MagicMock(spec=Path)}]
        mock_get_agents.return_value = []
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--skills", "--dry-run"])

        assert "DRY RUN" in result.output
        assert "0 agents" in result.output  # Shows in dry-run summary

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_agents_only_shows_summary(self, mock_scan, mock_get_agents, mock_get_skills, runner):
        """Test --agents shows agents summary with security."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--agents", "--dry-run"])

        assert "DRY RUN" in result.output
        assert "0 skills" in result.output  # Shows in dry-run summary
        assert "Security: 1 safe" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    @patch("rich.prompt.Confirm.ask", return_value=False)
    def test_publish_cancelled_by_user(self, mock_confirm, mock_scan, mock_get_agents, mock_get_skills, runner):
        """Test user can cancel publishing."""
        mock_get_skills.return_value = [{"name": "skill1", "path": MagicMock(spec=Path)}]
        mock_get_agents.return_value = []
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--skills"])

        assert result.exit_code == 0, result.output
        assert "cancelled" in result.output.lower()

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    def test_publish_nothing_found(self, mock_get_agents, mock_get_skills, runner):
        """Test when nothing to publish."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = []

        result = runner.invoke(main, ["publish"])

        assert result.exit_code == 0
        assert "Nothing found to publish" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_security_warning_for_agents(self, mock_scan, mock_get_agents, mock_get_skills, runner):
        """Test security warning shows agent-specific info when --agents."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--agents", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "Scanned for sensitive patterns" in result.output
        assert "You are about to publish agent instructions" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_both_shows_contextual_warning(self, mock_scan, mock_get_agents, mock_get_skills, runner):
        """Test --all shows BOTH skills and agents warning."""
        mock_get_skills.return_value = [{"name": "skill1", "path": MagicMock(spec=Path)}]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "BOTH skills AND agent instructions" in result.output
        assert "📚 Skills" in result.output
        assert "🤖 Agent Instructions" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_shows_security_status_table(self, mock_scan, mock_get_agents, mock_get_skills, runner):
        """Test agents table shows security status."""
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

        result = runner.invoke(main, ["publish", "--agents", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "✓ Safe" in result.output
        assert "⚠️ Warning" in result.output
        assert "Security: 1 safe" in result.output
        assert "Warnings: 1 flagged" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_shows_security_warning_details(self, mock_scan, mock_get_agents, mock_get_skills, runner):
        """Test flagged files show warning details."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "pi.dev", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(
            safe=False,
            issues=[{"rule": "TOKEN_OPENAI", "severity": "critical", "snippet": "sk-123..."}]
        )

        result = runner.invoke(main, ["publish", "--agents", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "Files with warnings" in result.output
        assert "pi.dev" in result.output
        assert "TOKEN_OPENAI" in result.output