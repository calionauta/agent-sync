# Autoresearch Ideas — agent-sync push

## Implemented Fixes (✅ Done)

- **O(n²) bug in `_stage_agent_configs()`**: Function iterates ALL agents internally but was called once per agent from `_stage_agent_files()` loop. Moved call to `_stage_all_agent_files()` — called once before the loop. Reduced from ~80s to ~8s.
- **Skip pi.dev git clone backup**: `~/.pi/agent/git/` contains 21k files (222MB+) of cloned repo worktrees. These are cache, not configuration. Skipped entirely. Reduced from ~8s to ~0.3s.

## Deferred Ideas

- **Review other pi.dev extra_paths for size**: `bin/`, `packages/`, `extensions/` could also grow large over time. Add size-based warnings or configurable exclude patterns per path.
- **Git push timeout**: `_run_git()` uses `subprocess.run()` without timeout. If git hangs on auth (GITHUB_TOKEN stripped, no credential helper), it blocks forever. Add 30s timeout with helpful error message.
- **Add `--dry-run` mode to push**: Show what would be staged/copied without committing, helpful for debugging slow pushes.
- **`.gitignore` in repo for large cache dirs**: After removing git clones, ensure `.gitignore` in `configs/pi.dev/` prevents re-adding them.
- **Pipx venv sync issue**: Source edits weren't reflected in pipx-installed CLI because pipx keeps separate physical copies. Add note to `setup.py` or `Makefile` about `pipx reinstall` after editable install changes.
