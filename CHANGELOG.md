# Changelog

All notable changes to this project will be documented in this file.

---

## [0.31.0-alpha] - 2026-06-04

### ✨ New Features

#### `publish run` — Auto-sync to private repo

After publishing the curated subset to the public repo, `agent-sync publish run` now also syncs the full local state to the private repo (`config.repo_url`) as a normal commit (preserves history). Default ON, opt-out with `--no-private`. New `PublishConfig.auto_push_private: bool = True` field in `~/.config/agent-sync/publish.yaml`.

#### `push` — Mirror-prune private repo

Private repo is now kept as a mirror of the local `~/.agents/skills/` instead of an accumulating archive. On every push, skills that exist in HEAD but are missing from the local hub are removed via `git rm` in the same commit (history preserved as `D` entries, no `--force`). Default ON, opt-out with `agent-sync push --no-prune`.

**Why:** the private repo previously kept every skill ever pushed, so `pull` or any restore could resurrect deleted/renamed skills. Mirror-prune closes that loop.

**Output example:**
```
📤 Changes to be pushed to agent-sync-private.git:

  skills/
    - cali-go-stack/SKILL.md
    - cali-go-stack/references/...
    - cali-go-standards/SKILL.md
    ...

15 item(s)
```

### 🧪 Tests

- `tests/test_publish_state.py` — +7 tests for `PublishConfig.auto_push_private` (default, to_dict, from_dict, roundtrip, backward compat)
- `tests/test_publish_private_sync.py` (new) — +8 tests for the publish-run auto-sync: CLI flag registration, default vs `--no-private`, missing `repo_url` skip, `auto_push_private=false` skip, push exception handling, zero-changes path
- `tests/test_prune_orphan_skills.py` (new) — +11 tests for mirror-prune: no orphans, orphan shape, `git rm` per orphan, missing hub, empty HEAD, hidden dirs, `git rm` failure isolation, default `prune=True` plumbing

**507/507 tests passing.**

### Backward compatible

- Without `--no-prune` opt-out: push still works as before (additive)
- Without `--no-private` opt-out: publish run still publishes to public only
- Old `publish.yaml` files load with `auto_push_private=True` default (backward compatible)

### Files changed

- `src/agent_sync/publish/base.py` — `PublishConfig.auto_push_private: bool = True`
- `src/agent_sync/sync.py` — `SyncManager.push(prune=True)`, `_push_stage_and_get_changes(prune=True)`, new `_prune_orphan_skills()` helper
- `src/agent_sync/cli.py` — `--no-prune` flag on `push`, `--no-private` flag on `publish run`, post-publish auto-sync block

---

## [0.20.0] - 2026-05-14

### ✨ New Features

#### `publish --agents` — Publish Agent Instructions

Publish AGENTS.md, GEMINI.md, and other agent instruction files to a public GitHub repository.

**New CLI commands:**
```bash
agent-sync publish              # Publish both skills AND agent instructions (default)
agent-sync publish --skills    # Publish only skills
agent-sync publish --agents    # Publish only agent instructions (NEW!)
```

**Features:**
- **Agent discovery** via `config_patterns` from agent_registry.yaml
- **Security scanner** with 12 regex patterns detecting:
  - Absolute paths: `/Users/`, `/home/`, `/root/`, `C:\`
  - API tokens: OpenAI `sk-`, GitHub `ghp_`, `gho_`
  - Internal commands: `/skill:`, `ctx_batch_execute()`, `ctx_search()`
  - Server paths: `server.`, `.renatocaliari.com`
- **TUI** with security indicators (⚠️ / ✓) per file
- **Security panel** with options: edit, skip, continue, cancel
- **Config persistence** for selection

**Repository structure:**
```
agents/
├── pi.dev/AGENTS.md
├── opencode/AGENTS.md
└── qwen-code/output-language.md
```

**New files:**
- `src/agent_sync/agent_discovery.py` — Discovery module
- `src/agent_sync/security_scanner.py` — Security scanner with 12 patterns
- `tests/test_agent_discovery.py` — 17 tests
- `tests/test_security_scanner.py` — 26 tests

---

## [0.21.0] - 2026-05-16

### ✨ New Features

#### Publish Command — Interactive Multi-Select with Saved State

Full interactive selection for skills and agents with toggle controls and persistent saved state.

**Skills Selection:**
- Options: `u` (use saved), `e` (edit with toggles), `a` (all), `n` (none)
- Shows previously saved selection with status indicators (saved, flagged)
- Toggle interface with real-time selection updates
- Saves selection to `config.published_skills`

**Agents Selection:**
- Same interface as skills with `u/e/a/n` options
- Shows security status per agent
- Saves selection to `config.published_agents`

**Output Improvements:**
- Removed duplicate "Publishing Skills..." messages
- Fixed repository visibility check placement (before confirmation)
- Removed misleading "Want to publish also skills?" hint
- Added consistent "Scanning X for sensitive content..." messages
- Removed redundant "Published to GitHub!" messages
- Added unified Final Summary showing both skills and agents counts

**Repository Enforcement:**
- Skills publishing now forced to `agent-sync-public` repository
- Removed custom repo URL support for public publishing
- Centralized visibility check in CLI before calling publish functions

**Bug Fixes:**
- Removed dangerous name skip check (no more "12 files skipped")
- Fixed `repo_name` undefined error in publish_skills

---

## [Unreleased]

### ✨ New Features

#### Unified Publish Flow — `--skills`, `--agents`, `--all`

Unified the publish command into a single cohesive flow with contextual security warnings.

**Changes:**
- Single `publish` command replaces separate `publish --skills` and `publish --agents`
- Default behavior (`--all`) publishes both skills AND agent instructions
- Contextual security warnings based on `--skills`/`--agents`/`--all` flags
- Phase 1: Discovery — shows what will be published
- Phase 2: Summary table with security status for agents
- Phase 3: Single confirmation before publishing
- Phase 4: Execute without re-confirmation

**New tests:**
- `tests/test_publish_cli.py` — 9 tests for unified publish flow

**Files changed:**
- `src/agent_sync/cli.py` — Unified publish command
- `tests/test_publish_cli.py` — New tests

---

## [0.20.0] - 2026-05-14

### ✨ New Features

#### Safe Centralize — Protection against unintentional skill import

**Problem:**
`agent-sync skills centralize` scanned agents and imported skills back to the hub without differentiation, causing resurrection of deleted skills, importing old copies, and silent destruction of unselected skills.

**Solution:**
Pipeline reordered with 3 layers of protection:

1. **Orphan selection TUI** (Hybrid A+E): Interactive TUI with checkboxes, default none selected. Shortcuts: `a`=all, `n`=none, Enter=done.
2. **Content comparison via hash**: Recursive MD5 hash detects divergent copies. Shows `⚠️ diverge` when agent copies differ.
3. **Post-selection Keep/Remove**: After importing selected, asks what to do with unselected — Keep (default) or Remove.

New CLI flags:
- `--yes` — Non-interactive: skip all orphans, auto-keep
- `--import-all` — Import all orphans without TUI (old behavior)
- `--dry-run` — Preview without modifying anything

**Architectural changes:**
- `_cleanup_agent_local_skills()` removed from `configure_agents()` — cleanup is pipeline-managed
- `_sync_from_repo()` moved to after fresh setup detection
- Fresh setup (empty hub) → auto-import all orphans
- Fallback for non-interactive terminals

#### DotAgents Protocol Alignment

**Problem:** Agent configuration lacked a standard directory convention, making it hard to share and version-control complete agent setups.

**Solution:** Aligned with the [DotAgents Protocol](https://dotagentsprotocol.com/):
- `~/.agents/skills/` hub follows the `.agents/` directory convention
- Added protocol alignment documentation to `agent_registry.yaml`
- Created `docs/dotagents.md` reference guide
- Vendor-neutral, git-friendly approach maintained

**Files:** `docs/dotagents.md`, `src/agent_sync/agent_registry.yaml`

#### DotAgents Config Export

**New command:** `agent-sync config export`
- Exports current registry to `~/.agents/config.json`
- DotAgents Protocol compatible format
- Options: `--dry-run`, `--output PATH`

**Files:** `src/agent_sync/config_exporter.py`, `tests/test_config_exporter.py`

#### DotAgents MCP Unified Export

**New command:** `agent-sync mcp`
- Scans vendor MCP configs (`~/.claude/mcp.json`, etc.)
- Merges into `~/.agents/mcp.json`
- Detects conflicts (same server in multiple configs)
- Options: `--dry-run`, `--force`, `--conflicts`, `-s/--source PATH`

**Files:** `src/agent_sync/mcp_merger.py`, `tests/test_mcp_merger.py`

#### Rich Push Output with Status Indicators

**Problem:**  
`agent-sync push` showed only file paths without indicating if each file was added, modified, or deleted. Deletions (e.g., removed skills) appeared identical to uploads, causing confusion.

**Solution:**  
Push output now groups files by directory (`skills/`, `configs/`, `agents/`) and shows per-file status:

```
✅ Pushed 4 files:
  • .agent-sync-manifest.json          📝 modified
  📂 skills/ (2 files)
    ├── old-skill/*                    🗑️ deleted (3 files)
    └── new-skill/*                    🆕 added (5 files)
```

- Homogeneous skill directories are collapsed with `*` notation and file count
- Mixed-status directories show individual files
- Backward-compatible: `sync_manager.push()` returns richer `list[dict]` with `path`, `status`, `label`, and `directory_count`

#### Flexible File Sync with Paths Support

**Problem:**  
Previously, agent-sync only synced config files (e.g., `opencode.jsonc`). Users couldn't backup plugins, commands, or other agent-specific files.

**Solution:**  
Added three new sync options in `~/.config/agent-sync/config.yaml`:

1. **`all_files: true`** - Backup entire agent directory
2. **`paths: [...]`** - Backup specific paths/glob patterns
3. **`exclude: [...]`** - Exclude patterns (works with both)

**Example Configuration:**

```yaml
# Backup everything
agents_config:
  opencode:
    sync:
      configs: true
      all_files: true
      exclude:
        - "**/*.lock"
        - "node_modules/**"

# Or backup specific paths
agents_config:
  opencode:
    sync:
      configs: true
      paths:
        - plugins/
        - commands/
        - "**/*.js"
```

**Features:**
- ✅ Glob patterns: `**/*.js`, `plugins/*`, `commands/`
- ✅ Preserves symlinks and file permissions
- ✅ Supports hidden files (.dotfiles)
- ✅ Backward compatible (default: configs only)

**Files Changed:**
- `src/agent_sync/config.py` - Added sync options with defaults
- `src/agent_sync/sync.py` - Added `_stage_agent_files()`, `_copy_directory()`, `_copy_path_pattern()`
- `tests/test_sync_paths.py` - New test file with 6 tests

---

## [0.19.0] - 2026-05-15

### 🧹 Code Quality — 39 Experiments Across 10 Sessions

**Cleanup:**
- Removed 25 dead/unused functions, 15 unused imports, 3 dead parameters
- Eliminated 30+ duplication instances via shared helpers (`push_to_github()`, `_stage_pi_extra_paths()`, `_restore_pi_extra_paths()`, `_copy_item()`, `scan_skills_dir()`, `_step_title()`, `parse_multiselect_input()`)
- Modernized typing: `List` / `Dict` / `Set` → `list` / `dict` / `set` (14 files)
- Simplified `skills_reconcile.py` — now inherits from `SkillsDiff`, 3 duplicated methods eliminated
- `secrets.py` shrunk from 198 to 60 lines (7 dead methods removed)
- `transforms.py` removed entirely (168 lines, all dead code)

**Bug Fixes:**
- Fixed 3 failing publish tests (timeout assertion mismatch)
- Fixed `setup.py` extension-skills iteration crash (dict vs list type mismatch)
- Fixed `config.py` YAML loading — defensive `isinstance` checks prevent `AttributeError` on malformed configs
- Fixed `_load_state` — try/except prevents crash on corrupted state file

**Tests:**
- Added 23 new tests: 14 for `parse_multiselect_input()`, 13 for `scan_skills_dir()` + `SkillsDiff.diff()`, 4 for `SkillsReconcile.apply_decisions()`, 6 for `generate_readme()`
- Total: 126 tests, all passing (+20 net from baseline 106)
- Removed 2 obsolete test files (`test_transforms.py`, `test_security_harden.py`)

**Dev Experience:**
- Updated `pyproject.toml`: Python 3.13/3.14 classifiers + Black targets, bumped ruff/black minimums, added `RUF100` ruff rule
- CI matrix expanded to test Python 3.10–3.14 (was 3.10–3.12)
- `docs/adding-agents.md` — removed references to dead `sync_skills` method, fixed Cline/Windsurf examples, expanded schema docs
- `README.md` — expanded CLI commands reference, fixed quick-start flow, removed nonexistent `--private` flag example
- `skills/agent-sync/SKILL.md` — removed reference to nonexistent `secrets export` command

**Files Changed:** 44 files, +1,709 / −2,425 lines (net −716)

---

## [0.15.1] - 2026-03-06

### 🐛 Critical Fix: Extension Skills Not Centralized

**Problem:**
Extension skills (e.g., `~/.config/opencode/superpowers/skills/`) were being moved to `~/.agents/skills/` during `agent-sync skills centralize`, when they should remain in their original locations.

**Solution:**
- Extension skills are now marked with `is_extension: True` flag during scan
- `centralize()` command skips extension skills entirely
- Extension skills only backed up via symlinks during `push`
- Regular skills (e.g., `~/.config/opencode/skills/`) still centralized as expected

### Fixed
- Extension skills incorrectly moved to global directory during centralize
- Skills from `opencode-superpowers` now stay in `~/.config/opencode/superpowers/skills/`
- Extension symlinks preserved and backed up correctly

### Added
- Test: `test_centralize_does_not_move_extension_skills` - ensures extension skills remain in place
- Console output shows "(extension - backup only)" for extension skills during scan

### Migration
If you ran `centralize` with v0.13.0 and extension skills were moved:
```bash
# Skills will be restored on next pull from repo
# Or manually restore from ~/.agents/skills/ to original location
```

---

## [0.7.0] - 2026-03-05

### 🚀 Major Architectural Shift: YAML-Driven Agent Registry

**Philosophy Change:**
- Agent definitions are now data-driven via `agent_registry.yaml`.
- Removed Symlink fallback in favor of a more robust `Native -> Config -> Copy` flow.
- Users can now override the `skills_method` for any agent in their local `config.yaml`.

### Added
- `src/agent_sync/agent_registry.yaml`: Centralized registry for all agent definitions.
- `src/agent_sync/agents/registry_loader.py`: Dynamic loader and validator for the YAML registry.
- `docs/adding-agents.md`: New documentation for adding support for new AI agents.
- `Skills Method` column in `agent-sync agents` command.
- Automatic persistence of the successful `skills_method` in user configuration.

### Changed
- **`BaseAgent` Refactor**: Now a generic class that initializes from YAML data instead of hardcoded subclasses.
- **`SkillsManager` Flow**: 
  1. Priority 1: User override in `config.yaml`.
  2. Priority 2: Registry default method.
  3. Priority 3: Implementation flow (`native` -> `config` -> `copy`).
- **`opencode` Configuration**: Now uses dynamic JSON path navigation (`skills.paths`) defined in the registry.

### Removed
- **Symlink Support**: Fully removed `_create_symlink` and `_create_fallback_symlinks` to improve cross-platform reliability and avoid permission issues.
- All hardcoded agent subclasses (`OpencodeAgent`, `ClaudeCodeAgent`, etc.).

### Migration
If upgrading from v0.6.3:
```bash
# Re-configure agents with the new registry system
agent-sync skills centralize
```
Your successful configuration methods will be automatically saved to `~/.config/agent-sync/config.yaml`.

---

## [0.6.3] - 2026-03-04

### 🎯 Major Refactor: Centralized Skills Architecture

**Philosophy Change:**
- Skills now exist ONLY in `~/.agents/skills/` (single source of truth)
- No local copies in agent directories
- Agents configured via native support, config, or symlink

### Changed

- **`_configure_agent()` priority** (NEW ORDER):
  1. **Native support** (pi.dev, qwen-code) - fastest, no setup
  2. **Config update** (opencode) - PREFERRED (explicit, robust, cross-platform)
  3. **Symlink** (claude-code, gemini-cli) - FALLBACK if config fails
  4. **Error** - if no method works

  **Why config is preferred:**
  - ✅ Explicit - visible in config file
  - ✅ Robust - survives reinstalls, doesn't break
  - ✅ Cross-platform - works on Windows
  - ✅ Versionable - can commit to repo
  - ✅ Flexible - can add multiple paths

  **Fallback behavior:**
  - If config fails → tries symlink
  - If symlink fails → returns error
  - No silent failures

- **`centralize()` behavior**:
  - Moves ALL skills to `~/.agents/skills/`
  - Removes ALL local skills from agent directories
  - Configures agents to use centralized location
  - No fallback copy (was creating duplicates)

### Added

- `_cleanup_agent_local_skills()` - Unified cleanup for all agents
  - Removes local skills before configuration
  - Preserves symlinks (like `_global`)
  - Ensures clean agent directories

### Removed

- `_copy_skills()` - No longer needed (was creating duplicates)
- `_cleanup_native_agents_skills()` - Replaced by unified cleanup

### Migration

If upgrading from v0.6.2 or earlier:
```bash
# Re-run centralize to clean up duplicates
agent-sync skills centralize

# Or use cleanup script
./scripts/cleanup-duplicates.sh
```

### Agent Configuration Matrix

| Agent | Method | Priority | Fallback? | Local Skills |
|-------|--------|----------|-----------|--------------|
| opencode | Config | 1st choice | → Symlink | ❌ None |
| claude-code | Symlink | 2nd choice | (no config) | ❌ None |
| gemini-cli | Symlink | 2nd choice | (no config) | ❌ None |
| pi.dev | Native | 1st choice | N/A | ❌ None |
| qwen-code | Native | 1st choice | N/A | ❌ None |

---

## [0.6.2] - 2026-03-04

### Fixed
- `_stage_skills()` now removes skills deleted from `~/.agents/skills/`
- `_stage_agent_configs()` now removes configs deleted locally (e.g., `.json` vs `.jsonc`)
- `pull()` console import moved to function level (fixes undefined error)

### Changed
- `push --skills-only` now syncs deletions (not just additions)
- `push --configs-only` now syncs deletions (not just additions)

### Use Cases Fixed
- Delete skill locally → removed from repo on push ✅
- Delete config file locally → removed from repo on push ✅
- Example: remove `opencode.json`, keep `opencode.jsonc` → repo updated ✅

---

## [0.6.1] - 2026-03-04

### Added
- `push --skills-only` - Push only skills (not configs)
- `push --configs-only` - Push only configs (not skills)
- `pull --skills-only` - Pull only skills (not configs)
- `pull --configs-only` - Pull only configs (not skills)

### Changed
- Updated README with new push/pull options

---

## [0.5.2] - 2026-03-04

### Fixed
- Critical: repo directory creation with error handling and verification
- Check if repo exists on GitHub before creating
- Security warning for public repos with explicit confirmation
- Default to NO for public repo confirmation (safe by default)

### Changed
- `init_repo()` now links to existing repos automatically (if private)
- Public repos require explicit user confirmation with security warning
- Better error messages for directory creation failures

---

## [0.5.1] - 2026-03-04

### Fixed
- Create repo directory before use (critical error on `init`)
- Filter `.DS_Store` and hidden files in skill scan
- Fix step numbering in wizard (Step 6 was duplicated)
- `get_summary()` counting all files instead of valid skills

### Changed
- Add symlink support for Gemini CLI (was using fallback copy)
- Verify symlink creation before returning success
- Fall through to other methods if symlink fails

---

## [0.5.0] - 2026-03-04

### Added
- `agent-sync config repo` - View/set repository without wizard
- `init --force` - Override existing config

### Security
- `init` blocks if already configured (prevents accidental overwrite)

---

## [0.4.0] - 2026-03-04

### Added
- `skills centralize --distribute` - Copy skills to all agent directories

### Fixed
- Native agents (pi.dev, qwen) receiving duplicate skill copies

---

## [0.3.0] - 2026-03-04

### Added
- Cross-platform paths (Linux, macOS, Windows)
- Pi.dev extensions/prompts/themes sync
- Version management (`--version`, `check-update`)

### Fixed
- Secrets sync UI removed (never implemented)

---

## [0.2.0] - 2026-03-04

### Added
- Initial release
