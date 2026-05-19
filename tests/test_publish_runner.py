"""Tests for runner.py (thin wrapper)."""

from unittest.mock import MagicMock, patch

import pytest


class TestItemType:
    """Tests for ItemType enum."""

    def test_skills_value(self):
        """SKILLS enum value is 'skills'."""
        from agent_sync.publish.runner import ItemType
        
        assert ItemType.SKILLS.value == "skills"

    def test_agents_value(self):
        """AGENTS enum value is 'agents'."""
        from agent_sync.publish.runner import ItemType
        
        assert ItemType.AGENTS.value == "agents"


class TestRunPublishFlow:
    """Tests for run_publish_flow."""

    def test_runs_skills_flow(self):
        """Delegates to run_skills_flow for SKILLS."""
        from agent_sync.publish.runner import run_publish_flow, ItemType
        
        with patch("agent_sync.publish.runner.run_skills_flow", return_value=True) as mock:
            result = run_publish_flow(ItemType.SKILLS)
            mock.assert_called_once()
            assert result is True

    def test_runs_agents_flow(self):
        """Delegates to run_agents_flow for AGENTS."""
        from agent_sync.publish.runner import run_publish_flow, ItemType
        
        with patch("agent_sync.publish.runner.run_agents_flow", return_value=True) as mock:
            result = run_publish_flow(ItemType.AGENTS)
            mock.assert_called_once()
            assert result is True


class TestRunAllPublishFlow:
    """Tests for run_all_publish_flow."""

    def test_calls_run_publish_setup(self):
        """Delegates to run_publish_setup."""
        from agent_sync.publish.runner import run_all_publish_flow
        
        with patch("agent_sync.publish.runner.run_publish_setup", return_value=True) as mock:
            result = run_all_publish_flow()
            mock.assert_called_once()
            assert result is True


# Tests for helpers that still exist in runner.py

class TestConfirm:
    """Tests for _confirm helper."""

    def test_confirm_returns_true_for_yes(self):
        """Returns True for yes input."""
        from agent_sync.publish.setup import confirm
        
        with patch("agent_sync.setup.Prompt.ask", return_value="Y"):
            result = confirm("Test?")
            assert result is True

    def test_confirm_returns_false_for_no(self):
        """Returns False for no input."""
        from agent_sync.publish.setup import confirm
        
        with patch("agent_sync.setup.Prompt.ask", return_value="n"):
            result = confirm("Test?")
            assert result is False

    def test_confirm_case_insensitive(self):
        """Handles uppercase input."""
        from agent_sync.publish.setup import confirm
        
        with patch("agent_sync.setup.Prompt.ask", return_value="Y"):
            result = confirm("Test?")
            assert result is True


class TestPrintRepoNotConfigured:
    """Tests for print_repo_not_configured."""

    def test_prints_error_message(self):
        """Prints error message about repo not configured."""
        from agent_sync.publish.setup import print_repo_not_configured
        from io import StringIO
        import sys
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        print_repo_not_configured()
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        assert "not configured" in output.lower() or "repository" in output.lower()


# These tests are now in test_publish_interactive.py
# class TestParseNumberInput moved to models tests
# class TestBuildFooterCommands moved to setup tests
# class TestTruncateUrl moved to discovery tests