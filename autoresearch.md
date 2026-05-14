# Autoresearch: Code Quality — DRY/KISS + Dead Code Removal

## Objective
Remove dead code, fix code smells, DRY up repeated patterns, fix failing tests, and simplify the agent-sync codebase. All existing functionality must continue working.

## Metrics
- **Primary**: exit_code (failures, lower is better) — 0 = all tests pass
- **Secondary**: tests_passed (higher is better), loc (lower = less code, better)

## How to Run
`bash autoresearch.sh` — runs pytest, parses results, outputs METRIC lines.

## Files in Scope
- `src/agent_sync/cli.py` — CLICK commands (long file, smelly)
- `src/agent_sync/sync.py` — SyncManager (very long, has DRY violations and dead code)
- `src/agent_sync/skills.py` — SkillsManager
- `src/agent_sync/secrets.py` — SecretsManager
- `src/agent_sync/publish.py` — Skill publishing
- `src/agent_sync/agents/__init__.py` — Agent registry access
- `src/agent_sync/agents/base.py` — BaseAgent (many repeated path properties)
- `src/agent_sync/agents/transforms.py` — Transform utilities (has dead code)
- `src/agent_sync/agents/registry_loader.py` — Registry loading
- `tests/` — All test files

## Off Limits
- `agent_registry.yaml` — Data, not code
- `pyproject.toml` — Build config
- `scripts/` — External tooling
- `skills/` — Skill definitions

## Constraints
- All tests must pass: exit_code=0, tests_passed=109+
- No new dependencies
- No breaking changes to CLI interface
- Hatch-VCS versioning must continue working

## What's Been Tried
- (none yet for this session)
