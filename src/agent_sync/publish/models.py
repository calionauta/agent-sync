from __future__ import annotations


"""Domain models for publish feature.

Separated from UI logic (tui.py) for better SoC and testability.
Reusable across different interfaces (CLI, tests, etc).
"""

from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# SELECTION STATE
# =============================================================================

@dataclass
class SelectionState:
    """Core selection state for multi-select interfaces.
    
    Generic enough to work with skills, agents, or any items.
    Can be used independently of any TUI.
    
    Usage:
        state = SelectionState()
        state.items = {"local": ["a", "b"], "ext": ["c"]}
        state.selected = {"local": set(), "ext": set()}
        state.build_index()
        
        state.toggle("local", "a")
        state.select_all_in_source("ext")
        
        result = state.get_selection_dict()
    """
    items: dict[str, list[str]] = field(default_factory=dict)  # source_id -> item_names
    selected: dict[str, set[str]] = field(default_factory=dict)  # source_id -> selected_names
    item_index: dict[int, tuple[str, str]] = field(default_factory=dict)  # idx -> (source_id, item_name)
    
    def __post_init__(self):
        """Sort items alphabetically after initialization."""
        for src in self.items:
            self.items[src] = sorted(self.items[src])
    
    # ─────────────────────────────────────────────────────────────
    # Query methods
    # ─────────────────────────────────────────────────────────────
    
    def get_total_count(self) -> int:
        """Total number of items across all sources."""
        return sum(len(items) for items in self.items.values())
    
    def get_selected_count(self) -> int:
        """Number of selected items."""
        return sum(len(sel) for sel in self.selected.values())
    
    def get_selected_names(self) -> list[str]:
        """Get list of all selected item names, sorted."""
        result = []
        for source_id, selected_set in self.selected.items():
            for name in sorted(selected_set):
                result.append(name)
        return result
    
    def is_selected(self, source_id: str, item_name: str) -> bool:
        """Check if item is selected."""
        return item_name in self.selected.get(source_id, set())
    
    def get_source_range(self, source_id: str) -> tuple[int, int]:
        """Get the index range for a source (1-indexed)."""
        start = 1
        for src_id, items in self.items.items():
            if src_id == source_id:
                end = start + len(items) - 1
                return (start, end)
            start += len(items)
        return (0, 0)
    
    def get_all_source_ranges(self) -> dict[str, tuple[int, int]]:
        """Get index ranges for all sources."""
        result = {}
        start = 1
        for source_id, items in self.items.items():
            end = start + len(items) - 1
            result[source_id] = (start, end)
            start = end + 1
        return result
    
    # ─────────────────────────────────────────────────────────────
    # Mutation methods
    # ─────────────────────────────────────────────────────────────
    
    def toggle(self, source_id: str, item_name: str) -> None:
        """Toggle item selection."""
        if source_id not in self.selected:
            self.selected[source_id] = set()
        if item_name in self.selected[source_id]:
            self.selected[source_id].discard(item_name)
        else:
            self.selected[source_id].add(item_name)
    
    def toggle_by_index(self, idx: int) -> bool:
        """Toggle item by index. Returns True if toggled."""
        if idx in self.item_index:
            source_id, item_name = self.item_index[idx]
            self.toggle(source_id, item_name)
            return True
        return False
    
    def select_all(self) -> None:
        """Select all items in all sources."""
        self.selected = {src: set(items) for src, items in self.items.items()}
    
    def select_none(self) -> None:
        """Deselect all items."""
        self.selected = {src: set() for src in self.items.keys()}
    
    def select_all_in_source(self, source_id: str) -> None:
        """Select all items in a specific source."""
        if source_id in self.items:
            self.selected[source_id] = set(self.items[source_id])
    
    def select_none_in_source(self, source_id: str) -> None:
        """Deselect all items in a specific source."""
        if source_id in self.selected:
            self.selected[source_id] = set()
    
    def build_index(self) -> None:
        """Build item index for number-based selection."""
        self.item_index = {}
        idx = 1
        for source_id, item_names in self.items.items():
            for name in item_names:  # Already sorted
                self.item_index[idx] = (source_id, name)
                idx += 1
    
    def get_selection_dict(self) -> dict[str, list[str]]:
        """Get selection as dict (source_id -> [item_names])."""
        return {src: list(items) for src, items in self.selected.items()}


# =============================================================================
# SOURCE INFO
# =============================================================================

@dataclass
class SourceInfo:
    """Information about a source of items."""
    source_id: str
    label: str  # Display label (e.g., "LOCAL", "EXTERNAL", "AGENTS")
    subtitle: str = ""  # Extra info (e.g., path, repo URL)
    items: list[str] = field(default_factory=list)  # Item names
    status: str = "active"  # Status icon: active, failed, skipped, unknown
    extra: str = ""  # Extra info like staleness


# =============================================================================
# SOURCE PICKER (for picker UI)
# =============================================================================

@dataclass
class SourcePickerItem:
    """A source displayed in the picker list."""
    source_id: str
    label: str
    item_count: int
    selected_count: int
    subtitle: str = ""
    is_empty: bool = False


@dataclass
class PublishState:
    """State of a publish session (saved after successful publish)."""
    timestamp: Optional[str] = None
    skills: dict[str, list[str]] = field(default_factory=dict)
    agents: dict[str, list[str]] = field(default_factory=dict)
    
    def get_skills_count(self) -> int:
        return sum(len(v) for v in self.skills.values())
    
    def get_agents_count(self) -> int:
        return sum(len(v) for v in self.agents.values())
    
    def get_total_count(self) -> int:
        return self.get_skills_count() + self.get_agents_count()
    
    def is_empty(self) -> bool:
        return self.get_total_count() == 0
    
    def get_all_source_ids(self) -> set[str]:
        result = set(self.skills.keys())
        result.update(self.agents.keys())
        return result
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "skills": self.skills,
            "agents": self.agents,
        }
    
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "PublishState":
        if not data:
            return cls()
        return cls(
            timestamp=data.get("timestamp"),
            skills=data.get("skills", {}),
            agents=data.get("agents", {}),
        )


# =============================================================================
# PICKER ITEM BUILDER (helper for picker UI)
# =============================================================================

def build_picker_items(
    source_infos: list[SourceInfo],
    selection: dict[str, set[str]],
) -> list[SourcePickerItem]:
    """Build picker items from source infos and selection.
    
    Args:
        source_infos: List of SourceInfo objects
        selection: Dict of source_id -> set of selected item names
    
    Returns:
        List of SourcePickerItem for display
    """
    items = []
    for src in source_infos:
        selected = len(selection.get(src.source_id, set()))
        items.append(SourcePickerItem(
            source_id=src.source_id,
            label=src.label,
            item_count=len(src.items),
            selected_count=selected,
            subtitle=src.subtitle,
            is_empty=len(src.items) == 0,
        ))
    return items


# =============================================================================
# NUMBER INPUT PARSER
# =============================================================================

def parse_number_input(input_str: str) -> list[int]:
    """Parse input like '1,3,5-10' into list of integers.
    
    Args:
        input_str: User input like "1,3-5,7" or "1-10"
    
    Returns:
        List of indices, e.g., [1, 3, 4, 5, 7]
    
    Examples:
        parse_number_input("1")        → [1]
        parse_number_input("1,3,5")    → [1, 3, 5]
        parse_number_input("1-5")      → [1, 2, 3, 4, 5]
        parse_number_input("1,3-5,7")  → [1, 3, 4, 5, 7]
        parse_number_input("1, 3, 5")  → [1, 3, 5]  (spaces ignored)
    """
    indices = []
    parts = input_str.replace(" ", "").split(",")
    for part in parts:
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            indices.extend(range(int(start), int(end) + 1))
        else:
            indices.append(int(part))
    return indices


def handle_number_input_for_state(
    state: SelectionState,
    source_id: str,
    input_str: str,
) -> None:
    """Handle number input for a single-source state.
    
    REPLACES selection (clears first, then selects given indices).
    
    Args:
        state: SelectionState with items and selected
        source_id: Source being configured
        input_str: User input like "1,3,5-10"
    """
    try:
        indices = parse_number_input(input_str)
        
        # Replace selection (clear first, then select given indices)
        state.selected[source_id] = set()
        
        for idx in indices:
            if idx in state.item_index:
                src, name = state.item_index[idx]
                if src == source_id:
                    state.selected[source_id].add(name)
                    
    except (ValueError, TypeError):
        pass