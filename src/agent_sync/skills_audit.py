"""Skills observability: audit and explain.

Two operations designed to give the user a clear picture of the skills
state across two sources of truth:
- Local hub: `~/.agents/skills/`
- Private repo HEAD: `skills/` in the private sync repository

Retirement is inferred from git history: a skill deleted from the repo
and not re-added stays retired (never re-imported). Re-adding to the hub
unretires it.

`audit_skills()`  — full report: every skill with its status.
`explain_skill(name)` — deep-dive into one skill: lifecycle, location.

Both are read-only.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .paths import GIT_TIMEOUT, HUB_DIR, REPO_DIR


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@dataclass
class SkillAuditRow:
    """One row of the audit report.

    `status` is derived from hub and repo booleans.
    A retired suffix is added when the skill is in the git-history
    retired set (deleted in past, not re-added).
    """
    name: str
    in_hub: bool
    in_repo: bool
    is_retired: bool = False
    status: str = ""

    def compute_status(self) -> str:
        if self.in_hub and self.in_repo:
            return "in_sync"
        if self.in_hub and not self.in_repo:
            return "in_hub_only"
        if not self.in_hub and self.in_repo:
            return "in_repo_only"
        return "untracked"


@dataclass
class AuditReport:
    """Full audit report with a summary header and per-skill rows."""
    rows: list[SkillAuditRow] = field(default_factory=list)
    hub_count: int = 0
    repo_count: int = 0

    def summary_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in self.rows:
            out[row.status] = out.get(row.status, 0) + 1
        return out


def _list_hub_skills() -> set[str]:
    if not HUB_DIR.exists():
        return set()
    return {
        d.name for d in HUB_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    }


def _list_repo_skills() -> set[str]:
    if not (REPO_DIR / ".git").exists():
        return set()
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-d", "--name-only", "HEAD", "skills/"],
            cwd=REPO_DIR,
            capture_output=True, text=True, timeout=GIT_TIMEOUT,
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


def audit_skills(
    hub_skills: set[str] | None = None,
    repo_skills: set[str] | None = None,
) -> AuditReport:
    """Build an audit report by comparing hub ↔ repo.

    Args:
        hub_skills: Override for testing. None → read from disk.
        repo_skills: Override for testing. None → query git.

    Returns:
        AuditReport with one row per unique skill name.
    """
    hub = hub_skills if hub_skills is not None else _list_hub_skills()
    repo = repo_skills if repo_skills is not None else _list_repo_skills()

    all_names = sorted(hub | repo)
    rows: list[SkillAuditRow] = []
    for name in all_names:
        row = SkillAuditRow(
            name=name,
            in_hub=name in hub,
            in_repo=name in repo,
        )
        row.status = row.compute_status()
        rows.append(row)

    return AuditReport(
        rows=rows,
        hub_count=len(hub),
        repo_count=len(repo),
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
    is_retired: bool = False
    first_added: str | None = None
    first_added_at: str | None = None
    last_modified: str | None = None
    last_modified_at: str | None = None
    commit_count: int = 0
    file_count: int = 0


def _git_log_for_skill(name: str) -> list[dict]:
    if not (REPO_DIR / ".git").exists():
        return []
    try:
        result = subprocess.run(
            ["git", "log",
             "--follow",
             "--name-status",
             "--format=%H|%ad|%s",
             "--date=iso",
             "--", f"skills/{name}/"],
            cwd=REPO_DIR,
            capture_output=True, text=True, timeout=GIT_TIMEOUT,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
    entries: list[dict] = []
    current: dict | None = None
    for line in result.stdout.splitlines():
        if "|" in line and not line.startswith("skills/") and "\t" not in line:
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
            change_type, _path = line.split("\t", 1)
            if _path.startswith(f"skills/{name}/") or _path == f"skills/{name}":
                current["change_type"] = change_type
    if current:
        entries.append(current)
    return entries


def _count_files_in_hub(name: str) -> int:
    skill_path = HUB_DIR / name
    if not skill_path.is_dir():
        return 0
    return sum(1 for f in skill_path.rglob("*") if f.is_file())


def explain_skill(
    name: str,
    hub_skills: set[str] | None = None,
    repo_skills: set[str] | None = None,
) -> SkillExplanation:
    """Build a lifecycle explanation for a single skill.

    Args:
        name: Skill name to explain.
        hub_skills/repo_skills: Overrides for testing.

    Returns:
        SkillExplanation with current state + git lifecycle.
    """
    hub = hub_skills if hub_skills is not None else _list_hub_skills()
    repo = repo_skills if repo_skills is not None else _list_repo_skills()

    log = _git_log_for_skill(name)
    first_added: dict | None = None
    last_modified: dict | None = None
    if log:
        last_modified = log[0]
        for entry in log:
            if entry.get("change_type") == "A":
                first_added = entry
                break

    return SkillExplanation(
        name=name,
        in_hub=name in hub,
        in_repo=name in repo,
        first_added=first_added["hash"] if first_added else None,
        first_added_at=first_added["date"] if first_added else None,
        last_modified=last_modified["hash"] if last_modified else None,
        last_modified_at=last_modified["date"] if last_modified else None,
        commit_count=len(log),
        file_count=_count_files_in_hub(name),
    )
