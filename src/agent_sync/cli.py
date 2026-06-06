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
from .paths import HUB_DIR
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
from ._tui import print_footer, build_footer_commands
from .skills_delete import SkillsDeleter


console = Console()


def print_full_help(ctx, param, value):
    if not value:
        return
    
    from rich.console import Console
    from rich.table import Table
    console = Console()
    
    console.print("\n[bold cyan]agent-sync Commands[/bold cyan]\n")
    
    # Group commands by category
    categories = {
        "Sync & Backup": ["init", "push", "pull", "status", "diff", "sync"],
        "Repositories": ["repos", "publish"],
        "Configuration": ["config", "generate-config"],
        "Skills": ["skills"],
        "Agents": ["agents", "enable", "disable", "export"],
        "System": ["secrets", "mcp", "update", "version"],
    }
    
    for cat_name, cmds in categories.items():
        console.print(f"[bold]{cat_name}:[/]")
        for cmd in cmds:
            if cmd == "repos":
                console.print(f"  [cyan]repos[/cyan]             list | target (list | remove) | source (add | list | remove)")
            elif cmd == "publish":
                console.print(f"  [cyan]publish[/cyan]           add | list | remove | run")
            elif cmd == "config":
                console.print(f"  [cyan]config[/cyan]            show | repo | edit | reset")
            elif cmd == "skills":
                console.print(f"  [cyan]skills[/cyan]           list | centralize")
            elif cmd == "secrets":
                console.print(f"  [cyan]secrets[/cyan]          list | edit | enable | disable")
            elif cmd == "agents":
                console.print(f"  [cyan]agents[/cyan]           list")
            else:
                console.print(f"  [cyan]{cmd}[/cyan]")
        console.print()
    
    console.print("[dim]Run 'agent-sync <command> --help' for more details on a command.[/dim]\n")
    ctx.exit()


@click.group()
@click.option('-h', '--help', is_flag=True, callback=print_full_help, expose_value=False, is_eager=True)
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
    
    console.print(f"\n[bold]🔄 Syncing with [cyan]{config.repo_url.split('/')[-1]}[/cyan]...[/]\n")
    
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
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without pushing")
@click.option("--message", "-m", default=None, help="Commit message")
@click.option("--skills-only", is_flag=True, help="Only push skills")
@click.option("--configs-only", is_flag=True, help="Only push configs")
@click.option("--skill", "-s", multiple=True, help="Specific skill to push (can repeat)")
@click.option("--agent", "-a", multiple=True, help="Specific agent config to push (can repeat)")
@click.option("--exclude-skill", multiple=True, help="Skill to exclude (can repeat)")
@click.option("--exclude-agent", multiple=True, help="Agent to exclude (can repeat)")
@click.option("--prune", is_flag=True, help="Remove orphan skills from the remote repo (in HEAD but not in local hub). Default: kept additively.")
@click.option("--strict", is_flag=True, help="Exit with code 2 if orphan skills were detected (for CI/scripts).")
def push(
    dry_run: bool,
    message: Optional[str],
    skills_only: bool,
    configs_only: bool,
    skill: tuple,
    agent: tuple,
    exclude_skill: tuple,
    exclude_agent: tuple,
    prune: bool,
    strict: bool,
):
    """Push local changes to the remote repository.

    By default, the remote repo is kept ADDITIVE: any skill that exists in
    the remote `skills/` but is missing from `~/.agents/skills/` is left
    alone. Use `--prune` to remove those orphans in the same commit
    (history preserved as `D` entries). Use `agent-sync skills prune` for
    a dedicated subcommand with `--dry-run` and `--yes` flags.

    Examples:
      agent-sync push                    # Push all (additive, default)
      agent-sync push --skill dogfood   # Specific skill
      agent-sync push --agent pi.dev    # Specific agent config
      agent-sync push --exclude-skill deprecated-skill  # Exclude skill
      agent-sync push --prune           # Remove remote orphans too
      agent-sync push --dry-run         # Preview changes
    """
    from ._tui import print_footer, build_footer_commands

    config = Config()

    if not config.repo_url:
        console.print("[red]✗ Not initialized. Run 'agent-sync init' first.[/red]")
        return

    sync_manager = SyncManager(config)

    commit_msg = message or "chore: sync config updates"

    # Pass the raw flags directly. With neither flag, both are False and
    # _push_stage_and_get_changes runs all three branches (skills, configs, agents).
    # `--skills-only` / `--configs-only` flip the respective flag to True,
    # which makes it skip the other branches. The previous
    # `do_skills = not configs_only` dance effectively set configs_only=True
    # by default, which made the prune check `not configs_only` always False
    # — prune never ran on default pushes.
    changed_files, orphans = sync_manager._push_stage_and_get_changes(
        message=commit_msg,
        skills_filter=list(skill) if skill else None,
        agents_filter=list(agent) if agent else None,
        skills_exclude=list(exclude_skill) if exclude_skill else None,
        agents_exclude=list(exclude_agent) if exclude_agent else None,
        skills_only=skills_only,
        configs_only=configs_only,
        prune=prune,
    )

    # No changes?
    if not changed_files:
        # Even if nothing was changed in this push, surface orphan info
        # so the user knows they exist (educational).
        if orphans:
            _warn_about_orphans(orphans)
        console.print("\n[yellow]Nothing to push (no changes since last sync).[/yellow]\n")
        return
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
    console.print(f"\n[bold]📤 Changes to be pushed to [cyan]{config.repo_url.split('/')[-1]}[/cyan]:[/]")

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

    # Dry run - stop here after preview
    if dry_run:
        console.print("[dim]Dry run — no changes made.[/dim]\n")
        return

    # Build footer with standardized format
    footer_cmds = build_footer_commands([("Enter", "push"), ("q", "cancel")], default_key="Enter")
    print_footer(footer_cmds)
    choice = Prompt.ask(r"[Enter] push (default), [q] quit: ")
    if choice.lower() in ("q", "quit"):
        console.print("\n[yellow]Cancelled — changes not pushed.[/yellow]\n")
        # Unstage everything
        sync_manager._run_git("reset", "HEAD", "--")
        return

    # User confirmed — commit and push
    console.print(f"\n  [dim]📝 Committing to {config.repo_url.split('/')[-1]}...[/dim]")
    try:
        sync_manager._run_git("add", ".")
        sync_manager._run_git("commit", "-m", commit_msg)
        console.print(f"  [dim]🚀 Pushing to {config.repo_url.split('/')[-1]}...[/dim]")
        sync_manager._run_git("push", "origin", "main")
        sync_manager._save_state("pushed", sync_manager.config.repo_url)
        console.print(f"\n[green]✓ Pushed to {config.repo_url.split('/')[-1]}[/green]\n")
    except subprocess.CalledProcessError as e:
        from .sync import _sanitize_git_output
        console.print(f"\n[red]✗ Push failed:[/red] {_sanitize_git_output(e.stderr) or e}")
        return

    # Educational warning: orphans detected but not pruned (default is safe).
    # The user just opted out of the destructive operation; tell them what
    # they could have done, without being preachy.
    if orphans and not prune:
        _warn_about_orphans(orphans)

    # CI-friendly strict mode: exit with code 2 if orphans were detected.
    # Without --strict, the warning is console-only (exit stays 0).
    if strict and orphans:
        raise SystemExit(2)


def _warn_about_orphans(orphans: list[str]) -> None:
    """Print a yellow warning listing orphan skills and how to prune them.

    Called after a successful `push` that detected orphans but did NOT
    prune them (the default). The user can then choose to run
    `agent-sync skills prune` or `agent-sync push --prune`.
    """
    n = len(orphans)
    sample = ", ".join(orphans[:5])
    more = f" (+{n - 5} more)" if n > 5 else ""
    console.print(
        f"\n[yellow]⚠  {n} orphan skill(s) in the remote repo "
        f"(missing from local hub): {sample}{more}[/yellow]"
    )
    console.print(
        "[yellow]   To remove them, run one of:[/yellow]\n"
        "    [cyan]agent-sync skills prune --dry-run[/cyan]  # preview\n"
        "    [cyan]agent-sync skills prune --yes[/cyan]       # execute\n"
        "    [cyan]agent-sync push --prune[/cyan]            # prune in next push\n"
    )


# =============================================================================
# PULL COMMAND
# =============================================================================

@main.command()
@click.option("--force", is_flag=True, help="Apply all remote (no confirmation)")
@click.option("--dry-run", is_flag=True, help="Show what would change")
@click.option("--interactive/--no-interactive", "interactive", default=True, help="Interactive conflict resolution")
@click.option("--skills-only", is_flag=True, help="Only pull skills")
@click.option("--configs-only", is_flag=True, help="Only pull configs")
@click.option("--skill", "-s", multiple=True, help="Specific skill to pull (can repeat)")
@click.option("--agent", "-a", multiple=True, help="Specific agent config to pull (can repeat)")
@click.option("--exclude-skill", multiple=True, help="Skill to exclude (can repeat)")
@click.option("--exclude-agent", multiple=True, help="Agent to exclude (can repeat)")
@click.option("--prune", is_flag=True, help="Remove local skills that are missing from the private repo (mirror-pull). Default: preview only.")
def pull(force: bool, dry_run: bool, interactive: bool, skills_only: bool, configs_only: bool, skill: tuple, agent: tuple, exclude_skill: tuple, exclude_agent: tuple, prune: bool):
    """Pull changes from the remote repository.

    Default behavior is additive (no local skill is deleted). Local skills
    that are missing from the private repo are always shown in the preview
    so you can see the cleanup opportunity. Pass --prune to actually
    remove them (mirror-pull, makes local a mirror of private).

    Examples:
      agent-sync pull                    # Pull all (additive, safe)
      agent-sync pull --skill cali-product-workflow   # Specific skill
      agent-sync pull --agent pi.dev     # Specific agent config
      agent-sync pull --exclude-skill deprecated-skill # Exclude skill
      agent-sync pull --dry-run          # Preview changes
      agent-sync pull --prune            # Mirror: also remove local orphans
    """
    config = Config()
    sync_manager = SyncManager(config)

    if not config.repo_url:
        console.print("[red]✗ Not initialized.[/red]")
        return

    # Pass the raw flags directly. With neither flag, both are False and
    # SyncManager.pull runs all three branches (configs, skills, agents).
    # `--skills-only` / `--configs-only` flip the respective flag to True,
    # which makes the SyncManager skip the other branches. The previous
    # `do_skills = not configs_only` dance was inverted and effectively
    # skipped everything by default.
    try:
        changes, summary = sync_manager.pull(
            force=force,
            dry_run=dry_run,
            interactive=interactive,
            skills_only=skills_only,
            configs_only=configs_only,
            skills_filter=list(skill) if skill else None,
            agents_filter=list(agent) if agent else None,
            skills_exclude=list(exclude_skill) if exclude_skill else None,
            agents_exclude=list(exclude_agent) if exclude_agent else None,
            prune=prune,
        )
        
        if dry_run:
            return  # Preview already shown
        
        if summary.has_conflicts:
            console.print("\n[yellow]⚠️  Some conflicts kept local.[/yellow]")
        
        if changes:
            console.print(f"\n[green]✓ Pulled {len(changes)} file(s)![/green]")
        else:
            console.print("\n[dim]No changes to pull.[/dim]")
    except RuntimeError as e:
        console.print(f"\n[red]✗ {e}[/red]")
        return


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


# =============================================================================
# REPOS COMMAND
# =============================================================================

@main.group("repos")
def repos_group():
    """Manage repositories (sync, publish, and sources).
    
    Subcommands:
      list     Show all target repositories (sync + publish)
      target   Configure sync and publish targets
      source   Manage skill sources (external repos to import from)
    
    Examples:
      agent-sync repos list
      agent-sync repos target private https://github.com/user/private.git
      agent-sync repos source add https://github.com/user/skills
    """
    pass


@repos_group.command("list")
def repos_list():
    """Show all configured target repositories.
    
    Shows sync repository and publish destination.
    For skill sources, use 'agent-sync repos source list'.
    """
    from .publish.config import get_published_repo
    from rich.table import Table
    from rich.box import ROUNDED
    
    console.print("\n[bold]Repositories[/]\n")
    
    table = Table(box=ROUNDED, show_header=True, header_style="bold dim")
    table.add_column("Purpose", width=20)
    table.add_column("Repository", width=45)
    table.add_column("Status", width=12)
    
    # Sync Repo
    config = Config()
    sync_repo = config.repo_url
    if sync_repo:
        sync_name = sync_repo.replace("https://github.com/", "").replace(".git", "")
        table.add_row("sync / push", sync_name, "[green]active[/green]")
    else:
        table.add_row("sync / push", "[dim]not configured[/dim]", "[yellow]missing[/yellow]")
    
    # Publish Repo
    published_repo = get_published_repo()
    if published_repo:
        pub_name = published_repo.replace("https://github.com/", "").replace(".git", "")
        table.add_row("publish", pub_name, "[green]active[/green]")
    else:
        table.add_row("publish", "[dim]not configured[/dim]", "[yellow]missing[/yellow]")
    
    console.print(table)
    console.print()
    console.print("[bold]Change repositories:[/]")
    console.print("  [cyan]agent-sync repos target private <url>[/cyan]  Set sync repository")
    console.print("  [cyan]agent-sync repos target public <url>[/cyan]   Set publish repository")
    console.print("  [cyan]agent-sync repos source list[/cyan]          View skill sources\n")


# =============================================================================
# REPOS TARGET COMMAND
# =============================================================================

@repos_group.group("target")
def repos_target_group():
    """Show or remove target repositories.
    
    Repos are auto-detected from gh auth + defaults (agent-sync-private, agent-sync-public).
    """
    pass


@repos_target_group.command("list")
def repos_target_list():
    """Show configured target repositories."""
    from .publish.config import get_published_repo
    from rich.table import Table
    from rich.box import ROUNDED
    
    console.print("\n[bold]Target Repositories[/]\n")
    
    table = Table(box=ROUNDED, show_header=True, header_style="bold dim")
    table.add_column("Type", width=15)
    table.add_column("Repository", width=50)
    
    config = Config()
    sync_repo = config.repo_url
    if sync_repo:
        sync_name = sync_repo.replace("https://github.com/", "").replace(".git", "")
        table.add_row("[cyan]private[/cyan]", sync_name)
    else:
        table.add_row("[cyan]private[/cyan]", "[dim]not configured[/dim]")
    
    published_repo = get_published_repo()
    if published_repo:
        pub_name = published_repo.replace("https://github.com/", "").replace(".git", "")
        table.add_row("[cyan]public[/cyan]", pub_name)
    else:
        table.add_row("[cyan]public[/cyan]", "[dim]not configured[/dim]")
    
    console.print(table)
    console.print()
    console.print("[dim]Repos are auto-detected from gh auth + agent-sync-private/agent-sync-public[/dim]\n")


@repos_target_group.command("remove")
def repos_target_remove():
    """Remove all configured target repositories."""
    from rich.prompt import Confirm
    from .publish.config import get_published_repo, load_config, save_config
    
    config = Config()
    sync_repo = config.repo_url
    published_repo = get_published_repo()
    
    if not sync_repo and not published_repo:
        console.print("[yellow]No targets configured.[/yellow]\n")
        return
    
    if not Confirm.ask("[bold]Remove all targets?[/]", default=False):
        console.print("[dim]Cancelled.[/dim]\n")
        return
    
    if sync_repo:
        config.set_repo_url("")
    
    if published_repo:
        pub_config = load_config()
        pub_config.published_repo = ""
        save_config(pub_config)
    
    console.print("[green]All targets removed.[/green]\n")


# =============================================================================
# REPOS SOURCE COMMAND
# =============================================================================

@repos_group.group("source")
def repos_source_group():
    """Manage skill sources (external repositories to import from).
    
    """
    pass


@repos_source_group.command("list")
def repos_source_list():
    """List configured skill sources."""
    from .publish.config import load_config
    from rich.table import Table
    from rich.box import ROUNDED
    
    config_data = load_config()
    sources = config_data.skill_sources
    
    if not sources:
        console.print("\n[yellow]No skill sources configured.[/yellow]")
        console.print("\n[dim]Add: agent-sync repos source add <url>[/dim]\n")
        return
    
    table = Table(box=ROUNDED, show_header=True, header_style="bold dim")
    table.add_column("#", width=3, justify="right")
    table.add_column("Repository", width=55)
    table.add_column("Status", width=10)
    
    for i, src in enumerate(sources, 1):
        status = src.status.value if hasattr(src, 'status') else "unknown"
        status_color = "green" if status == "active" else "yellow"
        name = src.url.replace("https://github.com/", "")
        table.add_row(f"[dim]{i}[/dim]", name, f"[{status_color}]{status}[/{status_color}]")
    
    console.print(f"\n[bold]Skill Sources ({len(sources)})[/]\n")
    console.print(table)
    console.print("\n[dim]Add/remove: agent-sync repos source add|remove <url>[/dim]\n")


@repos_source_group.command("add")
@click.argument("url")
def repos_source_add(url: str):
    """Add a skill source repository."""
    from .publish.config import add_source
    from .validators import validate_github_url
    
    if not validate_github_url(url):
        console.print(f"[red]Invalid URL: {url}[/red]")
        return
    
    try:
        add_source(url)
        console.print(f"\n[green]Added skill source: {url}[/green]")
        console.print(f"\n[dim]List: agent-sync repos source list[/dim]\n")
    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")


@repos_source_group.command("remove")
@click.argument("url")
def repos_source_remove(url: str):
    """Remove a skill source repository."""
    from .publish.config import remove_source
    
    success = remove_source(url)
    if success:
        console.print(f"\n[green]Removed: {url}[/green]\n")
    else:
        console.print(f"[yellow]Not found: {url}[/yellow]\n")


# PUBLISH REPOS COMMAND
# =============================================================================

# =============================================================================
# PUB-REPOS COMMAND
# =============================================================================

def _publish_repos_add(url: str) -> None:
    """Add a publish repository."""
    from .publish.config import get_published_repo, set_published_repo
    from .validators import validate_github_url
    import subprocess
    from rich.prompt import Confirm

    if not validate_github_url(url):
        console.print(f"[red]✗ Invalid URL: {url}[/red]")
        return
    
    if get_published_repo() == url:
        console.print(f"[yellow]⚠ Already current: {url}[/yellow]")
        return
    
    console.print(f"\n[dim]🔍 Checking {url}...[/dim]")
    try:
        result = subprocess.run(
            ["gh", "api", "repos", url.replace("https://github.com/", "")],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            console.print(f"[red]✗ Cannot access: {url}[/red]")
            return
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return
    
    if not Confirm.ask(f"\n[bold]Set as publish target?[/]\n  {url}", default=True):
        console.print("[dim]Cancelled.[/dim]")
        return
    
    set_published_repo(url)
    console.print(f"\n[green]✓ Added: {url}[/green]")
    console.print(f"\n[dim]Run 'agent-sync repos list' to see all repos.\n[/dim]")


def _publish_repos_list() -> None:
    """List all configured publish repositories."""
    from .publish.config import get_published_repo, load_config

    config = load_config()
    published_repo = get_published_repo()
    sources = config.skill_sources
    
    repos = []
    if published_repo:
        repos.append({"url": published_repo, "type": "published"})
    for src in sources:
        if src.url != published_repo:
            repos.append({"url": src.url, "type": "source"})
    
    if not repos:
        console.print("\n[yellow]No publish repositories configured.[/yellow]")
        console.print("\n[dim]Add: agent-sync publish add <url>[/dim]\n")
        return
    
    console.print(f"\n[bold]📦 Publish Repos ({len(repos)} repos)[/]\n")
    for i, repo in enumerate(repos, 1):
        t = "published" if repo["type"] == "published" else "source"
        name = repo["url"].replace("https://github.com/", "")
        console.print(f"  {i:02d}. {name} [dim]({t})[/dim]")
    console.print("\n[dim]Add/remove: agent-sync publish add|remove <url>[/dim]\n")


@main.group("publish")
def publish_group():
    """Manage publish repositories.
    
    Commands:
      add <url>     Add a publish repository
      list          List all configured repositories
      remove <url>  Remove a repository
      run           Run interactive publish flow
    
    Examples:
      agent-sync publish add https://github.com/user/repo
      agent-sync publish list
      agent-sync publish remove https://github.com/user/repo
      agent-sync publish run
    
    """
    pass


@publish_group.command("add")
@click.argument("url")
def publish_add(url: str):
    """Add a publish repository.
    
    Examples:
      agent-sync publish add https://github.com/user/repo
    """
    _publish_repos_add(url)


@publish_group.command("list")
def publish_list():
    """List all configured publish repositories."""
    _publish_repos_list()


@publish_group.command("remove")
@click.argument("url")
def publish_remove(url: str):
    """Remove a publish repository.
    
    Examples:
      agent-sync publish remove https://github.com/user/repo
    """
    from .publish.config import remove_source
    success = remove_source(url)
    if success:
        console.print(f"\n[green]✓ Removed: {url}[/green]\n")
    else:
        console.print(f"[yellow]⚠ Not found: {url}[/yellow]\n")



# =============================================================================
# PUBLISH COMMAND
# =============================================================================

# PUBLISH COMMAND
# =============================================================================


@skills_group.command("list")
def list_skills():
    """List and manage skills interactively."""
    from rich.box import ROUNDED
    skills_dir = HUB_DIR

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
        # ─── Clear screen for clean display ───────────────────────────────────
        console.clear()
        
        # ─── Header ───────────────────────────────────────────────────────────
        n = len(skills)
        s = len(selected)
        header = f"[bold]📚 Skills Hub ({n} skills)[/]"
        if s > 0:
            header += f"  |  Selected ({s}): {', '.join(sorted(selected))}"
        if remove_mode:
            header += "  [red]│ REMOVE MODE[/red]"

        console.print(f"\n{header}\n")

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

        # ─── Preview Panel ────────────────────────────────────────────────────
        preview_panel = _build_skill_preview_panel(preview_skill, skills_dir, selected)
        if preview_panel:
            console.print(preview_panel)
            console.print()

        # ─── Footer ───────────────────────────────────────────────────────────
        if remove_mode:
            footer_lines = [
                ("1-N", "[dim] toggle[/dim]"),
                ("a", "[cyan](a)[/cyan]ll"),
                ("n", "[cyan](n)[/cyan]one"),
                ("d", "[cyan](d)[/cyan]eselect"),
                ("Enter", "[cyan]confirm[/cyan]"),
                ("r", "[cyan](r)[/cyan]emove mode"),
                ("q", "[cyan](q)[/cyan]uit"),
            ]
        else:
            footer_lines = [
                ("1-N", "[dim] toggle[/dim]"),
                ("a", "[cyan](a)[/cyan]ll"),
                ("n", "[cyan](n)[/cyan]one"),
                ("d", "[cyan](d)[/cyan]eselect"),
                ("r", "[cyan](r)[/cyan]emove"),
                ("q", "[cyan](q)[/cyan]uit"),
                ("p", "[cyan](p)[/cyan]review"),
            ]
        print_footer(footer_lines, default_key="Enter" if selected else None)

        # ─── Input ───────────────────────────────────────────────────────────
        choice = Prompt.ask("[cyan]›[/cyan]", default="", show_default=False).strip()

        if not choice:
            if preview_skill:
                # Cycle preview through selected skills (or all if none selected)
                sel_list = sorted(selected) if selected else skills
                cur_idx = sel_list.index(preview_skill) + 1 if preview_skill in sel_list else 0
                preview_skill = sel_list[cur_idx % len(sel_list)]
            elif selected:
                preview_skill = sorted(selected)[0]
            elif skills:
                preview_skill = skills[0]
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


def _build_skill_preview_panel(skill_name: str | None, skills_dir: Path, selected: set[str]) -> Panel | None:
    from rich.box import ROUNDED
    
    """Build a rich preview panel for a skill showing full description."""
    if not skill_name:
        return None
    
    skill_path = skills_dir / skill_name
    s_list = sorted(selected) if selected else []
    
    if s_list:
        pos_idx = s_list.index(skill_name) + 1 if skill_name in s_list else 1
        total = len(s_list)
        pos_str = f' ({pos_idx}/{total})' if total > 1 else ''
    else:
        pos_str = ''
    
    lines = []
    skill_md = skill_path / 'SKILL.md'
    if skill_md.exists():
        try:
            md_content = skill_md.read_text()
            if md_content.startswith('---'):
                parts = md_content.split('---', 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1])
                    if fm:
                        name = fm.get('name', skill_name)
                        lines.append(f'[bold cyan]{name}[/bold cyan]')
                        desc = fm.get('description', '')
                        if desc:
                            lines.append(desc)
                        tools = fm.get('allowed-tools', '')
                        if tools:
                            lines.append(f'[dim]tools:[/dim] [yellow]{tools}[/yellow]')
        except:
            pass
    
    try:
        files = sorted([f.name for f in skill_path.iterdir() if f.is_file() and f.name != 'SKILL.md'])
        if files:
            lines.append('')
            lines.append(f'[dim]files ({len(files)}):[/dim]')
            for f in files[:5]:
                lines.append(f'  [dim]  • {f}[/dim]')
            if len(files) > 5:
                lines.append(f'  [dim]  ... (+{len(files)-5} more)[/dim]')
    except:
        pass
    
    return Panel(
        '\n'.join(lines) if lines else '[dim]No preview available[/dim]',
        box=ROUNDED,
        padding=(0, 1, 0, 1),
        title=f'[cyan]{skill_name}[/cyan]{pos_str}',
        title_align='left',
        border_style='dim',
    )


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


@skills_group.command("audit")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (machine-readable)")
@click.option("--limit", "-l", type=int, default=None, help="Maximum number of rows to show (for large outputs).")
@click.option("--filter", "-f", type=str, default=None, help="Only show skills whose name contains this substring.")
def audit_skills(as_json: bool, limit: int | None, filter: str | None):
    """Show every skill's status across the hub and the private repo.

    Compares two sources of truth:
    - Local hub: `~/.agents/skills/`
    - Private repo HEAD: `skills/`

    A skill can be:
    - in_sync: present in both hub and repo
    - in_hub_only: new skill, will be pushed on next push
    - in_repo_only: orphan in the repo (run `push --prune` or `skills prune`)
    """
    from .skills_audit import audit_skills as build_audit

    report = build_audit()

    if as_json:
        import json as _json
        console.print(_json.dumps({
            "hub_count": report.hub_count,
            "repo_count": report.repo_count,
            "summary": report.summary_counts(),
            "rows": [
                {
                    "name": r.name,
                    "in_hub": r.in_hub,
                    "in_repo": r.in_repo,
                    "status": r.status,
                }
                for r in report.rows
                if not filter or filter.lower() in r.name.lower()
            ][:limit],
        }, indent=2))
        return

    summary = report.summary_counts()
    console.print(
        f"\n[bold]Skills audit[/bold] — "
        f"[green]{report.hub_count}[/green] in hub, "
        f"[green]{report.repo_count}[/green] in repo\n"
    )

    # Apply `--filter` (substring match) and `--limit` before rendering
    filtered_rows = list(report.rows)
    if filter:
        filtered_rows = [r for r in filtered_rows if filter.lower() in r.name.lower()]
    if limit is not None:
        filtered_rows = filtered_rows[:limit]

    from rich.table import Table
    table = Table(box=None, show_header=True, header_style="bold dim", pad_edge=False)
    table.add_column("Skill", style="cyan", no_wrap=True)
    table.add_column("Hub", justify="center", width=3)
    table.add_column("Repo", justify="center", width=4)
    table.add_column("Status")

    STATUS_DISPLAY = {
        "in_sync": ("green", "in sync"),
        "in_hub_only": ("green", "new (will push)"),
        "in_repo_only": ("red", "orphan in repo"),
    }

    for row in filtered_rows:
        color, label = STATUS_DISPLAY.get(row.status, ("dim", row.status))
        table.add_row(
            row.name,
            "[green]\u2713[/green]" if row.in_hub else "[dim]\u00b7[/dim]",
            "[green]\u2713[/green]" if row.in_repo else "[dim]\u00b7[/dim]",
            f"[{color}]{label}[/{color}]",
        )

    console.print(table)
    console.print()

    problems = [r for r in filtered_rows if r.status == "in_repo_only"]
    if problems:
        console.print(
            f"[bold red]\u26a0 {len(problems)} orphan(s) in repo (need attention):[/bold red]"
        )
        for r in problems:
            fix = "run `agent-sync skills prune --yes` or `agent-sync push --prune`"
            console.print(f"  [red]\u2022[/red] [cyan]{r.name}[/cyan]: {fix}")
        console.print()
    else:
        console.print("[green]\u2713 No problems found. Hub and repo are in sync.[/green]\n")


@skills_group.command("explain")
@click.argument("name")
def explain_skill_cmd(name: str):
    """Show lifecycle and current state of a single skill.

    Useful for debugging "where did this skill go?". Shows:
    - Current location: hub / repo
    - When it was first added (commit + date)
    - When it was last modified (commit + date)
    - Total commits affecting it
    - File count in the local hub
    """
    from .skills_audit import explain_skill as build_explanation

    expl = build_explanation(name)

    if not expl.in_hub and not expl.in_repo:
        console.print(
            f"\n[yellow]\u26a0 Skill [cyan]{name}[/cyan] is not tracked anywhere "
            f"(not in hub or repo).[/yellow]\n"
        )
        return

    console.print(f"\n[bold]Skill: [cyan]{name}[/cyan][/bold]\n")

    from rich.table import Table
    state_table = Table(box=None, show_header=False, pad_edge=False)
    state_table.add_column("Source", style="bold", width=14)
    state_table.add_column("Status")
    state_table.add_row(
        "Local hub", "[green]present[/green]" if expl.in_hub else "[dim]absent[/dim]"
    )
    state_table.add_row(
        "Repo (HEAD)", "[green]present[/green]" if expl.in_repo else "[dim]absent[/dim]"
    )
    console.print(state_table)
    console.print()

    if expl.commit_count > 0:
        console.print("[bold]Git lifecycle[/bold] (from private repo, [dim]follow renames[/dim]):")
        if expl.first_added:
            console.print(
                f"  First added: [cyan]{expl.first_added[:10]}[/cyan] "
                f"[dim]on {expl.first_added_at}[/dim]"
            )
        if expl.last_modified:
            console.print(
                f"  Last modified: [cyan]{expl.last_modified[:10]}[/cyan] "
                f"[dim]on {expl.last_modified_at}[/dim]"
            )
        console.print(f"  Total commits: {expl.commit_count}")
    else:
        console.print(
            "[dim]No git history for this skill "
            "(it may only exist in the local hub).[/dim]"
        )
    console.print()

    if expl.in_hub:
        console.print(f"[bold]Local files:[/bold] {expl.file_count}")


@skills_group.command("prune")
@click.option("--dry-run", is_flag=True, help="Show what would be pruned; do not modify anything")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt")
def prune_skills(dry_run: bool, yes: bool):
    """Remove orphan skills from the remote repo (in HEAD, missing from local hub).

    Orphan skills accumulate in the private repo when you remove a skill
    from `~/.agents/skills/` without also removing it from the repo. This
    subcommand is the dedicated, safe way to clean them up.

    By default shows a preview and asks for confirmation. Use `--yes` to
    skip the prompt (for scripts), or `--dry-run` to only preview.

    Examples:
      agent-sync skills prune --dry-run    # preview only
      agent-sync skills prune              # preview + ask y/n
      agent-sync skills prune --yes        # execute without prompt
    """
    from .config import Config
    from .sync import SyncManager

    config = Config()
    if not config.repo_url:
        console.print("[red]✗ Not initialized. Run 'agent-sync init' first.[/red]")
        return

    sync_manager = SyncManager(config)
    orphans = sync_manager._detect_orphan_skills()

    if not orphans:
        console.print("[green]✓ No orphan skills — repo and hub are in sync.[/green]\n")
        return

    # Always show the preview (the user needs to see what will change)
    console.print(
        f"\n[bold]Orphan skills in remote repo "
        f"(in HEAD, missing from local hub):[/bold] [red]{len(orphans)}[/red]\n"
    )
    for name in orphans:
        console.print(f"  [red]-[/] skills/{name}/")
    console.print()

    if dry_run:
        console.print("[dim]Dry run — no changes made.[/dim]\n")
        return

    if not yes:
        console.print("[yellow]These skills will be removed from the remote repo in the next commit.[/yellow]")
        if not click.confirm("Proceed?", default=False):
            console.print("[yellow]Cancelled — no changes made.[/yellow]\n")
            return

    # Commit + push the prune
    try:
        sync_manager._run_git("add", ".")
        sync_manager._run_git("commit", "-m", "chore: prune orphan skills from local hub")
        console.print(f"  [dim]🚀 Pushing to {config.repo_url.split('/')[-1]}...[/dim]")
        sync_manager._run_git("push", "origin", "main")
        sync_manager._save_state("pushed", sync_manager.config.repo_url)
        console.print(f"\n[green]✓ Pruned {len(orphans)} orphan skill(s).[/green]\n")
    except subprocess.CalledProcessError as e:
        from .sync import _sanitize_git_output
        console.print(f"\n[red]✗ Prune failed:[/red] {_sanitize_git_output(e.stderr) or e}")


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
        changed = sync_mgr.push(skills_only=True)
        if changed:
            console.print(f"\n[green]✓ Pushed {len(changed)} file(s) to {cfg.repo_url}[/green]")
            console.print(f"\n[dim]Manage repos: agent-sync repos list[/dim]\n")
        else:
            console.print(f"\n[dim]Nothing to push to {cfg.repo_url}[/dim]\n")
@publish_group.command("run")
@click.option("--dry-run", is_flag=True, help="Show what would be published")
@click.option("--repo", "repo_url", help="Set GitHub repository URL")
@click.option("--add-source", "add_source_url", help="Add external skill source")
@click.option("--remove-source", "remove_source_url", help="Remove external skill source")
@click.option("--list-sources", "list_sources_flag", is_flag=True, help="List skill sources")
@click.option("--clear-cache", is_flag=True, help="Clear skill cache")
@click.option("--reset-selection", is_flag=True, help="Reset saved selection")
@click.option("--no-private", is_flag=True, help="Skip auto-sync to the private repo after publishing to public")
def publish(
    dry_run: bool,
    repo_url: Optional[str],
    add_source_url: Optional[str],
    remove_source_url: Optional[str],
    list_sources_flag: bool,
    clear_cache: bool,
    reset_selection: bool,
    no_private: bool,
):
    """Publish skills and agents to a public repository.

    Run without options to select and publish skills & agents interactively.

    After publishing the curated subset to the public repo, the full local
    state is also synced to the private repo (config.repo_url) as a normal
    commit (preserves history). Skip with --no-private or set
    PublishConfig.auto_push_private=false in ~/.config/agent-sync/publish.yaml.

    Examples:

      agent-sync publish                  Select and publish skills & agents
      agent-sync publish --repo URL       Set repository URL
      agent-sync publish --add-source URL  Add external skill source
      agent-sync publish --list-sources   List configured sources
      agent-sync publish --clear-cache    Clear cached repositories
      agent-sync publish --no-private    Publish to public only, skip private sync
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
    # Auto-sync to private repo (convention over configuration)
    # =============================================================================
    # After publishing the curated subset to the public repo (which uses
    # orphan commits + force-push, see git_publish.py), also sync the full
    # local state to the private repo via a normal commit. This preserves
    # the private repo's history (no force, no orphan).
    #
    # Skip when:
    #   - --no-private flag is set (explicit opt-out)
    #   - PublishConfig.auto_push_private is False (config opt-out)
    #   - No private repo configured (config.repo_url is empty)
    #
    # Failures here do NOT abort the publish (public already succeeded).
    if not no_private:
        try:
            from .config import Config
            from .sync import SyncManager
            from .publish.config import load_config as _load_pub_config
            from .sync import _sanitize_git_output

            cfg = Config()
            pub_cfg = _load_pub_config()
            if cfg.repo_url and getattr(pub_cfg, "auto_push_private", True):
                console.print(
                    f"\n[bold]📥 Syncing to private: [cyan]{cfg.repo_url}[/cyan]...[/]"
                )
                sync_manager = SyncManager(cfg)
                try:
                    changed = sync_manager.push(message="chore: sync private after publish")
                except Exception as push_err:
                    err_msg = _sanitize_git_output(str(push_err))
                    console.print(
                        f"[yellow]⚠ Private sync failed (public publish already succeeded): {err_msg}[/yellow]"
                    )
                else:
                    if changed:
                        # Try to get the new HEAD SHA from the local repo
                        sha = ""
                        try:
                            sha = sync_manager._run_git("rev-parse", "HEAD")
                            sha = sha[:7] if sha else ""
                        except Exception:
                            pass
                        sha_str = f" (commit {sha})" if sha else ""
                        console.print(
                            f"[green]✓ Synced {len(changed)} item(s) to private{sha_str}[/green]"
                        )
                        console.print(f"  [dim]→ {cfg.repo_url}[/dim]")
                    else:
                        console.print(
                            f"[dim]No local changes to sync to private ({cfg.repo_url})[/dim]"
                        )
            elif not cfg.repo_url:
                console.print(
                    "\n[dim]No private repo configured (skip auto-sync). "
                    "Run `agent-sync init` to set one.[/dim]"
                )
        except Exception as e:
            # Defensive: never let private sync failure break the publish success message
            console.print(
                f"\n[yellow]⚠ Auto-sync to private failed: {e}[/yellow]"
            )


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
    
    skills_dir = HUB_DIR
    if skills_dir.exists():
        skill_count = len([d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
        console.print(f"\n[cyan]Skills: {skill_count}[/cyan]")


# =============================================================================
# UPDATE COMMAND
# =============================================================================

@main.command()
@click.option("--check", is_flag=True, help="Check for updates only")
def update(check: bool):
    """Update agent-sync to the latest version.
    
    Shows before/after version to confirm the upgrade worked.
    """
    from . import __version__ as current_version
    console.print(f"\n[cyan]Current version: {current_version}[/cyan]")
    
    if check:
        console.print("[yellow]Check mode - use without --check to upgrade[/yellow]\n")
        return
    
    console.print("[cyan]Upgrading...[/cyan]\n")
    
    try:
        result = subprocess.run(
            ["pipx", "upgrade", "agent-sync"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode == 0:
            # Get new version after upgrade
            try:
                from importlib.metadata import version
                new_version = version("agent-sync")
                console.print(f"\n[green]✓ Updated from {current_version} → {new_version}[/green]\n")
            except Exception:
                console.print("\n[green]✓ Updated![/green]\n")
        else:
            console.print("[yellow]⚠ Update failed[/yellow]")
            if result.stderr:
                console.print(result.stderr)
    except subprocess.TimeoutExpired:
        console.print("[red]✗ Update timed out (took >5 minutes)[/red]")
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
