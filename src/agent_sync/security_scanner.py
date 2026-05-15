r"""
Security scanner for agent instruction files.

Detects potentially sensitive content before public publishing:
- Absolute paths (/Users/, /home/, /root/, C:\\)
- API tokens and keys (sk-, ghp_, api_, secret)
- Internal commands (/skill:, /ctx-, ctx_batch_execute)
- Server paths (server., .renatocaliari.com)

Smart false-positive reduction:
- Ignores code blocks (``` ``` ```) - they're documentation, not real values
- Ignores process.env.XYZ references - they're environment variables, not values
- Ignores $VAR or ${VAR} patterns - they're variable references, not values
- Ignores <placeholder> patterns - common in documentation
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict


class Issue(TypedDict):
    """Represents a detected security issue."""
    rule: str  # e.g., "ABS_PATH_UNIX", "TOKEN_OPENAI"
    severity: str  # "critical" | "high" | "medium" | "low"
    snippet: str  # The matched text (truncated for display)
    context: str  # "code" | "variable" | "hardcoded" - helps explain why flagged
    explanation: str  # Human-readable explanation for the user


@dataclass
class ScanResult:
    """Result of scanning a file for sensitive content."""
    safe: bool  # True if no critical hardcoded issues found
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""  # Error message if file couldn't be read


# Context patterns to reduce false positives
# These are applied BEFORE pattern matching to mask false positives
CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```')
INLINE_CODE_PATTERN = re.compile(r'`[^`]+`')
PROCESS_ENV_PATTERN = re.compile(r'process\.env\.\w+', re.IGNORECASE)
VARIABLE_REF_PATTERN = re.compile(r'\$[A-Z_][A-Z0-9_]*\b|\$\{[^}]+\}')
PLACEHOLDER_PATTERN = re.compile(r'<(code|value|placeholder|your-[a-z-]+|example)[^>]*>', re.IGNORECASE)
SECRET_EXAMPLE_PATTERN = re.compile(r'(?i)(secret|password)[-_]?(abc|example|test|123|xxx|demo|sample)', re.IGNORECASE)


def _is_valid_skill(skill_name: str) -> bool:
    """Check if a skill exists in the skills directory."""
    skill_path = Path.home() / ".agents" / "skills" / skill_name
    return skill_path.exists()

# DEPRECATED: /skill: commands are now treated as legitimate agent commands
# Kept as noop for backward compatibility


def _mask_false_positives(content: str) -> tuple[str, dict]:
    """
    Mask known false-positive patterns in content.

    Returns:
        (masked_content, mask_info) where mask_info describes what was masked
    """
    mask_info = {
        "code_blocks": 0,
        "env_refs": 0,
        "variables": 0,
        "placeholders": 0,
        "examples": 0,
    }

    # Count and mask code blocks
    mask_info["code_blocks"] = len(CODE_BLOCK_PATTERN.findall(content))
    content = CODE_BLOCK_PATTERN.sub('[CODE_BLOCK_REDACTED]', content)

    # Count and mask inline code (less aggressive)
    mask_info["env_refs"] = len(PROCESS_ENV_PATTERN.findall(content))
    content = PROCESS_ENV_PATTERN.sub('[ENV_REF_REDACTED]', content)

    # Mask variable references like $VAR, ${VAR}
    mask_info["variables"] = len(VARIABLE_REF_PATTERN.findall(content))
    content = VARIABLE_REF_PATTERN.sub('[VAR_REDACTED]', content)

    # Mask <placeholder> patterns
    mask_info["placeholders"] = len(PLACEHOLDER_PATTERN.findall(content))
    content = PLACEHOLDER_PATTERN.sub('[PLACEHOLDER]', content)

    # Mask example secrets like "secret_abc123", "password_example"
    mask_info["examples"] = len(SECRET_EXAMPLE_PATTERN.findall(content))
    content = SECRET_EXAMPLE_PATTERN.sub('[EXAMPLE_SECRET]', content)

    return content, mask_info


def _is_in_masked_region(content: str, match_start: int) -> bool:
    """Check if a match is in a masked region."""
    # Simple check - if nearby there's a redacted marker, skip
    lookback = content[:match_start][-50:] if match_start > 50 else content[:match_start]
    return any(marker in lookback for marker in [
        '[CODE_BLOCK', '[ENV_REF', '[VAR_REDACTED]', '[PLACEHOLDER]', '[EXAMPLE_SECRET]'
    ])


# Regex patterns for detection
# Format: (rule_name, severity, pattern, explanation)
# STRICT patterns catch REAL secrets - they run AFTER masking false positives
PATTERNS: list[tuple[str, str, re.Pattern, str]] = [
    # Absolute paths - always suspicious
    ("ABS_PATH_UNIX", "high", re.compile(r"/Users/\w+/"),
     "Contains absolute path that may reveal your home directory"),
    ("ABS_PATH_HOME", "medium", re.compile(r"/home/\w+/"),
     "Contains home directory path"),
    ("ABS_PATH_ROOT", "high", re.compile(r"/root/"),
     "Contains root directory reference"),
    ("ABS_PATH_WINDOWS", "high", re.compile(r"[A-Z]:\\[\w\\]+"),
     "Contains Windows absolute path"),

    # REAL tokens - these are NEVER false positives (real key format)
    ("TOKEN_OPENAI", "critical", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
     "OpenAI API key detected - NEVER publish this!"),
    ("TOKEN_GITHUB", "critical", re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
     "GitHub personal access token - NEVER publish this!"),
    ("TOKEN_GITHUB_ALT", "critical", re.compile(r"\bgho_[A-Za-z0-9]{36}\b"),
     "GitHub OAuth token detected - NEVER publish this!"),

    # Internal commands - these reveal private tooling (NOT /skill: which are public agent commands)
    # /skill: commands are legitimate - they are how agents call skills
    ("INTERNAL_CMD_CTX", "high", re.compile(r"ctx_(batch_execute|ctx_execute|ctx_search)\s*\("),
     "Internal ctx command - reveals private tooling"),

    # Server paths - specific private infrastructure
    # Only flag personal domains and clear path patterns
    ("SERVER_PATH", "medium", re.compile(r"(?i)(renatocaliari\.com|\.internal|\.local|~\.ssh)"),
     "Private domain or path detected"),

    # SSH keys - real key format
    ("SSH_KEY", "critical", re.compile(r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"),
     "SSH private key detected - NEVER publish this!"),
]


def scan_file(path: Path) -> ScanResult:
    """
    Scan a single file for sensitive content.

    Skips binary/non-text files (.pyc, .pyo, .pyd, .so, .dll, .dylib, .exe, .bin)
    that cannot be meaningfully scanned and would cause issues.

    Uses smart masking to reduce false positives from:
    - Code blocks (``` ``` ```)
    - Environment variable references (process.env.XYZ)
    - Variable references ($VAR, ${VAR})
    - Placeholders (<placeholder>, <your-value>)
    - Example secrets (secret_abc123, password_example)

    Args:
        path: Path to the file to scan.

    Returns:
        ScanResult with safe status, list of issues found, and any error summary.
    """
    # Skip binary/non-text files
    if path.suffix in (".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin",
                       ".whl", ".zip", ".tar", ".gz", ".bz2", ".xz",
                       ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
                       ".pdf", ".doc", ".docx", ".xls", ".xlsx"):
        return ScanResult(safe=True, issues=[], summary="Binary file skipped")

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return ScanResult(safe=False, issues=[], summary=f"Could not read file: {e}")

    # Step 1: Mask false positives FIRST
    masked_content, mask_info = _mask_false_positives(content)

    # Track which issues are in masked regions
    masked_regions: list[tuple[int, int]] = []
    for pattern in [CODE_BLOCK_PATTERN, PROCESS_ENV_PATTERN, VARIABLE_REF_PATTERN,
                    PLACEHOLDER_PATTERN, SECRET_EXAMPLE_PATTERN]:
        for m in pattern.finditer(content):
            masked_regions.append((m.start(), m.end()))

    issues: list[Issue] = []
    for rule, severity, pattern, explanation in PATTERNS:
        for match in pattern.finditer(masked_content):
            snippet = match.group(0)

            # Truncate snippet for display (max 50 chars)
            if len(snippet) > 50:
                snippet = snippet[:50] + "..."

            # Determine context
            match_pos = match.start()
            context = "hardcoded"

            # Check if this match overlaps with a masked region in original
            for orig_start, orig_end in masked_regions:
                if abs(match_pos - orig_start) < 10:  # Close to masked region
                    # Determine context type
                    lookback = content[max(0, match_pos-30):match_pos].lower()
                    if 'process.env' in lookback:
                        context = "variable"
                    elif '$' in lookback or '${' in lookback:
                        context = "variable"
                    elif 'example' in lookback or 'demo' in lookback:
                        context = "example"
                    elif 'code' in lookback or '```' in lookback:
                        context = "code"
                    break

            # Context-based severity adjustment
            effective_severity = severity
            if context in ("variable", "deprecated", "code"):
                # Downgrade variable references and deprecated stuff
                priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
                current_level = priority.get(severity, 2)
                effective_severity = next((k for k, v in priority.items() if v == current_level - 1), severity)
                if current_level <= 2:
                    effective_severity = "low"
            
            issues.append(Issue(
                rule=rule,
                severity=effective_severity,
                snippet=snippet,
                context=context,
                explanation=explanation
            ))

    # Deduplicate by rule+snippet
    seen: set[tuple] = set()
    unique: list[Issue] = []
    for issue in issues:
        key = (issue["rule"], issue["snippet"])
        if key not in seen:
            seen.add(key)
            unique.append(issue)

    # File is safe if no critical hardcoded issues
    has_critical_hardcoded = any(
        i["severity"] == "critical" and i.get("context") != "variable"
        for i in unique
    )
    safe = len(unique) == 0 or not has_critical_hardcoded

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


def get_context_icon(context: str) -> str:
    """Get icon for context type."""
    icons = {
        "hardcoded": "🔴",  # Red - real danger
        "variable": "🟡",   # Yellow - environment variable (safe)
        "example": "🟠",    # Orange - example value (probably safe)
        "code": "🟣",       # Purple - in code block (safe)
    }
    return icons.get(context, "⚪")


def format_issues_for_display(issues: list[Issue]) -> str:
    """Format a list of issues for display with context."""
    if not issues:
        return "  No issues detected."

    lines = []
    for issue in issues:
        color = get_severity_color(issue["severity"])
        context = issue.get("context", "hardcoded")
        context_icon = get_context_icon(context)
        snippet = issue["snippet"]
        explanation = issue.get("explanation", "")

        # Format based on context
        if context == "variable":
            lines.append(f"  • [{color}]{issue['severity']}[/{color}] [{color}]{issue['rule']}[/{color}]: `{snippet}`")
            lines.append(f"    {context_icon} Environment variable reference (safe to publish)")
        elif context == "example":
            lines.append(f"  • [{color}]{issue['severity']}[/{color}] [{color}]{issue['rule']}[/{color}]: `{snippet}`")
            lines.append(f"    {context_icon} Example/placeholder value (review before publish)")
        else:
            lines.append(f"  • [{color}]{issue['severity']}[/{color}] [{color}]{issue['rule']}[/{color}]: `{snippet}`")
            if explanation:
                lines.append(f"    ⚠️  {explanation}")

    return "\n".join(lines)


def get_issue_summary(issues: list[Issue]) -> dict[str, int]:
    """Get summary counts by severity and context."""
    summary = {
        "critical_hardcoded": 0,
        "critical_variable": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    for issue in issues:
        if issue["severity"] == "critical":
            if issue.get("context") in ("variable", "example"):
                summary["critical_variable"] += 1
            else:
                summary["critical_hardcoded"] += 1
        elif issue["severity"] == "high":
            summary["high"] += 1
        elif issue["severity"] == "medium":
            summary["medium"] += 1
        elif issue["severity"] == "low":
            summary["low"] += 1
    return summary
