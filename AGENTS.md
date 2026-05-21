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
-   **No Symlinks**: Always prefer `Native`, `Config`, or `Copy` methods. Do not re-introduce symlink fallbacks.
-   **UX/DX First**: CLI outputs must be categorized, visual (using Rich panels/tables), and provide clear guidance on errors.
-   **VS Code Extensions & IDEs**: Support for RooCode, Cline, Cursor, and Windsurf uses specialized handlers in `src/agent_sync/agents/` with transform support (e.g., Cursor's flatten transform).

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


## 🧪 Testing Protocol

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

# Run only fast tests
python3 -m pytest tests/ -m "not slow" -v
```

### Local CI Scripts

- `./scripts/ci-local.sh` - Run same tests as GitHub Actions
- `./scripts/pre-commit` - Pre-commit hook (run tests before commit)
- `.pre-commit-config.yaml` - Full pre-commit setup (install with `pre-commit install`)