"""Skills diff management - compare local vs remote."""

from pathlib import Path

from rich.console import Console

from .paths import HUB_DIR

console = Console()


def scan_skills_dir(skills_dir: Path) -> set[str]:
    """Scan a skills directory and return set of valid skill names."""
    if not skills_dir.exists():
        return set()
    return {
        item.name for item in skills_dir.iterdir()
        if item.is_dir() and not item.name.startswith(".")
        and (item / "SKILL.md").exists()
    }


class SkillsDiff:
    """Compare local skills with remote GitHub repository."""

    def __init__(self):
        from .config import Config

        self.config = Config()
        self.global_skills_dir = HUB_DIR
        self.repo_dir = None

        if self.config.repo_url:
            from .sync import SyncManager
            sync_manager = SyncManager(self.config)
            self.repo_dir = sync_manager.repo_dir

    def get_local_skills(self) -> set[str]:
        """Get set of local skill names."""
        return scan_skills_dir(self.global_skills_dir)

    def get_remote_skills(self) -> set[str]:
        """Get set of remote skill names from GitHub repo."""
        if not self.repo_dir or not self.repo_dir.exists():
            return set()

        return scan_skills_dir(self.repo_dir / "skills")

    def diff(self) -> dict[str, dict[str, list[str]]]:
        """
        Compare local and remote skills.

        Returns:
            Dictionary with:
            - local_only: Skills only on local (not on GitHub)
            - remote_only: Skills only on GitHub (not local)
            - both: Skills on both sides
        """
        local = self.get_local_skills()
        remote = self.get_remote_skills()

        return {
            "local_only": sorted(list(local - remote)),
            "remote_only": sorted(list(remote - local)),
            "both": sorted(list(local & remote)),
        }
    
    def get_diff_data(self) -> dict:
        """Get diff data for JSON output."""
        diff_result = self.diff()
        return {
            "in_sync": not diff_result["local_only"] and not diff_result["remote_only"],
            "local_only": diff_result["local_only"],
            "remote_only": diff_result["remote_only"],
            "both": diff_result["both"],
            "local_count": len(self.get_local_skills()),
            "remote_count": len(self.get_remote_skills()),
        }
    
    def show_diff(self) -> None:
        """Display diff in a formatted table."""
        from rich import box
        from rich.table import Table

        diff_result = self.diff()

        if not diff_result["local_only"] and not diff_result["remote_only"]:
            console.print("[green]✓ Local and remote are in sync[/green]\n")
            return

        console.print("\n[bold]📊 Skills Divergence Report[/]\n")

        # Local only
        if diff_result["local_only"]:
            table = Table(box=box.SIMPLE, title="[cyan]Local only[/cyan] (not on GitHub)", title_style="cyan")
            table.add_column("Skill Name", style="cyan")
            for skill in diff_result["local_only"]:
                table.add_row(f"  • {skill}")
            console.print(table)
            console.print()

        # Remote only
        if diff_result["remote_only"]:
            table = Table(box=box.SIMPLE, title="[yellow]Remote only[/yellow] (not local)", title_style="yellow")
            table.add_column("Skill Name", style="yellow")
            for skill in diff_result["remote_only"]:
                table.add_row(f"  • {skill}")
            console.print(table)
            console.print()

        # Summary
        console.print("[dim]─────────────────────────────────────────[/dim]")
        console.print(f"[dim]Local: {len(self.get_local_skills())} skills | Remote: {len(self.get_remote_skills())} skills[/dim]\n")
