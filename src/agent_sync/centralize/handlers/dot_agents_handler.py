"""DotAgents Protocol handler for agent-sync.

Integrates the .agents/ directory convention (https://dotagentsprotocol.com/)
with agent-sync's centralize workflow.

The .agents/ directory (global: ~/.agents/) is the canonical location for:
- skills/ — skill definitions
- agents/ — sub-agent profiles
- mcp.json — MCP server config
- config.json — model and agent defaults

Supports fmt:.agents for path normalization.
"""

from pathlib import Path

from rich.console import Console

console = Console()

DOTAGENTS_GLOBAL = Path.home() / ".agents"


class DotAgentsHandler:
    """Handles .agents/ directory structure alignment and path formatting."""

    def __init__(self, dotagents_path: Path = DOTAGENTS_GLOBAL):
        self.dotagents_path = dotagents_path

    def fmt(self, path: Path | str) -> str:
        """Format a path as .agents/ relative (fmt:.agents).

        Examples:
            fmt(~/.agents/skills/my-skill) -> .agents/skills/my-skill
            fmt(/etc/some/path) -> /etc/some/path (unchanged)
        """
        p = Path(path).expanduser().resolve()
        try:
            rel = p.relative_to(self.dotagents_path.resolve())
            return f".agents/{rel}"
        except (ValueError, FileNotFoundError):
            return str(p)

    def ensure_structure(self, dry_run: bool = False) -> bool:
        """Ensure ~/.agents/ has the DotAgents-compatible structure.

        Creates placeholder directories if they don't exist.
        Returns True if any directories were created.
        """
        created = False
        subdirs = ["skills", "agents"]

        for sub in subdirs:
            d = self.dotagents_path / sub
            if not d.exists():
                if not dry_run:
                    d.mkdir(parents=True, exist_ok=True)
                console.print(f"  [green]✓ Created {self.fmt(d)}[/]")
                created = True

        if not self.dotagents_path.exists():
            if not dry_run:
                self.dotagents_path.mkdir(parents=True, exist_ok=True)
            console.print(f"  [green]✓ Created {self.fmt(self.dotagents_path)}[/]")
            created = True

        return created

    def list_subdirs(self) -> list[Path]:
        """List all .agents/ subdirectories (skills, agents, etc.)."""
        if not self.dotagents_path.exists():
            return []
        return [p for p in self.dotagents_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
