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
from .mcp_merger import MCPMerger
from .secrets import SecretsManager
from ._tui import print_footer
from .skills_delete import SkillsDeleter


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
    from ._tui import print_footer

    config = Config()

    if not config.repo_url:
        console.print("[red]✗ Not initialized. Run 'agent-sync init' first.[/red]")
        return

    sync_manager = SyncManager(config)

    commit_msg = message or "chore: sync config updates"

    do_skills = not configs_only
    do_configs = not skills_only
    if not skills_only and not configs_only:
        do_skills = True
        do_configs = True

    # Stage and get changed files (don't commit yet)
    changed_files = sync_manager._push_stage_and_get_changes(
        message=commit_msg,
        skills_only=do_skills,
        configs_only=do_configs,
    )

    # No changes?
    if not changed_files:
        console.print("\n[yellow]Nothing to push (no changes since last sync).[/yellow]\n")
        return

    # Build category groups
    groups = {"skills": [], "configs": [], "agents": [], "other": []}
    for f in changed_files:
        path = f["path"]
        if path.startswith("skills/"):
            groups["skills"].append(f)
        elif path.startswith("configs/"):
            groups["configs"].append(f)
        elif path.startswith("agents/"):
            groups["agents"].append(f)
        else:
            groups["other"].append(f)

    # Print tree
    console.print("\n[bold]📤 Changes to be pushed:[/]")

    def status_label(f):
        s = f["status"]
        if s == "??": return "[green]+[/]"
        if "D" in s: return "[red]-[/]"
        if "A" in s: return "[green]+[/]"
        return "[yellow]·[/]"

    def sort_key(f):
        return f["path"].lower()

    # Skills section
    if groups["skills"]:
        console.print("\n  [cyan]skills/[/cyan]")
        for f in sorted(groups["skills"], key=sort_key):
            rel = f["path"].replace("skills/", "", 1)
            cnt = f.get("directory_count")
            extra = f" ({cnt} files)" if cnt else ""
            console.print(f"    {status_label(f)} {rel}{extra}")

    # Configs section
    if groups["configs"]:
        console.print("\n  [cyan]configs/[/cyan]")
        for f in sorted(groups["configs"], key=sort_key):
            rel = f["path"].replace("configs/", "", 1)
            console.print(f"    {status_label(f)} {rel}")

    # Agents section
    if groups["agents"]:
        console.print("\n  [cyan]agents/[/cyan]")
        for f in sorted(groups["agents"], key=sort_key):
            rel = f["path"].replace("agents/", "", 1)
            cnt = f.get("directory_count")
            extra = f" ({cnt} files)" if cnt else ""
            console.print(f"    {status_label(f)} {rel}{extra}")

    # Other
    if groups["other"]:
        console.print("\n  [cyan]other/[/cyan]")
        for f in sorted(groups["other"], key=sort_key):
            console.print(f"    {status_label(f)} {f['path']}")

    total = len(changed_files)
    console.print(f"\n[dim]{total} item(s)[/dim]\n")
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    print_footer([("Enter", "push"), ("q", "cancel")], default_key="Enter")
    choice = Prompt.ask("\n> ")
    if choice.lower() in ("q", "quit"):
        console.print("\n[yellow]Cancelled — changes not pushed.[/yellow]\n")
        # Unstage everything
        sync_manager._run_git("reset", "HEAD", "--")
        return

    # User confirmed — commit and push
    try:
        sync_manager._run_git("add", ".")
        sync_manager._run_git("commit", "-m", commit_msg)
        sync_manager._run_git("push", "origin", "main")
        sync_manager._save_state("pushed", sync_manager.config.repo_url)
        console.print("\n[green]✓ Pushed![/green]\n")
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]✗ Push failed:[/red] {e.stderr or e}")


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
    """List and manage skills interactively."""
    from rich.box import ROUNDED
    skills_dir = Path.home() / ".agents" / "skills"

    if not skills_dir.exists():
        console.print("[yellow]No skills directory found.[/yellow]")
        return

    skills = sorted([
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])

    if not skills:
        console.print("[yellow]No skills in hub.[/yellow]")
        return

    # ─── State ────────────────────────────────────────────────────────────────
    selected: set[str] = set()
    preview_skill: str | None = None
    remove_mode = False

    while True:
        # ─── Header ───────────────────────────────────────────────────────────
        n = len(skills)
        s = len(selected)
        header = f"[bold]📚 Skills Hub ({n} skills)[/]"
        if s > 0:
            header += f"  |  Selected ({s}): {", ".join(sorted(selected))}"
        if remove_mode:
            header += "  [red]│ REMOVE MODE[/red]"

        console.print(f"\n{header}\n")

        # ─── Preview panel ────────────────────────────────────────────────────
        if preview_skill:
            skill_path = skills_dir / preview_skill
            console.print(f"  [dim]⚡ Preview:[/dim] [cyan]{preview_skill}[/cyan]")
            desc_lines = _skill_description_lines(skill_path)
            for line in desc_lines[:5]:
                console.print(f"  [dim]{line}[/dim]")
            if len(desc_lines) > 5:
                console.print(f"  [dim]... ({len(desc_lines)-5} more lines)[/dim]")
            console.print()

        # ─── Table ────────────────────────────────────────────────────────────
        table = Table(box=ROUNDED, show_header=True, header_style="bold dim")
        table.add_column("#", width=3, justify="right")
        table.add_column("", width=3)
        table.add_column("Skill", width=40)
        table.add_column("Files", width=6, justify="right")

        for i, name in enumerate(skills, 1):
            mark = "●" if name in selected else "○"
            mark_color = "green" if name in selected else "dim"
            skill_path = skills_dir / name
            n_files = sum(1 for f in skill_path.rglob("*") if f.is_file())
            style = "" if not remove_mode else "red bold"

            table.add_row(
                f"[dim]{i:02d}[/dim]",
                f"[{mark_color}]{mark}[/{mark_color}]",
                name,
                f"[dim]{n_files}[/dim]",
                style=style,
            )

        console.print(table)
        console.print()

        # ─── Footer ───────────────────────────────────────────────────────────
        if remove_mode:
            footer_lines = [
                "(a) all  (n) none  (r) toggle-remove  (q) quit",
                "(p) preview  [Enter] confirm removal  (d) deselect",
            ]
        else:
            footer_lines = [
                "(1-N) toggle  (a) all  (n) none  (d) deselect",
                "(r) remove  (q) quit  (p) preview [Enter] confirm",
            ]
        print_footer(footer_lines, default_key="Enter" if selected else None)

        # ─── Input ───────────────────────────────────────────────────────────
        choice = Prompt.ask("\n›", default="").strip()

        if not choice:
            if selected:
                break
            continue

        if choice.lower() in ("q", "quit"):
            console.print("[dim]Cancelled.[/dim]\n")
            return

        if choice.lower() in ("a", "all"):
            selected = set(skills)

        elif choice.lower() in ("n", "none"):
            selected = set()
            preview_skill = None

        elif choice.lower() in ("d", "deselect"):
            selected = set()
            remove_mode = False

        elif choice.lower() in ("r", "remove"):
            remove_mode = not remove_mode

        elif choice.lower() in ("p", "preview"):
            if selected:
                sel_list = sorted(selected)
                cur_idx = sel_list.index(preview_skill) + 1 if preview_skill in sel_list else 0
                preview_skill = sel_list[cur_idx % len(sel_list)]
            else:
                cur_idx = skills.index(preview_skill) + 1 if preview_skill in skills else 0
                preview_skill = skills[cur_idx % len(skills)]

        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(skills):
                name = skills[idx]
                if name in selected:
                    selected.discard(name)
                    if preview_skill == name:
                        preview_skill = None
                else:
                    selected.add(name)

        elif "-" in choice or "," in choice:
            new_selected: set[str] = set()
            for part in choice.replace(",", " ").replace(";", " ").split():
                part = part.strip()
                if "-" in part:
                    try:
                        start_s, end_s = part.split("-", 1)
                        start = max(0, int(start_s) - 1)
                        end = min(len(skills), int(end_s))
                        for j in range(start, end):
                            new_selected.add(skills[j])
                    except ValueError:
                        pass
                else:
                    try:
                        idx = int(part) - 1
                        if 0 <= idx < len(skills):
                            new_selected.add(skills[idx])
                    except ValueError:
                        pass

            if new_selected:
                selected = new_selected

    # ─── Confirm deletion ──────────────────────────────────────────────────
    if not selected:
        return

    console.print(f"\n[bold]🗑 Delete {len(selected)} skill(s)?[/]")
    for name in sorted(selected):
        console.print(f"  • {name}")

    if not Confirm.ask("\n[bold]Confirm deletion?[/]", default=False):
        console.print("[dim]Cancelled.[/dim]\n")
        return

    # ─── Delete ─────────────────────────────────────────────────────────────
    deleter = SkillsDeleter()
    stats = deleter.delete_skills(list(selected))

    console.print(f"\n[green]✓ Deleted {stats['deleted_from_hub']} skill(s)[/green]")
    console.print(f"  [dim]└─ {stats['hub_files']} files from hub[/dim]")
    if stats["deleted_from_agents"]:
        console.print(f"  [dim]└─ {stats['deleted_from_agents']} from agents ({stats['agent_files']} files)[/dim]")
    if stats["not_found"]:
        console.print(f"  [yellow]⚠ {stats['not_found']} not found[/yellow]")
    if stats["errors"]:
        console.print(f"  [red]✗ {stats['errors']} errors[/red]")
    console.print()


def _skill_description_lines(skill_path: Path) -> list[str]:
    """Extract description lines from SKILL.md."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return [f"[dim]No SKILL.md[/dim]"]

    try:
        lines = skill_md.read_text().splitlines()
        desc = []
        capturing = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                continue
            if stripped.startswith("## "):
                break
            if stripped:
                capturing = True
                desc.append(stripped[:80])
            elif capturing and desc:
                break
        return desc if desc else [f"[dim]Empty SKILL.md[/dim]"]
    except Exception:
        return [f"[dim]Could not read SKILL.md[/dim]"]


@skills_group.command("centralize")
@click.option("--copy", is_flag=True, help="Copy skills (keep originals in agent directories)")
@click.option("--push", is_flag=True, help="Push to GitHub after centralizing")
@click.option("--dry-run", is_flag=True, help="Preview without modifying anything")
def centralize_skills(copy: bool, push: bool, dry_run: bool):
    """Centralize all skills from agents into ~/.agents/skills/.

    Pipeline: scan → sync from repo → import orphans → configure agents.
    No interaction needed — auto-centralizes everything.

    Examples:
      agent-sync skills centralize         # Auto: sync + import + configure
      agent-sync skills centralize --copy  # Copy instead of move
      agent-sync skills centralize --push  # + push to GitHub
      agent-sync skills centralize --dry-run  # Preview
    """
    from .centralize.handlers.dot_agents_handler import DotAgentsHandler
    from .skills import SkillsManager

    handler = DotAgentsHandler()
    handler.ensure_structure(dry_run=dry_run)

    skills_mgr = SkillsManager()
    stats = skills_mgr.centralize(dry_run=dry_run, move=not copy)

    if dry_run:
        console.print("\n[dim]Dry run — no changes made.[/dim]\n")
        return

    if push or Confirm.ask("\n[bold]Push to GitHub?[/]", default=False):
        from .sync import SyncManager
        from .config import Config

        cfg = Config()
        sync_mgr = SyncManager(cfg)
        sync_mgr.push(skills_only=True)

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



# =============================================================================
# LINK COMMAND
# =============================================================================

@main.command("link")
@click.argument("repo_url")
def link(repo_url: str):
    """Link to an existing sync repository (additional machines)."""
    if not validate_github_url(repo_url):
        console.print(f"\n✗ Invalid repository URL\n   Expected: https://github.com/user/repo.git\n   Got: {repo_url}\n")
        raise click.Abort()

    console.print(f"\n🔗 Linking to repository: {repo_url}")

    config = Config()
    sync_manager = SyncManager(config)

    try:
        sync_manager.link_repo(repo_url)
        console.print("\n✅ Successfully linked to repository")
        console.print("\n📥 Run 'agent-sync pull' to download configs")
    except Exception as e:
        console.print(f"\n❌ Error: {e}")



# =============================================================================
# CONFIG GROUP
# =============================================================================

@main.group("config")
def config_group():
    """Manage configuration (view, edit, reset)."""
    pass


@config_group.command("show")
def config_show():
    """Show current configuration."""
    config = Config()
    if not config.repo_url:
        console.print("\n[yellow]⚠ Not configured yet. Run 'agent-sync setup'[/yellow]\n")
        return

    console.print(f"\n[bold]📋 Current Configuration[/]\n")
    console.print(f"Repository: {config.repo_url}")
    console.print(f"Enabled agents: {', '.join(config.agents)}")
    console.print(f"Config file: {config.config_path}\n")


@config_group.command("repo")
@click.argument("repo_url", required=False)
@click.option("--remove", is_flag=True, help="Remove repository configuration")
def config_repo(repo_url: str | None, remove: bool):
    """View or set the GitHub repository URL."""
    config = Config()

    if remove:
        if not config.repo_url:
            console.print("\n[yellow]No repository configured[/yellow]\n")
            return
        old = config.repo_url
        config.repo_url = None
        console.print(f"\n[green]✓ Repository removed: {old}[/green]\n")
        return

    if repo_url:
        if not validate_github_url(repo_url):
            console.print(f"\n[red]✗ Invalid URL: {repo_url}[/red]\n")
            return
        config.repo_url = repo_url
        console.print(f"\n[green]✓ Repository set: {repo_url}[/green]\n")
        return

    if not config.repo_url:
        console.print("\n[yellow]⚠ Not configured[/yellow]\n")
        console.print("Run: agent-sync config repo <url>\n")
        return

    console.print(f"\n[cyan]📦 Repository:[/cyan] {config.repo_url}\n")


@config_group.command("edit")
def config_edit():
    """Open configuration file in editor."""
    import os, subprocess
    config = Config()
    if not config.config_path.exists():
        config.generate_default()
    editor = os.environ.get("EDITOR", "nano")
    try:
        subprocess.run([editor, str(config.config_path)], check=True)
        console.print("\n[green]✓ Configuration saved[/green]\n")
    except FileNotFoundError:
        console.print(f"\n[yellow]Editor '{editor}' not found[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")



@config_group.command()
@click.confirmation_option(prompt="Are you sure you want to reset?")
def reset():
    """Reset configuration to defaults (keeps repo linked)."""
    config = Config()
    path = config.reset()
    console.print(f"\n[green]✓ Reset to defaults: {path}[/green]\n")



# =============================================================================
# SECRETS GROUP
# =============================================================================

@main.group("secrets")
def secrets_group():
    """Manage secrets and environment variables.

    Note: agent-sync does not scrub secrets. Config files are synced as-is.
    ALWAYS use a private repository.
    """
    pass


@secrets_group.command("list")
def secrets_list():
    """List all secrets and environment variables."""
    secrets_mgr = SecretsManager()
    console.print("\n[bold]🔐 Secrets Manager[/]\n")
    console.print(f"[dim].env file: {secrets_mgr.env_file}[/dim]\n")
    if secrets_mgr.env_file.exists():
        content = secrets_mgr.env_file.read_text()
        if content.strip():
            console.print("[bold green]✓ .env file:[/]")
            console.print(f"[dim]{content}[/dim]\n")
        else:
            console.print("[yellow]⚠ .env file is empty[/yellow]\n")
    else:
        console.print("[yellow]⚠ No .env file found[/yellow]\n")


@secrets_group.command("edit")
def secrets_edit():
    """Edit secrets in your $EDITOR."""
    import os, subprocess
    secrets_mgr = SecretsManager()
    if not secrets_mgr.env_file.exists():
        secrets_mgr.env_file.parent.mkdir(parents=True, exist_ok=True)
        secrets_mgr.env_file.write_text("# agent-sync environment variables\n")
    editor = os.environ.get("EDITOR", "nano")
    try:
        subprocess.run([editor, str(secrets_mgr.env_file)], check=True)
        console.print("\n[green]✓ Secrets saved[/green]\n")
    except FileNotFoundError:
        console.print(f"\n[yellow]Editor '{editor}' not found[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]\n")



@secrets_group.command("enable")
def secrets_enable():
    """Enable secrets synchronization."""
    secrets_mgr = SecretsManager()
    secrets_mgr.enable()
    console.print("\n[green]✓ Secrets synchronization enabled[/green]")
    console.print("[dim]Warning: Secrets will be synced to your repository[/dim]\n")
    console.print("[yellow]⚠️  IMPORTANT: Only use with a PRIVATE repository![/yellow]\n")



@secrets_group.command("disable")
def secrets_disable():
    """Disable secrets synchronization."""
    secrets_mgr = SecretsManager()
    secrets_mgr.disable()
    console.print("\n[green]✓ Secrets synchronization disabled[/green]\n")



# =============================================================================
# MCP COMMAND
# =============================================================================

@main.command("mcp")
@click.option("--dry-run", is_flag=True, help="Show merge preview without creating file")
@click.option("--force", is_flag=True, help="Overwrite existing ~/.agents/mcp.json")
@click.option("--conflicts", is_flag=True, help="Show only conflict report")
@click.option("--source", "-s", multiple=True, type=click.Path(exists=True), help="Additional MCP config sources")
@click.option("--output", type=click.Path(), default=None, help="Output path")
def mcp(dry_run: bool, force: bool, conflicts: bool, source: tuple[str, ...], output: str | None):
    """Export unified MCP configuration.


    Scans vendor MCP configs and merges them into ~/.agents/mcp.json.
    Does NOT modify vendor configs - creates a unified DotAgents-compatible file.

    """
    from pathlib import Path

    sources = [Path(s) for s in source]
    merger = MCPMerger(sources=sources if sources else None)

    found = merger.find_mcp_configs()
    if not found and not sources:
        console.print("\n[yellow]⚠ No MCP configs found.[/yellow]")
        console.print("[dim]Known: ~/.claude/mcp.json, ~/.cursor/mcp.json[/dim]")
        console.print("[dim]Use --source to specify custom locations.[/dim]\n")
        return

    console.print("\n[bold]📋 MCP Config Sources[/]\n")
    for src in (found + sources):
        console.print(f"  • {src}")
    console.print()

    merger.merge()

    if merger.conflicts:
        console.print(merger.get_conflict_report())

    if conflicts:
        return

    output_path = Path(output) if output else MCPMerger.DEFAULT_OUTPUT

    if dry_run:
        console.print(f"[dim]Would export to: {output_path}[/dim]\n")
        console.print_json(data=merger.merge())
        console.print()
    elif output_path.exists() and not force:
        console.print(f"[yellow]⚠ {output_path} exists. Use --force.[/yellow]\n")
    else:
        merger.save(output_path)
        console.print(f"[green]✓[/green] Unified MCP config exported to {output_path}")
        console.print(f"[dim]Servers: {len(merger.servers)}, Conflicts: {len(merger.conflicts)}[/dim]\n")


if __name__ == "__main__":
    main()
