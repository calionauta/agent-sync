# Autoresearch Ideas — agent-sync push

## Implemented Fixes (✅ Done)

### Push Performance
- **O(n²) bug in `_stage_agent_configs()`**: Function iterates ALL agents internally but was called once per agent from `_stage_agent_files()` loop. Moved call to `_stage_all_agent_files()` — called once before the loop. Reduced from ~80s to ~8s. [experiment #1]
- **Skip pi.dev git clone backup**: `~/.pi/agent/git/` contains 21k files (222MB+) of cloned repo worktrees. These are cache, not configuration. Skipped entirely. Reduced from ~8s to ~0.3s. [experiment #1]
- **Git subprocess timeout**: `_run_git()` now has a 60s timeout on all subprocess calls. If git hangs on auth prompts or network issues, it raises a helpful `RuntimeError` instead of blocking forever. [experiment #2]
- **`.gitignore` in repo for cache dirs**: Added `configs/pi.dev/git/` to the repo's `.gitignore` (both in `_create_repo_structure()` and existing repo) to prevent re-adding stale git clone files. [experiment #2]
- **Verify all flags fast**: Tested `--skills-only` (2.0s), `--configs-only` (0.6s), `--agents-only` (0.0s), default (2.3s). All fast. [experiment #4]

### Pull Bugfix
- **Binary file crash in `_apply_synced_configs()`**: `read_text()` crashed with `UnicodeDecodeError` when comparing binary files (e.g., Mach-O executable in `~/.pi/agent/bin/`). Added `_same_content()` helper using `read_bytes()` — safe for both text and binary. Replaced all 17 read_text comparison calls across `_apply_synced_configs()`, `_apply_synced_skills()`, `_apply_synced_agents()`. [experiment #5]

## Current Performance

| Comando | Antes | Depois | Ganho |
|---------|-------|--------|-------|
| `agent-sync push` | **58s** | **2.3s** | **25× mais rápido** |
| `--skills-only` | — | 2.0s | ✅ |
| `--configs-only` | — | 0.6s | ✅ |
| `--agents-only` | — | 0.0s | ✅ |
| `agent-sync pull` | **crash** 🔴 | **OK** ✅ | Fix |

## Deferred Ideas (no longer needed)

- ✅ Review other pi.dev extra_paths for size: all tiny (<3MB total), no action.
- ✅ Pipx venv sync issue: documented — manually copy sync.py to pipx venv after edits.
- `--dry-run` mode: nice-to-have UX, not needed for performance.
- Configurable exclude patterns: nice-to-have, not needed with current sizes.
