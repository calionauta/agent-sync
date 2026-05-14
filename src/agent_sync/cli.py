"""Main CLI entry point for agent-sync."""

import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import DEFAULT_STATE_DIR, Config
from .sync import SyncManager
from .validators import validate_github_url, validate_repo_name

console = Console()

# Update check configuration
UPDATE_CHECK_FILE = DEFAULT_STATE_DIR / ".last_update_check"
UPDATE_PENDING_FILE = DEFAULT_STATE_DIR / ".pending_update"


def check_for_updates_async():
    """Check for updates once per week, asynchronously."""
    if not _should_check_for_updates():
        return

    # Run in background thread (doesn't block command)
    thread = threading.Thread(target=_check_and_notify, daemon=True)
    thread.start()


def _should_check_for_updates() -> bool:
    """Check if we should check for updates (once per week)."""
    if not UPDATE_CHECK_FILE.exists():
        return True

    try:
        last_check = datetime.fromisoformat(UPDATE_CHECK_FILE.read_text())
        return datetime.now() - last_check > timedelta(days=7)
    except Exception:
        return True


def _check_and_notify():
    """Check for updates and notify if available."""
    try:
        # Try with GITHUB_TOKEN if available (for private repos)
        import os

        import requests
        headers = {}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"

        response = requests.get(
            "https://api.github.com/repos/renatocaliari/agent-sync/releases/latest",
            headers=headers,
            timeout=3,  # Fast timeout
        )

        # If 404, repo might be private or no releases yet
        if response.status_code == 404:
            return

        response.raise_for_status()

        latest = response.json()["tag_name"].lstrip("v")

        if latest > __version__:
            # Save notification so we can show it after command completes
            UPDATE_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
            UPDATE_PENDING_FILE.write_text(f"{latest}|{datetime.now().isoformat()}")

        # Save last check time
        UPDATE_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
        UPDATE_CHECK_FILE.write_text(datetime.now().isoformat())

    except Exception:
        pass  # Silently fail (don't annoy user)


def push_to_github(message: str = "chore: sync updates") -> bool:
    """Push tracked files to GitHub repository.

    Args:
        message: Commit message for the push

    Returns:
        True if push succeeded or nothing to push, False on error
    """
    config = Config()

    if not config.repo_url:
        console.print("[yellow]⚠ No repository configured yet.[/yellow]")
        console.print("Run [green]agent-sync init[/green] to create a repository first.\n")
        return False

    try:
        sync_manager = SyncManager(config)
        pushed = sync_manager.push(message=message)
        _render_push_output(pushed)
        if pushed:
            console.print("💡 On other machines, run [green]agent-sync pull[/green]\n")
        return True
    except Exception as e:
        console.print(f"\n[red]✗ Push failed: {e}[/red]\n")
        console.print("[dim]You can run [green]agent-sync push[/green] manually later.[/dim]\n")
        return False


# ---------------------------------------------------------------------------
# Push output rendering helpers
# ---------------------------------------------------------------------------

_STATUS_ICONS = {
    'added': '🆕',
    'deleted': '🗑️',
    'modified': '📝',
}


def _status_icon(label: str) -> str:
    return _STATUS_ICONS.get(label, '📝')


def _render_group(category: str, group_name: str, items: list[dict]) -> None:
    """Render a sub-group (skill/agent) within a category."""
    labels = set(item['label'] for item in items)

    if len(labels) == 1:
        # All files in this group have the same status → collapse with *
        label = labels.pop()
        icon = _status_icon(label)
        total = sum(item.get('directory_count') or 1 for item in items)
        console.print(
            f"    └── {group_name + '/*':<46} {icon} {label}"
            f" ({total} file{'s' if total != 1 else ''})"
        )
    else:
        # Mixed statuses → show individual files
        for item in items:
            rel = item['path'].rsplit('/', 1)[-1]
            icon = _status_icon(item['label'])
            console.print(f"    └── {rel:<46} {icon} {item['label']}")


def _render_push_output(pushed: list[dict]) -> None:
    """Render pushed files with directory grouping and status indicators."""
    from collections import defaultdict

    if not pushed:
        console.print('\n✓ Nothing to push', style="yellow")
        return

    # Categorize by top-level directory
    top_level = []
    categories: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for item in pushed:
        p = item['path']
        parts = p.split('/', 2)
        if len(parts) >= 2 and parts[0] in ('skills', 'configs', 'agents'):
            categories[parts[0]][parts[1]].append(item)
        else:
            top_level.append(item)

    # Count total
    cat_total = sum(len(v) for cat in categories.values() for v in cat.values())
    total = len(top_level) + cat_total
    console.print(f'\n✅ Pushed {total} file{"s" if total != 1 else ""}:')

    # Top-level files (manifest, etc.)
    for item in top_level:
        icon = _status_icon(item['label'])
        console.print(f'  • {item["path"]:<50} {icon} {item["label"]}')

    # Grouped categories
    for cat_name in ('skills', 'configs', 'agents'):
        if cat_name not in categories:
            continue
        groups = categories[cat_name]
        group_count = sum(len(v) for v in groups.values())
        console.print(f'  📂 {cat_name}/ ({group_count} file{"s" if group_count != 1 else ""})')
        for group_name, items in sorted(groups.items()):
            _render_group(cat_name, group_name, items)

    console.print()


def show_pending_update_notification():
    """Show update notification if one is pending."""
    if not UPDATE_PENDING_FILE.exists():
        return

    try:
        latest, timestamp = UPDATE_PENDING_FILE.read_text().split("|")
        console.print(f"\n[dim]✨ Update available: v{latest} (Run 'agent-sync update' to install)[/dim]\n")

        # Clear notification
        UPDATE_PENDING_FILE.unlink()
    except Exception:
        pass  # Silently fail


class ExtendedHelpGroup(click.Group):
    """Custom Click group to show categorization and vertical tree structure in help."""

    def format_commands(self, ctx, formatter):
        # 1. Define Categories
        categories = {
            "🔄 Sync Commands": ["push", "pull", "status"],
            "🤖 Agent Management": ["agents", "enable", "disable"],
            "⚙️  Configuration": ["setup", "init", "link", "config", "generate-config"],
            "📚 Skills & Agents": ["skills", "custom-agents"],
            "🛠️  System": ["update", "version", "secrets"]
        }

        # Get all commands available in this group
        all_commands = {name: self.get_command(ctx, name) for name in self.list_commands(ctx)}

        for category, cmd_names in categories.items():
            category_commands = []

            for name in cmd_names:
                cmd = all_commands.get(name)
                if not cmd or cmd.hidden:
                    continue

                # Main Command Description
                help_text = cmd.get_short_help_str()

                # If it's NOT a group, show its options
                if not isinstance(cmd, click.Group):
                    opts = [p.opts[0] for p in cmd.params if isinstance(p, click.Option)]
                    if opts:
                        help_text += f" [{', '.join(opts)}]"

                category_commands.append((name, help_text))

                # If it IS a group, list its subcommands vertically
                if isinstance(cmd, click.Group):
                    sub_names = cmd.list_commands(ctx)
                    for i, sub_name in enumerate(sub_names):
                        sub_cmd = cmd.get_command(ctx, sub_name)
                        if sub_cmd:
                            is_last = (i == len(sub_names) - 1)
                            tree_char = "└──" if is_last else "├──"

                            sub_help = sub_cmd.get_short_help_str()
                            sub_opts = [p.opts[0] for p in sub_cmd.params if isinstance(p, click.Option)]
                            if sub_opts:
                                sub_help += f" [{', '.join(sub_opts)}]"

                            # Indented with tree structure
                            category_commands.append((f"  {tree_char} {sub_name}", sub_help))

            if category_commands:
                with formatter.section(category):
                    formatter.write_dl(category_commands)


@click.group(cls=ExtendedHelpGroup)
@click.version_option(version=__version__, prog_name="agent-sync")
def main():
    """
    🔄 agent-sync - Sync configs and skills across multiple AI agents.

    Supported agents: opencode, claude-code, gemini-cli, pi.dev, qwen-code
    """
    pass


@main.command()
@click.option("--name", help="Repository name (skips wizard if provided)")
@click.option("--agents", multiple=True, help="Agents to sync (skips wizard if provided)")
@click.option("--no-wizard", is_flag=True, help="Skip interactive wizard")
@click.option("--force", is_flag=True, help="Force initialization even if already configured")
def init(name: str | None, agents: tuple[str, ...], no_wizard: bool, force: bool):
    """Initialize a new sync repository (first machine).

    Runs the setup wizard and creates a new GitHub repository.

    \b
    Examples:
      # Interactive wizard (creates new repo)
      agent-sync init

      # Create specific repo name (non-interactive)
      agent-sync init --name agent-sync-private-configs

      # Force re-initialize (overwrites existing config)
      agent-sync init --name new-configs --force

    \b
    ⚠️ SECURITY:
      - Repositories are ALWAYS PRIVATE for configs
      - Configs may contain API keys and tokens
      - GitHub private repos are FREE for personal use
    """
    from .setup import run_setup_wizard

    # Check if config already exists
    config = Config()
    if config.repo_url and not force:
        console.print("\n[yellow]⚠ Already configured![/yellow]")
        console.print(f"   Repository: {config.repo_url}")
        console.print("\n💡 Options:")
        console.print("   - Use [green]agent-sync config repo[/green] to view/change repository")
        console.print("   - Use [green]agent-sync setup[/green] to reconfigure agents")
        console.print("   - Use [green]agent-sync init --force[/green] to overwrite existing config\n")
        return

    if config.repo_url and force:
        console.print("\n[yellow]⚠ Forcing re-initialization![/yellow]")
        console.print(f"   Existing repository: {config.repo_url}")
        console.print("   This will overwrite your local configuration.\n")

    # Run wizard if not provided via CLI args
    if not name and not no_wizard:
        console.print("\n[bold]Running setup wizard...[/]\n")
        repo_config = run_setup_wizard()

        if not repo_config:
            console.print("\n[yellow]Setup cancelled[/yellow]")
            raise click.Abort()

        name = repo_config["name"]
        # Always private for security
        private = True
        agents = repo_config["agents"]
    else:
        # Non-interactive: always private
        private = True

    if not name:
        console.print("[red]✗ Repository name is required[/red]")
        console.print("\n💡 Provide a name with --name or use the wizard")
        console.print("   Example: [green]agent-sync init --name agent-sync-private-configs[/green]\n")
        raise click.Abort()

    if not validate_repo_name(name):
        console.print(f"\n[red]✗ Invalid repository name: {name}[/red]")
        console.print("   Only alphanumeric characters, hyphens, underscores, and periods are allowed.")
        console.print("   Cannot start with a hyphen.\n")
        raise click.Abort()

    console.print(f"\n🚀 Initializing sync repository: {name}")
    console.print("[dim]Repository will be PRIVATE (for security)[/dim]\n")

    sync_manager = SyncManager(config)

    try:
        repo_url = sync_manager.init_repo(name=name, private=private, agents=agents)
        console.print(f"\n✅ Repository created: {repo_url}")
        console.print("\n📝 Next steps:")
        console.print("  1. Run 'agent-sync push' to upload your configs")
        console.print("  2. On other machines, run 'agent-sync link <repo-url>'")
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        raise click.Abort()


@main.command()
def setup():
    """Run the interactive setup wizard to configure or reconfigure.

    This can be used:
    - On first time setup
    - To add/remove agents
    - To change sync options
    - To reconfigure repository settings
    """
    from .setup import run_setup_wizard

    config = Config()

    if config.repo_url:
        console.print("\n[yellow]⚠ You already have an existing configuration![/yellow]")
        console.print(f"   Repository: {config.repo_url}")
        console.print("\nThis will [bold]overwrite[/] your current configuration.")
        console.print()

        if not Confirm.ask("Continue?", default=False):
            console.print("\n[yellow]Setup cancelled[/yellow]")
            return

        console.print("\n[bold]🔄 Reconfiguring Agent Sync[/]\n")
    else:
        console.print("\n[bold]🔄 Agent Sync Setup Wizard[/]\n")

    repo_config = run_setup_wizard()

    if repo_config:
        console.print("\n[green]✓ Setup complete![/green]")

        if config.repo_url:
            console.print("\n💡 Your repository URL is still the same.")
            console.print("   Run 'agent-sync push' to sync new configuration")
        else:
            console.print("\n💡 Run 'agent-sync init' to create a new repository")
            console.print("   Or 'agent-sync link <url>' to connect to existing one")
    else:
        console.print("\n[yellow]Setup cancelled[/yellow]")


@main.group(cls=ExtendedHelpGroup)
def config():
    """Manage configuration (view, edit, reset)."""
    pass


@config.command()
def show():
    """Show current configuration."""
    from rich.panel import Panel

    config = Config()

    console.print("\n[bold]📋 Current Configuration[/]\n")

    if not config.repo_url:
        console.print("[yellow]⚠ Not configured yet. Run 'agent-sync setup'[/yellow]\n")
        return

    # Show repo info
    console.print(Panel(f"[cyan]Repository:[/cyan] {config.repo_url}", border_style="blue"))
    console.print()

    # Show agents
    console.print("[bold]Enabled Agents:[/]")
    for agent_name in config.agents:
        if config.is_agent_enabled(agent_name):
            sync_opts = config.get_sync_options(agent_name)
            configs = "configs" if sync_opts.get("configs") else ""
            sync_str = ", ".join(filter(None, [configs])) or "skills only"
            console.print(f"  ✓ {agent_name}: {sync_str}")
        else:
            console.print(f"  ✗ {agent_name} [dim](disabled)[/dim]")
    console.print()

    # Show config file path
    console.print(f"[dim]Config file: {config.config_path}[/dim]\n")


@config.command()
@click.option("--dry-run", is_flag=True, help="Show what would be exported without creating a file")
@click.option("--output", type=click.Path(), default=None, help="Output path (default: ~/.agents/config.json)")
def export(dry_run: bool, output: str | None):
    """Export configuration to DotAgents JSON format.

    Creates a ~/.agents/config.json file compatible with the DotAgents Protocol.

    \b
    Examples:
      # Export to default location (~/.agents/config.json)
      agent-sync config export

      # Preview without creating file
      agent-sync config export --dry-run

      # Export to custom location
      agent-sync config export --output /custom/path/config.json
    """
    from pathlib import Path
    from rich.console import Console

    from .config_exporter import ConfigExporter
    from agent_sync.agents import GLOBAL_SKILLS_DIR

    console = Console()
    output_path = Path(output) if output else Path.home() / ".agents" / "config.json"

    exporter = ConfigExporter()

    if dry_run:
        console.print("\n[bold]📋 DotAgents Config Preview[/bold]\n")
        console.print(f"[dim]Would export to: {output_path}[/dim]\n")
        data = exporter.export()
        console.print_json(data=exporter.export())
        console.print()
    else:
        exporter.save(output_path)
        console.print(f"\n[green]✓[/green] Config exported to {output_path}")
        console.print(f"[dim]Skills hub: {GLOBAL_SKILLS_DIR}[/dim]\n")


@config.command()
@click.argument("repo_url", required=False)
@click.option("--remove", is_flag=True, help="Remove repository configuration")
def repo(repo_url: str | None, remove: bool):
    """View or set the GitHub repository URL.

    \b
    Examples:
      # View current repository
      agent-sync config repo

      # Set repository URL
      agent-sync config repo https://github.com/user/repo.git

      # Remove repository configuration
      agent-sync config repo --remove
    """
    config = Config()

    if remove:
        if not config.repo_url:
            console.print("\n[yellow]No repository configured[/yellow]\n")
            return

        old_url = config.repo_url
        config.repo_url = None
        console.print("\n[green]✓ Repository configuration removed[/green]")
        console.print(f"  Was: {old_url}")
        console.print("\n[dim]Your local files are still intact.[/dim]")
        console.print("[dim]Run 'agent-sync config repo <url>' to configure again.[/dim]\n")
        return

    if repo_url:
        # Set repository URL
        if not validate_github_url(repo_url):
            console.print("\n[red]✗ Invalid repository URL[/red]")
            console.print("   Expected: https://github.com/user/repo.git")
            console.print(f"   Got: {repo_url}\n")
            return

        config.repo_url = repo_url
        console.print("\n[green]✓ Repository configured[/green]")
        console.print(f"  URL: {repo_url}")
        console.print("\n💡 Run 'agent-sync pull' to download configs")
        console.print("   Run 'agent-sync push' to upload configs\n")
        return

    # View current repository
    if not config.repo_url:
        console.print("\n[yellow]⚠ Not configured yet[/yellow]\n")
        console.print("Configure a repository with:")
        console.print("  [green]agent-sync config repo https://github.com/user/repo.git[/green]\n")
        console.print("Or create a new one with:")
        console.print("  [green]agent-sync init --name my-configs[/green]\n")
        return

    console.print(f"\n[cyan]📦 Repository:[/cyan] {config.repo_url}\n")
    console.print("[dim]Use 'agent-sync config repo --remove' to disconnect.[/dim]\n")


@config.command()
def edit():
    """Open configuration file in editor."""
    import subprocess

    config = Config()

    if not config.config_path.exists():
        config.generate_default()

    # Try to open with default editor
    editor = os.environ.get("EDITOR", "nano")

    try:
        subprocess.run([editor, str(config.config_path)])
        console.print("\n[green]✓ Configuration saved[/green]\n")
    except FileNotFoundError:
        console.print(f"\n[yellow]Editor '{editor}' not found[/yellow]")
        console.print(f"Edit manually: {config.config_path}\n")


@config.command()
@click.confirmation_option(prompt="Are you sure you want to reset configuration?")
def reset():
    """Reset configuration to defaults (keeps repo linked)."""

    config = Config()

    if not config.repo_url:
        console.print("\n[yellow]No configuration to reset[/yellow]\n")
        return

    repo_url = config.repo_url

    # Generate fresh default config
    config.generate_default()
    config.repo_url = repo_url

    console.print("\n[green]✓ Configuration reset to defaults[/green]")
    console.print(f"  Repository: {repo_url}")
    console.print("\n💡 Run 'agent-sync setup' to reconfigure\n")


@main.group(cls=ExtendedHelpGroup)
def skills():
    """Manage global skills."""
    pass


@skills.command("list")
def list_skills():
    """List all centralized skills."""
    from rich import box
    from rich.table import Table

    skills_dir = Path.home() / ".agents" / "skills"

    if not skills_dir.exists():
        console.print("\n[yellow]No skills directory found.[/yellow]")
        console.print("Run [green]`agent-sync skills centralize`[/green] to centralize skills.\n")
        return

    skills = []
    for item in skills_dir.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            skills.append({
                "name": item.name,
                "path": str(item),
                "valid": True
            })
        elif item.is_file() and item.suffix in [".md", ".py", ".sh"]:
            skills.append({
                "name": item.name,
                "path": str(item),
                "valid": False
            })

    if not skills:
        console.print("\n[yellow]No skills found in ~/.agents/skills/[/yellow]\n")
        return

    console.print(f"\n[bold]📚 Centralized Skills ({len(skills)})[/]\n")

    table = Table(box=box.SIMPLE)
    table.add_column("Status", style="green")
    table.add_column("Skill Name", style="cyan")
    table.add_column("Path", style="dim")

    for skill in sorted(skills, key=lambda s: s["name"]):
        icon = "✓" if skill["valid"] else "⚠"
        "Valid" if skill["valid"] else "File (no SKILL.md)"
        table.add_row(icon, skill["name"], skill["path"])

    console.print(table)
    console.print()


@main.group(cls=ExtendedHelpGroup)
def custom_agents():
    """Manage custom agents (.claude/agents/, .opencode/agents/)."""
    pass


@custom_agents.command("list")
def list_custom_agents():
    """List custom agents for all supported agents."""
    from rich import box
    from rich.table import Table

    from .agents import get_all_agents

    console.print("\n[bold]🤖 Custom Agents\n[/]\n")

    table = Table(box=box.SIMPLE)
    table.add_column("Agent", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Path", style="dim")
    table.add_column("Files", style="green")

    found_any = False

    for agent in get_all_agents():
        if not agent.supports_custom_agents():
            continue

        # Check project-level agents
        if agent.agents_path and agent.agents_path.exists():
            found_any = True
            agent_files = list(agent.agents_path.rglob("*.md"))
            if agent_files:
                table.add_row(
                    agent.name,
                    "Project",
                    str(agent.agents_path),
                    str(len(agent_files))
                )

        # Check global agents
        if agent.agents_path_global and agent.agents_path_global.exists():
            found_any = True
            agent_files = list(agent.agents_path_global.rglob("*.md"))
            if agent_files:
                table.add_row(
                    agent.name,
                    "Global",
                    str(agent.agents_path_global),
                    str(len(agent_files))
                )

    if not found_any:
        console.print("[yellow]No custom agents found.[/yellow]\n")
        console.print("Custom agents are stored in:")
        console.print("  • [dim]~/.claude/agents/[/dim] - Claude Code global agents")
        console.print("  • [dim].claude/agents/[/dim] - Claude Code project agents")
        console.print("  • [dim]~/.config/opencode/agents/[/dim] - OpenCode global agents")
        console.print("  • [dim].opencode/agents/[/dim] - OpenCode project agents\n")
        return

    console.print(table)
    console.print()


@skills.command()
def diff():
    """Show differences between local and remote skills.

    \b
    Compares skills in ~/.agents/skills/ with skills in GitHub repository.
    Shows which skills exist only locally or only remotely.

    \b
    Examples:
      # Show differences
      agent-sync skills diff

      # Check if in sync
      agent-sync skills diff  # Shows "✓ Local and remote are in sync" if matched
    """
    from .skills_diff import SkillsDiff

    diff_mgr = SkillsDiff()

    if not diff_mgr.repo_dir:
        console.print("[yellow]⚠ No repository configured yet.[/yellow]")
        console.print("Run [green]agent-sync init[/green] or [green]agent-sync link[/green] first.\n")
        return

    diff_mgr.show_diff()


@skills.command()
@click.option("--auto", is_flag=True, help="Auto-resolve: keep local for all divergences")
@click.option("--dry-run", is_flag=True, help="Show what would be done without applying")
def reconcile(auto: bool, dry_run: bool):
    """Reconcile differences between local and remote skills.

    \b
    Resolves divergences where skills exist only locally or only remotely.

    \b
    Examples:
      # Interactive reconciliation
      agent-sync skills reconcile

      # Auto-resolve (keep local for all)
      agent-sync skills reconcile --auto

      # Dry run (preview)
      agent-sync skills reconcile --dry-run

    \b
    Actions:
      - Local-only skills: Will be added to remote on next push
      - Remote-only skills: Choose to download or delete from remote
    """
    from rich.prompt import Confirm

    from .skills_reconcile import SkillsReconcile

    reconcile_mgr = SkillsReconcile()

    if not reconcile_mgr.repo_dir:
        console.print("[yellow]⚠ No repository configured yet.[/yellow]")
        console.print("Run [green]agent-sync init[/green] or [green]agent-sync link[/green] first.\n")
        return

    # Get decisions
    if auto:
        # Auto mode: keep local for everything
        from .skills_diff import SkillsDiff
        diff_mgr = SkillsDiff()
        diff_result = diff_mgr.diff()

        decisions = {}
        for skill in diff_result["local_only"]:
            decisions[skill] = "local"
        for skill in diff_result["remote_only"]:
            decisions[skill] = "remote"  # Download to local

        if not decisions:
            console.print("[green]✓ No divergences to reconcile[/green]\n")
            return

        console.print(f"[bold]Auto mode: {len(decisions)} skills will be reconciled[/]\n")
    else:
        # Interactive mode
        decisions = reconcile_mgr.reconcile_interactive()

        if not decisions:
            return

        if not dry_run:
            if not Confirm.ask("Apply these changes?", default=True):
                console.print("\n[yellow]Reconciliation cancelled.[/yellow]\n")
                return

    # Apply decisions
    stats = reconcile_mgr.apply_decisions(decisions, dry_run=dry_run)
    reconcile_mgr.show_summary(stats)

    # Ask if user wants to push
    if not dry_run and (stats["added_to_remote"] > 0 or stats["downloaded_to_local"] > 0):
        from rich.prompt import Confirm

        should_push = Confirm.ask(
            "\n[bold]Would you like to push these changes to GitHub now?[/]",
            default=True,
        )

        if should_push:
            console.print("\n[bold]📤 Pushing to GitHub...[/]\n")
            push_to_github(message="chore: reconcile skills")


@skills.command()
@click.argument("skill_names", nargs=-1, required=False)
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without actually deleting")
@click.option("--push", is_flag=True, help="Automatically push to GitHub after deleting")
@click.option("--interactive/--no-interactive", default=True, help="Toggle interactive TUI selection")
def delete(skill_names: tuple[str, ...], dry_run: bool, push: bool, interactive: bool):
    """Delete skills from hub and all agent directories.

    \b
    Examples:
      # Interactive selection (default)
      agent-sync skills delete

      # Delete specific skills
      agent-sync skills delete my-skill another-skill

      # Dry run (see what would be deleted)
      agent-sync skills delete my-skill --dry-run

      # Delete and push to GitHub
      agent-sync skills delete my-skill --push

    \b
    What happens:
      1. Deletes skills from ~/.agents/skills/ (hub)
      2. Deletes copies from all agent directories
      3. Optionally pushes changes to GitHub

    \b
    Note: To delete ALL skills, use interactive mode and type 'all'.
    """
    from rich import box
    from rich.prompt import Confirm, Prompt
    from rich.table import Table

    from ._selection import parse_multiselect_input
    from .skills_delete import SkillsDeleter

    deleter = SkillsDeleter()

    # Get list of all available skills
    all_skills = deleter.list_skills()

    if not all_skills:
        console.print("[yellow]No skills found in ~/.agents/skills/[/yellow]\n")
        return

    # Determine which skills to delete
    skills_to_delete = set()

    if skill_names:
        # Validate provided skill names
        from .validators import validate_skill_name
        for name in skill_names:
            if not validate_skill_name(name):
                console.print(f"[red]✗ Invalid skill name: {name}[/red]")
                console.print("[dim]Skill names must be alphanumeric and can contain hyphens, underscores, and periods.[/dim]")
                raise click.Abort()
        skills_to_delete = set(skill_names)
    elif interactive:
        # Interactive TUI selection
        console.print("\n[bold red]🗑 Select Skills to Delete[/bold red]\n")

        selected = set()

        while True:
            table = Table(box=box.SIMPLE)
            table.add_column("#", style="dim", width=4)
            table.add_column("Status", style="green", width=8)
            table.add_column("Skill Name", style="cyan")

            for idx, name in enumerate(sorted(all_skills), 1):
                status = "[red]✓ DEL[/]" if name in selected else ""
                table.add_row(f"{idx}.", status, name)

            console.print(table)
            console.print(f"\n[dim]Selected: {len(selected)} / {len(all_skills)} skills[/dim]\n")
            console.print("[bold]Controls:[/bold]")
            console.print("  • Enter numbers to toggle (e.g. [green]'1,3,5'[/green])")
            console.print("  • Type [cyan]'all'[/cyan] or [cyan]'none'[/cyan]")
            console.print("  • Press [bold white]Enter[/] when done")

            choice = Prompt.ask("\nSelection", default="done")
            result = parse_multiselect_input(choice, all_skills, selected)
            if result is None:
                break
            selected = result

        skills_to_delete = selected
    else:
        console.print("[yellow]No skills specified.[/yellow]\n")
        console.print("Usage: [green]agent-sync skills delete <skill-name> [skill-name...][/green]\n")
        console.print("Or run interactively: [green]agent-sync skills delete[/green]\n")
        return

    if not skills_to_delete:
        console.print("[yellow]No skills selected for deletion.[/yellow]\n")
        return

    # Show confirmation
    console.print(f"\n[bold red]⚠ Skills to be deleted ({len(skills_to_delete)}):[/]\n")

    for name in sorted(skills_to_delete):
        console.print(f"  • {name}")

    console.print()

    if not dry_run:
        if not Confirm.ask("Continue with deletion?", default=True):
            console.print("\n[yellow]Deletion cancelled.[/yellow]\n")
            return

    # Delete skills
    stats = deleter.delete_skills(list(skills_to_delete), dry_run=dry_run)

    # Show summary
    console.print("\n[bold]📊 Summary:[/]\n")

    if dry_run:
        console.print(f"  [yellow]Would delete {stats['deleted_from_hub']} skills ({stats['hub_files']} files) from hub[/yellow]")
        console.print(f"  [yellow]Would delete {stats['deleted_from_agents']} agent copies ({stats['agent_files']} files)[/yellow]")
    else:
        total_files = stats['hub_files'] + stats['agent_files']
        console.print(f"  [green]✓ Deleted {stats['deleted_from_hub']} skills[/green] ({stats['hub_files']} files from hub)")
        console.print(f"  [green]✓ Deleted {stats['deleted_from_agents']} agent copies[/green] ({stats['agent_files']} files)")
        console.print(f"\n  [dim]Total: {total_files} files removed[/dim]")

    if stats["not_found"] > 0:
        console.print(f"  [yellow]⚠ {stats['not_found']} skills not found[/yellow]")
    if stats["errors"] > 0:
        console.print(f"  [red]✗ {stats['errors']} errors[/red]")

    console.print()

    # Ask if user wants to push
    should_push = push

    if not should_push and not dry_run:
        should_push = Confirm.ask(
            "[bold]Would you like to push these changes to GitHub now?[/]",
            default=True,
        )

    if should_push and not dry_run:
        console.print("\n[bold]📤 Pushing to GitHub...[/]\n")
        push_to_github(message="chore: delete skills")
    elif not dry_run:
        console.print("💡 Run [green]agent-sync push[/green] to sync to GitHub\n")


@skills.command()
@click.option("--copy", is_flag=True, help="Copy instead of moving skills")
@click.option("--push", is_flag=True, help="Automatically push to GitHub after centralizing")
@click.option("--distribute", is_flag=True, help="After centralizing, copy all skills to all agent directories (for backup or testing)")
@click.option("--yes", is_flag=True, help="Non-interactive: skip all orphans, auto-keep")
@click.option("--import-all", is_flag=True, help="Import all orphans without TUI (old behavior)")
@click.option("--dry-run", is_flag=True, help="Show what would be done without changing anything")
def centralize(copy: bool, push: bool, distribute: bool,
               yes: bool, import_all: bool, dry_run: bool):
    """Centralize skills from all agents to ~/.agents/skills/.

    This command scans all agent directories for existing skills and centralizes
    them to the global ~/.agents/skills/ directory (single source of truth).

    \b
    Examples:
      # Move skills (default - removes from agent directories)
      agent-sync skills centralize

      # Copy skills (keeps originals in agent directories)
      agent-sync skills centralize --copy

      # Move skills and push to GitHub automatically
      agent-sync skills centralize --push

      # Copy skills and push to GitHub
      agent-sync skills centralize --copy --push

      # Centralize AND copy to all agent directories (backup/testing)
      agent-sync skills centralize --distribute

    \b
    What happens:
      1. Scans all agent directories for skills
      2. Detects conflicts (same skill name in multiple agents)
      3. Resolves conflicts by renaming with agent prefix
      4. Moves/copies skills to ~/.agents/skills/
      5. Optionally pushes to GitHub
      6. With --distribute: copies all skills to all agent directories

    \b
    After centralizing:
      - Skills live in ~/.agents/skills/ (source of truth)
      - Agents use symlinks or config to access global skills
      - Original skill directories may be removed (if --copy not used)
      - With --distribute: all agents have local copies for backup/testing
    """
    from rich.prompt import Confirm

    from .skills import SkillsManager

    # Ensure DotAgents structure (.agents/ directory)
    from .centralize.handlers.dot_agents_handler import DotAgentsHandler
    handler = DotAgentsHandler()
    handler.ensure_structure(dry_run=dry_run)
    console.print()

    move = not copy
    action = "Copying" if copy else "Moving"

    console.print(f"\n[bold]📁 {action} Skills[/]\n")

    skills_mgr = SkillsManager()
    stats = skills_mgr.centralize(move=move, skip_orphans=yes,
                                 import_all=import_all, dry_run=dry_run)

    # Show final reassurance
    console.print("[bold green]🎉 Centralization Complete![/bold green]\n")
    console.print("What happened:\n")

    if move:
        console.print(f"  ✓ [green]{stats['moved']} skills moved[/green] to ~/.agents/skills/")
        console.print("    [dim]Original files removed from agent directories[/dim]\n")
    else:
        console.print(f"  ✓ [green]{stats['copied']} skills copied[/green] to ~/.agents/skills/")
        console.print("    [dim]Original files kept in agent directories[/dim]\n")

    if stats['symlinks_removed'] > 0:
        console.print(f"  ✓ [yellow]{stats['symlinks_removed']} user symlinks removed[/yellow]")
        console.print("    [dim]Cleaning up manual symlinks from agent directories[/dim]\n")

    if stats['conflicts_resolved'] > 0:
        console.print(f"  ✓ [yellow]{stats['conflicts_resolved']} conflicts resolved[/yellow]")
        console.print("    [dim]Duplicate skill names renamed with agent prefix[/dim]\n")

    console.print("Where are my skills now?\n")
    console.print("  [bold cyan]~/.agents/skills/[/bold cyan] [dim]← Single source of truth[/dim]\n")
    console.print("All your skills are now in one place and will be synced to GitHub.\n")

    if move:
        console.print("[dim]Note: Agent directories now use symlinks or config to read from ~/.agents/skills/[/dim]\n")

    # Optional: distribute skills to all agent directories
    if distribute:
        console.print("\n[bold]📤 Distributing Skills to All Agents[/]\n")
        console.print("[yellow]⚠ This will copy ALL skills to ALL agent directories.[/yellow]\n")
        console.print("Use this for:")
        console.print("  • Backup: local copies in each agent directory")
        console.print("  • Testing: verify agents read from local vs global")
        console.print("  • Debug: troubleshoot symlink/config issues\n")

        if Confirm.ask("Continue with distribution?", default=True):
            dist_stats = skills_mgr.distribute_to_all_agents()
            console.print(f"\n[green]✓ Distributed {dist_stats['distributed']} skills to {dist_stats['agents_configured']} agents[/green]\n")
            console.print("[dim]Note: Native agents (pi.dev, qwen-code) will still prefer ~/.agents/skills/[/dim]\n")
        else:
            console.print("\n[yellow]⚠ Distribution skipped[/yellow]\n")

    # Ask if user wants to push
    should_push = push

    if not should_push:
        should_push = Confirm.ask(
            "\n[bold]Would you like to push these changes to GitHub now?[/]",
            default=True,
        )

    if should_push:
        console.print("\n[bold]📤 Pushing to GitHub...[/]\n")
        push_to_github(message="chore: centralize skills")
    else:
        console.print("💡 Run [green]agent-sync push[/green] to sync to GitHub\n")


@skills.command()
@click.option("--repo", "repo_url", help="GitHub repository URL for publishing skills")
@click.option("--dry-run", is_flag=True, help="Show what would be published without actually publishing")
@click.option("--interactive/--no-interactive", default=True, help="Toggle interactive TUI selection")
def publish(repo_url: str | None, dry_run: bool, interactive: bool):
    """Publish selected skills to a public GitHub repository."""
    from .publish import publish_skills
    success = publish_skills(repo_url=repo_url, dry_run=dry_run, interactive=interactive)
    if not success:
        raise click.Abort()


@main.command()
@click.argument("repo_url")
def link(repo_url: str):
    """Link to an existing sync repository (additional machines)."""
    if not validate_github_url(repo_url):
        console.print("\n[red]✗ Invalid repository URL[/red]")
        console.print("   Expected: https://github.com/user/repo.git")
        console.print(f"   Got: {repo_url}\n")
        raise click.Abort()

    console.print(f"\n🔗 Linking to repository: {repo_url}")

    config = Config()
    sync_manager = SyncManager(config)

    try:
        sync_manager.link_repo(repo_url)
        console.print("\n✅ Successfully linked to repository")
        console.print("\n📥 Run 'agent-sync pull' to download configs")
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        raise click.Abort()


@main.command()
@click.option("--force", is_flag=True, help="Force pull even with local changes")
@click.option("--skills-only", is_flag=True, help="Pull only skills (not configs)")
@click.option("--configs-only", is_flag=True, help="Pull only configs (not skills)")
@click.option("--agents-only", is_flag=True, help="Pull only custom agents (not configs or skills)")
def pull(force: bool, skills_only: bool, configs_only: bool, agents_only: bool):
    """Fetch and apply remote configuration.

    Restores global skills, extension skills, symlinks, and custom agents automatically.

    Examples:
      # Pull everything (default)
      agent-sync pull

      # Pull only skills
      agent-sync pull --skills-only

      # Pull only configs
      agent-sync pull --configs-only

      # Pull only custom agents
      agent-sync pull --agents-only

      # Force pull (overwrite local changes)
      agent-sync pull --force
    """
    console.print("\n📥 Pulling remote configuration...")

    # Check for updates asynchronously (once per week)
    check_for_updates_async()

    config = Config()
    sync_manager = SyncManager(config)

    try:
        changes = sync_manager.pull(force=force, skills_only=skills_only, configs_only=configs_only, agents_only=agents_only)
        if changes:
            console.print(f"\n✅ Applied {len(changes)} changes:")
            for change in changes:
                console.print(f"  • {change}", style="green")
        else:
            console.print("\n✓ Already up to date", style="yellow")
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        raise click.Abort()

    # Show update notification if available
    show_pending_update_notification()


@main.command()
@click.option("-m", "--message", default="chore: sync config updates", help="Commit message")
@click.option("--skills-only", is_flag=True, help="Push only skills (not configs)")
@click.option("--configs-only", is_flag=True, help="Push only configs (not skills)")
@click.option("--agents-only", is_flag=True, help="Push only custom agents (not configs or skills)")
def push(message: str, skills_only: bool, configs_only: bool, agents_only: bool):
    """Commit and push local changes.

    Backs up global skills, extension skills, symlinks, and custom agents automatically.

    Examples:
      # Push everything (default)
      agent-sync push

      # Push only skills
      agent-sync push --skills-only

      # Push only configs
      agent-sync push --configs-only

      # Push only custom agents
      agent-sync push --agents-only

      # Push with custom message
      agent-sync push -m "feat: add new skill"
    """
    console.print("\n📤 Pushing local changes...")

    # Check for updates asynchronously (once per week)
    check_for_updates_async()

    config = Config()
    sync_manager = SyncManager(config)

    try:
        pushed = sync_manager.push(message=message, skills_only=skills_only, configs_only=configs_only, agents_only=agents_only)
        _render_push_output(pushed)
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        raise click.Abort()

    # Show update notification if available
    show_pending_update_notification()


@main.command()
@click.option("--dry-run", is_flag=True, help="Show merge preview without creating file")
@click.option("--force", is_flag=True, help="Overwrite existing ~/.agents/mcp.json")
@click.option("--conflicts", is_flag=True, help="Show only conflict report")
@click.option("--source", "-s", multiple=True, type=click.Path(exists=True), help="Additional MCP config sources")
@click.option("--output", type=click.Path(), default=None, help="Output path")
def mcp(dry_run: bool, force: bool, conflicts: bool, source: tuple[str, ...], output: str | None):
    """Export unified MCP configuration.

    Scans vendor MCP configs and merges them into ~/.agents/mcp.json.
    Does NOT modify vendor configs — creates a unified DotAgents-compatible file.

    \b
    Examples:
      # Scan and preview merge
      agent-sync mcp --dry-run

      # Export unified MCP config
      agent-sync mcp --force

      # Show only conflicts
      agent-sync mcp --conflicts

      # Add custom sources
      agent-sync mcp --force -s ~/.custom/mcp.json
    """
    from pathlib import Path

    from .mcp_merger import MCPMerger

    sources = [Path(s) for s in source]
    merger = MCPMerger(sources=sources if sources else None)

    # Find MCP configs
    found = merger.find_mcp_configs()
    if not found and not sources:
        console.print("[yellow]⚠ No MCP configs found in known locations.[/yellow]")
        console.print("[dim]Known locations: ~/.claude/mcp.json, ~/.cursor/mcp.json[/dim]")
        console.print("[dim]Use --source to specify custom locations.[/dim]\n")
        return

    console.print("\n[bold]📋 MCP Config Sources[/bold]\n")
    for src in (found + sources):
        console.print(f"  • {src}")
    console.print()

    # Merge
    merger.merge()

    # Show conflicts
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
        console.print(f"[yellow]⚠ {output_path} exists. Use --force to overwrite.[/yellow]\n")
    else:
        merger.save(output_path)
        console.print(f"[green]✓[/green] Unified MCP config exported to {output_path}")
        console.print(f"[dim]Servers: {len(merger.servers)}, Conflicts: {len(merger.conflicts)}[/dim]\n")


@main.command()
def status():
    """Show sync status and last sync times."""
    console.print("\n📊 Sync Status\n")

    config = Config()
    sync_manager = SyncManager(config)

    try:
        status_info = sync_manager.get_status()

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Agent", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Installed", style="yellow")
        table.add_column("Last Sync", style="blue")
        table.add_column("Changes", style="red")

        for agent, info in status_info.items():
            # Status with color coding
            status = info["status"]
            if status == "active":
                status_display = "✅ active"
            elif status == "not_installed":
                status_display = "⚠️ not_installed"
            elif status == "disabled":
                status_display = "❌ disabled"
            else:
                status_display = status

            # Installed indicator
            installed = info.get("installed", False)
            if installed:
                installed_display = "✓"
            elif status == "disabled":
                installed_display = "-"  # Don't care if disabled
            else:
                installed_display = "✗"

            table.add_row(
                agent,
                status_display,
                installed_display,
                info["last_sync"],
                info["changes"] or "-",
            )

        console.print(table)

        # Legend
        console.print("\n[dim]Legend:[/]")
        console.print("  [green]✅ active[/] = Enabled in config + Installed")
        console.print("  [yellow]⚠️ not_installed[/] = Enabled in config but not installed")
        console.print("  [dim]❌ disabled[/] = Disabled in config\n")

        if config.repo_url:
            console.print(f"🔗 Repository: {config.repo_url}")
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        raise click.Abort()


@main.group(cls=ExtendedHelpGroup)
def secrets():
    """Manage secrets and environment variables.

    Note: agent-sync does not scrub secrets. Config files are synced as-is.
    ALWAYS use a private repository.
    """
    pass


@main.command()
def update():
    """Check for available updates and install them."""
    import os
    import subprocess

    import requests
    from packaging import version
    from rich.panel import Panel
    from rich.prompt import Confirm

    console.print("[bold]🔍 Checking for updates...[/]\n")

    current = __version__

    try:
        # Try with GITHUB_TOKEN if available (for private repos)
        headers = {}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"

        response = requests.get(
            "https://api.github.com/repos/renatocaliari/agent-sync/releases/latest",
            headers=headers,
            timeout=5,
        )

        if response.status_code == 404:
            console.print(f"[dim]Current version: v{current}[/dim]")
            console.print("[yellow]⚠ No official releases found on GitHub[/yellow]\n")
            return

        response.raise_for_status()
        latest_data = response.json()
        latest = latest_data["tag_name"].lstrip("v")

        # Use proper version comparison (handles dev versions correctly)
        try:
            current_ver = version.parse(current)
            latest_ver = version.parse(latest)

            # Skip update check if current is a dev version
            if current_ver.is_devrelease:
                console.print(f"[dim]Current version: v{current} (development)[/dim]")
                console.print("[yellow]⚠ You are running a development version.[/yellow]")
                console.print("Update manually with: [cyan]pipx upgrade agent-sync[/cyan]\n")
                return

            if latest_ver > current_ver:
                console.print(f"✨ [green]Update available:[/green] [bold]v{latest}[/] (Current: v{current})")
            else:
                console.print(f"✓ [green]Up to date:[/green] [bold]v{current}[/]\n")
                return
        except Exception:
            # Fallback to string comparison if packaging fails
            if latest > current:
                console.print(f"✨ [green]Update available:[/green] [bold]v{latest}[/] (Current: v{current})")
            else:
                console.print(f"✓ [green]Up to date:[/green] [bold]v{current}[/]\n")
                return

        if Confirm.ask("\nDo you want to update now?", default=True):
            console.print("\n🚀 [bold]Updating agent-sync...[/]")

            # Execution logic with captured output for better UX
            def run_upgrade(cmd_list):
                return subprocess.run(cmd_list, capture_output=True, text=True, timeout=120)

            # 1. Try PIPX
            res = run_upgrade(["pipx", "upgrade", "agent-sync"])
            if res.returncode == 0:
                console.print("\n[bold green]✅ Updated successfully via pipx![/bold green]\n")
                return

            # 2. Try PIP with safety flag
            cmd_pip = ["python3", "-m", "pip", "install", "--upgrade", "git+https://github.com/renatocaliari/agent-sync.git", "--break-system-packages"]
            res = run_upgrade(cmd_pip)
            if res.returncode == 0:
                console.print("\n[bold green]✅ Updated successfully via pip![/bold green]\n")
                return

            # 3. If all fails, show a beautiful help panel
            error_msg = res.stderr or res.stdout
            is_managed = "externally-managed-environment" in error_msg

            instruction = ""
            if is_managed:
                instruction = (
                    "[yellow]Your Python environment is managed by the OS (macOS/Linux).[/yellow]\n\n"
                    "[bold]Please run one of these commands manually:[/]\n\n"
                    "  [cyan]pipx upgrade agent-sync[/cyan] (Recommended)\n"
                    "  [cyan]python3 -m pip install --upgrade git+https://github.com/renatocaliari/agent-sync.git --break-system-packages[/cyan]"
                )
            else:
                instruction = (
                    f"[red]Update failed with error:[/red] {error_msg[:100]}...\n\n"
                    "[bold]Try manual update:[/]\n"
                    "  [cyan]pipx upgrade agent-sync[/cyan]"
                )

            console.print("\n")
            console.print(Panel(instruction, title="[bold red]Update Required[/bold red]", expand=False))
            console.print("\n")

    except Exception as e:
        console.print(f"[dim]Current version: v{current}[/dim]")
        console.print(f"[yellow]⚠ Could not check for updates: {e}\n[/yellow]")


@main.command()
def version():
    """Show version information."""
    console.print(f"\n[bold]agent-sync[/] v{__version__}\n")


@main.command()
def agents():
    """List supported agents and their status."""
    console.print("\n🤖 Supported Agents\n")

    from .agents import get_agents

    agents = get_agents()

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Agent", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Sync", style="magenta")
    table.add_column("Skills Method", style="blue")
    table.add_column("Config Path", style="green")

    config = Config()

    for agent in agents:
        enabled = config.is_agent_enabled(agent.name)
        status = "✓" if agent.is_available() else "✗"
        sync_status = "🟢 ON" if enabled else "🔴 OFF"

        # Get actual method from user config or default to agent's registry method
        method = config.get_skills_method(agent.name) or agent.method

        config_path_str = str(agent.config_path) if agent.config_path else "-"

        table.add_row(
            agent.name,
            status,
            sync_status,
            method,
            config_path_str,
        )

    console.print(table)
    console.print("\n💡 Use 'agent-sync enable <agent>' or 'agent-sync disable <agent>' to toggle sync")
    console.print("\n🔧 [bold]How to customize skills method:[/]")
    console.print("  Edit your config with [green]agent-sync config edit[/green] and add:")
    console.print("  [dim]agents_config:[/dim]")
    console.print("  [dim]  claude-code:[/dim]")
    console.print("  [dim]    skills_method: copy  # Options: native, config, copy[/dim]\n")


@main.command()
@click.option("--agent", multiple=True, help="Specific agents to include")
def generate_config(agent: tuple[str, ...]):
    """Generate initial configuration file."""
    console.print("\n⚙️  Generating configuration...\n")

    config = Config()
    target_agents = agent if agent else None

    try:
        config_path = config.generate_default(target_agents)
        console.print(f"✅ Config generated: {config_path}", style="green")
        console.print("\n📝 Edit ~/.config/agent-sync/config.yaml to customize")
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        raise click.Abort()


def _resolve_agent(agent_name: str):
    """Look up an agent by name, printing available agents on failure."""
    from .agents import get_agent, get_agents

    agent = get_agent(agent_name)
    if not agent:
        console.print(f"❌ Unknown agent: {agent_name}", style="red")
        console.print("\nAvailable agents:", style="yellow")
        for a in get_agents():
            console.print(f"  • {a.name}")
        raise click.Abort()
    return agent


@main.command()
@click.argument("agent_name")
def enable(agent_name: str):
    """Enable sync for a specific agent."""
    console.print(f"\n✅ Enabling sync for: {agent_name}")
    agent = _resolve_agent(agent_name)
    try:
        Config().enable_agent(agent_name)
        agent.enable()
        console.print(f"✅ Sync enabled for {agent_name}", style="green")
        console.print("\n💡 Run 'agent-sync push' to sync this agent's configs")
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        raise click.Abort()


@main.command()
@click.argument("agent_name")
def disable(agent_name: str):
    """Disable sync for a specific agent."""
    console.print(f"\n🚫 Disabling sync for: {agent_name}")
    agent = _resolve_agent(agent_name)
    try:
        Config().disable_agent(agent_name)
        agent.disable()
        console.print(f"✅ Sync disabled for {agent_name}", style="green")
        console.print("\n💡 This agent's configs will no longer be synced")
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        raise click.Abort()


if __name__ == "__main__":
    main()
