"""Tests for publish setup flows."""

from unittest.mock import MagicMock, patch

import pytest

from agent_sync.publish.setup import (
    confirm,
    run_skills_flow,
    run_agents_flow,
    run_publish_setup,
    print_repo_not_configured,
    _build_initial_selection,
    _build_footer_commands,
)
from agent_sync.publish.models import SourceInfo


class TestConfirm:
    """Tests for confirm helper."""

    def test_confirm_returns_true_for_yes(self):
        """Returns True for yes input."""
        with patch("agent_sync.publish.setup.Prompt.ask", return_value="Y"):
            result = confirm("Test?")
            assert result is True

    def test_confirm_returns_false_for_no(self):
        """Returns True for no input."""
        with patch("agent_sync.publish.setup.Prompt.ask", return_value="n"):
            result = confirm("Test?")
            assert result is False

    def test_confirm_case_insensitive(self):
        """Handles uppercase input."""
        with patch("agent_sync.publish.setup.Prompt.ask", return_value="Y"):
            result = confirm("Test?")
            assert result is True


class TestPrintRepoNotConfigured:
    """Tests for print_repo_not_configured."""

    def test_prints_error_message(self):
        """Prints error message."""
        import sys
        from io import StringIO
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        print_repo_not_configured()
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        assert "not configured" in output.lower() or "repository" in output.lower()


class TestBuildFooterCommands:
    """Tests for _build_footer_commands."""

    def test_empty_sources(self):
        """Returns empty list for no sources."""
        commands = _build_footer_commands([])
        assert commands == [("p", "publish"), ("q", "quit")]

    def test_single_source(self):
        """Builds commands for single source."""
        sources = [
            SourceInfo(source_id="local", label="LOCAL", items=["a", "b", "c"]),
        ]
        commands = _build_footer_commands(sources)
        
        # Should have source range + generic commands
        assert len(commands) >= 4
        assert ("1-3", "LOCAL") in commands

    def test_multiple_sources(self):
        """Builds commands for multiple sources."""
        sources = [
            SourceInfo(source_id="local", label="LOCAL", items=["a", "b"]),
            SourceInfo(source_id="ext", label="EXTERNAL", items=["x", "y", "z"]),
        ]
        commands = _build_footer_commands(sources)
        
        assert ("1-2", "LOCAL") in commands
        assert ("3-5", "EXTERN") in commands
        # Generic commands
        assert any(k == "a" for k, _ in commands)
        assert any(k == "p" for k, _ in commands)
        assert any(k == "q" for k, _ in commands)


class TestBuildInitialSelection:
    """Tests for _build_initial_selection."""

    def test_empty_selection(self):
        """Returns empty selection when no saved data."""
        mock_config = MagicMock()
        mock_config.get_skills_for_source.return_value = []
        
        sources = [
            MagicMock(source_id="local", skills=[]),
            MagicMock(source_id="ext", skills=[]),
        ]
        
        result = _build_initial_selection(mock_config, sources)
        
        assert result == {"local": set(), "ext": set()}

    def test_restores_saved_selection(self):
        """Restores saved selection from config."""
        mock_config = MagicMock()
        mock_config.get_skills_for_source.side_effect = [["a", "b"], ["c"]]
        
        sources = [
            MagicMock(source_id="local"),
            MagicMock(source_id="ext"),
        ]
        
        result = _build_initial_selection(mock_config, sources)
        
        assert result["local"] == {"a", "b"}
        assert result["ext"] == {"c"}


class TestRunPublishSetup:
    """Tests for run_publish_setup - step-by-step flow."""

    def test_repo_not_configured(self):
        """Shows error when repo not configured."""
        with patch("agent_sync.publish.setup.get_published_repo", return_value=""):
            result = run_publish_setup()
            assert result is False

    def test_no_sources(self):
        """Shows warning when no sources found."""
        with patch("agent_sync.publish.setup.get_published_repo", return_value="https://github.com/test/repo"):
            with patch("agent_sync.publish.setup.discover_skills_sources", return_value=[]):
                with patch("agent_sync.publish.setup.discover_agents_sources", return_value=[]):
                    result = run_publish_setup()
                    assert result is False


class TestRunSkillsFlow:
    """Tests for run_skills_flow."""

    def test_no_skills_found(self):
        """Shows warning when no skills found."""
        with patch("agent_sync.publish.setup.get_published_repo", return_value="https://github.com/test/repo"):
            with patch("agent_sync.publish.setup.console.print"):
                with patch("agent_sync.publish.setup.discover_skills_sources", return_value=[]):
                    result = run_skills_flow()
                    assert result is False


class TestRunAgentsFlow:
    """Tests for run_agents_flow."""

    def test_no_agents_found(self):
        """Shows warning when no agents found."""
        with patch("agent_sync.publish.setup.get_published_repo", return_value="https://github.com/test/repo"):
            with patch("agent_sync.publish.setup.console.print"):
                with patch("agent_sync.publish.setup.discover_agents_sources", return_value=[]):
                    result = run_agents_flow()
                    assert result is False