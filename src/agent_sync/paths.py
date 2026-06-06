"""Centralized filesystem paths for agent-sync.

Single source of truth for:
- The global skills hub (`~/.agents/skills/`) — the DotAgents-protocol
  canonical skills directory.
- The retired-skills manifest (`RETIRED.md` inside the hub).
- The agent-sync data directory (cross-platform via `platformdirs`).
- The private sync repository (cloned inside the data directory).

All other modules MUST import from here. Do not re-derive these paths
with `Path.home() / ".agents" / "skills"` or similar — that is what
created the duplication this module exists to eliminate.
"""

from pathlib import Path

from platformdirs import user_data_dir

# --- Application identity ----------------------------------------------------

APP_NAME = "agent-sync"

# --- The global skills hub (DotAgents protocol: ~/.agents/) -----------------

#: Root directory of the global skills hub. All skills are centralized
#: here and exposed to all agents that support `native` or `config`
#: skill paths.
HUB_DIR: Path = Path.home() / ".agents" / "skills"

#: User-editable manifest listing intentionally retired skills. Skills
#: named here are NEVER re-imported to the hub by `centralize`.
RETIRED_MANIFEST: Path = HUB_DIR / "RETIRED.md"

#: Internal sync metadata (not user-editable). Auto-managed by agent-sync.
INTERNAL_MANIFEST_FILENAME = ".agent-sync-manifest.json"
INTERNAL_MANIFEST: Path = HUB_DIR / INTERNAL_MANIFEST_FILENAME

# --- The agent-sync data directory (cross-platform) -------------------------

#: User-specific data directory for agent-sync itself. Resolved via
#: `platformdirs` to follow OS conventions (e.g.
#: `~/Library/Application Support/agent-sync/` on macOS,
#: `~/.local/share/agent-sync/` on Linux).
DATA_DIR: Path = Path(user_data_dir(APP_NAME, APP_NAME))

#: Local clone of the private sync repository. The user pushes and
#: pulls from this working copy.
REPO_DIR: Path = DATA_DIR / "repo"

#: Persisted sync state (last action, last timestamp, etc.).
STATE_FILE: Path = DATA_DIR / "sync-state.json"

#: Manifest that lives inside the private repo (different from the
#: hub manifest — this one tracks repo-level sync metadata).
REPO_MANIFEST: Path = REPO_DIR / INTERNAL_MANIFEST_FILENAME

# --- Timeouts (seconds) ----------------------------------------------------

#: Default timeout for `git` subprocess calls.
GIT_TIMEOUT: int = 10

#: How long the centralize lock is valid before it's considered stale.
LOCK_STALE_TIMEOUT: int = 600  # 10 minutes
