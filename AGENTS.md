# LLM Foundation & Project Mandates

This file provides critical instructions for AI models (like Gemini, Claude, etc.) working on the `agent-sync` project.

## 🚀 Automatic Versioning (Hatch-VCS)

This project uses `hatch-vcs` for dynamic versioning based on Git Tags.

**Rules for LLMs:**
1.  **NEVER** hardcode version strings in `pyproject.toml` or `__init__.py`. 
2.  The `__init__.py` should use `importlib.metadata.version("agent-sync")` to read its version.
3.  **To Release a New Version**:
    -   Perform your code changes and commit.
    -   Determine the next semantic version (e.g., `v0.8.1`).
    -   Execute: `git tag vX.X.X`
    -   Execute: `git push origin vX.X.X`
    -   Create a GitHub Release using `gh release create`.

## 🏗️ Architecture Mandates

-   **Agent Registry**: New agent CLI support must be added to `src/agent_sync/agent_registry.yaml`, not hardcoded in Python.
-   **No Symlinks**: Always prefer `Native`, `Config`, or `Copy` methods. Do not re-introduce symlink fallbacks *as a sync method*. User-side FS symlinks (e.g. `~/.pi/extensions → ~/.pi/agent/extensions` to avoid dual-path duplication) are out of scope.
-   **UX/DX First**: CLI outputs must be categorized, visual (using Rich panels/tables), and provide clear guidance on errors.
-   **VS Code Extensions & IDEs**: Support for RooCode, Cline, Cursor, and Windsurf uses specialized handlers in `src/agent_sync/agents/` with transform support (e.g., Cursor's flatten transform).

## 🛠️ Dev Workflow

**Verify editable install before testing.** A system-installed `agent-sync` at `/opt/homebrew/bin/agent-sync` will silently use a stale package, not your source edits:

```bash
which agent-sync && head -1 $(which agent-sync)
# Expected: /Users/cali/Development/sync-agents-configs/.venv/bin/agent-sync
# Sympt: /opt/homebrew/bin/agent-sync  → tests pass against OLD code, not yours
```

If the wrong binary is active, override it:

```bash
mv /opt/homebrew/bin/agent-sync /opt/homebrew/bin/agent-sync.system.bak
ln -sf "$(pwd)/.venv/bin/agent-sync" /opt/homebrew/bin/agent-sync
```

Bootstrap from scratch with `uv venv .venv --python 3.14 && source .venv/bin/activate && uv pip install -e ".[dev]"`.

## 📦 Distribution

-   Users update via `agent-sync update`. Ensure this command remains bulletproof and supports both `pipx` and `pip` (with `--break-system-packages` for macOS).

## 🔗 DotAgents Protocol Alignment

This project follows the [DotAgents Protocol](https://dotagentsprotocol.com/) conventions for AI agent configuration.

**What we follow:**
- `~/.agents/skills/` as the canonical skills hub (vendor-neutral, shared across all agents)
- `.agents/` directory structure for centralized configuration
- Git-friendly, version-controllable agent configurations

**Why vendor-specific paths still exist:**
Some agents (Claude Code, Gemini CLI, etc.) don't natively read from `~/.agents/`. agent-sync bridges this by:
1.  Using `~/.agents/skills/` as the **source of truth**
2.  Copying/syncing to vendor-specific paths when needed
3.  Supporting multiple sync methods: `native`, `config`, and `copy`

**Not implemented (yet):**
- `./.agents/` workspace overrides
- `~/.agents/mcp.json` unified MCP configuration
- `.dotagents` bundles from hub.dotagentsprotocol.com

- Gemini CLI: AI contributor overseeing architectural mandates.


#### Skill Lifecycle (for LLMs)

Skills exist in three layers: **hub** (`~/.agents/skills/`), **private repo**
(GitHub backup), and **agent directories** (`~/.claude/commands/`, etc.).

The hub is the source of truth. `push` mirrors hub → repo working tree,
then `git add .` + commit persists the change. There is no manifest file.

**Concrete flows:**

1. **User removes skill from hub → `push` (default)**
   → `_stage_skills` mirrors hub to repo working tree (removes skills
   not in hub). Deletion is staged. User sees the diff (including `D`
   entries) plus a pre-confirmation warning, then presses Enter.
   Commit → deletion is in `git log -D`. HEAD no longer has the skill.
   → **retired**. `_sync_from_repo` checks `ever_deleted - current_head`
   and won't re-import. Agent stale copies are also ignored.

2. **User puts skill back in hub → `push`**
   → `_stage_skills` copies hub → repo. Skill is back in HEAD.
   `ever_deleted - current_head` empties it → NOT retired.
   `centralize` re-imports on other machines. Full backup/sync restored.

3. **`push --prune`** — same as default, plus `_prune_orphan_skills` runs
   `git rm --cached` for index edge cases. The flag is about index
   cleanup, not the deletion itself (`_stage_skills` handles that).

**Key implementation details:**
- `_get_retired_skill_names()` does `git log --all --diff-filter=D` →
   parses deleted paths → subtract `git ls-tree -d HEAD skills/`.
- `_sync_from_repo` filters by retired — never resurrects deleted skills.
- `_prune_orphan_skills` does NOT filter by retired.
- Default `push` safety comes from: (a) user sees complete diff before
  confirming, (b) pre-confirmation warning lists orphans, (c) post-hoc
  `--strict` flag exits 2 for CI.
- `audit` shows `in_sync` | `in_hub_only` | `in_repo_only`. No retired
  column — that's an implementation detail.

**Do NOT re-introduce a RETIRED.md manifest** — the git-history approach
is KISS (zero files), testable (12 integration tests), and avoids sync
confusion across machines. Re-adding to the hub immediately unretires.

# 🧪 Testing Protocol

### When to Run Tests

| Action | Command | Why |
|--------|---------|-----|
| **Before commit** | `./scripts/ci-local.sh` | Catch failures before CI |
| **Before push** | `python3 -m pytest tests/ -v` | Verify main branch is green |
| **After merge conflicts** | `python3 -m pytest tests/ -v --tb=short` | Confirm resolution |
| **After refactoring** | `python3 -m pytest tests/ -v` | Regression check |

### What to Test

**1. CLI Commands (always test the actual CLI, not just mocks)**
```bash
# Test that filter flags don't cause TypeErrors
agent-sync push --skill dogfood --exclude-skill old
agent-sync pull --skill foo --dry-run
```

**2. Integration with real git (in tests/)**
- Don't mock `SyncManager._run_git` unless necessary
- Test the actual CLI flow with `CliRunner`
- When mocking `Config`, mock it at the module level, not just `SyncManager`

**3. Common failure patterns to avoid:**
- ❌ `patch.object(SyncManager, 'method')` without also patching `Config()`
- ❌ Checking exact parameters passed to mocks (fragile)
- ✅ Verifying no TypeErrors occur when calling CLI
- ✅ Checking error messages are user-friendly

### Testing Anti-Patterns

```python
# BAD: Tests break when implementation details change
def test_push_passes_skill_filter_as_skills_filter():
    with patch.object(SyncManager, 'push') as mock_push:
        mock_push.return_value = ([], {})
        result = runner.invoke(main, ['push', '--skill', 'foo'])
        assert mock_push.call_args[1]['skills_filter'] == ['foo']  # Fragile!

# GOOD: Tests verify the contract, not implementation
def test_push_with_filter_no_typeerror():
    result = runner.invoke(main, ['push', '--skill', 'foo'])
    assert 'TypeError' not in result.output  # Stable contract
    assert result.exit_code in [0, 1]  # No crash
```

### Quick Test Commands

```bash
# Run all tests (same as GitHub Actions)
python3 -m pytest tests/ -v --tb=short

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
python3 -m pytest tests/test_cli_params_e2e.py -v

# Run only fast tests (skip integration)
python3 -m pytest tests/ -m "not integration" -v

# Run only integration tests (real git, real fs)
python3 -m pytest -m integration tests/integration/ -v
```

### Skills state observability

When debugging skill sync issues, use:

```bash
# Full hub/repo/manifest state across all skills
agent-sync skills audit

# Lifecycle of one skill (when added, last modified, current state)
agent-sync skills explain <name>

# Preview prune before executing
agent-sync skills prune --dry-run
```

### Local CI Scripts

- `./scripts/ci-local.sh` - Run same tests as GitHub Actions
- `./scripts/pre-commit` - Pre-commit hook (run tests before commit)
- `.pre-commit-config.yaml` - Full pre-commit setup (install with `pre-commit install`)