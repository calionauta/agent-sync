from __future__ import annotations


"""Publish setup flows - orchestrates discovery, selection, and publishing.

SoC: Orchestration logic separated from git operations and discovery.
DRY: Single entry point per publish mode (skills, agents, setup).
"""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt

from .config import get_published_repo, load_config, save_selected_skills, PublishStateManager
from .discovery import discover_skills_sources, skills_to_source_infos, discover_agents_sources, load_saved_selection
from .git_publish import publish_skills, publish_agents, publish_all
from .models import SelectionState, SourceInfo


console = Console()


# =============================================================================
# CONFIRM HELPER (reusable)
# =============================================================================

def confirm(prompt: str, default_yes: bool = True) -> bool:
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


# =============================================================================
# SKILLS-ONLY FLOW (legacy single-source TUI)
# =============================================================================

def run_skills_flow() -> bool:
    """Run skills-only publish flow with step-by-step TUI.
    
    Reuses run_publish_setup() but skips agents step.
    
    Returns:
        True if published successfully
    """
    published_repo = get_published_repo()
    
    if not published_repo:
        print_repo_not_configured()
        return False
    
    console.print("\n[blue]🔍 Discovering skills...[/]")
    
    config = load_config()
    skills_sources = discover_skills_sources(config)
    
    if not skills_sources:
        console.print("[yellow]⚠ No skills found![/]")
        return False
    
    # Build source infos for skills only
    source_infos = skills_to_source_infos(skills_sources)
    
    # Build combined source infos (including agents placeholder for load_saved_selection)
    agents_source_infos = discover_agents_sources()
    all_source_infos = list(source_infos) + list(agents_source_infos)
    
    # Load saved state from PublishStateManager (consistent with run_publish_setup)
    selection = load_saved_selection(all_source_infos)
    
    # Filter to skills only
    skills_selection = {k: v for k, v in selection.items() if k != "agents"}
    
    # Step-by-step through each source
    for src_info in source_infos:
        if not src_info.items:
            console.print(f"\n[dim]Skipping {src_info.label} (no items)[/]")
            continue
        
        # Title
        if src_info.source_id == "local":
            title = "📁 LOCAL"
        else:
            title = f"📦 {src_info.label}"
        
        # Build state
        state = SelectionState()
        state.items = {src_info.source_id: sorted(src_info.items)}
        state.selected = {src_info.source_id: skills_selection.get(src_info.source_id, set())}
        state.build_index()
        
        # Source loop
        while True:
            console.clear()
            
            console.print(f"\n[bold cyan]{title}[/]")
            console.print("[dim]────────────────────────────────────────────────────────[/]")
            
            selected = len(state.selected.get(src_info.source_id, set()))
            total = len(src_info.items)
            console.print(f"  Selected: [bold green]{selected}[/] / {total}")
            
            if src_info.subtitle:
                console.print(f"  [dim]{src_info.subtitle}[/]")
            
            console.print()
            
            current_idx = 1
            for name in src_info.items:
                is_sel = state.is_selected(src_info.source_id, name)
                status = "[green]●[/]" if is_sel else "[dim]○[/]"
                console.print(f"    [dim]{current_idx:02d}[/] {status} {name}")
                current_idx += 1
            
            console.print()
            console.print("[dim]────────────────────────────────────────────────────────[/]")
            console.print("  (1-N) select  (a) all  (n) none  (done) next  (q) quit")
            
            choice = Prompt.ask("\n[cyan]>[/]", default="done")
            choice = choice.strip()
            
            if choice in ("done", "d"):
                skills_selection[src_info.source_id] = state.selected.get(src_info.source_id, set())
                break
            
            if choice == "q":
                console.print("\n[yellow]Cancelled.[/]")
                return False
            
            if choice in ("a", "all"):
                state.select_all_in_source(src_info.source_id)
            elif choice in ("n", "none"):
                state.select_none_in_source(src_info.source_id)
            else:
                _handle_number_input(state, choice)
    
    # Summary
    console.clear()
    console.print("\n[bold cyan]📦 Publish Summary[/]")
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    
    total_selected = 0
    for src_info in source_infos:
        selected = skills_selection.get(src_info.source_id, set())
        if selected:
            console.print(f"\n[bold]{src_info.label}[/] - {len(selected)} selected:")
            for name in sorted(selected):
                console.print(f"  • {name}")
            total_selected += len(selected)
        else:
            console.print(f"\n[dim]{src_info.label}[/] - none selected")
    
    if total_selected == 0:
        console.print("\n[yellow]⚠ Nothing selected![/]")
        return False
    
    console.print()
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    
    if not confirm(f"\nPublish {total_selected} skills to [green]{published_repo}[/]?"):
        console.print("\n[yellow]Cancelled.[/]")
        return False
    
    # Publish skills only (single operation)
    console.print("\n[blue]Publishing...[/]")
    from .git_publish import publish_all
    success = publish_all(skills_selection, skills_sources, [], published_repo)
    
    if success:
        console.print("\n[green]✓ Published successfully![/]")
        PublishStateManager.save(skills_selection, {"agents": []})
        return True
    
    return False


def _build_initial_selection(config, sources) -> dict[str, set[str]]:
    """Build initial selection from config."""
    selection: dict[str, set[str]] = {}
    for src in sources:
        saved = config.get_skills_for_source(src.source_id)
        selection[src.source_id] = set(saved) if saved else set()
    return selection


def _build_footer_commands(source_infos: list[SourceInfo]) -> list[tuple[str, str]]:
    """Build footer commands for single-source TUI."""
    if not source_infos:
        return [("p", "publish"), ("q", "quit")]
    
    ranges = {}
    start = 1
    for src in source_infos:
        end = start + len(src.items) - 1
        ranges[src.source_id] = (start, end)
        start = end + 1
    
    commands = []
    for src in source_infos:
        src_start, src_end = ranges[src.source_id]
        label = src.label[:6]
        commands.append((f"{src_start}-{src_end}", label))
    
    commands.extend([("a", "select all"), ("n", "none"), ("p", "publish"), ("q", "quit")])
    return commands


# =============================================================================
# AGENTS-ONLY FLOW
# =============================================================================

def run_agents_flow() -> bool:
    """Run agents-only publish flow with step-by-step TUI.
    
    Returns:
        True if published successfully
    """
    published_repo = get_published_repo()
    
    if not published_repo:
        print_repo_not_configured()
        return False
    
    console.print("\n[blue]🔍 Discovering agents...[/]")
    
    agents_source_infos = discover_agents_sources()
    
    if not agents_source_infos:
        console.print("[yellow]⚠ No agents found![/]")
        return False
    
    # Load saved state from PublishStateManager (consistent with other flows)
    selection = load_saved_selection(agents_source_infos)
    agents_selection = selection.get("agents", set())
    
    # Build state
    state = SelectionState()
    state.items = {"agents": sorted(agents_source_infos[0].items)}
    state.selected = {"agents": agents_selection}
    state.build_index()
    
    # TUI loop
    while True:
        console.clear()
        
        console.print("\n[bold cyan]🤖 AGENTS[/]")
        console.print("[dim]────────────────────────────────────────────────────────[/]")
        
        selected = len(state.selected.get("agents", set()))
        total = len(state.items.get("agents", []))
        console.print(f"  Selected: [bold green]{selected}[/] / {total}")
        console.print(f"  [dim]~/.pi/agent/[/]")
        console.print()
        
        current_idx = 1
        for name in state.items.get("agents", []):
            is_sel = state.is_selected("agents", name)
            status = "[green]●[/]" if is_sel else "[dim]○[/]"
            console.print(f"    [dim]{current_idx:02d}[/] {status} {name}")
            current_idx += 1
        
        console.print()
        console.print("[dim]────────────────────────────────────────────────────────[/]")
        console.print("  (1-N) select  (a) all  (n) none  (p) publish  (q) quit")
        
        choice = Prompt.ask("\n[cyan]>[/]", default="p")
        choice = choice.strip()
        
        if choice == "q":
            console.print("\n[yellow]Cancelled.[/]")
            return False
        
        if choice in ("a", "all"):
            state.select_all_in_source("agents")
        elif choice in ("n", "none"):
            state.select_none_in_source("agents")
        elif choice in ("p", "publish", "done", "d"):
            break
        else:
            _handle_number_input(state, choice)
    
    # Get final selection
    final_selection = list(state.selected.get("agents", set()))
    
    if not final_selection:
        console.print("\n[yellow]⚠ No agents selected![/]")
        return False
    
    # Summary
    console.clear()
    console.print("\n[bold cyan]📦 Publish Summary[/]")
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    console.print(f"\n[bold]AGENTS[/] - {len(final_selection)} selected:")
    for name in sorted(final_selection):
        console.print(f"  • {name}")
    console.print()
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    
    if not confirm(f"\nPublish {len(final_selection)} agents to [green]{published_repo}[/]?"):
        console.print("\n[yellow]Cancelled.[/]")
        return False
    
    # Publish using publish_all (consistent with other flows)
    console.print("\n[blue]Publishing...[/]")
    from .git_publish import publish_all
    success = publish_all({}, [], final_selection, published_repo)
    
    if success:
        console.print("\n[green]✓ Published successfully![/]")
        PublishStateManager.save({}, {"agents": final_selection})
        return True
    
    return False


# =============================================================================
# GENERIC TUI RUNNER
# =============================================================================

def _run_tui(
    title: str,
    sources: list[SourceInfo],
    initial_selection: dict[str, set[str]],
    footer_commands: list[tuple[str, str]],
    on_publish,
) -> bool:
    """Generic TUI runner.
    
    Args:
        title: TUI title
        sources: List of SourceInfo
        initial_selection: Initial selection state
        footer_commands: List of (key, description) tuples
        on_publish: Callback when user publishes
    
    Returns:
        True if published successfully
    """
    # Build state
    state = SelectionState()
    for src in sources:
        state.items[src.source_id] = sorted(src.items)
    
    state.selected = initial_selection.copy()
    state.build_index()
    
    # TUI loop
    while True:
        console.clear()
        _print_tui_header(title, state)
        _print_tui_sources(state, sources)
        _print_tui_footer(footer_commands)
        
        choice = Prompt.ask("\n[cyan]>[/]", default="p")
        choice = choice.strip()
        
        if choice in ("q", "quit"):
            return False
        
        if choice in ("a", "all"):
            state.select_all()
        elif choice in ("n", "none"):
            state.select_none()
        elif choice in ("p", "publish"):
            result = on_publish(state.get_selection_dict())
            if result:
                return True
        else:
            _handle_number_input(state, choice)


def _print_tui_header(title: str, state: SelectionState) -> None:
    """Print TUI header."""
    console.print(f"\n[bold cyan]{title}[/]")
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    console.print(f"  Total: [bold]{state.get_total_count()}[/] | Selected: [bold green]{state.get_selected_count()}[/]")
    
    selected_names = state.get_selected_names()
    if selected_names:
        preview = ", ".join(selected_names[:5])
        if len(selected_names) > 5:
            preview += f" [+{len(selected_names) - 5} more]"
        console.print(f"  [dim]Selected:[/dim] {preview}")


def _print_tui_sources(state: SelectionState, sources: list[SourceInfo]) -> None:
    """Print TUI sources."""
    console.print()
    
    current_idx = 1
    for src in sources:
        console.print(f"[bold magenta]▸ {src.label}[/]")
        if src.subtitle:
            console.print(f"  [dim]{src.subtitle}[/]")
        
        for name in src.items:
            is_sel = state.is_selected(src.source_id, name)
            status = "[green]●[/]" if is_sel else "[dim]○[/]"
            console.print(f"    [dim]{current_idx:02d}[/] {status} {name}")
            current_idx += 1
        
        console.print()


def _print_tui_footer(commands: list[tuple[str, str]]) -> None:
    """Print TUI footer."""
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    cmd_parts = [f"[cyan][{k}][/]{desc}" for k, desc in commands]
    console.print("  " + "  ".join(cmd_parts))


def _handle_number_input(state: SelectionState, input_str: str) -> None:
    """Handle number input for state."""
    from .models import parse_number_input
    
    try:
        indices = parse_number_input(input_str)
        state.selected = {src: set() for src in state.items.keys()}
        for idx in indices:
            state.toggle_by_index(idx)
    except (ValueError, TypeError):
        pass


# =============================================================================
# STEP-BY-STEP SETUP FLOW
# =============================================================================

def run_publish_setup() -> bool:
    """Step-by-step publish flow.
    
    Goes through each source (LOCAL → EXTERNAL → AGENTS) sequentially:
    1. Shows all items in the source
    2. User selects items (numbers, all, none, done)
    3. Moves to next source
    4. After all sources, shows summary and publishes
    
    Returns:
        True if published successfully, False otherwise.
    """
    published_repo = get_published_repo()
    
    if not published_repo:
        print_repo_not_configured()
        return False
    
    console.print("\n[blue]🔍 Discovering skills and agents...[/]")
    
    # Discover sources
    config = load_config()
    skills_sources = discover_skills_sources(config)
    agents_source_infos = discover_agents_sources()
    
    # Build combined source infos
    source_infos: list[SourceInfo] = []
    source_infos.extend(skills_to_source_infos(skills_sources))
    source_infos.extend(agents_source_infos)
    
    if not source_infos:
        console.print("[yellow]⚠ No skills or agents found![/]")
        return False
    
    # Load saved state
    selection = load_saved_selection(source_infos)
    
    # ============================================================
    # STEP-BY-STEP: Iterate through each source
    # ============================================================
    
    for src_info in source_infos:
        if not src_info.items:
            console.print(f"\n[dim]Skipping {src_info.label} (no items)[/]")
            continue
        
        # Title
        if src_info.source_id == "agents":
            title = "🤖 AGENTS"
        elif src_info.source_id == "local":
            title = "📁 LOCAL"
        else:
            title = f"📦 {src_info.label}"
        
        # Build state
        state = SelectionState()
        state.items = {src_info.source_id: sorted(src_info.items)}
        state.selected = {src_info.source_id: selection.get(src_info.source_id, set())}
        state.build_index()
        
        # Source loop
        while True:
            console.clear()
            
            console.print(f"\n[bold cyan]{title}[/]")
            console.print("[dim]────────────────────────────────────────────────────────[/]")
            
            selected = len(state.selected.get(src_info.source_id, set()))
            total = len(src_info.items)
            console.print(f"  Selected: [bold green]{selected}[/] / {total}")
            
            if src_info.subtitle:
                console.print(f"  [dim]{src_info.subtitle}[/]")
            
            console.print()
            
            current_idx = 1
            for name in src_info.items:
                is_sel = state.is_selected(src_info.source_id, name)
                status = "[green]●[/]" if is_sel else "[dim]○[/]"
                console.print(f"    [dim]{current_idx:02d}[/] {status} {name}")
                current_idx += 1
            
            console.print()
            console.print("[dim]────────────────────────────────────────────────────────[/]")
            console.print("  (1-N) select  (a) all  (n) none  (done) next  (q) quit")
            
            choice = Prompt.ask("\n[cyan]>[/]", default="done")
            choice = choice.strip()
            
            if choice in ("done", "d"):
                selection[src_info.source_id] = state.selected.get(src_info.source_id, set())
                break
            
            if choice == "q":
                console.print("\n[yellow]Cancelled.[/]")
                return False
            
            if choice in ("a", "all"):
                state.select_all_in_source(src_info.source_id)
            elif choice in ("n", "none"):
                state.select_none_in_source(src_info.source_id)
            else:
                _handle_number_input(state, choice)
    
    # ============================================================
    # SUMMARY
    # ============================================================
    
    console.clear()
    console.print("\n[bold cyan]📦 Publish Summary[/]")
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    
    total_selected = 0
    for src_info in source_infos:
        selected = selection.get(src_info.source_id, set())
        if selected:
            console.print(f"\n[bold]{src_info.label}[/] - {len(selected)} selected:")
            for name in sorted(selected):
                console.print(f"  • {name}")
            total_selected += len(selected)
        else:
            console.print(f"\n[dim]{src_info.label}[/] - none selected")
    
    if total_selected == 0:
        console.print("\n[yellow]⚠ Nothing selected![/]")
        return False
    
    console.print()
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    
    if not confirm(f"\nPublish {total_selected} items to [green]{published_repo}[/]?"):
        console.print("\n[yellow]Cancelled.[/]")
        return False
    
    # ============================================================
    # PUBLISH
    # ============================================================
    
    skills_sel = {k: list(v) for k, v in selection.items() if k != "agents"}
    agents_sel = list(selection.get("agents", set()))
    
    # Publish skills AND agents in ONE operation to prevent --force overwrite
    console.print("\n[blue]Publishing...[/]")
    success = publish_all(skills_sel, skills_sources, agents_sel, published_repo)
    
    if success:
        console.print("\n[green]✓ Published successfully![/]")
        PublishStateManager.save(skills_sel, {"agents": agents_sel})
        return True
    
    return False


# =============================================================================
# UTILITIES
# =============================================================================

def print_repo_not_configured() -> None:
    """Print message when repo is not configured."""
    console.print("[red]✗ Published repo not configured![/]")
    console.print("[dim]Run: agent-sync publish --repo https://github.com/user/repo[/]")