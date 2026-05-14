"""MCP config merger for DotAgents compatibility."""
from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any

from rich.console import Console

console = Console()

# Known MCP config locations by vendor
KNOWN_MCP_LOCATIONS: dict[str, Path] = {
    "claude-code": Path.home() / ".claude" / "mcp.json",
    "cursor": Path.home() / ".cursor" / "mcp.json",
    "windsurf": Path.home() / ".codeium" / "windsurf" / "mcp.json",
}


@dataclass
class MCPServer:
    """Represents an MCP server definition."""
    name: str
    config: dict[str, Any]
    source: Path


@dataclass
class MCPConflict:
    """Represents a server name conflict."""
    server_name: str
    sources: list[Path] = field(default_factory=list)
    resolution: str = "first"  # first | manual


class MCPMerger:
    """Merge multiple MCP configs into unified format."""

    VERSION = "1.0"
    DEFAULT_OUTPUT = Path.home() / ".agents" / "mcp.json"

    def __init__(self, sources: list[Path] | None = None):
        self.sources = sources or []
        self.servers: dict[str, MCPServer] = {}
        self.conflicts: list[MCPConflict] = []
        self._raw_sources: list[Path] = []

    def find_mcp_configs(self) -> list[Path]:
        """Find MCP configs in known locations."""
        found = []
        for path in KNOWN_MCP_LOCATIONS.values():
            if path.exists():
                found.append(path)
        return found

    def merge(self, conflict_strategy: str = "first") -> dict:
        """Merge all MCP configs into unified format."""
        sources = self.sources if self.sources else self.find_mcp_configs()
        self._raw_sources = sources

        for source in sources:
            if not source.exists():
                continue
            try:
                data = json.loads(source.read_text())
                # Handle different JSON formats from vendors
                servers = data.get("mcpServers", data.get("servers", {}))
                for name, config in servers.items():
                    if name in self.servers:
                        existing = self.conflicts_by_name(name)
                        if not existing:
                            self.conflicts.append(MCPConflict(
                                server_name=name,
                                sources=[self.servers[name].source, source],
                                resolution=conflict_strategy,
                            ))
                        if conflict_strategy == "first":
                            continue  # Keep first, skip duplicates
                    self.servers[name] = MCPServer(
                        name=name,
                        config=config,
                        source=source,
                    )
            except (json.JSONDecodeError, OSError):
                pass

        return self._build_output()

    def conflicts_by_name(self, name: str) -> MCPConflict | None:
        """Find existing conflict by server name."""
        for c in self.conflicts:
            if c.server_name == name:
                return c
        return None

    def _build_output(self) -> dict:
        """Build output dictionary."""
        return {
            "version": self.VERSION,
            "generated_by": "agent-sync",
            "sources": [str(s) for s in self._raw_sources],
            "servers": {s.name: s.config for s in self.servers.values()},
            "conflicts": [
                {
                    "server": c.server_name,
                    "sources": [str(src) for src in c.sources],
                    "resolution": c.resolution,
                }
                for c in self.conflicts
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string."""
        return json.dumps(self.merge(), indent=indent)

    def save(self, path: Path) -> None:
        """Save to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())

    def get_conflict_report(self) -> str:
        """Generate a conflict report string."""
        if not self.conflicts:
            return "No conflicts detected."

        lines = ["[yellow]⚠ Conflicts detected:[/yellow]", ""]
        for c in self.conflicts:
            lines.append(f"  • {c.server_name}:")
            for src in c.sources:
                lines.append(f"    - {src}")
            lines.append(f"    resolution: {c.resolution}")
            lines.append("")
        return "\n".join(lines)