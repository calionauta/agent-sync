"""Skills and Agent Instructions publishing to public GitHub repositories.

Publish selected skills or agent instructions to a PUBLIC repository
for sharing with the community. Separate from private agent-sync-private repository.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .agent_discovery import get_available_agents as get_available_agents_from_discovery
from .config import Config
from .security_scanner import ScanResult, format_issues_for_display, scan_file
from .validators import validate_github_url, validate_repo_name

console = Console()

PUBLISH_CONFIG_PATH = Path.home() / ".config" / "agent-sync" / "publish.yaml"
SKILLS_DIR = Path.home() / ".agents" / "skills"

# Files to skip during publish (not meaningful to publish, machine-specific, or binary)
SKIP_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin",
                   ".whl", ".zip", ".tar", ".gz", ".bz2", ".xz",
                   ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
                   ".pdf", ".doc", ".docx", ".xls", ".xlsx",
                   ".pycache__", ".egg-info__"}

# Templates path
TEMPLATES_DIR = Path(__file__).parent / "templates"


# =============================================================================
# SHARED HELPERS
# =============================================================================

def _resolve_repo_url(repo_url: str | None = None) -> str | None:
    """Resolve repo URL: param → publish.yaml → prompt."""
    publish_config = {}
    if PUBLISH_CONFIG_PATH.exists():
        try:
            publish_config = yaml.safe_load(PUBLISH_CONFIG_PATH.read_text()) or {}
        except Exception: pass

    resolved = repo_url or publish_config.get("repo_url")
    if not resolved:
        try:
            result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True, text=True, timeout=5,
            )
            username = result.stdout.strip() if result.returncode == 0 else "YOUR_USERNAME"
        except Exception:
            username = "YOUR_USERNAME"

        default_repo = f"{username}/agent-sync-public-skills"
        resolved = Prompt.ask(
            "\n[bold]Enter GitHub repository URL[/]",
            default=f"https://github.com/{default_repo}",
        )
        if not validate_github_url(resolved):
            console.print("\n[red]✗ Invalid repository URL[/red]\n")
            return None

        PUBLISH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        publish_config["repo_url"] = resolved
        PUBLISH_CONFIG_PATH.write_text(yaml.dump(publish_config))

    return resolved


def _check_repo_visibility(repo_url: str) -> None:
    """Check if repo is public or private, warn if private."""
    repo_name = repo_url.replace("https://github.com/", "").replace(".git", "")
    try:
        res = subprocess.run(
            ["gh", "api", f"repos/{repo_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode == 0:
            is_private = json.loads(res.stdout).get("private", False)
            if is_private:
                console.print(f"\n[yellow]⚠️  Warning: Repository {repo_name} is PRIVATE.[/yellow]")
            else:
                console.print(f"\n[green]✓ Repository {repo_name} is PUBLIC.[/green]")
    except Exception: pass


def _git_clone_or_init(repo_url: str, tmp_path: Path) -> None:
    """Clone existing repo or init fresh."""
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(tmp_path)],
            capture_output=True, timeout=60,
        )
    except Exception:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, timeout=15)
        subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_path, capture_output=True, timeout=15)


def _git_push(tmp_path: Path, repo_url: str, message: str) -> None:
    """Add, commit and push to remote."""
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, timeout=30)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=tmp_path,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", repo_url],
        cwd=tmp_path,
        capture_output=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main", "--force"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        timeout=120,
    )


# =============================================================================
# SHARED HELPERS (DRY)
# =============================================================================

def _render_flagged_table(
    flagged_items: list[tuple],
    title: str = "⚠️  Flagged Items",
) -> Table:
    """Render a table showing flagged items with their security issues.
    
    DRY helper for both skills and agents.
    
    Args:
        flagged_items: List of (item, result, prefix) tuples
        title: Table title
    """
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold yellow")
    table.add_column("Item", style="cyan")
    table.add_column("Issues", style="red")

    for item, result, prefix in flagged_items:
        name = item.get("name") or item.get("filename") or str(item)
        if prefix:
            name = f"{prefix}/{name}"
        issues_text = format_issues_for_display(result.issues)
        # Truncate for table display
        issues_text = "\n".join(issues_text.split("\n")[:3])  # Max 3 lines
        table.add_row(name, issues_text)

    return table


def _interactive_flagged_selection(
    flagged_items: list[tuple],
    title: str = "Select flagged items to publish",
    include_safe: bool = False,
) -> tuple[list, bool]:
    """Interactive selection for flagged items.
    
    Shows items with HIGH or CRITICAL issues and lets user select
    which ones to publish. Skips low/deprecated issues automatically.
    
    Args:
        flagged_items: List of (item, result, prefix) tuples
        title: Selection title
        include_safe: If True, also shows safe items
    
    Returns:
        Tuple of (selected_items, confirmed)
    """
    from ._selection import parse_multiselect_input

    if not flagged_items:
        return [], True

    # Filter to only items with significant issues (high/critical, not variable/deprecated)
    def has_significant_issues(result: ScanResult) -> bool:
        """Check if result has issues that warrant user attention."""
        if not result.safe:
            return True
        return any(
            issue.get('context') not in ('variable', 'deprecated')
            and issue.get('severity') in ('critical', 'high')
            for issue in result.issues
        )

    display_items = [
        (item, result, prefix) for item, result, prefix in flagged_items
        if has_significant_issues(result)
    ]

    if not display_items:
        return [], True  # No significant issues, auto-confirm

    selected = set()
    item_names = []
    item_map = {}

    # Build key-indexed maps using display index
    for i, (item, result, prefix) in enumerate(display_items, 1):
        name = item.get("name") or item.get("filename") or str(item)
        if prefix:
            name = f"{prefix}/{name}"

        # Key for selection (include index for uniqueness)
        key = f"{i}:{name}"
        item_names.append(key)
        item_map[key] = (item, result, prefix)

        # Default: select items with high/critical issues
        if has_significant_issues(result):
            selected.add(key)

    while True:
        console.clear()
        console.print(f"\n[bold yellow]⚠️  {title}[/bold yellow]\n")
        console.print(f"[dim]Showing {len(display_items)} items with HIGH or CRITICAL security concerns[/dim]\n")
        console.print("[dim]Items with 🔴 deprecated or 🟡 env var issues are hidden[/dim]\n")

        # Render table with security status + detailed issues
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("ID", justify="right", style="dim", width=4)
        table.add_column("Pub", justify="center", width=5)
        table.add_column("Item", style="cyan")
        table.add_column("Security", justify="center", width=10)
        table.add_column("Issues", style="red")

        for i, (item, result, prefix) in enumerate(display_items, 1):
            name = item.get("name") or item.get("filename") or str(item)
            if prefix:
                name = f"{prefix}/{name}"

            key = f"{i}:{name}"
            is_selected = key in selected
            status = "[bold green]✓[/]" if is_selected else "[red]○[/]"

            icon = "[red]⚠️[/]" if not result.safe else "[green]✓[/]"

            # Build issue summary with context (hardcoded vs variable)
            if hasattr(result, "issues") and result.issues:
                rules_seen: list = []
                severities: set = set()
                contexts: set = set()

                for issue in result.issues:
                    if issue.get("rule") not in rules_seen:
                        rules_seen.append(issue.get("rule", "UNKNOWN"))
                    severities.add(issue.get("severity", "medium"))
                    if issue.get("context"):
                        contexts.add(issue["context"])

                # Priority for severity
                priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
                highest = max((priority.get(s, 0) for s in severities), default=2)
                sev_label = next((k for k, v in priority.items() if v == highest), "medium")

                # Color mapping
                color_map = {"critical": "red bold", "high": "yellow bold", "medium": "magenta", "low": "cyan"}
                color = color_map.get(sev_label, "white")

                # Show rules
                rules_text = ", ".join(rules_seen[:3])
                if len(rules_seen) > 3:
                    rules_text += f" +{len(rules_seen) - 3}"

                # Context indicator
                if "hardcoded" in contexts:
                    context_note = "🔴 hardcoded"
                elif "deprecated" in contexts:
                    context_note = "🟠 deprecated"
                elif "variable" in contexts:
                    context_note = "🟡 env var"
                else:
                    context_note = ""

                issue_text = f"[{color}]{sev_label.upper()}[/{color}]: {rules_text}"
                if context_note:
                    issue_text += f" {context_note}"
            else:
                issue_text = "[dim]none[/dim]"

            table.add_row(str(i), status, name, icon, issue_text)

        console.print(table)

        # Show current selection count
        if selected:
            console.print(f"\n[dim]Selected: {len(selected)} of {len(item_names)}[/dim]")
        else:
            console.print(f"\n[dim]None selected[/dim]")

        console.print("\n[bold]Controls:[/bold]")
        console.print("  • Enter numbers to toggle (e.g. [green]'1,3,5'[/green])")
        console.print("  • Type [cyan]'all'[/cyan] or [cyan]'none'[/cyan]")
        console.print("  • Press [bold white]Enter[/] to confirm")

        choice = Prompt.ask("\nSelection", default="done")
        
        # Parse input
        result = parse_multiselect_input(choice, item_names, selected)
        
        # If user typed 'done' or pressed Enter with empty input and has selection, confirm and exit
        if result is None or choice.strip() == "":
            if selected:
                console.print(f"\n[green]✓ Selected {len(selected)} items[/green]")
            break
        
        # Update selection and loop to show updated table
        selected = result

    # Build selected items list
    selected_items = [item_map[k][0] for k in selected if k in item_map]

    # Confirmation
    console.print("\n[bold green]📋 Selection Summary[/]\n")
    summary = Table(box=box.SIMPLE, show_header=False)
    summary.add_column("Item", style="cyan")
    for item, _, _ in [item_map[k] for k in sorted(selected)]:
        name = item.get("name") or item.get("filename") or str(item)
        summary.add_row(f"  • {name}")
    console.print(summary)

    confirmed = Confirm.ask("\n[bold]Confirm this selection?[/]", default=True)
    return selected_items, confirmed




def _generate_public_repo_readme(repo_url: str) -> str:
    """Generate README.md for public repo from template."""
    # Get username and repo name from URL
    repo_name = repo_url.replace("https://github.com/", "").replace(".git", "")
    if "/" not in repo_name:
        return ""

    parts = repo_name.split("/")
    username = parts[0]
    full_repo_name = repo_name

    # Try to read template
    template_path = TEMPLATES_DIR / "README_public_repo.md"
    if template_path.exists():
        content = template_path.read_text()
        return content.format(
            repo_name=parts[1],
            full_repo_name=full_repo_name,
            username=username,
        )

    # Fallback: generate basic README
    return f"""# {parts[1]}

Public repository for sharing AI agent skills and configuration.

## Installation

```bash
npx skills add {full_repo_name}
```

## About

Published using [agent-sync](https://github.com/{username}/agent-sync).
"""


def _generate_skills_readme(repo_url: str) -> str:
    """Generate skills/README.md from template."""
    repo_name = repo_url.replace("https://github.com/", "").replace(".git", "")
    if "/" not in repo_name:
        return ""

    parts = repo_name.split("/")
    username = parts[0]
    full_repo_name = repo_name

    # Try to read template
    template_path = TEMPLATES_DIR / "README_skills.md"
    if template_path.exists():
        content = template_path.read_text()
        return content.format(
            full_repo_name=full_repo_name,
            username=username,
        )

    # Fallback
    return f"""# Skills

Install skills with:

```bash
npx skills add {full_repo_name}
```
"""


# =============================================================================
# AGENT INSTRUCTIONS PUBLISHING
# =============================================================================

def get_available_agents() -> list[dict]:
    """Get available agent instruction files from discovery."""
    return get_available_agents_from_discovery()


def render_agents_table(agents: list, selected_names: set) -> Table:
    """Render TUI table for agent instruction selection."""
    table = Table(box=box.ROUNDED, show_header=True,
                  header_style="bold cyan", expand=True)
    table.add_column("ID", justify="right", style="dim", width=4)
    table.add_column("Pub", justify="center", width=5)
    table.add_column("Agent", style="green")
    table.add_column("File", style="cyan")
    table.add_column("Security", justify="center", width=10)

    for i, agent in enumerate(agents, 1):
        key = f"{agent['agent']}:{agent['filename']}"
        is_selected = key in selected_names
        status = "[bold green]✓[/]" if is_selected else "[red]○[/]"
        result = scan_file(agent['path'])
        security_icon = "[red]⚠️[/]" if not result.safe else "[green]✓[/]"
        table.add_row(str(i), status, agent["agent"], agent["filename"], security_icon)

    return table


def interactive_agents_selection(agents: list, initial_selected: set) -> set:
    """TUI for selecting agent instructions to publish."""
    from ._selection import parse_multiselect_input

    selected = set(initial_selected)
    item_names = [f"{a['agent']}:{a['filename']}" for a in agents]

    while True:
        console.clear()
        console.print("\n[bold cyan]📤 Select Agent Instructions to Publish[/bold cyan]\n")

        table = render_agents_table(agents, selected)
        console.print(table)

        # Show current selection count
        if selected:
            console.print(f"\n[dim]Selected: {len(selected)} of {len(agents)}[/dim]")
        else:
            console.print(f"\n[dim]None selected[/dim]")

        console.print("\n[bold]Controls:[/bold]")
        console.print("  • Enter numbers to toggle (e.g. [green]'1,3,5'[/green])")
        console.print("  • Type [cyan]'all'[/cyan] or [cyan]'none'[/cyan]")
        console.print("  • Press [bold white]Enter[/] to confirm")

        choice = Prompt.ask("\nSelection", default="done")
        
        # Parse input
        result = parse_multiselect_input(choice, item_names, selected)
        
        # If user typed 'done' or pressed Enter with empty input and has selection, confirm and exit
        if result is None or choice.strip() == "":
            if selected:
                console.print(f"\n[green]✓ Selected {len(selected)} items[/green]")
            break
        
        # Update selection and loop to show updated table
        selected = result

    return selected


def show_security_panel(results: dict[Path, ScanResult]) -> str | list[Path]:
    """Show security panel for files with issues.
    
    Returns: 'cancel', list of Path to skip, or empty list to continue.
    """
    unsafe_files = {path: result for path, result in results.items() if not result.safe}

    if not unsafe_files:
        return []

    panel_content = []
    for path, result in unsafe_files.items():
        issues_text = format_issues_for_display(result.issues)
        panel_content.append(f"[bold]{path.name}[/] ([yellow]{path.parent.name}[/])\n{issues_text}")

    console.print(Panel(
        "\n\n".join(panel_content),
        title="[bold yellow]⚠️  Security Warnings Detected[/bold yellow]",
        border_style="yellow",
    ))

    console.print("\n[bold]What would you like to do?[/]")
    console.print("  [[bold green]c[/]] Continue publishing (you've been warned)")
    console.print("  [[bold cyan]e[/]] Edit files before publishing (opens $EDITOR)")
    console.print("  [[bold magenta]s[/]] Skip unsafe files from selection")
    console.print("  [[bold red]q[/]] Cancel publish")

    choice = Prompt.ask("\nChoice", choices=["c", "e", "s", "q"], default="s")

    if choice == "q":
        return "cancel"
    elif choice == "s":
        return list(unsafe_files.keys())
    elif choice == "e":
        editor = os.environ.get("EDITOR", "vim")
        for path in unsafe_files:
            console.print(f"\n[bold]Editing {path}[/]")
            subprocess.run([editor, str(path)], check=False)
        return []
    else:
        return []


def publish_agents(
    repo_url: str | None = None,
    dry_run: bool = False,
    interactive: bool = False,
    selected_override: set | None = None,
    skip_confirm: bool = False,
) -> bool:
    """Publish selected agent instructions to a public GitHub repository."""
    config = Config()

    available_agents = get_available_agents()
    if not available_agents:
        console.print("\n[yellow]⚠ No agent instruction files found.[/yellow]\n")
        return False

    scan_results = {item["path"]: scan_file(item["path"]) for item in available_agents}

    selected = selected_override if selected_override is not None else set()

    if interactive:
        saved = config.published_agents
        if not selected:
            selected = set(saved) if saved else set()
        selected = interactive_agents_selection(available_agents, selected)
    else:
        if not selected:
            selected = {f"{a['agent']}:{a['filename']}" for a in available_agents}

    selected_items = [
        item for item in available_agents
        if f"{item['agent']}:{item['filename']}" in selected
    ]

    if not selected_items:
        console.print("\n[yellow]⚠ No agent instructions selected[/yellow]\n")
        return False

    if interactive:
        selected_paths = [item["path"] for item in selected_items]
        selected_results = {p: scan_results[p] for p in selected_paths}
        skip_result = show_security_panel(selected_results)
        if skip_result == "cancel":
            console.print("\n[yellow]Publish cancelled[/yellow]\n")
            return False
        if skip_result:
            selected_items = [i for i in selected_items if i["path"] not in skip_result]
            selected = {f"{i['agent']}:{i['filename']}" for i in selected_items}

    if not selected_items:
        console.print("\n[yellow]⚠ All files skipped[/yellow]\n")
        return False

    console.print("\n[bold green]📋 Summary[/]\n")
    summary = Table(box=box.SIMPLE)
    summary.add_column("Agent", style="green")
    summary.add_column("File", style="cyan")
    summary.add_column("Security", justify="center")
    for item in selected_items:
        result = scan_results[item["path"]]
        icon = "[red]⚠️[/]" if not result.safe else "[green]✓[/]"
        summary.add_row(item["agent"], item["filename"], icon)
    console.print(summary)

    console.print("\n[dim]💡 Want to publish also skills? Use [bold]agent-sync publish --skills[/bold][/dim]")

    repo_url = _resolve_repo_url(repo_url)
    if not repo_url:
        return False

    _check_repo_visibility(repo_url)

    if dry_run:
        console.print(f"\n[blue]🔍 DRY RUN: Would publish {len(selected_items)} agent instructions to {repo_url}[/blue]\n")
        return True

    if interactive and not skip_confirm and not Confirm.ask("\n[bold red]Confirm publishing?[/]", default=True):
        console.print("\n[yellow]Publish cancelled[/yellow]\n")
        return False

    return _push_agents_to_repo(selected_items, repo_url, config)


def _push_agents_to_repo(items: list[dict], repo_url: str, config: Config) -> bool:
    """Clone repo, copy agents/, commit, push."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        _git_clone_or_init(repo_url, tmp_path)

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(exist_ok=True)

        for item in items:
            agent_subdir = agents_dir / item["agent"]
            agent_subdir.mkdir(exist_ok=True)
            shutil.copy2(item["path"], agent_subdir / item["filename"])

        readme_path = tmp_path / "README.md"
        if readme_path.exists():
            readme_path.write_text(_generate_readme_for_agents(items, repo_url))

        console.print(f"\n[bold]📤 Publishing {len(items)} agent instructions...[/]")

        try:
            _git_push(tmp_path, repo_url, f"feat: publish {len(items)} agent instructions")
            console.print(f"\n[green]✓ Published {len(items)} agent instructions to {repo_url}![/green]\n")
            config.published_agents = [f"{i['agent']}:{i['filename']}" for i in items]
            return True
        except Exception as e:
            console.print(f"\n[red]✗ Failed to publish: {e}[/red]\n")
            return False


def _generate_readme_for_agents(items: list[dict], repo_url: str) -> str:
    """Generate agents/README section for the repository README."""
    repo_name = repo_url.replace("https://github.com/", "").replace(".git", "")
    sections: dict[str, list[str]] = {}
    for item in items:
        agent = item["agent"]
        if agent not in sections:
            sections[agent] = []
        sections[agent].append(item["filename"])

    lines = ["\n## Agent Instructions\n"]
    for agent, files in sorted(sections.items()):
        lines.append(f"### {agent}")
        for f in files:
            lines.append(f"- `{f}`")
        lines.append("")
    return "\n".join(lines)


# =============================================================================
# SKILLS PUBLISHING
# =============================================================================


def get_available_skills() -> list[dict]:
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
    from ._selection import parse_multiselect_input

    selected = set(initial_selected)
    item_names = [s["name"] for s in skills]

    while True:
        console.clear()
        console.print("\n[bold magenta]📤 Select Skills to Publish[/bold magenta]\n")

        table = render_selection_table(skills, selected)
        console.print(table)

        # Show current selection count
        if selected:
            console.print(f"\n[dim]Selected: {len(selected)} of {len(skills)}[/dim]")
        else:
            console.print(f"\n[dim]None selected[/dim]")

        console.print("\n[bold]Controls:[/bold]")
        console.print("  • Enter numbers to toggle (e.g. [green]'1,3,5'[/green])")
        console.print("  • Type [cyan]'all'[/cyan] or [cyan]'none'[/cyan]")
        console.print("  • Press [bold white]Enter[/] to confirm")

        choice = Prompt.ask("\nSelection", default="done")
        
        # Parse input
        result = parse_multiselect_input(choice, item_names, selected)
        
        # If user typed 'done' or pressed Enter with empty input and has selection, confirm and exit
        if result is None or choice.strip() == "":
            if selected:
                console.print(f"\n[green]✓ Selected {len(selected)} items[/green]")
            break
        
        # Update selection and loop to show updated table
        selected = result

    return selected


def show_selection_summary(selected_names: set) -> bool:
    """Show summary table and confirm."""
    console.print("\n[bold green]📋 Selection Summary[/] [dim](to be published)[/dim]\n")
    summary_table = Table(box=box.SIMPLE, show_header=False)
    summary_table.add_column("Skill", style="cyan")
    for name in sorted(list(selected_names)):
        summary_table.add_row(f"  • {name}")
    console.print(summary_table)

    return Confirm.ask("\n[bold]Confirm this selection?[/]", default=True)


def publish_skills(repo_url: str | None = None, dry_run: bool = False, interactive: bool = False, skip_security_panel: bool = False, skip_confirm: bool = False) -> bool:
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
    missing = set(saved_selection) - set(valid_saved)
    if missing:
        console.print("\n[yellow]⚠ The following previously published skills no longer exist locally [/yellow][red](removed from selection)[/red]:")
        for name in sorted(missing):
            console.print(f"  [red]• {name}[/red]")
        console.print()
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

    # 4. SECURITY WARNING & REPO SETTINGS (Skip if already shown by caller)
    if not skip_security_panel:
        console.print("\n")
        console.print(Panel(
            "[yellow]⚠️  SECURITY WARNING[/yellow]\n\n"
            "You are about to publish skills to a [bold]PUBLIC[/] repository.\n\n"
            "What WILL be published:\n"
            "  ✓ SKILL.md files (skill definitions)\n"
            "  ✓ .md, .py, .sh files (skill scripts)\n"
            "  ✓ references/, templates/, scripts/ directories\n\n"
            "What will NEVER be published:\n"
            "  ✗ Any config files (settings.json, config.yaml, etc.)\n"
            "  ✗ Files with: auth, token, key, secret, credentials in name\n"
            "  ✗ .env files\n"
            "  ✗ Your private agent-sync-private repository",
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

    if not skip_confirm and not Confirm.ask("\n[bold red]Confirm publishing to GitHub?[/]", default=True):
        console.print("\n[yellow]Publish cancelled[/yellow]\n")
        return False

    # 5. SECURITY SCAN (same as agents)
    console.print("\n[dim]🔍 Scanning skills for sensitive content...[/dim]")

    # Collect all files from selected skills (skip binary/incompatible files)
    all_files: list[Path] = []
    file_to_skill: dict[Path, str] = {}
    for skill in selected_skills:
        if skill["path"].is_dir():
            for f in skill["path"].rglob("*"):
                if f.is_file() and not f.name.startswith(".") and f.suffix not in SKIP_EXTENSIONS and "__pycache__" not in str(f):
                    all_files.append(f)
                    file_to_skill[f] = skill["name"]
        elif skill["path"].is_file() and skill["path"].suffix not in SKIP_EXTENSIONS:
            all_files.append(skill["path"])
            file_to_skill[skill["path"]] = skill["name"]

    # Scan all files
    scan_results = {f: scan_file(f) for f in all_files}

    # Identify files to skip (dangerous names)
    SKIP_NAMES = {"auth", "token", "key", "secret", "credentials", "password"}
    skip_files = set()
    for f in all_files:
        if any(skip in f.name.lower() for skip in SKIP_NAMES):
            skip_files.add(f)

    # Identify flagged files (scanner detected issues but not critical block)
    flagged_files = {
        f: r for f, r in scan_results.items()
        if f not in skip_files and not r.safe
    }

    # Show skip summary
    if skip_files:
        console.print(f"[yellow]  ⏭ {len(skip_files)} files skipped (dangerous name)[/yellow]")

    # Show flagged (warning only, still published)
    if flagged_files:
        console.print(f"[yellow]  ⚠️ {len(flagged_files)} files flagged (review after publish)[/yellow]")
        for f, result in flagged_files.items():
            skill_name = file_to_skill[f]
            console.print(f"    [dim]• {skill_name}/{f.name}[/dim]")

    console.print("")

    # 6. EXECUTION
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        skills_tmp_dir = tmp_path / "skills"
        skills_tmp_dir.mkdir(parents=True, exist_ok=True)

        for skill in selected_skills:
            src, dst = skill["path"], skills_tmp_dir / skill["name"]
            if src.is_dir(): shutil.copytree(src, dst)
            else: shutil.copy2(src, dst)

        (tmp_path / "README.md").write_text(_generate_public_repo_readme(repo_url))
        (tmp_path / "skills" / "README.md").write_text(_generate_skills_readme(repo_url))
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
