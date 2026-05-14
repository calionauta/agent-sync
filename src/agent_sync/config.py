"""Configuration management for agent-sync."""

from pathlib import Path

import yaml
from platformdirs import user_config_dir, user_data_dir

# Cross-platform directories
# Linux: ~/.config/agent-sync, ~/.local/share/agent-sync
# macOS: ~/Library/Application Support/agent-sync
# Windows: ~\AppData\Roaming\agent-sync
DEFAULT_CONFIG_DIR = Path(user_config_dir("agent-sync", "renatocaliari"))
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
# State files (last sync, update check) in data dir
DEFAULT_STATE_DIR = Path(user_data_dir("agent-sync", "renatocaliari"))
DEFAULT_OVERRIDES_FILE = DEFAULT_CONFIG_DIR / "overrides.yaml"


class Config:
    """Manages agent-sync configuration."""

    def __init__(self, config_path: Path | None = None, overrides_path: Path | None = None):
        self.config_path = config_path or DEFAULT_CONFIG_FILE
        self._overrides_path = overrides_path or DEFAULT_OVERRIDES_FILE
        self._config: dict = {}
        self._overrides: dict = {}
        self.load()

    @property
    def overrides_path(self) -> Path:
        """Get the overrides file path."""
        return self._overrides_path

    @overrides_path.setter
    def overrides_path(self, path: Path) -> None:
        """Set the overrides file path and reload."""
        self._overrides_path = Path(path)
        self.load()

    def load(self) -> None:
        """Load configuration from files."""
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load main config
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._config = yaml.safe_load(f) or {}

        # Load overrides (local-only, not synced)
        if self.overrides_path.exists():
            with open(self.overrides_path) as f:
                self._overrides = yaml.safe_load(f) or {}

    def save(self) -> None:
        """Save configuration to file with help header."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        header = (
            "# agent-sync - User Configuration\n"
            "# -------------------------------\n"
            "# repo_url: Your GitHub configs repository (private recommended)\n"
            "# agents: List of agents enabled for sync\n"
            "# agents_config:\n"
            "#   <agent-name>:\n"
            "#     skills_method: native | config | copy\n"
            "#       - native: Agent reads from ~/.agents/skills/\n"
            "#       - config: Updates agent's own JSON config with global path\n"
            "#       - copy:   Copies skills to agent folder (fallback)\n"
            "# published_skills: List of skill names to include when running 'skills publish'\n"
            "# -------------------------------\n\n"
        )

        with open(self.config_path, "w") as f:
            f.write(header)
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)

    @property
    def published_skills(self) -> list[str]:
        """Get list of skills whitelisted for public publishing."""
        return self._config.get("published_skills", [])

    @published_skills.setter
    def published_skills(self, skills: list[str]) -> None:
        """Set list of skills whitelisted for public publishing."""
        self._config["published_skills"] = sorted(list(set(skills)))
        self.save()

    def save_overrides(self) -> None:
        """Save local overrides (not synced)."""
        self.overrides_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.overrides_path, "w") as f:
            yaml.dump(self._overrides, f, default_flow_style=False, sort_keys=False)

    @property
    def repo_url(self) -> str | None:
        """Get the sync repository URL."""
        return self._config.get("repo_url")

    @repo_url.setter
    def repo_url(self, url: str) -> None:
        """Set the sync repository URL."""
        self._config["repo_url"] = url
        self.save()

    @property
    def agents(self) -> list[str]:
        """Get list of enabled agents."""
        return self._config.get("agents", [])

    @agents.setter
    def agents(self, agents: list[str]) -> None:
        """Set enabled agents."""
        self._config["agents"] = agents
        self.save()

    def get_agent_config(self, agent_name: str) -> dict:
        """Get configuration for a specific agent."""
        agents_config = self._config.get("agents_config", {})
        return agents_config.get(agent_name, {})

    def set_agent_config(self, agent_name: str, config: dict) -> None:
        """Set configuration for a specific agent."""
        if "agents_config" not in self._config:
            self._config["agents_config"] = {}

        self._config["agents_config"][agent_name] = config
        self.save()

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if sync is enabled for a specific agent."""
        agent_config = self.get_agent_config(agent_name)
        return agent_config.get("enabled", True)

    def enable_agent(self, agent_name: str) -> None:
        """Enable sync for a specific agent."""
        agent_config = self.get_agent_config(agent_name)
        agent_config["enabled"] = True
        self.set_agent_config(agent_name, agent_config)

    def disable_agent(self, agent_name: str) -> None:
        """Disable sync for a specific agent."""
        agent_config = self.get_agent_config(agent_name)
        agent_config["enabled"] = False
        self.set_agent_config(agent_name, agent_config)

    def get_sync_options(self, agent_name: str) -> dict:
        """Get sync options for a specific agent.

        Returns dict with:
        - configs: bool - Sync config files (default: true)
        - all_files: bool - Sync all files in agent directory (default: false)
        - paths: list[str] - Specific paths/patterns to sync (default: None)
        - exclude: list[str] - Patterns to exclude (default: [])
        """
        agent_config = self.get_agent_config(agent_name)
        sync_config = agent_config.get("sync", {})

        # Return with defaults
        return {
            "configs": sync_config.get("configs", True),
            "all_files": sync_config.get("all_files", False),
            "paths": sync_config.get("paths"),
            "exclude": sync_config.get("exclude", []),
        }

    def get_skills_method(self, agent_name: str) -> str | None:
        """Get skills sync method for a specific agent."""
        agent_config = self.get_agent_config(agent_name)
        return agent_config.get("skills_method")

    def set_skills_method(self, agent_name: str, method: str) -> None:
        """Set skills sync method for a specific agent."""
        agent_config = self.get_agent_config(agent_name)
        agent_config["skills_method"] = method
        self.set_agent_config(agent_name, agent_config)

    @property
    def include_secrets(self) -> bool:
        """Check if secrets sync is enabled."""
        return self._config.get("include_secrets", False)

    @include_secrets.setter
    def include_secrets(self, value: bool) -> None:
        """Enable/disable secrets sync."""
        self._config["include_secrets"] = value
        self.save()

    @property
    def include_mcp_secrets(self) -> bool:
        """Check if MCP secrets sync is enabled."""
        return self._config.get("include_mcp_secrets", False)

    @include_mcp_secrets.setter
    def include_mcp_secrets(self, value: bool) -> None:
        """Enable/disable MCP secrets sync."""
        self._config["include_mcp_secrets"] = value
        self.save()

    def get_override(self, key: str, default=None):
        """Get a local override value."""
        return self._overrides.get(key, default)

    def set_override(self, key: str, value) -> None:
        """Set a local override (not synced)."""
        self._overrides[key] = value
        self.save_overrides()

    def generate_default(self, target_agents: list[str] | None = None) -> Path:
        """Generate a default configuration file.

        Preserves existing repo_url if already configured.
        """
        # Preserve existing repo_url if it exists
        existing_repo_url = self._config.get("repo_url")

        default_agents = target_agents or [
            "opencode",
            "claude-code",
            "gemini-cli",
            "pi.dev",
            "qwen-code",
            "global-skills",
        ]

        default_config = {
            "repo_url": existing_repo_url,  # Preserve existing repo URL
            "agents": default_agents,
            "agents_config": {
                agent: {
                    "enabled": True,
                    "sync": {
                        "configs": True,
                        # skills: sempre true (global skills)
                    }
                }
                for agent in default_agents
            },
            "include_secrets": False,
            "include_mcp_secrets": False,
            # global_skills: sempre true (implícito)
        }

        self._config = default_config
        self.save()
        return self.config_path


