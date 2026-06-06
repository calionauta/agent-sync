"""Skills observability: audit and explain.

Two operations designed to give the user a clear picture of the skills
state across three sources of truth:
- Local hub: `~/.agents/skills/`
- Private repo HEAD: `skills/` in the private sync repository
- Retirement manifest: `~/.agents/skills/RETIRED.md`

`audit_skills()`  — full report: every skill with its status across all
three sources. The user sees drift, orphans, and conflicts at a glance.

`explain_skill(name)` — deep-dive into one skill: when it was added,
when it was last modified, total commits, current location, retirement
status. Useful for debugging "where did this skill go?".

Both operations are read-only and never modify state.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .paths import GIT_TIMEOUT, HUB_DIR, REPO_DIR, RETIRED_MANIFEST


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@dataclass
class SkillAuditRow:
    """One row of the audit report.

    `status` is a human-readable summary derived from the (hub, repo,
    retired) booleans. Color codes in the CLI are chosen based on status.
    """
    name: str
    in_hub: bool
    in_repo: bool
    in_manifest: bool
    status: str = ""

    def compute_status(self) -> str:
        if self.in_hub and self.in_repo and not self.in_manifest:
            return "in_sync"
        if self.in_hub and not self.in_repo and not self.in_manifest:
            return "in_hub_only"
        if not self.in_hub and self.in_repo and not self.in_manifest:
            return "in_repo_only"  # orphan in repo
        if not self.in_hub and self.in_repo and self.in_manifest:
            return "retired_in_repo"
        if self.in_hub and not self.in_repo and self.in_manifest:
            return "conflict_retired_in_hub"
        if self.in_hub and self.in_repo and self.in_manifest:
            return "conflict_retired_everywhere"
        if not self.in_hub and not self.in_repo and self.in_manifest:
            return "retired_clean"
        return "unknown"


@dataclass
class AuditReport:
    """Full audit report with a summary header and per-skill rows."""
    rows: list[SkillAuditRow] = field(default_factory=list)
    hub_count: int = 0
    repo_count: int = 0
    manifest_count: int = 0

    def summary_counts(self) -> dict[str, int]:
        """Count rows by status (for the summary header)."""
        out: dict[str, int] = {}
        for row in self.rows:
            out[row.status] = out.get(row.status, 0) + 1
        return out


def _list_hub_skills() -> set[str]:
    """Skill names in the local hub (directories only)."""
    if not HUB_DIR.exists():
        return set()
    return {
        d.name for d in HUB_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    }


def _list_repo_skills() -> set[str]:
    """Skill names in the private repo HEAD:skills/ (directories only)."""
    if not (REPO_DIR / ".git").exists():
        return set()
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-d", "--name-only", "HEAD", "skills/"],
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if result.returncode != 0:
            return set()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return set()

    out: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("skills/"):
            bare = line[len("skills/"):].rstrip("/")
            if bare and "/" not in bare and not bare.startswith("."):
                out.add(bare)
    return out


def _list_manifest_skills(manifest_path: Path | None = None) -> set[str]:
    """Skill names listed in the retirement manifest.

    Imports the parser lazily to avoid a circular import at module load.
    """
    from .skills import SkillsManager

    path = manifest_path or RETIRED_MANIFEST
    if not path.exists():
        return set()
    sm = SkillsManager(global_skills_dir=HUB_DIR)
    return sm._parse_retired_manifest(path)


def audit_skills(
    hub_skills: set[str] | None = None,
    repo_skills: set[str] | None = None,
    manifest_skills: set[str] | None = None,
) -> AuditReport:
    """Build an audit report by comparing hub ↔ repo ↔ manifest.

    Args:
        hub_skills: Override the hub set (for testing). None → read from disk.
        repo_skills: Override the repo set (for testing). None → query git.
        manifest_skills: Override the manifest set. None → read RETIRED.md.

    Returns:
        AuditReport with one row per unique skill name across all sources.
    """
    hub = hub_skills if hub_skills is not None else _list_hub_skills()
    repo = repo_skills if repo_skills is not None else _list_repo_skills()
    manifest = manifest_skills if manifest_skills is not None else _list_manifest_skills()

    all_names = sorted(hub | repo | manifest)
    rows: list[SkillAuditRow] = []
    for name in all_names:
        row = SkillAuditRow(
            name=name,
            in_hub=name in hub,
            in_repo=name in repo,
            in_manifest=name in manifest,
        )
        row.status = row.compute_status()
        rows.append(row)

    return AuditReport(
        rows=rows,
        hub_count=len(hub),
        repo_count=len(repo),
        manifest_count=len(manifest),
    )


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------


@dataclass
class SkillExplanation:
    """Lifecycle and current-state info for one skill."""
    name: str
    in_hub: bool
    in_repo: bool
    in_manifest: bool
    first_added: str | None = None       # commit hash of first addition
    first_added_at: str | None = None    # ISO date
    last_modified: str | None = None     # commit hash of most recent change
    last_modified_at: str | None = None  # ISO date
    commit_count: int = 0
    file_count: int = 0
    manifest_line: str | None = None     # the line from RETIRED.md (if any)


def _git_log_for_skill(name: str) -> list[dict]:
    """Return git log entries for `skills/<name>/` (add/modify/delete only).

    Each entry: {hash, date, subject, change_type} where change_type is
    'A' (added), 'M' (modified), 'D' (deleted), 'R' (renamed).
    """
    if not (REPO_DIR / ".git").exists():
        return []

    try:
        result = subprocess.run(
            [
                "git", "log",
                "--follow",  # follow renames
                "--name-status",
                "--format=%H|%ad|%s",
                "--date=iso",
                "--", f"skills/{name}/",
            ],
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    entries: list[dict] = []
    current: dict | None = None
    for line in result.stdout.splitlines():
        if "|" in line and not line.startswith("skills/") and "\t" not in line:
            # Commit header line (format = "hash|date|subject")
            if current:
                entries.append(current)
            parts = line.split("|", 2)
            current = {
                "hash": parts[0],
                "date": parts[1],
                "subject": parts[2] if len(parts) > 2 else "",
                "change_type": "",
            }
        elif "\t" in line and current is not None:
            # Status line: "<X>\t<path>" where X ∈ {A, M, D, R, C, T, ...}
            change_type, _path = line.split("\t", 1)
            # We only care about changes to skills/<name>/ for the current
            # name; ignore changes to other paths that may appear in the
            # same commit.
            if _path.startswith(f"skills/{name}/") or _path == f"skills/{name}":
                current["change_type"] = change_type
    if current:
        entries.append(current)
    return entries


def _read_manifest_line(name: str, manifest_path: Path | None = None) -> str | None:
    """Return the line from RETIRED.md that declares this skill retired."""
    path = manifest_path or RETIRED_MANIFEST
    if not path.exists():
        return None
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            tokens = stripped.split()
            if tokens and tokens[0] == name:
                return raw  # preserve original formatting
    except OSError:
        pass
    return None


def _count_files_in_hub(name: str) -> int:
    """Number of files in the local skill directory (recursive)."""
    skill_path = HUB_DIR / name
    if not skill_path.is_dir():
        return 0
    return sum(1 for f in skill_path.rglob("*") if f.is_file())


def explain_skill(
    name: str,
    hub_skills: set[str] | None = None,
    repo_skills: set[str] | None = None,
    manifest_skills: set[str] | None = None,
) -> SkillExplanation:
    """Build a lifecycle explanation for a single skill.

    Args:
        name: Skill name to explain.
        hub_skills/repo_skills/manifest_skills: Overrides for testing.

    Returns:
        SkillExplanation with current state + git lifecycle.
    """
    hub = hub_skills if hub_skills is not None else _list_hub_skills()
    repo = repo_skills if repo_skills is not None else _list_repo_skills()
    manifest = manifest_skills if manifest_skills is not None else _list_manifest_skills()

    log = _git_log_for_skill(name)
    first_added: dict | None = None
    last_modified: dict | None = None

    # Git log is reverse-chronological: last entry is the oldest.
    # The oldest "A" (add) entry is the first addition. The newest
    # entry overall is the last change.
    if log:
        last_modified = log[0]
        for entry in log:
            if entry.get("change_type") == "A":
                first_added = entry
                break  # keep oldest

    return SkillExplanation(
        name=name,
        in_hub=name in hub,
        in_repo=name in repo,
        in_manifest=name in manifest,
        first_added=first_added["hash"] if first_added else None,
        first_added_at=first_added["date"] if first_added else None,
        last_modified=last_modified["hash"] if last_modified else None,
        last_modified_at=last_modified["date"] if last_modified else None,
        commit_count=len(log),
        file_count=_count_files_in_hub(name),
        manifest_line=_read_manifest_line(name),
    )
