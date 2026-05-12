# Autoresearch Ideas — agent-sync push

## Implemented Fixes (✅ Done)

- **O(n²) bug in `_stage_agent_configs()`**: Function iterates ALL agents internally but was called once per agent from `_stage_agent_files()` loop. Moved call to `_stage_all_agent_files()` — called once before the loop. Reduced from ~80s to ~8s. [experiment #1]
- **Skip pi.dev git clone backup**: `~/.pi/agent/git/` contains 21k files (222MB+) of cloned repo worktrees. These are cache, not configuration. Skipped entirely. Reduced from ~8s to ~0.3s. [experiment #1]
- **Git subprocess timeout**: `_run_git()` now has a 60s timeout on all subprocess calls. If git hangs on auth prompts or network issues, it raises a helpful `RuntimeError` instead of blocking forever. [experiment #2]
- **`.gitignore` in repo for cache dirs**: Added `configs/pi.dev/git/` to the repo's `.gitignore` (both in `_create_repo_structure()` and existing repo) to prevent re-adding stale git clone files. [experiment #2]

## Deferred Ideas

- **Review other pi.dev extra_paths for size**: `bin/`, `packages/`, `extensions/` were checked — all are tiny (<3MB total). No action needed.
- **Add `--dry-run` mode to push**: Show what would be staged/copied without committing, helpful for debugging slow pushes.
- **Pipx venv sync issue**: Source edits weren't reflected in pipx-installed CLI because pipx keeps separate physical copies. Add note to `setup.py` or `Makefile` about needing to `pipx reinstall` after edits.
- **Configurable exclude patterns per extra_path**: Let users choose which pi.dev directories to sync (e.g., skip `bin/` too).
