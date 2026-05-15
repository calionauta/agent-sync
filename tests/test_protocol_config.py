"""Tests for protocol support in Config."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_sync.cli import main


class TestProtocolConfig:
    """Tests for protocol configuration."""

    def test_config_show_protocols(self, tmp_path, monkeypatch):
        """Config show should display (or eventually display) protocol settings."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "show"])
        
        # Currently config show doesn't show protocols, but should not crash
        assert result.exit_code == 0
        # Config file path should be shown
        assert "config" in result.output.lower()

    def test_enable_gitagent_protocol(self, tmp_path, monkeypatch):
        """Should be able to enable gitagent protocol."""
        from agent_sync.config import Config
        
        config_path = tmp_path / "config.yaml"
        config = Config(config_path=config_path)
        config.repo_url = "https://github.com/test/repo.git"
        
        # Initially gitagent should not be enabled
        assert config.is_protocol_enabled("gitagent") is False
        
        # Enable it
        config.enable_protocol("gitagent")
        
        # Now should be enabled
        assert config.is_protocol_enabled("gitagent") is True

    def test_disable_gitagent_protocol(self, tmp_path, monkeypatch):
        """Should be able to disable gitagent protocol."""
        from agent_sync.config import Config
        
        config_path = tmp_path / "config.yaml"
        config = Config(config_path=config_path)
        config.repo_url = "https://github.com/test/repo.git"
        
        # Enable then disable
        config.enable_protocol("gitagent")
        assert config.is_protocol_enabled("gitagent") is True
        
        config.disable_protocol("gitagent")
        assert config.is_protocol_enabled("gitagent") is False

    def test_get_protocol_settings(self, tmp_path, monkeypatch):
        """Should retrieve protocol settings correctly."""
        from agent_sync.config import Config
        
        config_path = tmp_path / "config.yaml"
        config = Config(config_path=config_path)
        config.repo_url = "https://github.com/test/repo.git"
        
        # Get gitagent settings - should have defaults from generate_default
        gitagent = config.get_protocol_settings("gitagent")
        
        # Even without generate_default, should return empty dict (not crash)
        assert isinstance(gitagent, dict)
        
        # After generate_default, should have patterns
        config.generate_default()
        gitagent = config.get_protocol_settings("gitagent")
        patterns = gitagent.get("patterns", [])
        
        assert "agent.yaml" in patterns
        assert "SOUL.md" in patterns

    def test_generate_default_includes_protocols(self, tmp_path, monkeypatch):
        """Generate default should include protocol settings."""
        from agent_sync.config import Config
        
        config_path = tmp_path / "config.yaml"
        config = Config(config_path=config_path)
        config.generate_default()
        
        # Check protocols are in config
        assert "protocols" in config._config
        assert "dotagents" in config._config["protocols"]
        assert "gitagent" in config._config["protocols"]
        
        # DotAgents should be enabled by default
        assert config.is_protocol_enabled("dotagents") is True
        
        # GitAgent should be disabled by default
        assert config.is_protocol_enabled("gitagent") is False

    def test_gitagent_patterns_in_defaults(self, tmp_path, monkeypatch):
        """Default gitagent patterns should include key files."""
        from agent_sync.config import Config
        
        config_path = tmp_path / "config.yaml"
        config = Config(config_path=config_path)
        config.generate_default()
        
        gitagent = config.get_protocol_settings("gitagent")
        patterns = gitagent.get("patterns", [])
        
        expected_patterns = [
            "agent.yaml",
            "SOUL.md",
            "RULES.md",
            "DUTIES.md",
            "AGENTS.md"
        ]
        
        for pattern in expected_patterns:
            assert pattern in patterns, f"{pattern} should be in gitagent patterns"