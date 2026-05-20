"""Shared TUI helpers — DRY components for interactive CLI interfaces."""

from rich.console import Console

console = Console()


def print_footer(
    commands: list[tuple[str, str]],
    default_key: str | None = None,
) -> None:
    """Print a consistent footer bar with command shortcuts.

    Each command is a (key, desc) tuple.
    - key: The key letter(s), e.g. "a", "1-N", "Enter"
    - desc: Description with the key letter(s) highlighted, e.g. "(a)ll", "[r]emove"

    The key letter appears in brackets [a] in desc, and separately as [key].

    Example commands:
        ("a", "(a)ll")       → [a] (a)ll
        ("r", "[r]emove")     → [r] [r]emove  (key appears twice)
        ("1-N", " toggle")    → [1-N] toggle

    For short keys, desc should include (k)ey pattern:
        ("a", "(a)ll"), ("n", "(n)one"), ("q", "(q)uit")
    For multi-char keys, desc should include [key] pattern:
        ("1-N", " toggle"), ("Enter", " confirm")
    """
    console.print("[dim]────────────────────────────────────────────────────────[/]")
    parts = []
    for key, desc in commands:
        # Format: [key] desc  — key always in brackets, desc as-is
        if key == default_key or (default_key and key == default_key):
            label = f"[cyan][{key}][/]{desc}[dim] (default)[/dim]"
        else:
            label = f"[cyan][{key}][/]{desc}"
        parts.append(label)
    console.print("  " + "    ".join(parts))