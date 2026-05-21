"""End-to-end integration tests for CLI parameter handling.

These tests verify that CLI commands handle filter flags correctly
without raising TypeErrors due to wrong parameter names.
"""

import pytest
from unittest.mock import patch, Mock
from click.testing import CliRunner

from agent_sync.cli import main


runner = CliRunner()


class TestCLIPushFilters:
    """Verify push command handles filter flags correctly."""

    def test_push_no_typeerror_on_filter_flags(self):
        """push with filter flags should not raise TypeError."""
        result = runner.invoke(main, [
            'push',
            '--skill', 'dogfood',
            '--agent', 'pi.dev',
            '--exclude-skill', 'deprecated',
            '--exclude-agent', 'old',
            '--dry-run'
        ])
        
        # Should NOT have TypeError (wrong param names)
        assert 'TypeError' not in result.output, f"TypeError in output: {result.output}"
        # Should NOT have Traceback
        assert 'Traceback' not in result.output or result.exit_code == 0, f"Traceback in output: {result.output}"

    def test_push_with_all_filters_no_errors(self):
        """push with all filter combinations should work."""
        result = runner.invoke(main, [
            'push',
            '--skill', 'dogfood',
            '--agent', 'pi.dev',
            '--exclude-skill', 'skip1', '--exclude-skill', 'skip2',
            '--exclude-agent', 'skip3',
            '--skills-only',
            '--dry-run'
        ])
        
        assert 'TypeError' not in result.output
        assert 'NoSuchOption' not in result.output
        assert 'Traceback' not in result.output or result.exit_code == 0

    def test_pull_no_typeerror_on_filter_flags(self):
        """pull with filter flags should not raise TypeError."""
        result = runner.invoke(main, [
            'pull',
            '--skill', 'dogfood',
            '--agent', 'pi.dev',
            '--exclude-skill', 'deprecated',
            '--exclude-agent', 'old',
            '--dry-run'
        ])
        
        assert 'TypeError' not in result.output
        assert 'NoSuchOption' not in result.output
        assert 'Traceback' not in result.output or result.exit_code == 0


class TestCLIPullFilters:
    """Verify pull command handles filter flags correctly."""

    def test_pull_with_exclude_skill_no_error(self):
        """pull --exclude-skill should work without errors."""
        result = runner.invoke(main, [
            'pull',
            '--exclude-skill', 'deprecated',
            '--dry-run'
        ])
        
        assert 'TypeError' not in result.output
        assert 'Traceback' not in result.output or result.exit_code == 0

    def test_pull_with_multiple_filters_no_error(self):
        """pull with multiple filter combinations should work."""
        result = runner.invoke(main, [
            'pull',
            '--skill', 'skill1', '--skill', 'skill2',
            '--agent', 'agent1',
            '--exclude-skill', 'skip1', '--exclude-skill', 'skip2',
            '--exclude-agent', 'skip3',
            '--dry-run'
        ])
        
        assert 'TypeError' not in result.output
        assert 'NoSuchOption' not in result.output
        assert 'Traceback' not in result.output or result.exit_code == 0
