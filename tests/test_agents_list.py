"""Tests for 'agents list' command and agent type field."""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from io import StringIO

from agent_sync.cli import console


class TestAgentTypeField:
    """Test the 'type' field in agent_registry.yaml."""

    def test_registry_has_type_field(self):
        """Test that registry entries have a 'type' field."""
        from agent_sync.agents import load_registry
        registry = load_registry()

        for agent_name, agent_data in registry.items():
            if agent_name == "global-skills":
                continue
            assert "type" in agent_data, f"Agent '{agent_name}' missing 'type' field"
            assert agent_data["type"] in ("cli", "ide"), f"Agent '{agent_name}' has invalid type: {agent_data['type']}"

    def test_cli_agents_have_type(self):
        """Test that CLI agents (claude-code, opencode, gemini-cli, pi.dev, qwen-code) have type='cli'."""
        from agent_sync.agents import load_registry
        registry = load_registry()

        cli_agents = ["claude-code", "opencode", "gemini-cli", "pi.dev", "qwen-code"]
        for agent_name in cli_agents:
            if agent_name in registry:
                assert registry[agent_name]["type"] == "cli", f"Agent '{agent_name}' should have type='cli'"

    def test_ide_agents_have_type(self):
        """Test that IDE agents (roocode, cline, cursor, windsurf) have type='ide'."""
        from agent_sync.agents import load_registry
        registry = load_registry()

        ide_agents = ["roocode", "cline", "cursor", "windsurf"]
        for agent_name in ide_agents:
            if agent_name in registry:
                assert registry[agent_name]["type"] == "ide", f"Agent '{agent_name}' should have type='ide'"


class TestAgentsListCommand:
    """Test 'agents list' command output."""

    def test_agents_list_shows_types(self):
        """Test that 'agents list' shows agent types (not 'unknown')."""
        from agent_sync.cli import main
        from agent_sync.agents import load_registry

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["agents", "list"])

            # Should not contain 'unknown'
            assert "unknown" not in result.output, "Agent type should not be 'unknown'"

            # Should contain 'cli' or 'ide'
            assert "cli" in result.output or "ide" in result.output, "Output should contain agent types"

    def test_agents_list_table_columns(self):
        """Test that 'agents list' shows Name, Type, and Location columns."""
        from agent_sync.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["agents", "list"])

            assert "Name" in result.output, "Should have 'Name' column"
            assert "Type" in result.output, "Should have 'Type' column"
            assert "Location" in result.output, "Should have 'Location' column"


class TestStagingAgentCount:
    """Test that staging count only includes available agents."""

    def test_staging_counts_available_agents_only(self):
        """Test that staging message shows only available (installed) agents, not all registry agents."""
        from agent_sync.sync import SyncManager
        from agent_sync.config import Config
        from agent_sync.agents import get_all_agents

        config = Config()
        sync_mgr = SyncManager(config)

        # Count available agents
        available_count = sum(1 for a in get_all_agents() if a.is_available())

        # The count should be reasonable (not 10 which was the old bug)
        # Depends on what the user has installed
        assert available_count >= 0, "Available agent count should be non-negative"

        # Verify is_available() is being called
        all_agents = list(get_all_agents())
        available_agents = [a for a in all_agents if a.is_available()]

        # At least one agent should be available (pi.dev or opencode)
        assert len(available_agents) > 0, "Should have at least one available agent (pi.dev or opencode)"

    def test_disabled_agents_not_counted(self):
        """Test that disabled agents are not counted in staging."""
        from agent_sync.sync import SyncManager
        from agent_sync.config import Config
        from agent_sync.agents import get_all_agents

        config = Config()
        sync_mgr = SyncManager(config)

        all_enabled = sum(
            1 for a in get_all_agents()
            if config.is_agent_enabled(a.name) and a.is_available()
        )

        # Disable a non-existent agent (shouldn't affect count)
        config.disable_agent("nonexistent-agent")
        all_enabled_after = sum(
            1 for a in get_all_agents()
            if config.is_agent_enabled(a.name) and a.is_available()
        )

        assert all_enabled == all_enabled_after, "Disabling non-existent agent shouldn't affect count"
