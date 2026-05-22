"""Configuration management for agent-sync."""


from pathlib import Path

import yaml
from platformdirs import user_config_dir, user_data_dir


def _get_app_name() -> str:
    """Get app name from package metadata (or fallback)."""
    try:
        from importlib.metadata import version
        return version("agent-sync").split(".")[0]
    except Exception:
        return "agent-sync"


APP_NAME = "agent-sync"

# Cross-platform directories (generic, not hardcoded)
DEFAULT_CONFIG_DIR = Path(user_config_dir(APP_NAME, APP_NAME))
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_STATE_DIR = Path(user_data_dir(APP_NAME, APP_NAME))
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
                loaded = yaml.safe_load(f)
                self._config = loaded if isinstance(loaded, dict) else {}

        # Load overrides (local-only, not synced)
        if self.overrides_path.exists():
            with open(self.overrides_path) as f:
                loaded = yaml.safe_load(f)
                self._overrides = loaded if isinstance(loaded, dict) else {}

        # Ensure protocols section is always initialized from defaults if not present
        self._init_protocols_defaults()

    def _init_protocols_defaults(self) -> None:
        """Ensure protocols section has defaults (for migrating existing configs)."""
        defaults = self._init_protocols_default()
        if "protocols" not in self._config:
            self._config["protocols"] = {}
        # Merge each protocol's defaults
        for proto_name, proto_defaults in defaults.items():
            if proto_name not in self._config["protocols"]:
                self._config["protocols"][proto_name] = proto_defaults
            else:
                # Merge individual keys
                for key, value in proto_defaults.items():
                    if key not in self._config["protocols"][proto_name]:
                        self._config["protocols"][proto_name][key] = value

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

    @property
    def published_agents(self) -> list[str]:
        """Get list of agent instruction files whitelisted for public publishing.
        
        Format: ["agent:filename", ...]
        e.g., ["pi.dev:AGENTS.md", "gemini-cli:GEMINI.md"]
        """
        return self._config.get("published_agents", [])

    @published_agents.setter
    def published_agents(self, items: list[str]) -> None:
        """Set list of agent instruction files for public publishing."""
        self._config["published_agents"] = sorted(list(set(items)))
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
        agents_config = self._config.get("agents_config")
        if not isinstance(agents_config, dict):
            agents_config = {}
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

    def get_sync_mode(self, agent_name: str) -> str:
        """Get sync mode for a specific agent.


        Values:
        - 'installed': Only sync if agent is installed (is_available=True)
        - 'always': Always sync regardless of installation status
        """
        agent_config = self.get_agent_config(agent_name)
        return agent_config.get("sync_mode", "installed")


    def set_sync_mode(self, agent_name: str, mode: str) -> None:
        """"Set sync mode for a specific agent."""
        if mode not in ("installed", "always"):
            raise ValueError("sync_mode must be 'installed' or 'always'")
        agent_config = self.get_agent_config(agent_name)
        agent_config["sync_mode"] = mode
        self.set_agent_config(agent_name, agent_config)
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
            # Protocol support (opt-in)
            "protocols": self._init_protocols_default()
        }

        self._config = default_config
        self.save()
        return self.config_path

    def _init_protocols_default(self) -> dict:
        """Get default protocols configuration."""
        return {
            "dotagents": {
                "enabled": True,
                "skills_hub": "~/.agents/skills/"
            },
            "gitagent": {
                "enabled": False,
                "patterns": [
                    "agent.yaml", "SOUL.md", "RULES.md", "DUTIES.md",
                    "AGENTS.md", "skills/", "knowledge/", "memory/",
                    "hooks/", "workflows/", "tools/", "compliance/"
                ]
            }
        }

    def get_protocol_settings(self, protocol: str) -> dict:
        """Get settings for a specific protocol.

        Args:
            protocol: Protocol name ("dotagents" or "gitagent")

        Returns:
            dict with protocol settings, or empty dict if not configured
        """
        protocols = self._config.get("protocols", {})
        return protocols.get(protocol, {})

    def is_protocol_enabled(self, protocol: str) -> bool:
        """Check if a protocol is enabled.

        Args:
            protocol: Protocol name ("dotagents" or "gitagent")

        Returns:
            True if protocol is enabled, False otherwise
        """
        protocol_settings = self.get_protocol_settings(protocol)
        return protocol_settings.get("enabled", False)

    def enable_protocol(self, protocol: str) -> None:
        """Enable a protocol for sync.

        Args:
            protocol: Protocol name ("dotagents" or "gitagent")
        """
        if "protocols" not in self._config:
            self._config["protocols"] = {}

        if protocol not in self._config["protocols"]:
            self._config["protocols"][protocol] = {}

        self._config["protocols"][protocol]["enabled"] = True
        self.save()

    def disable_protocol(self, protocol: str) -> None:
        """Disable a protocol for sync.

        Args:
            protocol: Protocol name ("dotagents" or "gitagent")
        """
        protocol_settings = self.get_protocol_settings(protocol)
        if protocol_settings:
            protocol_settings["enabled"] = False
            self._config["protocols"][protocol] = protocol_settings
            self.save()


