"""Tests for the unified publish command in CLI.

NOTE: These tests are for the OLD publish flow which used get_available_skills,
get_available_agents, scan_file from the root publish.py module.

The NEW flow uses:
- run_publish_flow() for skills
- run_agents_publish_flow() for agents

These tests are kept for reference but are SKIPPED since the old flow is deprecated.
The new flow is tested in:
- test_publish_interactive.py (TUI)
- test_publish_agents.py (agents discovery)
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Tests for deprecated publish flow. New flow tested in test_publish_interactive.py and test_publish_agents.py"
)

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agent_sync.cli import main


class TestPublishCLI:
    """Tests for agent-sync publish command (DEPRECATED)."""

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

        mock_get_skills.return_value = [
            {"name": "skill1", "path": skill1_path},
        ]
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])

        result = runner.invoke(main, ["publish", "--dry-run"], input="\n")

        assert result.exit_code == 0, result.output
        assert "Publishing Summary" in result.output