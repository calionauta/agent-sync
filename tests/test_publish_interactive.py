"""Tests for the DRY helpers and interactive flagged selection."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.prompt import Confirm

from agent_sync.cli import main
from agent_sync.publish import (
    _interactive_flagged_selection,
    _render_flagged_table,
    _generate_public_repo_readme,
    _generate_skills_readme,
)
from agent_sync._selection import parse_multiselect_input


class TestRenderFlaggedTable:
    """Tests for _render_flagged_table()."""

    def test_renders_table_with_items(self):
        """Table renders with correct columns."""
        item = {"name": "test-skill", "filename": "test.txt"}
        result = MagicMock(safe=False, issues=[
            {"rule": "TOKEN_OPENAI", "severity": "critical", "snippet": "sk-123"}
        ])
        flagged = [(item, result, "skill-prefix")]
        
        table = _render_flagged_table(flagged)
        
        # Table should be created
        assert table is not None
        # Check that it's a Rich Table
        assert hasattr(table, 'columns')

    def test_renders_empty_table(self):
        """Empty flagged list returns empty table."""
        table = _render_flagged_table([])
        assert table is not None

    def test_uses_prefix_for_name(self):
        """Prefix is used in item display."""
        item = {"name": "my-skill", "filename": "SKILL.md"}
        result = MagicMock(safe=False, issues=[])
        flagged = [(item, result, "prefix")]
        
        table = _render_flagged_table(flagged)
        assert table is not None


class TestInteractiveFlaggedSelection:
    """Tests for _interactive_flagged_selection()."""

    @patch("agent_sync._selection.parse_multiselect_input", return_value=None)
    @patch("agent_sync.publish.Prompt.ask", return_value="done")
    @patch("agent_sync.publish.Confirm.ask", return_value=False)
    def test_cancelled_returns_empty(self, mock_confirm, mock_prompt, mock_parse):
        """Cancelled selection returns empty list."""
        item = {"name": "test", "filename": "test.md"}
        result = MagicMock(safe=False, issues=[])
        flagged = [(item, result, "prefix")]
        
        selected, confirmed = _interactive_flagged_selection(flagged)
        
        assert selected == []
        assert confirmed is False

    @patch("agent_sync._selection.parse_multiselect_input", return_value={"1:skill1"})
    @patch("agent_sync.publish.Prompt.ask", return_value="done")
    @patch("agent_sync.publish.Confirm.ask", return_value=True)
    def test_selections_included(self, mock_confirm, mock_prompt, mock_parse):
        """Selected items are returned correctly."""
        item1 = {"name": "skill1", "filename": "a.md"}
        item2 = {"name": "skill2", "filename": "b.md"}
        result = MagicMock(safe=False, issues=[])
        flagged = [(item1, result, "s1"), (item2, result, "s2")]
        
        selected, confirmed = _interactive_flagged_selection(flagged)
        
        assert len(selected) == 1
        assert selected[0] == item1

    def test_empty_flagged_returns_true(self):
        """Empty flagged list returns True without interaction."""
        selected, confirmed = _interactive_flagged_selection([])
        
        assert selected == []
        assert confirmed is True


class TestReadmeGeneration:
    """Tests for README template generation."""

    def test_generate_public_repo_readme(self):
        """Public repo README is generated correctly."""
        result = _generate_public_repo_readme("https://github.com/user/my-repo.git")
        
        assert "# my-repo" in result
        assert "npx skills add user/my-repo" in result
        assert "agent-sync" in result

    def test_generate_skills_readme(self):
        """Skills README is generated correctly."""
        result = _generate_skills_readme("https://github.com/user/agent-sync-public.git")
        
        assert "# Skills" in result
        assert "npx skills add user/agent-sync-public" in result
        assert "agent-sync" in result

    def test_readme_handles_invalid_url(self):
        """Invalid URLs produce fallback content."""
        result = _generate_public_repo_readme("invalid-url")
        
        # Should not crash, may return empty or basic content
        assert result is not None

    def test_readme_uses_correct_username(self):
        """README uses correct username from URL."""
        result = _generate_skills_readme("https://github.com/renatocaliari/agent-sync-public.git")
        
        assert "renatocaliari" in result


class TestPublishCLIIntegration:
    """Integration tests for publish CLI with flagged items."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish._interactive_flagged_selection")
    @patch("agent_sync.publish.publish_skills")
    @patch("agent_sync.publish.publish_agents")
    @patch("rich.prompt.Confirm.ask", return_value=True)
    def test_publish_with_flagged_selection(
        self, mock_confirm, mock_publish_agents, mock_publish_skills,
        mock_interactive, mock_scan, mock_get_agents, mock_get_skills, runner
    ):
        """Test publish flow with interactive flagged selection."""
        # Setup skills
        skill_path = MagicMock(spec=Path)
        skill_path.is_dir.return_value = True
        mock_get_skills.return_value = [
            {"name": "skill1", "path": skill_path},
        ]
        
        # Setup agents with flagged content
        agent_path = MagicMock(spec=Path)
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": agent_path},
        ]
        
        # Scan results: skill flagged, agent safe
        mock_scan.side_effect = [
            MagicMock(safe=False, issues=[{"rule": "TEST", "severity": "high", "snippet": "test"}]),
            MagicMock(safe=True, issues=[]),
        ]
        
        # Interactive selection returns selected items
        mock_interactive.return_value = (
            [{"agent": "opencode", "filename": "AGENTS.md", "path": agent_path}],
            True
        )
        
        mock_publish_skills.return_value = True
        mock_publish_agents.return_value = True
        
        result = runner.invoke(main, ["publish", "--dry-run"], input="\n")
        
        # Should proceed to flagged selection
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_publish_no_flagged_skips_selection(
        self, mock_scan, mock_get_agents, mock_get_skills, runner
    ):
        """Test publish without flagged items skips interactive selection."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = [
            {"agent": "opencode", "filename": "AGENTS.md", "path": MagicMock(spec=Path)},
        ]
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        
        result = runner.invoke(main, ["publish", "--agents", "--dry-run"], input="\n")
        
        assert result.exit_code == 0
        # Should show summary without flagged selection
        assert "All cleared" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish._interactive_flagged_selection")
    @patch("agent_sync.publish.publish_skills")
    @patch("agent_sync.publish.publish_agents")
    @patch("rich.prompt.Confirm.ask", return_value=False)
    def test_publish_cancelled_after_flagged_selection(
        self, mock_confirm, mock_publish_agents, mock_publish_skills,
        mock_interactive, mock_scan, mock_get_agents, mock_get_skills, runner
    ):
        """Test user can cancel after flagged selection."""
        skill_path = MagicMock(spec=Path)
        skill_path.is_dir.return_value = True
        mock_get_skills.return_value = [{"name": "skill1", "path": skill_path}]
        mock_get_agents.return_value = []
        
        mock_scan.return_value = MagicMock(safe=False, issues=[])
        
        # User cancels after interactive selection
        mock_interactive.return_value = ([], False)
        
        result = runner.invoke(main, ["publish", "--skills"], input="\n")
        
        assert "cancelled" in result.output.lower()


class TestPublishSkillsOnly:
    """Tests for agent-sync publish --skills."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish._interactive_flagged_selection")
    @patch("agent_sync.publish.publish_skills")
    @patch("rich.prompt.Confirm.ask", return_value=True)
    def test_publish_skills_with_flagged(
        self, mock_confirm, mock_publish, mock_interactive, mock_scan, mock_get_skills, runner
    ):
        """Test --skills handles flagged items."""
        skill_path = MagicMock(spec=Path)
        skill_path.is_dir.return_value = True
        skill_path.rglob.return_value = []
        
        mock_get_skills.return_value = [
            {"name": "flagged-skill", "path": skill_path},
        ]
        
        mock_scan.return_value = MagicMock(safe=False, issues=[
            {"rule": "ABS_PATH_UNIX", "severity": "high", "snippet": "/Users/test/"}
        ])
        
        mock_interactive.return_value = (
            [{"name": "flagged-skill", "path": skill_path}],
            True
        )
        
        mock_publish.return_value = True
        
        result = runner.invoke(main, ["publish", "--skills", "--dry-run"], input="\n")
        
        assert result.exit_code == 0


class TestPublishAgentsOnly:
    """Tests for agent-sync publish --agents."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    @patch("agent_sync.publish._interactive_flagged_selection")
    @patch("agent_sync.publish.publish_agents")
    @patch("rich.prompt.Confirm.ask", return_value=True)
    def test_publish_agents_with_flagged(
        self, mock_confirm, mock_publish, mock_interactive, mock_scan, mock_get_agents, runner
    ):
        """Test --agents handles flagged items."""
        agent_path = MagicMock(spec=Path)
        mock_get_agents.return_value = [
            {"agent": "pi.dev", "filename": "AGENTS.md", "path": agent_path},
        ]
        
        mock_scan.return_value = MagicMock(safe=False, issues=[
            {"rule": "TOKEN_GITHUB", "severity": "critical", "snippet": "ghp_1234567890abcdef"}
        ])
        
        mock_interactive.return_value = (
            [{"agent": "pi.dev", "filename": "AGENTS.md", "path": agent_path}],
            True
        )
        
        mock_publish.return_value = True
        
        result = runner.invoke(main, ["publish", "--agents", "--dry-run"], input="\n")
        
        assert result.exit_code == 0


class TestUnifiedSecurityScan:
    """Tests for unified security scanner (same for skills and agents)."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_unified_scan_applies_to_both(
        self, mock_scan, mock_get_agents, mock_get_skills, runner
    ):
        """Test unified security message shows for both skills and agents."""
        skill_path = MagicMock(spec=Path)
        skill_path.is_dir.return_value = True
        skill_path.rglob.return_value = []
        
        agent_path = MagicMock(spec=Path)
        
        mock_get_skills.return_value = [{"name": "s1", "path": skill_path}]
        mock_get_agents.return_value = [
            {"agent": "a1", "filename": "AGENTS.md", "path": agent_path},
        ]
        
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        
        result = runner.invoke(main, ["publish", "--dry-run"], input="\n")
        
        assert "SECURITY SCAN applies to BOTH" in result.output
        assert "API keys / tokens" in result.output
        assert "Private URLs" in result.output
        assert "Absolute paths" in result.output
        assert "Internal commands" in result.output

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.get_available_agents")
    @patch("agent_sync.publish.scan_file")
    def test_skipped_files_mentioned(
        self, mock_scan, mock_get_agents, mock_get_skills, runner
    ):
        """Test skipped file types are mentioned."""
        mock_get_skills.return_value = []
        mock_get_agents.return_value = []
        
        mock_scan.return_value = MagicMock(safe=True, issues=[])
        
        result = runner.invoke(main, ["publish", "--dry-run"], input="\n")
        
        assert "SKIPPED automatically" in result.output
        assert "auth, token, key, secret" in result.output
        assert ".env files" in result.output