"""Tests for agent-sync configuration management."""


from agent_sync.config import Config


class TestConfig:
    """Test configuration management."""

    def test_config_initialization(self, tmp_path):
        """Test config initializes with defaults."""
        config_file = tmp_path / "config.yaml"
        config = Config(config_path=config_file)

        assert config.repo_url is None
        assert config.agents == []
        assert config.include_secrets is False

    def test_config_save_and_load(self, tmp_path):
        """Test config persists correctly."""
        config_file = tmp_path / "config.yaml"
        config = Config(config_path=config_file)

        # Set values
        config.repo_url = "https://github.com/test/repo.git"
        config.agents = ["opencode", "claude-code"]
        config.include_secrets = True

        # Reload
        config2 = Config(config_path=config_file)

        assert config2.repo_url == "https://github.com/test/repo.git"
        assert config2.agents == ["opencode", "claude-code"]
        assert config2.include_secrets is True

    def test_config_overrides(self, tmp_path):
        """Test local overrides work correctly."""
        config_file = tmp_path / "config.yaml"
        overrides_file = tmp_path / "overrides.yaml"

        config = Config(config_path=config_file, overrides_path=overrides_file)

        # Set override
        config.set_override("machine_name", "test-machine")
        config.set_override("custom_path", "/tmp/test")

        # Reload and verify
        config2 = Config(config_path=config_file, overrides_path=overrides_file)

        assert config2.get_override("machine_name") == "test-machine"
        assert config2.get_override("custom_path") == "/tmp/test"
        assert config2.get_override("nonexistent", "default") == "default"

    def test_generate_default(self, tmp_path):
        """Test default config generation."""
        config_file = tmp_path / "config.yaml"
        config = Config(config_path=config_file)

        result_path = config.generate_default()

        assert result_path == config_file
        # Updated to include global-skills
        assert "global-skills" in config.agents
        assert "opencode" in config.agents
        assert len(config.agents) == 6
        assert config.include_secrets is False

    def test_generate_default_with_agents(self, tmp_path):
        """Test default config generation with specific agents."""
        config_file = tmp_path / "config.yaml"
        config = Config(config_path=config_file)

        config.generate_default(target_agents=["opencode", "qwen-code"])

        assert config.agents == ["opencode", "qwen-code"]

    def test_mcp_secrets_setting(self, tmp_path):
        """Test MCP secrets configuration."""
        config_file = tmp_path / "config.yaml"
        config = Config(config_path=config_file)

        config.include_mcp_secrets = True

        config2 = Config(config_path=config_file)
        assert config2.include_mcp_secrets is True

    def test_published_skills(self, tmp_path):
        """Test published_skills persistence."""
        config_file = tmp_path / "config.yaml"
        config = Config(config_path=config_file)

        skills = ["skill1", "skill2"]
        config.published_skills = skills

        config2 = Config(config_path=config_file)
        assert config2.published_skills == sorted(skills)
