"""Skills publishing to public GitHub repositories.

Publish selected skills to a PUBLIC repository for sharing with the community.
Separate from private agent-sync-configs repository.
"""

import shutil
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

import yaml
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box
from .config import Config
from .validators import validate_github_url, validate_repo_name

console = Console()

PUBLISH_CONFIG_PATH = Path.home() / ".config" / "agent-sync" / "publish.yaml"
SKILLS_DIR = Path.home() / ".agents" / "skills"


def get_available_skills() -> list[dict]:
    """Scan for available skills in ~/.agents/skills/."""
    skills_list = []
    if not SKILLS_DIR.exists():
        return []
        
    for item in SKILLS_DIR.iterdir():
        if item.name.startswith("."):
            continue
        
        # We consider anything in the skills directory a publishable unit
        if item.is_dir() or (item.is_file() and item.suffix in [".md", ".py", ".sh"]):
            skills_list.append({
                "name": item.name,
                "path": item
            })
    return sorted(skills_list, key=lambda x: x["name"])


def render_selection_table(skills: list, selected_names: set) -> Table:
    """Render the TUI selection table."""
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta", expand=True)
    table.add_column("ID", justify="right", style="dim", width=4)
    table.add_column("Pub", justify="center", width=5)
    table.add_column("Skill Name", style="cyan")

    for i, skill in enumerate(skills, 1):
        is_selected = skill["name"] in selected_names
        status = "[bold green]✓[/]" if is_selected else "[red]○[/]"
        table.add_row(str(i), status, skill["name"])
    
    return table


def interactive_selection(skills: list, initial_selected: set) -> set:
    """TUI for selecting skills to publish."""
    selected = set(initial_selected)
    
    while True:
        console.clear()
        console.print("\n[bold magenta]📤 Select Skills to Publish[/bold magenta]\n")
        
        table = render_selection_table(skills, selected)
        console.print(table)
        
        console.print("\n[bold]Controls:[/bold]")
        console.print("  • Enter numbers to toggle (e.g. [green]'1,3,5'[/green])")
        console.print("  • Type [cyan]'all'[/cyan] or [cyan]'none'[/cyan]")
        console.print("  • Press [bold white]Enter[/] when done")
        
        choice = Prompt.ask("\nSelection", default="done")
        
        if choice.lower() in ["done", ""]:
            break
        elif choice.lower() == "all":
            selected = {s["name"] for s in skills}
        elif choice.lower() == "none":
            selected = set()
        else:
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                for idx in indices:
                    if 0 <= idx < len(skills):
                        name = skills[idx]["name"]
                        if name in selected:
                            selected.remove(name)
                        else:
                            selected.add(name)
            except ValueError:
                pass
                
    return selected


def show_selection_summary(selected_names: set) -> bool:
    """Show summary table and confirm."""
    console.print("\n[bold green]📋 Selection Summary[/] [dim](to be published)[/dim]\n")
    summary_table = Table(box=box.SIMPLE)
    summary_table.add_column("Skill Name", style="cyan")
    for name in sorted(list(selected_names)):
        summary_table.add_row(f"  • {name}")
    console.print(summary_table)
    
    return Confirm.ask("\n[bold]Confirm this selection?[/]", default=True)


def publish_skills(repo_url: Optional[str] = None, dry_run: bool = False, interactive: bool = False) -> bool:
    """Publish selected skills to a public GitHub repository."""
    if repo_url and not validate_github_url(repo_url):
        console.print(f"\n[red]✗ Invalid repository URL: {repo_url}[/red]\n")
        return False

    config = Config()
    
    # 1. Scan for skills on disk
    available_skills = get_available_skills()
    if not available_skills:
        console.print("\n[yellow]⚠ No skills found in ~/.agents/skills/[/yellow]")
        console.print("Run [green]agent-sync skills centralize[/green] first.\n")
        return False

    available_names = {s["name"] for s in available_skills}

    # 2. Determine initial selection and handle missing skills
    saved_selection = config.published_skills
    valid_saved = [name for name in saved_selection if name in available_names]
    if len(valid_saved) != len(saved_selection):
        config.published_skills = valid_saved
        saved_selection = valid_saved

    # 3. Interactive flow
    selected_names = set()
    
    if interactive:
        confirmed = False
        while not confirmed:
            if saved_selection and not selected_names:
                # SHOW CURRENT SAVED
                console.print("\n[bold blue]📋 Current Saved Selection[/]")
                summary_table = Table(box=box.SIMPLE, show_header=False)
                summary_table.add_column("Skill", style="cyan")
                for name in sorted(saved_selection):
                    summary_table.add_row(f"  • {name}")
                console.print(summary_table)

                console.print("\n[bold]What would you like to do?[/]")
                console.print("  [[bold green]u[/]] Use this selection")
                console.print("  [[bold cyan]e[/]] Edit selection")
                console.print("  [[bold magenta]a[/]] Select ALL available")
                
                choice = Prompt.ask("\nChoice", choices=["u", "e", "a"], default="u")
                
                if choice == "u":
                    selected_names = set(saved_selection)
                    confirmed = True
                elif choice == "a":
                    selected_names = available_names
                    confirmed = show_selection_summary(selected_names)
                else: # e (edit)
                    selected_names = set(saved_selection)
                    selected_names = interactive_selection(available_skills, selected_names)
                    confirmed = show_selection_summary(selected_names)
            else:
                # No saved config OR selection changed but not confirmed
                if not selected_names:
                    console.print("\n[bold]Publishing Mode[/]")
                    console.print("  [[bold green]a[/]] Publish ALL available")
                    console.print("  [[bold cyan]s[/]] Select specific skills")
                    
                    mode = Prompt.ask("\nChoice", choices=["a", "s"], default="a")
                    if mode == "a":
                        selected_names = available_names
                    else:
                        selected_names = interactive_selection(available_skills, selected_names)
                else:
                    selected_names = interactive_selection(available_skills, selected_names)
                
                confirmed = show_selection_summary(selected_names)
            
            if not confirmed:
                selected_names = set()
                console.clear()
            else:
                config.published_skills = list(selected_names)
    else:
        # Non-interactive: use saved selection or all available
        selected_names = set(saved_selection) if saved_selection else available_names
    
    # Final skill objects
    selected_skills = [s for s in available_skills if s["name"] in selected_names]
    if not selected_skills:
        console.print("\n[yellow]⚠ No skills selected for publishing[/yellow]\n")
        return False

    # 4. SECURITY WARNING & REPO SETTINGS (Only after selection is confirmed)
    console.print("\n")
    console.print(Panel(
        "[bold yellow]⚠️  SECURITY WARNING[/bold yellow]\n\n"
        "You are about to publish skills to a [bold]PUBLIC[/] repository.\n\n"
        "What WILL be published:\n"
        "  ✓ SKILL.md files (skill definitions)\n"
        "  ✓ .md, .py, .sh files (skill scripts)\n"
        "  ✓ references/, templates/, scripts/ directories\n\n"
        "What will [bold red]NEVER[/bold red] be published:\n"
        "  ✗ Any config files (settings.json, config.yaml, etc.)\n"
        "  ✗ Any files containing 'auth', 'token', 'key', 'secret' in name\n"
        "  ✗ .env files\n"
        "  ✗ Your private agent-sync-configs repository",
        border_style="yellow",
        title="[bold yellow]Public Disclosure[/]",
    ))

    # Repo logic...
    publish_config = {}
    if PUBLISH_CONFIG_PATH.exists():
        try:
            publish_config = yaml.safe_load(PUBLISH_CONFIG_PATH.read_text()) or {}
        except Exception: pass

    repo_url = repo_url or publish_config.get("repo_url")
    if not repo_url:
        # Suggest new standard naming convention
        try:
            result = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True, timeout=5)
            username = result.stdout.strip() if result.returncode == 0 else "YOUR_USERNAME"
        except Exception:
            username = "YOUR_USERNAME"
        
        default_repo = f"{username}/agent-sync-public-skills"
        repo_url = Prompt.ask(
            "\n[bold]Enter GitHub repository URL for publishing[/]",
            default=f"https://github.com/{default_repo}",
        )
        if not repo_url or not validate_github_url(repo_url):
            console.print("\n[red]✗ Invalid repository URL[/red]\n")
            return False

        PUBLISH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        publish_config["repo_url"] = repo_url
        PUBLISH_CONFIG_PATH.write_text(yaml.dump(publish_config))

    # Visibility check
    repo_name = repo_url.replace("https://github.com/", "").replace(".git", "")
    if not validate_github_url(repo_url) or not repo_name or "/" not in repo_name:
        console.print(f"\n[red]✗ Invalid repository URL or name: {repo_url}[/red]\n")
        return False

    try:
        res = subprocess.run(["gh", "api", f"repos/{repo_name}"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            is_private = json.loads(res.stdout).get("private", False)
            if is_private:
                console.print(f"\n[yellow]⚠️  Warning: Repository {repo_name} is PRIVATE.[/yellow]")
            else:
                console.print(f"\n[green]✓ Repository {repo_name} is PUBLIC.[/green]")
    except Exception: pass

    if dry_run:
        console.print(f"\n[blue]🔍 DRY RUN: Would publish {len(selected_skills)} skills to {repo_url}[/blue]\n")
        return True

    if not Confirm.ask("\n[bold red]Confirm publishing to GitHub?[/]", default=True):
        console.print("\n[yellow]Publish cancelled[/yellow]\n")
        return False

    # 5. EXECUTION
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        skills_tmp_dir = tmp_path / "skills"
        skills_tmp_dir.mkdir(parents=True, exist_ok=True)
        
        for skill in selected_skills:
            src, dst = skill["path"], skills_tmp_dir / skill["name"]
            if src.is_dir(): shutil.copytree(src, dst)
            else: shutil.copy2(src, dst)
        
        (tmp_path / "README.md").write_text(generate_readme(selected_skills, repo_url))
        (tmp_path / ".gitignore").write_text("*.json\n*.yaml\n*.yml\n.env\n*auth*\n*token*\n*key*\n*secret*\n*credentials*\n")
        
        console.print(f"\n[bold]📤 Publishing {len(selected_skills)} skills...[/]")
        
        try:
            # Final safety check on repo_name before subprocess
            if not validate_repo_name(repo_name):
                raise ValueError(f"Invalid repository name: {repo_name}")

            subprocess.run(["gh", "api", f"repos/{repo_name}"], capture_output=True, check=False, timeout=30)
            subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True, timeout=15)
            subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True, timeout=30)
            subprocess.run(["git", "commit", "-m", f"feat: publish {len(selected_skills)} skills"], cwd=tmp_path, capture_output=True, check=True, timeout=30)
            subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_path, capture_output=True, check=True, timeout=15)
            subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=tmp_path, capture_output=True, check=True, timeout=15)
            subprocess.run(["git", "push", "-u", "origin", "main", "--force"], cwd=tmp_path, capture_output=True, check=True, timeout=120)
            
            console.print(f"\n[green]✓ Successfully published to {repo_url}![/green]")
            console.print(f"💡 Others can install with: [bold]npx skills add {repo_name}[/]\n")
            return True
        except Exception as e:
            console.print(f"\n[red]✗ Failed to publish: {e}[/red]\n")
            return False


def generate_readme(selected_skills: list, repo_url: str) -> str:
    """Generate README.md for the skills repository."""
    repo_name = repo_url.replace("https://github.com/", "").replace(".git", "")
    if "/" not in repo_name:
        repo_name = "your-repo"

    skills_list = "\n".join(f"- {s['name']}" for s in selected_skills)

    return f"""# Agent Skills

A collection of custom skills for AI agents.

## Installation

Install these skills with:

```bash
npx skills add {repo_name}
```

## Skills

{skills_list}

## About

This repository contains skills published using [agent-sync](https://github.com/renatocaliari/agent-sync).
"""
