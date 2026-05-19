"""Reusable TUI components for multi-selection interfaces.

SoC: UI logic separated from domain models (models.py).
DRY: Single MultiSelectTUI for skills, agents, and any multi-select scenario.
"""

from typing import Callable, Optional

from rich.console import Console

from .models import (
    SelectionState,
    SourceInfo,
)


console = Console()


# =============================================================================
# SOURCE INFO (re-export for backward compatibility)
# =============================================================================

# SourceInfo is now imported from models


# =============================================================================
# MULTI-SELECT TUI (Main Controller)
# =============================================================================

class MultiSelectTUI:
    """Reusable multi-selection TUI with single-column list display.
    
    Usage:
        tui = MultiSelectTUI(
            title="Skills Selection",
            footer_commands=[
                ("1-N", "select"),
                ("a", "all"),
                ("n", "none"),
                ("p", "publish"),
                ("q", "quit"),
            ],
            on_publish=my_publish_func,
        )
        result = tui.run(sources, initial_selection)
    """
    
    def __init__(
        self,
        title: str,
        footer_commands: list[tuple[str, str]],
        on_publish: Optional[Callable[[dict[str, list[str]]], Optional[dict]]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        self.title = title
        self.footer_commands = footer_commands
        self.on_publish = on_publish
        self.on_cancel = on_cancel
    
    def run(
        self,
        sources: list[SourceInfo],
        initial_selection: dict[str, set[str]] = None,
    ) -> Optional[dict[str, list[str]]]:
        """Run the TUI and return selection dict, or None if cancelled."""
        
        # Build state from sources (items already sorted alphabetically)
        state = SelectionState()
        for src in sources:
            state.items[src.source_id] = sorted(src.items)
        
        state.selected = initial_selection or {src.source_id: set() for src in sources}
        state.build_index()
        
        # Create source map for lookups
        source_map = {src.source_id: src for src in sources}
        
        while True:
            console.clear()
            self._print_header(state)
            self._print_sources(state, sources)
            self._print_footer()
            
            choice = self._get_input()
            
            result = self._handle_input(choice, state, sources)
            if result == "continue":
                continue  # Keep going
            elif result is None:
                return None  # Cancelled
            else:
                return result  # Published
    
    def _print_header(self, state: SelectionState) -> None:
        """Print the header with title and selection count."""
        total = state.get_total_count()
        selected = state.get_selected_count()
        
        console.print(f"\n[bold cyan]{self.title}[/]")
        console.print("[dim]────────────────────────────────────────────────────────[/]")
        console.print(f"  Total: [bold]{total}[/] | Selected: [bold green]{selected}[/]")
        
        # Show selected items preview
        selected_names = state.get_selected_names()
        if selected_names:
            preview = ", ".join(selected_names[:5])
            if len(selected_names) > 5:
                preview += f" [+{len(selected_names) - 5} more]"
            console.print(f"  [dim]Selected:[/dim] {preview}")
    
    def _print_sources(self, state: SelectionState, sources: list[SourceInfo]) -> None:
        """Print all sources with their items in single column."""
        console.print()
        
        current_idx = 1
        for src in sources:
            src_selected = len(state.selected.get(src.source_id, set()))
            src_total = len(src.items)
            
            status_icon = self._get_status_icon(src.status)
            
            # Source header
            console.print(f"[bold magenta]▸ {src.label}[/]")
            if src.subtitle:
                console.print(f"  [dim]{src.subtitle}[/]")
            if src.extra:
                console.print(f"  [yellow]{src.extra}[/]")
            console.print(f"  [dim][{src_selected}/{src_total}][/] {status_icon}")
            
            if not src.items:
                console.print("  [dim]  No items found[/]")
            else:
                for name in src.items:
                    is_sel = state.is_selected(src.source_id, name)
                    status = "[green]●[/]" if is_sel else "[dim]○[/]"
                    console.print(f"    [dim]{current_idx:02d}[/] {status} {name}")
                    current_idx += 1
            
            console.print()
    
    def _print_footer(self) -> None:
        """Print the footer with commands."""
        console.print("[dim]────────────────────────────────────────────────────────[/]")
        
        cmd_parts = []
        for key, desc in self.footer_commands:
            cmd_parts.append(f"[cyan][{key}][/]{desc}")
        
        console.print("  " + "  ".join(cmd_parts))
    
    def _get_input(self) -> str:
        """Get user input."""
        from rich.prompt import Prompt
        return Prompt.ask("\n[cyan]>[/]", default="publish")
    
    def _handle_input(
        self,
        choice: str,
        state: SelectionState,
        sources: list[SourceInfo],
    ) -> Optional[dict]:
        """Handle user input."""
        
        if choice in ("q", "quit"):
            if self.on_cancel:
                self.on_cancel()
            return None
        
        elif choice in ("a", "all"):
            state.select_all()
        
        elif choice in ("n", "none"):
            state.select_none()
        
        elif choice in ("p", "publish"):
            if self.on_publish:
                result = self.on_publish(state.get_selection_dict())
                if result:
                    return state.get_selection_dict()
            return state.get_selection_dict()
        
        else:
            self._handle_number_input(choice, state)
        
        return "continue"
    
    def _handle_number_input(self, input_str: str, state: SelectionState) -> None:
        """Parse and handle number input like '1,3,5-10'."""
        from .models import parse_number_input
        
        try:
            indices = parse_number_input(input_str)
            state.selected = {src: set() for src in state.items.keys()}
            for idx in indices:
                state.toggle_by_index(idx)
        except (ValueError, TypeError):
            pass
    
    def _get_status_icon(self, status: str) -> str:
        """Get status icon."""
        icons = {
            "active": "[green]✓[/]",
            "failed": "[red]✗[/]",
            "skipped": "[yellow]⚠[/]",
            "unknown": "[dim]?[/]",
        }
        return icons.get(status, "[dim]?[/]")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_skills_tui(
    on_publish: Optional[Callable] = None,
    on_cancel: Optional[Callable] = None,
) -> MultiSelectTUI:
    """Create a TUI for skills selection."""
    return MultiSelectTUI(
        title="📚 Skills Selection",
        footer_commands=[
            ("a", "select all"),
            ("n", "clear"),
            ("p", "publish"),
            ("q", "quit"),
        ],
        on_publish=on_publish,
        on_cancel=on_cancel,
    )


def create_agents_tui(
    on_publish: Optional[Callable] = None,
    on_cancel: Optional[Callable] = None,
) -> MultiSelectTUI:
    """Create a TUI for agents selection."""
    return MultiSelectTUI(
        title="🤖 Agents Selection",
        footer_commands=[
            ("a", "select all"),
            ("n", "clear"),
            ("p", "publish"),
            ("q", "quit"),
        ],
        on_publish=on_publish,
        on_cancel=on_cancel,
    )