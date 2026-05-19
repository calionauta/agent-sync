from __future__ import annotations


"""Agent source discovery for publishing."""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt

from .config import get_published_repo, load_config, save_selected_skills
from .tui import MultiSelectTUI, SourceInfo
from ..agent_discovery import AgentInstructionFile, discover_agent_instructions


console = Console()


def _confirm(prompt: str, default_yes: bool = True) -> bool:
    """Ask a confirmation question with Y as default."""
    default_char = "Y" if default_yes else "n"
    choices = ["Y", "n"] if default_yes else ["y", "N"]
    
    result = Prompt.ask(
        prompt,
        choices=choices,
        default=default_char,
        show_default=False,
    )
    return result.upper() == "Y"


@dataclass
class AgentSource:
    """Represents a discovered agent instruction file."""
    name: str  # e.g., "pi.dev", "gemini-cli"
    filename: str  # e.g., "AGENTS.md"
    path: str  # Full path as string


class AgentSourceStatus(Enum):
    """Status of an agent source."""
    ACTIVE = "active"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


def discover_local_agents() -> list[AgentSource]:
    """Discover agent instruction files from local config directories.
    
    Returns:
        List of AgentSource objects for all found agent instruction files.
    """
    results: list[AgentSource] = []
    
    agent_files = discover_agent_instructions()
    
    for agent_file in agent_files:
        if agent_file.exists:
            results.append(AgentSource(
                name=agent_file.agent_name,
                filename=agent_file.filename,
                path=str(agent_file.full_path),
            ))
    
    return results


def get_local_agent_status() -> AgentSourceStatus:
    """Check if any agent instruction files exist."""
    agents = discover_local_agents()
    return AgentSourceStatus.ACTIVE if agents else AgentSourceStatus.UNKNOWN


# =============================================================================
# AGENTS PUBLISH FLOW (uses same TUI as skills)
# =============================================================================

def run_agents_publish_flow() -> bool:
    """Main publish flow for agents using the reusable TUI."""
    
    config = load_config()
    published_repo = get_published_repo()
    
    if not published_repo:
        console.print("[red]✗ Published repo not configured![/]")
        console.print("[dim]Run: agent-sync publish --repo https://github.com/user/repo[/]")
        return False
    
    console.print("\n[blue]🔍 Discovering agents...[/]")
    
    # Discover agents
    agents = discover_local_agents()
    
    if not agents:
        console.print("[yellow]⚠ No agent instruction files found![/]")
        return False
    
    # Build source info (single source: local agents)
    source_infos = [
        SourceInfo(
            source_id="agents",
            label="AGENTS",
            subtitle="~/.pi/agent/",
            items=[a.name for a in agents],  # Will be sorted in TUI
            status="active",
            extra="",
        )
    ]
    
    # Initial selection from config (if saved)
    initial_selection = config.selected_skills.get("agents", {})
    
    # Calculate range
    total_count = len(agents)
    footer_commands = [
        (f"1-{total_count}", "select"),
        ("all", "select all"),
        ("none", "clear"),
        ("publish", "publish"),
        ("quit", "exit"),
    ]
    
    # Create callback for publish
    def on_publish_callback(selection: dict[str, list[str]]) -> Optional[dict[str, list[str]]]:
        # Save selection to config
        save_selected_skills(selection)
        total = sum(len(v) for v in selection.values())
        if _confirm(f"\nPublish {total} agents to [green]{published_repo}[/]?"):
            if publish_agents(selection, published_repo):
                return selection
        return None
    
    # Create and run TUI
    tui = MultiSelectTUI(
        title="🤖 Agents Selection",
        footer_commands=footer_commands,
        on_publish=on_publish_callback,
    )
    result = tui.run(source_infos, {"agents": initial_selection} if initial_selection else None)
    
    if not result:
        console.print("\n[yellow]Publishing cancelled.[/]")
    
    return bool(result)


def publish_agents(
    selected: dict[str, list[str]],
    published_repo: str,
) -> bool:
    """Publish selected agents to the target repository."""
    import subprocess
    
    agents_to_publish = selected.get("agents", [])
    
    if not agents_to_publish:
        console.print("[yellow]⚠ No agents selected to publish[/]")
        return False
    
    # Find agent paths
    all_agents = {a.name: a for a in discover_local_agents()}
    
    # Create temp directory
    tmp_dir = Path(tempfile.mkdtemp(prefix="agent-sync-agents-"))
    try:
        agents_dir = tmp_dir / "agents"
        agents_dir.mkdir(parents=True)
        
        for agent_name in agents_to_publish:
            agent = all_agents.get(agent_name)
            if agent:
                dest = agents_dir / f"{agent_name}.md"
                shutil.copy2(Path(agent.path), dest)
        
        # Git operations
        subprocess.run(["git", "init"], cwd=tmp_dir, capture_output=True, timeout=10)
        subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_dir, capture_output=True, timeout=10)
        subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True, timeout=30)
        subprocess.run(
            ["git", "commit", "-m", f"feat: publish {len(agents_to_publish)} agents"],
            cwd=tmp_dir,
            capture_output=True,
            timeout=30,
        )
        
        subprocess.run(
            ["git", "remote", "add", "origin", published_repo],
            cwd=tmp_dir,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "main", "--force"],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            timeout=120,
        )
        
        console.print(f"\n[green]✓ Published {len(agents_to_publish)} agents![/]")
        return True
        
    except Exception as e:
        console.print(f"\n[red]✗ Error publishing agents: {e}[/]")
        return False
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)