"""Skills reconcile - resolve divergences between local and remote."""

from rich.console import Console
from rich.prompt import Prompt

from .skills_diff import SkillsDiff

console = Console()


class SkillsReconcile(SkillsDiff):
    """Resolve divergences between local and remote skills."""

    def reconcile_interactive(self) -> dict[str, str]:
        """Interactive reconciliation of divergent skills.

        Returns:
            Dictionary mapping skill name to action:
            - "local": Keep local version (delete from remote)
            - "remote": Keep remote version (download to local)
            - "skip": Keep both for now
        """
        diff_result = self.diff()
        local_only = diff_result["local_only"]
        remote_only = diff_result["remote_only"]

        if not local_only and not remote_only:
            console.print("[green]✓ No divergences to reconcile[/green]\n")
            return {}

        decisions = {}

        console.print("\n[bold]🔄 Reconcile Divergent Skills[/]\n")
        console.print("[dim]For each skill, choose which version to keep:[/dim]\n")

        if local_only:
            console.print("[cyan]Local only (will be added to remote):[/cyan]")
            for skill in local_only:
                decisions[skill] = "local"
            console.print(f"  {len(local_only)} skills will be [green]added to remote[/green]\n")

        if remote_only:
            console.print("[yellow]Remote only (not on local):[/yellow]")
            console.print("[dim]Choose action for each skill:[/dim]\n")
            for skill in remote_only:
                console.print(f"  [bold]{skill}[/bold]")
                choice = Prompt.ask("Action", choices=["l", "r", "s"], default="r", show_choices=False)
                if choice == "l":
                    decisions[skill] = "local"
                    console.print("  [red]→ Will delete from remote[/red]")
                elif choice == "r":
                    decisions[skill] = "remote"
                    console.print("  [green]→ Will download to local[/green]")
                else:
                    decisions[skill] = "skip"
                    console.print("  [yellow]→ Skip (keep for now)[/yellow]")
                console.print()

        return decisions

    def apply_decisions(self, decisions: dict[str, str], dry_run: bool = False) -> dict[str, int]:
        """Apply reconciliation decisions.

        Args:
            decisions: Dictionary mapping skill name to action
            dry_run: If True, only show what would be done

        Returns:
            Statistics dictionary
        """
        import shutil

        stats = {"added_to_remote": 0, "downloaded_to_local": 0, "deleted_from_remote": 0, "skipped": 0}

        for skill_name, action in decisions.items():
            if action == "local":
                stats["added_to_remote"] += 1
                if not dry_run:
                    console.print(f"  [green]✓ {skill_name}[/green] [dim](will add to remote on push)[/dim]")
            elif action == "remote":
                if self.repo_dir:
                    remote_skill = self.repo_dir / "skills" / skill_name
                    local_skill = self.global_skills_dir / skill_name
                    if remote_skill.exists():
                        if not dry_run:
                            self.global_skills_dir.mkdir(parents=True, exist_ok=True)
                            shutil.copytree(remote_skill, local_skill, dirs_exist_ok=True)
                            stats["downloaded_to_local"] += 1
                            console.print(f"  [green]✓ {skill_name}[/green] [dim](downloaded from remote)[/dim]")
                    else:
                        stats["skipped"] += 1
                        console.print(f"  [yellow]⚠ {skill_name}[/yellow] [dim](not found on remote)[/dim]")
            elif action == "skip":
                stats["skipped"] += 1
                if not dry_run:
                    console.print(f"  [yellow]⊘ {skill_name}[/yellow] [dim](skipped)[/dim]")

        return stats

    def show_summary(self, stats: dict[str, int]) -> None:
        """Show reconciliation summary."""
        console.print("\n[bold]📊 Summary:[/]\n")
        if stats["added_to_remote"] > 0:
            console.print(f"  [green]✓ {stats['added_to_remote']} skills[/green] will be added to remote (on push)")
        if stats["downloaded_to_local"] > 0:
            console.print(f"  [green]✓ {stats['downloaded_to_local']} skills[/green] downloaded to local")
        if stats["skipped"] > 0:
            console.print(f"  [yellow]⚠ {stats['skipped']} skills[/yellow] skipped")
        console.print()
