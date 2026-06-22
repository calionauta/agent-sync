"""Tests for agents source discovery and publish."""

import pytest

from agent_sync.publish.agents_source import (
    AgentSource,
    AgentSourceStatus,
    discover_local_agents,
    get_local_agent_status,
)


class TestAgentSource:
    """Tests for AgentSource dataclass."""

    def test_creates_agent_source(self):
        """AgentSource stores agent info."""
        from pathlib import Path

        agent = AgentSource(
            name="pi.dev",
            filename="AGENTS.md",
            path=str(Path.home() / ".pi" / "agent" / "AGENTS.md"),
        )

        assert agent.name == "pi.dev"
        assert agent.filename == "AGENTS.md"
        assert ".pi" in agent.path


class TestAgentSourceStatus:
    """Tests for AgentSourceStatus enum."""

    def test_status_values(self):
        """All expected status values exist."""
        assert AgentSourceStatus.ACTIVE.value == "active"
        assert AgentSourceStatus.FAILED.value == "failed"
        assert AgentSourceStatus.SKIPPED.value == "skipped"
        assert AgentSourceStatus.UNKNOWN.value == "unknown"


class TestDiscoverLocalAgents:
    """Tests for discover_local_agents()."""

    def test_returns_list(self):
        """Returns a list (may be empty)."""
        agents = discover_local_agents()
        assert isinstance(agents, list)

    def test_agent_items_have_required_fields(self):
        """Each agent has required fields."""
        agents = discover_local_agents()
        
        for agent in agents:
            assert hasattr(agent, 'name')
            assert hasattr(agent, 'filename')
            assert hasattr(agent, 'path')
            assert isinstance(agent.name, str)
            assert isinstance(agent.filename, str)
            assert isinstance(agent.path, str)

    def test_agent_names_are_valid(self):
        """Agent names follow expected format."""
        agents = discover_local_agents()
        
        for agent in agents:
            # Names should be lowercase with hyphens or dots
            assert agent.name.replace('-', '').replace('.', '').isalnum() or '.' in agent.name


class TestGetLocalAgentStatus:
    """Tests for get_local_agent_status()."""

    def test_returns_status(self):
        """Returns a valid AgentSourceStatus."""
        status = get_local_agent_status()
        assert isinstance(status, AgentSourceStatus)