"""Export agent-sync config to DotAgents JSON format."""
import json
from datetime import datetime, timezone
from pathlib import Path

from agent_sync.agents import get_agents
from agent_sync.config import Config
from agent_sync.paths import HUB_DIR


class ConfigExporter:
    """Export configuration to DotAgents-compatible JSON."""

    VERSION = "1.0"

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.registry: dict = {}
        self._agents: list = []

    def load(self) -> None:
        """Load registry and agents data."""
        from agent_sync.agents.registry_loader import load_registry
        self.registry = load_registry()
        self._agents = get_agents()

    def export(self) -> dict:
        """Export to DotAgents config format."""
        self.load()

        return {
            "version": self.VERSION,
            "generated_by": "agent-sync",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "skills_hub": str(HUB_DIR),
            "model": {},
            "agents": self._export_agents(),
            "sync": self._export_sync(),
        }

    def _export_agents(self) -> dict:
        """Export agent configurations."""
        agents = {}
        for agent in self._agents:
            if agent.name in ("global-skills",):
                continue
            agents[agent.name] = {
                "enabled": agent.enabled,
                "method": agent.method,
                "skills_dir": str(agent.skills_path),
            }
        return agents

    def _export_sync(self) -> dict:
        """Export sync configuration."""
        return {
            "method": "git",
            "repo_url": self.config.repo_url or "",
        }

    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string."""
        return json.dumps(self.export(), indent=indent)

    def save(self, path: Path) -> None:
        """Save to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())
