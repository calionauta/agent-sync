"""Vendored, pinned third-party skill sources.

Problem this solves: a third-party skill published to the public repo as a
hand-made copy (e.g. `skills/local/last30days/`) silently drifts from upstream.
By the time someone notices, the published copy is 12 releases behind and
nobody knows which commit it came from.

A vendored source is declared once, with the upstream repo and the ref to pin:

    vendor_sources:
      - name: last30days
        url: https://github.com/mvanhorn/last30days-skill
        ref: v3.30.0
        path: skills/last30days     # optional, auto-detected when omitted
      - name: first-reader
        url: https://github.com/Shubhamsaboo/awesome-llm-apps
        ref: main                   # upstream has no tags
        path: agent_skills/first-reader

The content is materialised by cloning upstream at that exact ref and copying
the skill directory into `skills/local/<name>/`, so it stays installable with
`npx skills add <published-repo>`. Repo + ref + resolved commit SHA are written
to `vendor.lock.yaml` at the root of the published repo — bumping a skill is an
explicit edit to `ref`, and the lock records exactly what was shipped.

SoC: vendoring (fetch + copy + lock) lives here; git_commit_and_push() stays in
git_publish and knows nothing about where content came from.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from .cache import normalize_repo_id

LOCK_FILENAME = "vendor.lock.yaml"

# Files/dirs never copied out of an upstream checkout.
VENDOR_IGNORE = {".git", ".github", ".gitignore", ".gitattributes", "__pycache__"}


@dataclass
class VendorSource:
    """A third-party skill pinned to an upstream ref."""

    name: str
    url: str
    ref: str = "main"
    path: str | None = None
    status: str = "active"

    @property
    def repo_id(self) -> str:
        return normalize_repo_id(self.url)

    @property
    def source_id(self) -> str:
        """Source id used in the published tree: `vendor/<repo>`.

        Kept distinct from `local` on purpose: a vendored skill must never be
        overwritten by whatever happens to sit in the local hub under the same
        name, and `vendor/` documents at a glance that the content is upstream.
        """
        return f"vendor/{self.repo_id}"

    def to_dict(self) -> dict:
        data: dict = {"name": self.name, "url": self.url, "ref": self.ref}
        if self.path:
            data["path"] = self.path
        data["status"] = self.status
        return data

    @classmethod
    def from_dict(cls, data: dict) -> VendorSource:
        return cls(
            name=data["name"],
            url=data["url"],
            ref=data.get("ref", "main"),
            path=data.get("path"),
            status=data.get("status", "active"),
        )


@dataclass
class LockEntry:
    """What was actually published for one vendored skill."""

    name: str
    url: str
    ref: str
    commit: str
    path: str
    published_path: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "ref": self.ref,
            "commit": self.commit,
            "path": self.path,
            "published_path": self.published_path,
        }


class VendorError(RuntimeError):
    """Raised when a vendored source cannot be resolved at its pinned ref."""


def read_lock(repo_root: Path) -> dict[str, LockEntry]:
    """Read vendor.lock.yaml from a published repo checkout."""
    lock_path = repo_root / LOCK_FILENAME
    if not lock_path.exists():
        return {}

    data = yaml.safe_load(lock_path.read_text()) or {}
    entries: dict[str, LockEntry] = {}
    for entry in data.get("vendored", []):
        lock_entry = LockEntry(
            name=entry["name"],
            url=entry["url"],
            ref=entry["ref"],
            commit=entry["commit"],
            path=entry["path"],
            published_path=entry["published_path"],
        )
        entries[lock_entry.name] = lock_entry
    return entries


def write_lock(publish_dir: Path, entries: list[LockEntry]) -> None:
    """Write vendor.lock.yaml at the root of the published repo."""
    data = {"vendored": [e.to_dict() for e in sorted(entries, key=lambda e: e.name)]}
    (publish_dir / LOCK_FILENAME).write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False)
    )


def checkout_upstream(source: VendorSource, workdir: Path) -> tuple[Path, str]:
    """Shallow-clone `source.url` at `source.ref` into `workdir`.

    Returns:
        (checkout path, resolved commit SHA)

    Raises:
        VendorError: if the ref cannot be fetched.
    """
    checkout = workdir / source.name
    # Fetch the exact ref (tag or branch) instead of cloning the default branch
    # and hoping the wanted ref happens to be reachable.
    commands = [
        ["git", "init", "-q", str(checkout)],
        ["git", "-C", str(checkout), "remote", "add", "origin", source.url],
        ["git", "-C", str(checkout), "fetch", "--depth", "1", "origin", source.ref],
        ["git", "-C", str(checkout), "checkout", "-q", "FETCH_HEAD"],
    ]
    for cmd in commands:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env={**subprocess.os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode != 0:
            raise VendorError(
                f"{source.name}: `{' '.join(cmd)}` failed at ref {source.ref!r}: "
                f"{(result.stderr or result.stdout).strip()}"
            )

    commit = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    ).stdout.strip()

    return checkout, commit


def find_skill_dir(checkout: Path, source: VendorSource) -> Path:
    """Locate the skill directory inside an upstream checkout.

    Resolution order: explicit `path`, `skills/<name>`, `<name>`, a single
    `*/<name>` match, then a single `<name>/SKILL.md` anywhere in the tree.
    """
    if source.path:
        candidate = checkout / source.path
        if not (candidate / "SKILL.md").exists():
            raise VendorError(f"{source.name}: declared path {source.path!r} has no SKILL.md")
        return candidate

    for candidate in (checkout / "skills" / source.name, checkout / source.name):
        if (candidate / "SKILL.md").exists():
            return candidate

    matches = [
        p.parent
        for p in checkout.rglob(f"{source.name}/SKILL.md")
        if not any(part in VENDOR_IGNORE for part in p.relative_to(checkout).parts)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise VendorError(
            f"{source.name}: no directory named {source.name!r} with a SKILL.md "
            f"at ref {source.ref!r} — set `path:` explicitly"
        )
    raise VendorError(
        f"{source.name}: ambiguous — {len(matches)} SKILL.md matches "
        f"({', '.join(str(m.relative_to(checkout)) for m in matches[:4])}); "
        "set `path:` explicitly"
    )


def _copy_skill(skill_dir: Path, dest: Path) -> None:
    """Copy a skill directory, dropping VCS metadata and Python caches."""

    def _ignore(_dir, names):
        return [n for n in names if n in VENDOR_IGNORE or n.endswith(".pyc")]

    shutil.copytree(skill_dir, dest, ignore=_ignore)


def materialize(
    sources: list[VendorSource],
    publish_dir: Path,
) -> list[LockEntry]:
    """Copy every vendored skill into `<publish_dir>/skills/local/<name>/`.

    Args:
        sources: declared vendor sources
        publish_dir: root of the tree that will be committed and pushed

    Returns:
        Lock entries for what was published.

    Raises:
        VendorError: when a source cannot be resolved. Never falls back to a
            stale copy — a wrong pin must fail loudly, not ship silently.
    """
    entries: list[LockEntry] = []
    errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="agent-sync-vendor-") as tmp:
        workdir = Path(tmp)
        for source in sources:
            if source.status != "active":
                continue
            try:
                checkout, commit = checkout_upstream(source, workdir)
                skill_dir = find_skill_dir(checkout, source)
                dest = publish_dir / "skills" / "local" / source.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.rmtree(dest)
                _copy_skill(skill_dir, dest)
                entries.append(
                    LockEntry(
                        name=source.name,
                        url=source.url,
                        ref=source.ref,
                        commit=commit,
                        path=str(skill_dir.relative_to(checkout)),
                        published_path=f"skills/local/{source.name}",
                    )
                )
            except VendorError as exc:
                errors.append(str(exc))
            except subprocess.TimeoutExpired:
                errors.append(f"{source.name}: fetch timed out")
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")

    if errors:
        raise VendorError("vendored sources failed:\n  " + "\n  ".join(errors))

    return entries
