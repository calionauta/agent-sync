"""Shared interactive TUI selection utilities."""

from typing import Set, List


def parse_multiselect_input(choice: str, items: List[str], selected: Set[str]) -> Set[str]:
    """Parse user input for a multi-select TUI and return updated selection.
    
    Handles comma-separated numbers ("1,3,5"), "all", "none", "done", and empty input.
    Numbers toggle the item's selection state.
    
    Args:
        choice: Raw user input string.
        items: Full ordered list of selectable items.
        selected: Currently selected items.
    
    Returns:
        Updated set of selected items. Returns None if choice is "done" or empty.
    """
    if choice.lower() in ("done", ""):
        return None
    if choice.lower() == "all":
        return set(items)
    if choice.lower() == "none":
        return set()
    try:
        indices = [int(x.strip()) - 1 for x in choice.split(",")]
        for idx in indices:
            if 0 <= idx < len(items):
                name = items[idx]
                if name in selected:
                    selected.remove(name)
                else:
                    selected.add(name)
    except ValueError:
        pass
    return selected
