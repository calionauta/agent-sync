"""Interactive setup wizard for agent-sync."""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .agents import get_all_agents
from .config import Config
from .skills import SkillsManager
from .validators import validate_repo_name

console = Console()


class SetupWizard:
    """Interactive setup wizard for agent-sync."""

    def __init__(self):
        self.config = Config()
        self.selected_agents: list[str] = []
        self.agent_configs: dict[str, dict] = {}
        self.include_global_skills = True  # Always true
        self.repo_name: str = ""
        self.is_private = True
        self.skills_centralized = False
        self.agent_configure_results: dict = {}

    def _step_title(self, step: str, title: str, description: str = "", border: str = "green") -> None:
        """Print a standardized step header."""
        body = f"[bold]{step}: {title}[/]"
        if description:
            body += f"\n\n{description}"
        console.print(Panel.fit(body, border_style=border))
        console.print()

    def run(self) -> bool:
        """Run the complete setup wizard."""
        from . import __version__

        console.print()
        console.print(
            Panel.fit(
                f"🔄 [bold]Agent Sync v{__version__}[/] - Setup Wizard\n\n"
                "This wizard will help you configure agent-sync.\n"
                "Global skills (~/.agents/skills/) are always enabled.",
                border_style="blue",
            )
        )
        console.print()

        # Step 1: Detect installed agents
        self._step_detect_agents()

        # Step 2: Select agents to sync
        self._step_select_agents()

        # Step 3: Centralize skills (single question for all agents)
        self._step_centralize_skills()

        # Step 4: Configure sync options (configs - with smart defaults)
        self._step_configure_agents()

        # Step 5: Configure agents automatically
        self._step_auto_configure_agents()

        # Step 6: Repository settings
        self._step_repo_settings()

        # Step 7: Review and confirm
        return self._step_review()

    def _step_detect_agents(self) -> None:
        """Step 1: Detect installed agents."""
        self._step_title("Step 1", "Detecting Installed Agents")

        installed = []
        not_installed = []
        path_warnings = []

        for agent in get_all_agents():
            if agent.name == "global-skills":
                continue

            if agent.is_available():
                installed.append(agent)

                # Validate config path exists
                if agent.config_path and not agent.config_path.exists():
                    path_warnings.append(
                        {
                            "agent": agent.name,
                            "path": agent.config_path,
                            "message": f"Config file not found at {agent.config_path}",
                        }
                    )
            else:
                not_installed.append(agent)

        if installed:
            console.print("[green]✓ Found installed agents:[/green]")
            for agent in installed:
                console.print(f"  • {agent.name}")
        else:
            console.print("[yellow]⚠ No agents detected on your system[/yellow]")

        if not_installed:
            console.print(f"\n[yellow]Not installed ({len(not_installed)}):[/yellow]")
            for agent in not_installed:
                console.print(f"  • {agent.name}")

        # Show path warnings
        if path_warnings:
            console.print(f"\n[yellow]⚠ Path warnings ({len(path_warnings)}):[/yellow]")
            for warning in path_warnings:
                console.print(f"  • {warning['agent']}: {warning['message']}")
            console.print(
                "\n[dim]This may indicate the agent is installed but not configured yet.[/dim]\n"
            )

        console.print()

    def _step_select_agents(self) -> None:
        """Step 2: Select agents to sync."""
        self._step_title("Step 2", "Select Agents to Sync", "Choose which agents you want to synchronize.")

        # Show all agents with status
        table = Table(box=box.SIMPLE)
        table.add_column("Agent", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Config Path", style="dim")

        for agent in get_all_agents():
            if agent.name == "global-skills":
                continue

            status = "✓" if agent.is_available() else "✗"
            config_path = str(agent.config_path)
            if len(config_path) > 50:
                config_path = "..." + config_path[-47:]

            table.add_row(agent.name, status, config_path)

        console.print(table)
        console.print()

        # Ask which agents to enable
        default_agents = "all"
        selected = Prompt.ask(
            "Which agents to sync",
            default=default_agents,
            show_default=True,
        )

        if selected.lower() == "all":
            # Select all installed agents
            for agent in get_all_agents():
                if agent.name != "global-skills" and agent.is_available():
                    self.selected_agents.append(agent.name)
        elif selected.lower() == "none":
            pass  # Select none
        else:
            # Parse comma-separated list
            names = [n.strip().lower() for n in selected.split(",")]
            for agent in get_all_agents():
                if agent.name in names:
                    self.selected_agents.append(agent.name)

        console.print(f"\n[green]✓ Selected {len(self.selected_agents)} agent(s):[/green]")
        for name in self.selected_agents:
            console.print(f"  • {name}")

        console.print()

    def _step_configure_agents(self) -> None:
        """Step 4: Configure sync options (configs - with smart defaults).

        Asks once if user wants to sync configs from ALL agents.
        Only asks individually if user declines.
        """
        self._step_title("Step 4", "Configure Sync Options",
            "Choose what to sync for each agent.\n"
            "[dim]Note: Skills are already synced to ~/.agents/skills/ (Step 3)[/dim]")

        # First question: sync configs from ALL agents?
        sync_all_configs = Confirm.ask(
            "[bold]Sync configuration files from ALL selected agents?[/]\n"
            "  [dim](e.g., settings.json, opencode.jsonc)[/dim]",
            default=True,  # Default: YES, sync all
        )

        console.print()

        if sync_all_configs:
            # User said YES - enable configs for all agents
            for agent_name in self.selected_agents:
                if agent_name == "global-skills":
                    continue

                self.agent_configs[agent_name] = {
                    "enabled": True,
                    "sync": {
                        "configs": True,
                    },
                }

            console.print(
                f"[green]✓ Configs enabled for {len(self.selected_agents) - 1} agent(s)[/green]\n"
            )
        else:
            # User said NO - ask individually
            console.print("[yellow]Which agents should sync configs?[/yellow]\n")

            for agent_name in self.selected_agents:
                if agent_name == "global-skills":
                    continue

                agent = next((a for a in get_all_agents() if a.name == agent_name), None)
                if not agent:
                    continue

                console.print(f"Configuring [cyan]{agent_name}:[/cyan]")

                sync_configs = Confirm.ask(
                    "  Sync configuration files?",
                    default=True,
                )

                self.agent_configs[agent_name] = {
                    "enabled": True,
                    "sync": {
                        "configs": sync_configs,
                    },
                }

                console.print()

        # Show summary
        console.print("[bold]Summary:[/]\n")
        for agent_name in self.selected_agents:
            if agent_name == "global-skills":
                continue

            agent_config = self.agent_configs.get(agent_name, {})
            sync_opts = agent_config.get("sync", {})
            sync_configs = sync_opts.get("configs", False)

            status = "[green]✓ configs[/green]" if sync_configs else "[dim]skills only[/dim]"
            console.print(f"  • {agent_name}: {status}")

        console.print()

    def _step_centralize_skills(self) -> None:
        """Step 3: Centralize skills to ~/.agents/skills/ (single question)."""
        self._step_title("Step 3", "Centralizing Skills",
            "Scanning for existing skills in all agents...\n"
            "All skills will be centralized to ~/.agents/skills/")

        skills_mgr = SkillsManager()

        # Check if there are any skills to centralize
        skills_found = skills_mgr.scan_all_agents()

        if skills_found:
            # Count unique skills by name (deduplicate across agents, skip extensions)
            unique_skill_names = set()
            for agent_skills in skills_found.values():
                if isinstance(agent_skills, dict):
                    continue  # extension skills — not centralized, skip
                for skill_path in agent_skills:
                    unique_skill_names.add(skill_path.name)

            total_unique = len(unique_skill_names)
            total_copies = sum(
                len(s.get("paths", [])) if isinstance(s, dict) else len(s)
                for s in skills_found.values()
            )

            if total_copies > total_unique:
                console.print(
                    f"Found [cyan]{total_unique}[/cyan] unique skills "
                    f"([dim]{total_copies} copies[/dim] across {len(skills_found)} agents).\n"
                )
            else:
                console.print(
                    f"Found [cyan]{total_unique}[/cyan] skills across {len(skills_found)} agents.\n"
                )

            if Confirm.ask("Centralize all skills to ~/.agents/skills/?", default=True):
                skills_mgr.centralize()
                self.skills_centralized = True
            else:
                console.print("[yellow]Skipping centralization.[/yellow]\n")
                self.skills_centralized = False
        else:
            console.print(
                "[green]✓ No existing skills found. Global skills directory is empty.[/green]\n"
            )
            self.skills_centralized = True

        # Always add global-skills to selected agents
        if "global-skills" not in self.selected_agents:
            self.selected_agents.append("global-skills")

        self.agent_configs["global-skills"] = {
            "enabled": True,
            "sync": {
                "configs": False,
            },
        }

    def _step_auto_configure_agents(self) -> None:
        """Step 5: Configure agents to use global skills (automatic)."""
        self._step_title("Step 5", "Configuring Agents", "Automatically configuring agents to use global skills...")

        skills_mgr = SkillsManager()
        self.agent_configure_results = skills_mgr.configure_agents()

        console.print()

    def _step_repo_settings(self) -> None:
        """Step 6: Repository settings."""
        self._step_title("Step 6", "Repository Settings",
            "[yellow]⚠ SECURITY: Use PRIVATE repository for configs![/yellow]\n\n"
            "Your configs may contain sensitive information.\n"
            "Private repositories are FREE on GitHub.")

        # Repository name
        while True:
            self.repo_name = Prompt.ask(
                "Repository name",
                default="agent-sync-private-configs",
            )

            if validate_repo_name(self.repo_name):
                break

            console.print(f"\n[red]✗ Invalid repository name: {self.repo_name}[/red]")
            console.print(
                "   Only alphanumeric characters, hyphens, underscores, and periods are allowed."
            )
            console.print("   Cannot start with a hyphen.\n")

        # Always private for security
        self.is_private = True
        console.print("[dim]Repository will be PRIVATE (for security)[/dim]\n")

    def _step_review(self) -> bool:
        """Step 7: Review configuration and show summary."""
        self._step_title("Step 7", "Summary", border="blue")

        # Show final summary
        self._show_final_summary()

        # Confirm
        confirmed = Confirm.ask(
            "\n[bold]Proceed with this configuration?[/]",
            default=True,
        )

        if confirmed:
            self._save_configuration()

        console.print()
        return confirmed

    def _show_final_summary(self) -> None:
        """Show detailed final summary of what was done."""

        # Repository info
        console.print(
            Panel(
                f"[cyan]📦 Repository:[/cyan] {self.repo_name}\n"
                f"[cyan]Visibility:[/cyan] {'🔒 Private' if self.is_private else '🌍 Public'}",
                title="GitHub",
                border_style="blue",
            )
        )
        console.print()

        # Skills summary
        skills_mgr = SkillsManager()
        skills_summary = skills_mgr.get_summary()

        console.print(
            Panel(
                f"[cyan]📁 Location:[/cyan] {skills_summary['global_skills_dir']}\n"
                f"[cyan]Skills:[/cyan] {skills_summary['skill_count']} skills",
                title="Global Skills",
                border_style="green",
            )
        )
        console.print()

        # Per-agent summary
        console.print("[bold]Per-Agent Summary:[/]\n")

        for agent_name in self.selected_agents:
            if agent_name == "global-skills":
                continue

            agent = next((a for a in get_all_agents() if a.name == agent_name), None)
            if not agent:
                continue

            # Get configuration result
            config_result = self.agent_configure_results.get(agent_name, {})
            method = config_result.get("method", "unknown")
            success = config_result.get("success", False)

            # Status icon
            if success:
                if method == "symlink":
                    icon = "🔗"
                elif method == "config":
                    icon = "⚙️"
                elif method == "fallback":
                    icon = "📋"
                else:
                    icon = "✓"
                status_color = "green"
            else:
                icon = "⚠️"
                status_color = "yellow"

            # Config sync status
            agent_config = self.agent_configs.get(agent_name, {})
            sync_opts = agent_config.get("sync", {})
            sync_configs = sync_opts.get("configs", True)

            console.print(f"[{status_color}]{icon} {agent_name}[/{status_color}]")
            console.print(f"   [dim]Config:[/dim] {agent.config_path}")

            if method == "symlink":
                console.print("   [dim]Skills:[/dim] ~/.agents/skills/ (symlink)")
            elif method == "config":
                console.print("   [dim]Skills:[/dim] ~/.agents/skills/ (configured)")
            elif method == "fallback":
                console.print(f"   [dim]Skills:[/dim] {agent.skills_path} (copy)")
            else:
                console.print("   [dim]Skills:[/dim] ~/.agents/skills/ (native)")

            console.print(f"   [dim]Sync configs:[/dim] {'Yes' if sync_configs else 'No'}")
            if success:
                console.print("   [dim]Status:[/dim] [green]✅ Ready[/green]")
            else:
                console.print("   [dim]Status:[/dim] [yellow]⚠ Needs attention[/yellow]")
            console.print()

        # Next steps
        console.print(
            Panel(
                "[bold]Next Steps:[/]\n\n"
                "  1. [green]agent-sync config show[/green]   - Review configuration\n"
                "  2. [green]agent-sync push[/green]          - Push to GitHub\n"
                "  3. [green]agent-sync link <url>[/green]    - Link other machines",
                title="📋 What's Next",
                border_style="yellow",
            )
        )

    def _save_configuration(self) -> None:
        """Save the configuration."""
        console.print("\n[bold]Saving configuration...[/]\n")

        # Save agent-specific configs
        for agent_name, config in self.agent_configs.items():
            self.config.set_agent_config(agent_name, config)

        console.print("[green]✓ Configuration saved to ~/.config/agent-sync/config.yaml[/green]\n")

    def get_repo_config(self) -> dict:
        """Get repository configuration for init."""
        return {
            "name": self.repo_name,
            "private": self.is_private,
            "agents": tuple(self.selected_agents),
        }


def run_setup_wizard() -> dict | None:
    """Run the setup wizard and return repo config."""
    wizard = SetupWizard()

    if wizard.run():
        return wizard.get_repo_config()

    return None
