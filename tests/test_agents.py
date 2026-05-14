"""Tests for agent-sync agent integrations based on YAML registry."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent_sync.agents import (
    get_agents,
    get_all_agents,
    get_agent,
    BaseAgent,
)


class TestAgentIntegrations:
    """Test agent integrations."""

    def test_get_all_agents_includes_internal(self):
        """Test get_all_agents includes internal entries like global-skills."""
        agents = get_all_agents()
        
        # 9 real agents + 1 internal (global-skills) = 10
        assert len(agents) == 10
        names = [a.name for a in agents]
        assert "global-skills" in names

    def test_get_agents_excludes_internal(self):
        """Test get_agents excludes internal entries."""
        agents = get_agents()
        
        # Only real agents: opencode, claude-code, gemini-cli, pi.dev, qwen-code,
        # roocode, cline, cursor, windsurf = 9
        assert len(agents) == 9
        agent_names = [a.name for a in agents]

        # CLI agents
        assert "opencode" in agent_names
        assert "claude-code" in agent_names
        assert "gemini-cli" in agent_names
        assert "pi.dev" in agent_names
        assert "qwen-code" in agent_names
        
        # VS Code Extensions & IDEs
        assert "roocode" in agent_names
        assert "cline" in agent_names
        assert "cursor" in agent_names
        assert "windsurf" in agent_names
        
        # Internal should NOT be in the list
        assert "global-skills" not in agent_names


    def test_get_agent_by_name(self):
        """Test getting specific agent by name."""
        agent = get_agent("opencode")
        assert agent is not None
        assert agent.name == "opencode"

        agent = get_agent("claude-code")
        assert agent is not None
        assert agent.name == "claude-code"

        # VS Code/IDE agents
        agent = get_agent("roocode")
        assert agent is not None
        assert agent.name == "roocode"
        
        agent = get_agent("cline")
        assert agent is not None
        assert agent.name == "cline"
        
        agent = get_agent("cursor")
        assert agent is not None
        assert agent.name == "cursor"
        
        agent = get_agent("windsurf")
        assert agent is not None
        assert agent.name == "windsurf"

        # Non-existent agent
        agent = get_agent("nonexistent")
        assert agent is None
    
    def test_opencode_agent(self, tmp_path):
        """Test Opencode agent integration."""
        agent = get_agent("opencode")
        agent.config_dir = tmp_path
        
        assert agent.name == "opencode"
        assert "opencode" in str(agent.config_path)
        assert "skills" in str(agent.skills_path)
    
    def test_claude_code_agent(self, tmp_path):
        """Test Claude Code agent integration."""
        agent = get_agent("claude-code")
        agent.config_dir = tmp_path
        
        assert agent.name == "claude-code"
        assert "settings.json" in str(agent.config_path)
        assert "commands" in str(agent.skills_path)
    
    def test_gemini_cli_agent(self, tmp_path):
        """Test Gemini CLI agent integration."""
        agent = get_agent("gemini-cli")
        agent.config_dir = tmp_path
        
        assert agent.name == "gemini-cli"
        assert "settings.json" in str(agent.config_path)
        assert "tools" in str(agent.skills_path)
    
    def test_pi_dev_agent(self, tmp_path):
        """Test Pi.dev agent integration."""
        agent = get_agent("pi.dev")
        agent.config_dir = tmp_path
        
        assert agent.name == "pi.dev"
        assert "settings.json" in str(agent.config_path)
        assert "skills" in str(agent.skills_path)
    
    def test_qwen_code_agent(self, tmp_path):
        """Test Qwen Code agent integration."""
        agent = get_agent("qwen-code")
        agent.config_dir = tmp_path
        
        assert agent.name == "qwen-code"
        assert "settings.json" in str(agent.config_path)
        assert "skills" in str(agent.skills_path)
    
    def test_agent_config_path_structure(self, tmp_path):
        """Test agent config path structure."""
        agent = BaseAgent("test-agent", {
            "method": "copy",
            "config_dir": str(tmp_path),
            "config_filename": "config.json",
            "skills_dir_name": "skills",
            "check": {"binary": "test"}
        })
        
        expected_config = tmp_path / "config.json"
        expected_skills = tmp_path / "skills"

        assert agent.config_path == expected_config
        assert agent.skills_path == expected_skills

    def test_agent_repr(self):
        """Test agent string representation."""
        agent = get_agent("opencode")
        repr_str = repr(agent)

        assert "BaseAgent" in repr_str
        assert "opencode" in repr_str


class TestVSCodeAgents:
    """Test VS Code Extensions & IDE agents."""

    def test_roocode_agent(self, tmp_path):
        """Test RooCode agent integration."""
        agent = get_agent("roocode")
        agent.config_dir = tmp_path

        assert agent.name == "roocode"
        assert agent.method == "native"
        assert "custom_modes.yaml" in str(agent.config_path)
        assert "skills" in str(agent.skills_path)
        
        # RooCode supports mode-specific skills
        if hasattr(agent, "supports_mode_specific"):
            assert agent.supports_mode_specific()

    def test_cline_agent(self, tmp_path):
        """Test Cline agent integration."""
        agent = get_agent("cline")
        agent.config_dir = tmp_path

        assert agent.name == "cline"
        assert agent.method == "copy"
        assert "state.json" in str(agent.config_path)
        
        # Cline copies FROM project skills TO global hub
        if hasattr(agent, "copy_from"):
            # copy_from is a list of source paths
            assert isinstance(agent.copy_from, list)
            assert ".cline/skills/" in str(agent.copy_from)
        if hasattr(agent, "copy_to"):
            # copy_to is the hub destination
            assert "agents/skills" in str(agent.copy_to)

    def test_cursor_agent(self, tmp_path):
        """Test Cursor agent integration."""
        agent = get_agent("cursor")
        agent.config_dir = tmp_path

        assert agent.name == "cursor"
        assert agent.method == "native"
        assert "settings.json" in str(agent.config_path)
        
        # Cursor has native support and migrate_from paths
        if hasattr(agent, "migrate_from"):
            assert isinstance(agent.migrate_from, list)
            assert ".cursor/skills/" in str(agent.migrate_from)

    def test_windsurf_agent(self, tmp_path):
        """Test Windsurf agent integration."""
        agent = get_agent("windsurf")
        agent.config_dir = tmp_path

        assert agent.name == "windsurf"
        assert agent.method == "copy"
        assert "config.json" in str(agent.config_path)
        
        # Windsurf copies FROM project/global skills TO hub
        if hasattr(agent, "copy_from"):
            # copy_from is a list of source paths
            assert isinstance(agent.copy_from, list)
        if hasattr(agent, "copy_to"):
            # copy_to is the hub destination
            assert "agents/skills" in str(agent.copy_to)
