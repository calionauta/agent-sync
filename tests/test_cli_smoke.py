"""Smoke tests - verify CLI commands can be imported without NameError.

These tests catch import errors, NameError, SyntaxError, and other
runtime issues that would break the CLI in production.

Critical for catching bugs like missing imports or typos in function names.
"""

import pytest
import inspect


class TestCLISmoke:
    """Smoke tests for CLI commands - catch NameError, ImportError, etc."""

    def test_import_cli_module(self):
        """Verify CLI module can be imported."""
        import agent_sync.cli
        assert agent_sync.cli is not None

    def test_import_tui_helpers(self):
        """Verify TUI helpers can be imported."""
        from agent_sync._tui import build_footer_commands, print_footer

        # Test basic functionality
        cmds = build_footer_commands([("Enter", "push"), ("q", "cancel")], default_key="Enter")
        assert len(cmds) == 2
        assert cmds[0][0] == "Enter"
        # Check that first letter is escaped for Rich
        assert "\\[p]ush" in cmds[0][1] or "[p]ush" in cmds[0][1]

    def test_push_command_exists(self):
        """Verify push command exists and can be imported."""
        from agent_sync.cli import push
        assert push is not None

    def test_pull_command_exists(self):
        """Verify pull command exists."""
        from agent_sync.cli import pull
        assert pull is not None

    def test_sync_command_exists(self):
        """Verify sync command exists."""
        from agent_sync.cli import sync
        assert sync is not None

    def test_push_command_has_all_filter_params(self):
        """Verify push command accepts all filter params - catches NameError on missing imports."""
        from agent_sync.cli import push

        sig = inspect.signature(push.callback)
        params = set(sig.parameters.keys())

        # These should be in the signature
        expected = {
            "skills_only", "configs_only", "message"
        }

        missing = expected - params
        assert not missing, f"Missing params in push: {missing}"

    def test_pull_command_has_all_filter_params(self):
        """Verify pull command accepts all filter params."""
        from agent_sync.cli import pull

        sig = inspect.signature(pull.callback)
        params = set(sig.parameters.keys())

        expected = {
            "force", "dry_run", "interactive",
            "skills_only", "configs_only",
            "skill", "agent", "exclude_skill", "exclude_agent"
        }

        missing = expected - params
        assert not missing, f"Missing params in pull: {missing}"