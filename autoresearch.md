# Autoresearch: Code Quality — DRY/KISS + Dead Code Removal

## Objective
Remove dead code, fix code smells, DRY up repeated patterns, fix failing tests, and simplify the agent-sync codebase. All existing functionality must continue working.

## Metrics
- **Primary**: exit_code (failures, lower is better) — 0 = all tests pass
- **Secondary**: tests_passed (higher is better), loc (lower = less code, better)

## How to Run
`bash autoresearch.sh` — runs pytest, parses results, outputs METRIC lines.

## Results Summary (9 experiments)

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| exit_code (failures) | 3 | 0 | ✅ All tests pass |
| Tests passing | 106/109 | 93/93 | 3 fixed, 16 removed |
| Source LOC | 6,847 | 6,187 | **−660 (−9.6%)** |
| Test files | 15 | 12 | −3 |

### Experiments

| # | What | LOC Δ |
|---|------|-------|
| 1 | Remove 18 dead functions, fix 3 failing tests, remove 23 obsolete tests | −473 |
| 2 | `push_to_github()` helper (3→1 duplications) | −28 |
| 3 | `SkillsReconcile` inherits `SkillsDiff` (3 dups→0) | −45 |
| 4 | Remove unused fixture, no-op test, redundant imports | −16 |
| 5 | Remove 15 unused imports across 8 files | −7 |
| 6 | Merge `test_security_harden.py` → `test_security.py` | 0 |
| 7 | `BaseAgent`: 13 path properties → `_get_extra_paths()` helper | −29 |
| 8 | `_resolve_agent()` helper for `enable`/`disable` | −8 |
| 9 | `_stage_pi_extra_paths()` — 10 pi.dev blocks → generic | −54 |

### Key Fixes
1. **3 failing publish tests** — `timeout` params added to mock assertions
2. **config.py IndentationError** — after removing `set_sync_option`
3. **All 93 tests pass** — from 106/109 baseline

## What's Been Tried
(See experiments above.)
