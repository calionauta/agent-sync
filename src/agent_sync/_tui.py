"""Shared TUI helpers — DRY components for interactive CLI interfaces."""

from rich.console import Console

console = Console()


def build_footer_commands(
    commands: list[tuple[str, str]],
    default_key: str | None = None,
) -> list[tuple[str, str]]:
    """Build properly formatted footer commands for TUI.

    Standardizes the format of footer commands across all interactive interfaces.
    Each command should be provided WITHOUT brackets - this function adds them.

    Format (Rich markup):
        - Default key: [Enter][p]ush (default) [q][c]ancel
        - Other keys:   [1-N] toggle    [a]all    [n]none    [q]quit

    Args:
        commands: List of (key, description) tuples.
                  Key should be simple (a-z, 1-9, Enter, etc.)
                  Desc should be verb/action in lowercase (push, cancel, all, none)
        default_key: The key that is the default action (Enter/confirm key)

    Returns:
        List of (key, formatted_description) tuples ready for print_footer().

    Example:
        >>> build_footer_commands([("Enter", "push"), ("q", "cancel")], default_key="Enter")
        [("Enter", "\\[p]ush (default)"), ("q", "\\[c]ancel")]
    """
    if not commands:
        return []

    formatted = []
    for key, desc in commands:
        # Skip first letter in desc since we'll add it with brackets
        first_letter = desc[0] if desc else key[0] if key else ""
        desc_rest = desc[1:] if desc else ""

        # Format the description: \\[p] + ush = [p]ush (literal brackets)
        # Use \\ [ to escape for Rich markup, producing literal [ in output
        formatted_desc = f"\\[{first_letter}]{desc_rest}"

        # Add (default) marker if this is the default key
        if key == default_key:
            formatted_desc += " (default)"

        formatted.append((key, formatted_desc))

    return formatted


def print_footer(
    commands: list[tuple[str, str]],
    default_key: str | None = None,
) -> None:
    """Print a consistent footer bar with command shortcuts.

    Format: [Enter][p]ush (default)    [q][c]ancel

    Args:
        commands: List of (key, desc) tuples where:
                  - key: The key letter(s), e.g. "Enter", "q", "1-N"
                  - desc: Description with escaped brackets, e.g. "[p]ush", "[c]ancel"
        default_key: The key that is the default action (highlighted differently)
    """
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    parts = []
    for key, desc in commands:
        # Format: [Enter] + [p]ush (default) = [Enter][p]ush (default)
        if key == default_key:
            # Default action: cyan brackets + (default) marker
            label = f"[cyan][{key}][/]{desc}[dim] (default)[/dim]"
        else:
            # Other actions: cyan brackets
            label = f"[cyan][{key}][/]{desc}"
        parts.append(label)
    console.print("  " + "    ".join(parts))


def print_footer_simple(commands: list[tuple[str, str]]) -> None:
    """Print footer without default markers (for read-only lists)."""
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    cmd_parts = [f"[cyan][{k}][/]{desc}" for k, desc in commands]
    console.print("  " + "  ".join(cmd_parts))