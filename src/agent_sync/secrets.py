"""Secrets management for agent-sync."""

from pathlib import Path

from dotenv import load_dotenv


class SecretsManager:
    """Manages secrets and environment variables for agent-sync."""

    # Common secret file paths by agent
    SECRET_PATHS = {
        "opencode": [
            Path.home() / ".local" / "share" / "opencode" / "auth.json",
            Path.home() / ".local" / "share" / "opencode" / "mcp-auth.json",
        ],
        "claude-code": [
            Path.home() / ".config" / "claude" / "auth.json",
        ],
        "gemini-cli": [
            Path.home() / ".config" / "gemini" / "credentials.json",
        ],
        "pi.dev": [
            Path.home() / ".config" / "pi" / "auth.json",
        ],
        "qwen-code": [
            Path.home() / ".config" / "qwen" / "auth.json",
        ],
    }

    # Environment file location
    ENV_FILE = Path.home() / ".config" / "agent-sync" / ".env"

    def __init__(self):
        self.env_file = self.ENV_FILE
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        load_dotenv(self.env_file)

    def enable(self, include_mcp: bool = False) -> None:
        """Enable secrets synchronization."""
        from .config import Config
        config = Config()
        config.include_secrets = True
        config.include_mcp_secrets = include_mcp

    def disable(self) -> None:
        """Disable secrets synchronization."""
        from .config import Config
        config = Config()
        config.include_secrets = False
        config.include_mcp_secrets = False

    def is_enabled(self) -> bool:
        """Check if secrets sync is enabled."""
        from .config import Config
        config = Config()
        return config.include_secrets

    def get_secret_paths(self, agent: str) -> list[Path]:
        """Get secret file paths for an agent."""
        return self.SECRET_PATHS.get(agent, [])
