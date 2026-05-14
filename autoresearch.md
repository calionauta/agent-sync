# Autoresearch: Code Quality — DRY/KISS + Dead Code Removal

## Objective
Remove dead code, fix code smells, DRY up repeated patterns, fix failing tests, and simplify the agent-sync codebase. All existing functionality must continue working.

## Metrics
- **Primary**: exit_code (failures, lower is better) — 0 = all tests pass
- **Secondary**: tests_passed (higher is better), loc (lower = less code, better)

## How to Run
`bash autoresearch.sh` — runs pytest, parses results, outputs METRIC lines.

## Files in Scope
- `src/agent_sync/cli.py` — CLICK commands
- `src/agent_sync/sync.py` — SyncManager
- `src/agent_sync/skills.py` — SkillsManager
- `src/agent_sync/secrets.py` — SecretsManager
- `src/agent_sync/publish.py` — Skill publishing
- `src/agent_sync/agents/__init__.py` — Agent registry access
- `src/agent_sync/agents/base.py` — BaseAgent
- `src/agent_sync/agents/transforms.py` — Transform utilities
- `src/agent_sync/agents/registry_loader.py` — Registry loading
- `src/agent_sync/agents/roocode.py` — RooCode handler
- `src/agent_sync/agents/cline.py` — Cline handler
- `src/agent_sync/agents/cursor.py` — Cursor handler
- `src/agent_sync/agents/windsurf.py` — Windsurf handler
- `src/agent_sync/skills_diff.py` — Skills diff
- `src/agent_sync/skills_reconcile.py` — Skills reconcile
- `src/agent_sync/skills_delete.py` — Skills delete
- `src/agent_sync/config.py` — Config management
- `tests/` — All test files

## Off Limits
- `agent_registry.yaml` — Data, not code
- `pyproject.toml` — Build config
- `scripts/` — External tooling
- `skills/` — Skill definitions

## Constraints
- All tests must pass: exit_code=0
- No new dependencies
- No breaking changes to CLI interface
- Hatch-VCS versioning must continue working

## Results Summary (7 experiments)

| # | Experiment | Before | After | Δ |
|---|-----------|--------|-------|---|
| 1 | Remove 18 dead functions + fix 3 failing tests | exit_code=3, 106/109 pass, LOC=6847 | exit_code=0, 94/94 pass, LOC=6374 | **-473 LOC, +3 tests fixed** |
| 2 | DRY push_to_github() helper (3→1 duplications) | LOC=6374 | LOC=6346 | **-28 LOC** |
| 3 | SkillsReconcile inherits SkillsDiff (3 dups→0) | LOC=6346 | LOC=6301 | **-45 LOC** |
| 4 | Remove unused fixture, no-op test, redundant imports | tests=94/94, LOC=6301 | tests=93/93, LOC=6285 | **-16 LOC, -1 test** |
| 5 | Remove 15 unused imports across 8 files | LOC=6285 | LOC=6278 | **-7 LOC** |
| 6 | Merge test_security_harden → test_security | 93/93 | 93/93 | **-1 file** |

### Final State
- **exit_code**: 0 (from 3) — all tests pass
- **Tests**: 93/93 pass (was 106/109)
- **LOC**: 6,278 (from 6,847) — **569 lines removed (-8.3%)**
- **Test files**: 12 (from 15)
- **Dead functions removed**: 18
- **Duplications eliminated**: 7 instances
- **Unused imports removed**: 15

### Key Fixes
1. **3 failing publish tests** — added `timeout` parameters to mock assertions (timeouts added in previous autoresearch weren't reflected in tests)
2. **config.py IndentationError** — broken after removing `set_sync_option`

## What's Been Tried
- **Experiment 1**: Removed 18 dead/unused functions across agents/__init__.py (get_agent_by_method, get_enabled_agents, is_internal_entry), transforms.py (transform_skill, unflatten_md_to_skill, remove_yaml_frontmatter, flatten_skill_to_md, copy_skill_directory), registry_loader.py (expand_path), config.py (set_sync_option, to_dict), and all 4 agent handlers (sync_skills, sync_to_cline, sync_to_windsurf, get_all_skills_paths, get_source_paths, get_mode_specific_path, supports_mode_specific). Fixed 3 failing publish tests (timeout assertions). Removed 23 obsolete transforms tests. LOC -473.
- **Experiment 2**: Extracted push_to_github() helper to eliminate 3 duplicated push-to-GitHub-after-ops blocks in CLI (centralize, reconcile, delete).
- **Experiment 3**: SkillsReconcile now inherits from SkillsDiff, eliminating 3 duplicated methods (init, get_local_skills, get_remote_skills).
- **Experiment 4**: Removed unused tmp_env_file fixture, removed no-op test_publish_validation_logic test, moved local imports to module level in sync.py.
- **Experiment 5**: Removed 15 unused imports across 8 source files.
- **Experiment 6**: Merged test_security_harden.py into test_security.py.
