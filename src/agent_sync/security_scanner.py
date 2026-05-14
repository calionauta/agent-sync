"""
Security scanner for agent instruction files.

Detects potentially sensitive content before public publishing:
- Absolute paths (/Users/, /home/, /root/, C:\\)
- API tokens and keys (sk-, ghp_, api_, secret)
- Internal commands (/skill:, /ctx-, ctx_batch_execute)
- Server paths (server., .renatocaliari.com)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict, Optional


class Issue(TypedDict):
    """Represents a detected security issue."""
    rule: str  # e.g., "ABS_PATH_UNIX", "TOKEN_OPENAI"
    severity: str  # "critical" | "high" | "medium" | "low"
    snippet: str  # The matched text (truncated for display)


@dataclass
class ScanResult:
    """Result of scanning a file for sensitive content."""
    safe: bool  # True if no critical issues found
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""  # Error message if file couldn't be read


# Regex patterns for detection
# Format: (rule_name, severity, pattern)
PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # Absolute paths
    ("ABS_PATH_UNIX", "high", re.compile(r"/Users/\w+/")),
    ("ABS_PATH_HOME", "medium", re.compile(r"/home/\w+/")),
    ("ABS_PATH_ROOT", "high", re.compile(r"/root/")),
    ("ABS_PATH_WINDOWS", "high", re.compile(r"[A-Z]:\\[\w\\]+")),
    # Tokens and keys
    ("TOKEN_OPENAI", "critical", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("TOKEN_GITHUB", "critical", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("TOKEN_GITHUB_ALT", "critical", re.compile(r"gho_[A-Za-z0-9]{36}")),
    ("KEY_API", "critical", re.compile(r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[\w-]{20,}['\"]?")),
    ("KEY_SECRET", "critical", re.compile(r"(?i)(secret|password|passwd)\s*[=:]\s*['\"]?[\w!@#$%^&*]{8,}['\"]?")),
    # Internal commands
    ("INTERNAL_CMD_SKILL", "high", re.compile(r"/skill:[a-z0-9-]+")),
    ("INTERNAL_CMD_CTX", "high", re.compile(r"(ctx_batch_execute|ctx_search|ctx_execute)\(")),
    # Server paths
    ("SERVER_PATH", "medium", re.compile(r"(?i)(server\.|renatocaliari\.com|SSH|cat ~/\\.ssh/)")),
]


def scan_file(path: Path) -> ScanResult:
    """
    Scan a single file for sensitive content.

    Args:
        path: Path to the file to scan.

    Returns:
        ScanResult with safe status, list of issues found, and any error summary.
    """
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return ScanResult(safe=False, issues=[], summary=f"Could not read file: {e}")

    issues: list[Issue] = []
    for rule, severity, pattern in PATTERNS:
        for match in pattern.finditer(content):
            snippet = match.group(0)
            # Truncate snippet for display (max 60 chars)
            if len(snippet) > 60:
                snippet = snippet[:60] + "..."
            issues.append(Issue(rule=rule, severity=severity, snippet=snippet))

    # Deduplicate by rule+snippet
    seen: set[tuple] = set()
    unique: list[Issue] = []
    for issue in issues:
        key = (issue["rule"], issue["snippet"])
        if key not in seen:
            seen.add(key)
            unique.append(issue)

    # File is safe if no critical issues
    has_critical = any(i["severity"] == "critical" for i in unique)
    safe = len(unique) == 0 or not has_critical

    return ScanResult(safe=safe, issues=unique, summary="")


def scan_multiple(paths: list[Path]) -> dict[Path, ScanResult]:
    """
    Scan multiple files and return results per file.

    Args:
        paths: List of file paths to scan.

    Returns:
        Dict mapping each path to its ScanResult.
    """
    return {path: scan_file(path) for path in paths}


def scan_and_report(
    files: list[tuple[str, Path]],
    verbose: bool = False,
) -> dict[Path, ScanResult]:
    """
    Scan multiple files (with optional label) and generate a report.

    Args:
        files: List of (label, path) tuples. Label is unused but kept for API compatibility.
        verbose: If True, print progress to stdout.

    Returns:
        Dict mapping each path to its ScanResult.
    """
    results: dict[Path, ScanResult] = {}
    for i, (_, path) in enumerate(files):
        if verbose:
            print(f"Scanning {i + 1}/{len(files)}: {path.name}")
        results[path] = scan_file(path)
    return results


def get_severity_color(severity: str) -> str:
    """Get the appropriate color for a severity level."""
    colors = {
        "critical": "red",
        "high": "yellow",
        "medium": "magenta",
        "low": "cyan",
    }
    return colors.get(severity, "white")


def format_issues_for_display(issues: list[Issue]) -> str:
    """Format a list of issues for display."""
    if not issues:
        return "  No issues detected."

    lines = []
    for issue in issues:
        color = get_severity_color(issue["severity"])
        lines.append(f"  • [{color}]{issue['severity']}[/{color}] [{color}]{issue['rule']}[/{color}]: `{issue['snippet']}`")
    return "\n".join(lines)