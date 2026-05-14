"""Tests for agent_discovery module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_sync.agent_discovery import (
    AgentInstructionFile,
    discover_agent_instructions,
    get_available_agents,
    load_registry,
)


class TestAgentInstructionFile:
    """Test AgentInstructionFile dataclass."""

    def test_creation(self):
        """Test creating an AgentInstructionFile."""
        file = AgentInstructionFile(
            agent_name="pi.dev",
            filename="AGENTS.md",
            full_path=Path("/home/user/.pi/agent/AGENTS.md"),
            exists=True,
        )
        assert file.agent_name == "pi.dev"
        assert file.filename == "AGENTS.md"
        assert file.full_path == Path("/home/user/.pi/agent/AGENTS.md")
        assert file.exists is True


class TestLoadRegistry:
    """Test load_registry function."""

    def test_load_registry_returns_dict(self):
        """Test that load_registry returns a dictionary."""
        registry = load_registry()
        assert isinstance(registry, dict)
        assert len(registry) > 0

    def test_load_registry_contains_agents(self):
        """Test that registry contains expected agents."""
        registry = load_registry()
        assert "pi.dev" in registry
        assert "gemini-cli" in registry


class TestDiscoverAgentInstructions:
    """Test discover_agent_instructions function."""

    def test_returns_list(self):
        """Test that discover returns a list."""
        result = discover_agent_instructions()
        assert isinstance(result, list)

    def test_all_items_are_AgentInstructionFile(self):
        """Test all returned items are AgentInstructionFile instances."""
        result = discover_agent_instructions()
        for item in result:
            assert isinstance(item, AgentInstructionFile)

    def test_only_md_files_returned(self):
        """Test that only .md files are returned."""
        result = discover_agent_instructions()
        for item in result:
            assert item.filename.endswith(".md")

    def test_only_existing_files_returned(self):
        """Test that only files that exist are returned."""
        result = discover_agent_instructions()
        for item in result:
            assert item.full_path.exists()
            assert item.full_path.is_file()

    def test_no_dot_files(self):
        """Test that files starting with . are not returned."""
        result = discover_agent_instructions()
        for item in result:
            assert not item.filename.startswith(".")

    def test_deduplication(self):
        """Test that duplicate (agent, filename) pairs are removed."""
        result = discover_agent_instructions()
        seen = set()
        for item in result:
            key = (item.agent_name, item.filename)
            assert key not in seen
            seen.add(key)

    def test_sorted_by_agent_then_filename(self):
        """Test results are sorted by agent_name, then filename."""
        result = discover_agent_instructions()
        for i in range(len(result) - 1):
            current = result[i]
            next_item = result[i + 1]
            assert (current.agent_name, current.filename) <= (next_item.agent_name, next_item.filename)

    def test_exclude_global_skills(self):
        """Test that global-skills (which has no config_dir) is excluded."""
        result = discover_agent_instructions()
        agent_names = [item.agent_name for item in result]
        assert "global-skills" not in agent_names

    def test_include_agents_filter(self):
        """Test include_agents filter."""
        result = discover_agent_instructions(include_agents=["pi.dev"])
        agent_names = [item.agent_name for item in result]
        assert all(name == "pi.dev" for name in agent_names)

    def test_exclude_agents_filter(self):
        """Test exclude_agents filter."""
        result = discover_agent_instructions(exclude_agents=["pi.dev", "opencode"])
        agent_names = [item.agent_name for item in result]
        assert "pi.dev" not in agent_names
        assert "opencode" not in agent_names


class TestGetAvailableAgents:
    """Test get_available_agents function."""

    def test_returns_list(self):
        """Test that get_available_agents returns a list."""
        result = get_available_agents()
        assert isinstance(result, list)

    def test_dict_format(self):
        """Test that each item has expected keys."""
        result = get_available_agents()
        for item in result:
            assert "name" in item
            assert "agent" in item
            assert "filename" in item
            assert "path" in item
            assert isinstance(item["path"], Path)

    def test_name_format(self):
        """Test that name is 'agent/filename' format."""
        result = get_available_agents()
        for item in result:
            expected = f"{item['agent']}/{item['filename']}"
            assert item["name"] == expected

    def test_matches_discover_output(self):
        """Test that get_available_agents matches discover_agent_instructions output."""
        discover_result = discover_agent_instructions()
        available_result = get_available_agents()

        assert len(discover_result) == len(available_result)
        for disc, avail in zip(discover_result, available_result):
            assert disc.agent_name == avail["agent"]
            assert disc.filename == avail["filename"]
            assert disc.full_path == avail["path"]