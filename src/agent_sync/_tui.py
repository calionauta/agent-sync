"""Shared TUI helpers — DRY components for interactive CLI interfaces."""

from typing import Optional

from rich.console import Console

console = Console()


def print_footer(
    commands: list[tuple[str, str]],
    default_key: str | None = None,
) -> None:
    """Print a consistent footer bar with command shortcuts.

    Pattern from publish TUI:
        [1-N]select    [a]all    [n]none    [m]move to hub    [Enter]confirm (default)

    Args:
        commands: List of (key, description) tuples.
                  Key can include brackets like "[1-N]" or be just "a".
        default_key: Key that gets (default) suffix. e.g. "Enter" → "[Enter]confirm (default)".
    """
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    parts = []
    for key, desc in commands:
        # Strip existing brackets from key if present
        key_clean = key.strip("[]")
        if key_clean == default_key or key == f"[{default_key}]":
            label = f"[cyan][{key_clean}][/]{desc} (default)"
        else:
            label = f"[cyan][{key_clean}][/]{desc}"
        parts.append(label)
    console.print("  " + "    ".join(parts))