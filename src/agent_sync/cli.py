"""CLI commands for agent-sync."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import __version__
from .agents import load_registry
from .config import Config
from .publish import (
    add_source,
    clear_cache as clear_publish_cache,
    get_published_repo,
    list_sources,
    load_config as load_publish_config,
    remove_source,
    run_publish_setup,
    save_selected_skills,
    set_published_repo,
)
from .sync import SyncManager
from .validators import validate_github_url


console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """agent-sync - Sync configs and skills across multiple AI agents."""
    pass


# =============================================================================
# INIT COMMAND
# =============================================================================

@main.command()
@click.option("--name", "name", help="Repository name")
@click.option("--agents", multiple=True, help="Agents to sync")
@click.option("--no-wizard", is_flag=True, help="Skip interactive prompts")
@click.option("--force", is_flag=True, help="Force overwrite existing config")
def init(name: Optional[str], agents: tuple[str, ...], no_wizard: bool, force: bool):
    """Initialize agent-sync in the current directory."""
    config = Config()
    sync_manager = SyncManager(config)
    
    # Check if already initialized
    if sync_manager.is_initialized() and not force:
        console.print("[yellow]⚠ Already initialized. Use --force to reinitialize.[/yellow]")
        return
    
    if not no_wizard:
        console.print("\n[bold cyan]agent-sync Initializer[/bold cyan]\n")
        console.print("This will create a .sync/ directory with your agent configurations.\n")
    
    # Get agents to sync
    if not agents:
        console.print("[cyan]Available agents:[/cyan]")
        console.print("  • opencode - RooCode extension")
        console.print("  • claude-code - Claude Code")
        console.print("  • gemini-cli - Gemini CLI")
        console.print("  • pi.dev - Pi.dev")
        console.print("  • qwen-code - Qwen Code\n")
        
        agents_input = Prompt.ask(
            "\n[cyan]Which agents?[/cyan] (comma-separated)",
            default="all",
        )
        
        if agents_input.lower() == "all":
            agents = ("opencode", "claude-code", "gemini-cli", "pi.dev", "qwen-code")
        else:
            agents = tuple(a.strip() for a in agents_input.split(","))
    
    private = not no_wizard and Confirm.ask("Create private repository?", default=False)
    
    if no_wizard:
        repo_name = name or "agent-sync"
    else:
        repo_name = name or Prompt.ask("Repository name", default="agent-sync")
    
    success = sync_manager.init_repo(name=repo_name, private=private, agents=agents)
    
    if success:
        console.print("\n[green]✓ Initialized![/green]")
        console.print(f"   Commit and push the [.sync/] directory to start syncing.")
    else:
        console.print("\n[red]✗ Failed to initialize.[/red]")


# =============================================================================
# SYNC COMMAND
# =============================================================================

@main.command()
@click.option("--force", is_flag=True, help="Force pull even if up to date")
@click.option("--skills-only", is_flag=True, help="Only sync skills")
@click.option("--configs-only", is_flag=True, help="Only sync configs")
@click.option("--agents-only", is_flag=True, help="Only sync agent configs")
def sync(force: bool, skills_only: bool, configs_only: bool, agents_only: bool):
    """Sync skills and configs with the remote repository."""
    config = Config()
    sync_manager = SyncManager(config)
    
    if not config.repo_url:
        console.print("[red]✗ Not initialized. Run 'agent-sync init' first.[/red]")
        return
    
    # Determine what to sync
    do_skills = skills_only or (not configs_only and not agents_only)
    do_configs = configs_only or (not skills_only and not agents_only)
    do_agents = agents_only
    
    if not (do_skills or do_configs or do_agents):
        do_skills = do_configs = do_agents = True
    
    console.print("\n[cyan]Syncing...[/cyan]\n")
    
    success = sync_manager.sync(
        force=force,
        skills=do_skills,
        configs=do_configs,
        agents=do_agents,
    )
    
    if success:
        console.print("\n[green]✓ Synced![/green]")
    else:
        console.print("\n[yellow]⚠ Sync completed with warnings.[/yellow]")


# =============================================================================
# PUSH COMMAND
# =============================================================================

@main.command()
@click.option("--message", "-m", default=None, help="Commit message")
@click.option("--skills-only", is_flag=True, help="Only push skills")
@click.option("--configs-only", is_flag=True, help="Only push configs")
def push(message: Optional[str], skills_only: bool, configs_only: bool):
    """Push local changes to the remote repository."""
    
    config = Config()
    
    if not config.repo_url:
        console.print("[red]✗ Not initialized. Run 'agent-sync init' first.[/red]")
        return
    
    sync_manager = SyncManager(config)
    
    commit_msg = message or "chore: sync config updates"
    
    # Default: push both (unless explicit --skills-only or --configs-only)
    do_skills = not configs_only  # True unless --configs-only
    do_configs = not skills_only  # True unless --skills-only
    # If neither flag, do both
    if not skills_only and not configs_only:
        do_skills = True
        do_configs = True
    
    success = sync_manager.push(message=commit_msg, skills_only=do_skills, configs_only=do_configs)
    
    if success is not False:  # Success if not explicitly False (empty list is success)
        console.print("\n[green]✓ Pushed![/green]")
    else:
        console.print("\n[red]✗ Push failed.[/red]")


# =============================================================================
# PULL COMMAND
# =============================================================================

@main.command()
@click.option("--force", is_flag=True, help="Overwrite local changes")
@click.option("--skills-only", is_flag=True, help="Only pull skills")
@click.option("--configs-only", is_flag=True, help="Only pull configs")
def pull(force: bool, skills_only: bool, configs_only: bool):
    """Pull changes from the remote repository."""
    config = Config()
    sync_manager = SyncManager(config)
    
    if not config.repo_url:
        console.print("[red]✗ Not initialized.[/red]")
        return
    
    # Default: pull both (unless explicit --skills-only or --configs-only)
    do_skills = not configs_only  # True unless --configs-only
    do_configs = not skills_only  # True unless --skills-only
    # If neither flag, do both
    if not skills_only and not configs_only:
        do_skills = True
        do_configs = True
    
    success = sync_manager.pull(force=force, skills_only=do_skills, configs_only=do_configs)
    
    if success is not False:  # Success if not explicitly False (empty list is success)
        console.print("\n[green]✓ Pulled![/green]")
    else:
        console.print("\n[red]✗ Pull failed.[/red]")


# =============================================================================
# EXPORT COMMAND
# =============================================================================

@main.command("export")
@click.option("--output", type=click.Path(), default=None, help="Output path")
def export_config(output: Optional[str]):
    """Export agent config to JSON format."""
    config = Config()
    
    output_path = Path(output) if output else Path.home() / ".agents" / "config.json"
    
    config_data = config.to_dict()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.dump(config_data, default_flow_style=False))
    
    console.print(f"[green]✓ Exported to {output_path}[/green]")


# =============================================================================
# AGENTS COMMAND
# =============================================================================

@main.group()
def agents():
    """Manage agent configurations."""
    pass


@agents.command("list")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def list_agents(json_output: bool):
    """List all configured agents."""
    registry = load_registry()
    
    if json_output:
        import json
        console.print(json.dumps(registry, indent=2))
        return
    
    table = Table(title="Configured Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Location", style="dim")
    
    for agent_name, agent_data in registry.items():
        if agent_name == "global-skills":
            continue
        
        agent_type = agent_data.get("type", "unknown")
        location = agent_data.get("config_dir", "N/A")
        
        table.add_row(agent_name, agent_type, location)
    
    console.print(table)


# =============================================================================
# SETUP COMMAND
# =============================================================================

# @main.command()
# @click.option("--agent", "-a", multiple=True, help="Specific agents to setup")
# def setup(agent: tuple[str, ...]):
#     """Setup agent configurations interactively."""
#     console.print("\n[bold cyan]Agent Setup[/bold cyan]\n")
#     
#     agents_to_setup = list(agent) if agent else []
#     
#     if not agents_to_setup:
#         console.print("Available agents: opencode, claude-code, gemini-cli, pi.dev, qwen-code")
#         choice = Prompt.ask("\nWhich agents to setup?", default="all")
#         if choice.lower() == "all":
#             agents_to_setup = ["opencode", "claude-code", "gemini-cli", "pi.dev", "qwen-code"]
#         else:
#             agents_to_setup = [a.strip() for a in choice.split(",")]
#     
#     for agent_name in agents_to_setup:
#         console.print(f"\n[cyan]Setting up {agent_name}...[/cyan]")
#         handler = AgentHandler(agent_name)
#         
#         if handler.exists():
#             console.print(f"  [dim]Already configured[/dim]")
#         else:
#             success = handler.setup()
#             if success:
#                 console.print(f"  [green]✓ Configured[/green]")
#             else:
#                 console.print(f"  [red]✗ Failed[/red]")


# =============================================================================
# GENERATE COMMAND
# =============================================================================

@main.command("generate-config")
@click.option("--agent", "-a", multiple=True, required=True, help="Agents to generate config for")
def generate_config(agent: tuple[str, ...]):
    """Generate configuration files for agents."""
    from . import config
    
    target_agents = list(agent)
    console.print(f"\n[cyan]Generating config for: {', '.join(target_agents)}[/cyan]\n")
    
    config_path = config.generate_default(target_agents)
    
    console.print(f"[green]✓ Config generated: {config_path}[/green]")


# =============================================================================
# ENABLE/DISABLE COMMANDS
# =============================================================================

@main.command()
@click.argument("agent_name")
def enable(agent_name: str):
    """Enable an agent for syncing."""
    config = Config()
    
    if agent_name in config.agents:
        console.print(f"[yellow]⚠ {agent_name} already enabled.[/yellow]")
        return
    
    config.agents.append(agent_name)
    config.save()
    
    console.print(f"[green]✓ Enabled {agent_name}[/green]")


@main.command()
@click.argument("agent_name")
def disable(agent_name: str):
    """Disable an agent from syncing."""
    config = Config()
    
    if agent_name not in config.agents:
        console.print(f"[yellow]⚠ {agent_name} not enabled.[/yellow]")
        return
    
    config.agents.remove(agent_name)
    config.save()
    
    console.print(f"[green]✓ Disabled {agent_name}[/green]")


# =============================================================================
# SKILLS MANAGEMENT
# =============================================================================

@main.group("skills")
def skills_group():
    """Manage skills."""
    pass


@skills_group.command("list")
def list_skills():
    """List available skills."""
    skills_dir = Path.home() / ".agents" / "skills"
    
    if not skills_dir.exists():
        console.print("[yellow]No skills directory found.[/yellow]")
        return
    
    skills = [d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    
    console.print(f"\n[cyan]Skills ({len(skills)}):[/cyan]")
    for skill in sorted(skills):
        console.print(f"  • {skill}")


# =============================================================================
# PUBLISH COMMAND
# =============================================================================

@main.command("publish")
@click.option("--dry-run", is_flag=True, help="Show what would be published")
@click.option("--repo", "repo_url", help="Set GitHub repository URL")
@click.option("--add-source", "add_source_url", help="Add external skill source")
@click.option("--remove-source", "remove_source_url", help="Remove external skill source")
@click.option("--list-sources", "list_sources_flag", is_flag=True, help="List skill sources")
@click.option("--clear-cache", is_flag=True, help="Clear skill cache")
@click.option("--reset-selection", is_flag=True, help="Reset saved selection")
def publish(
    dry_run: bool,
    repo_url: Optional[str],
    add_source_url: Optional[str],
    remove_source_url: Optional[str],
    list_sources_flag: bool,
    clear_cache: bool,
    reset_selection: bool,
):
    """Publish skills and agents to a public repository.
    
    Run without options to select and publish skills & agents interactively.
    
    Examples:
    
      agent-sync publish                  Select and publish skills & agents
      agent-sync publish --repo URL       Set repository URL
      agent-sync publish --add-source URL  Add external skill source
      agent-sync publish --list-sources   List configured sources
      agent-sync publish --clear-cache    Clear cached repos
    """
    
    # Handle repo URL
    if repo_url:
        if not validate_github_url(repo_url):
            console.print("[red]✗ Invalid repository URL[/red]")
            raise click.Abort()
        set_published_repo(repo_url)
        console.print(f"[green]✓ Repository set to {repo_url}[/]")
        return
    
    # Handle source management
    if add_source_url:
        if not validate_github_url(add_source_url):
            console.print("[red]✗ Invalid repository URL[/red]")
            raise click.Abort()
        add_source(add_source_url)
        console.print(f"[green]✓ Added source: {add_source_url}[/]")
        return
    
    if remove_source_url:
        if remove_source(remove_source_url):
            console.print(f"[green]✓ Removed source: {remove_source_url}[/]")
        else:
            console.print(f"[yellow]⚠ Source not found: {remove_source_url}[/]")
        return
    
    # Handle list sources
    if list_sources_flag:
        # Trigger discovery to update last_success and ensure cache is valid
        from agent_sync.publish import load_config
        config = load_config()
        from agent_sync.publish.discovery import discover_skills_sources
        discover_skills_sources(config)
        
        from agent_sync.publish.config import list_sources as get_sources
        sources = get_sources()
        if sources:
            console.print("\n[bold]📚 External Skill Sources[/]\n")
            for src in sources:
                console.print(f"  • {src.url}")
                console.print(f"    Status: {src.status.value}, Last: {src.last_success or 'N/A'}")
        else:
            console.print("\n[dim]No external sources configured.[/dim]")
        from agent_sync.publish.config import get_published_repo
        console.print(f"\n[dim]Published repo: {get_published_repo() or 'Not set'}[/dim]\n")
        return
    
    # Handle clear cache
    if clear_cache:
        config = load_publish_config()
        count = clear_publish_cache(config.cache_dir)
        console.print(f"[green]✓ Cleared {count} cached repositories[/]")
        return
    
    # Handle reset selection
    if reset_selection:
        save_selected_skills({})
        console.print("[green]✓ Selection reset[/]")
        return
    
    # =============================================================================
    # Publish Flow
    # =============================================================================
    
    # Simple: just run step-by-step publish setup
    # User selects/deselects skills and agents in the TUI
    success = run_publish_setup()
    if not success:
        raise click.Abort()


# =============================================================================
# DIFF COMMAND
# =============================================================================

@main.command()
@click.option("--skills", is_flag=True, help="Show skills diff")
@click.option("--configs", is_flag=True, help="Show configs diff")
def diff(skills: bool, configs: bool):
    """Show differences between local and remote."""
    config = Config()
    sync_manager = SyncManager(config)
    
    if not config.repo_url:
        console.print("[red]✗ Not initialized.[/red]")
        return
    
    do_skills = skills or (not configs)
    do_configs = configs or (not skills)
    
    if do_skills:
        console.print("\n[cyan]Skills Diff:[/cyan]")
        # Show skills diff
    
    if do_configs:
        console.print("\n[cyan]Configs Diff:[/cyan]")
        # Show configs diff


# =============================================================================
# STATUS COMMAND
# =============================================================================

@main.command()
def status():
    """Show sync status."""
    config = Config()
    
    console.print("\n[bold cyan]agent-sync Status[/bold cyan]\n")
    
    if config.repo_url:
        console.print("[green]✓ Initialized[/green]")
        console.print(f"  Repository: {config.repo_url}")
    else:
        console.print("[yellow]⚠ Not initialized[/yellow]")
        console.print("  Run 'agent-sync init' to setup")
    
    console.print(f"\n[cyan]Enabled agents ({len(config.agents)}):[/cyan]")
    for agent in config.agents:
        console.print(f"  • {agent}")
    
    skills_dir = Path.home() / ".agents" / "skills"
    if skills_dir.exists():
        skill_count = len([d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
        console.print(f"\n[cyan]Skills: {skill_count}[/cyan]")


# =============================================================================
# UPDATE COMMAND
# =============================================================================

@main.command()
@click.option("--check", is_flag=True, help="Check for updates only")
def update(check: bool):
    """Update agent-sync to the latest version."""
    console.print("\n[cyan]Checking for updates...[/cyan]\n")
    
    try:
        result = subprocess.run(
            ["pipx", "upgrade", "agent-sync"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            console.print("[green]✓ Updated![/green]")
        else:
            console.print("[yellow]⚠ Update check failed[/yellow]")
            console.print(result.stderr)
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")


# =============================================================================
# VERSION COMMAND
# =============================================================================

@main.command()
def version():
    """Show version information."""
    console.print(f"\n[cyan]agent-sync {__version__}[/cyan]\n")
    console.print("  Config: ~/.config/agent-sync/")
    console.print("  Skills: ~/.agents/skills/")
    console.print("  Cache: ~/.cache/agent-sync/")


if __name__ == "__main__":
    main()
