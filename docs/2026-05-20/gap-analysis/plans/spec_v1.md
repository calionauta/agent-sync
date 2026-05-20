# Plan: Gap Analysis & Cleanup — agent-sync v0.24.6+

**Date:** 2026-05-20
**Author:** pi (auto-generated)
**Status:** Draft — awaiting Plannotator review

---

## Context

After v0.24.6 (skills list TUI + centralize simplification), a systematic double-check revealed 10 pending items across 4 priority levels. This plan investigates each topic and defines concrete resolutions.

---

## Topic 1 — Dead Methods in `skills.py`

### Investigation Result

`skills.py` (1024 lines) contains **4 methods that are NEVER called from anywhere** — not from `centralize()`, not from any CLI command, not from any test, not from any other file. All 4 are remnants from the removed orphan TUI:

| Method | Lines | Location | Why Dead |
|--------|-------|----------|----------|
| `_orphan_selection_tui()` | 70 | 210–279 | Replaced by auto-import in new `centralize()` |
| `_post_selection_prompt()` | 10 | 281–290 | Called only by `_orphan_selection_tui` |
| `_find_conflicts()` | ~35 | 363–~405 | Never called (no external callers) |
| `_remove_orphans_from_agents()` | 21 | 663–683 | Never called (centralize now uses `_pick_best_source`) |

**Total dead code: ~136 lines** across 4 methods, plus their docstrings and helper comments.

The `find_conflicts()` vs `_find_conflicts()` naming is confusing — there's a `find_conflicts()` (non-underscore) that IS called internally by other methods in `skills.py`, and the underscore version is dead. Both coexist in the same file.

### Resolution

**Delete all 4 dead methods.** No refactoring needed — they are pure dead code with no side effects or dependencies.

**Steps:**
1. Remove `_orphan_selection_tui()` (lines 210–279)
2. Remove `_post_selection_prompt()` (lines 281–290)
3. Remove `_find_conflicts()` (lines ~363–~405) — keep `find_conflicts()` (non-underscore, it IS called)
4. Remove `_remove_orphans_from_agents()` (lines 663–683)
5. Verify: `python3 -c "from agent_sync.skills import SkillsManager; print('OK')"` — should succeed
6. Run: `python3 -m pytest tests/ -q` — must pass with 347 tests
7. Expected result: `skills.py` goes from 1024 → ~888 lines

**Verification:**
- No `rg "_orphan_selection_tui|_post_selection_prompt|_find_conflicts|_remove_orphans_from_agents" src/` should return 0 results in `skills.py`
- All tests pass

---

## Topic 2 — Outdated Docs: `docs/cli.md`

### Investigation Result

`docs/cli.md` (123 lines) documents `skills centralize` with **removed flags**:

```markdown
- `--distribute` — Copy all skills to all agent directories   ← REMOVED
- `--yes` — Skip orphan skills (non-interactive)              ← REMOVED
- `--import-all` — Import all orphan skills without TUI       ← REMOVED
```

And does **not document** the new interactive `skills list` TUI (multi-select, `[r]remove`, `[p]preview`, `[Enter]` confirm).

Current `docs/cli.md` state:
- `skills list`: 1 line — `list — List all skills in ~/.agents/skills/` ❌
- `skills centralize`: 6 options, 3 are wrong ✅
- Missing: `[r]remove`, `[p]preview`, numbered table, remove mode

### Resolution

**Rewrite the Skills section** of `docs/cli.md` to reflect current behavior.

**Steps:**
1. Update `## Skills` section header
2. Replace `skills list` description with full interactive TUI docs
3. Replace `skills centralize` options list — remove `--distribute`, `--yes`, `--import-all`, add `--copy` and `--dry-run`
4. Add a "Tips" subsection for keyboard shortcuts
5. Verify: `wc -l docs/cli.md` and check content

**New `skills list` documentation:**
```markdown
### `agent-sync skills list`
Interactive skill management console.

**Features:**
- Numbered table with file count
- Multi-select: (1-N) toggle, (a) all, (n) none, (d) deselect
- Preview: (p) cycles through SKILL.md descriptions
- Remove: (r) toggles REMOVE MODE (skills shown in red), Enter confirms deletion

**Remove mode flow:**
1. Press (r) to enter REMOVE MODE
2. Select skills to delete with (1-N)
3. Press Enter → confirmation prompt → SkillsDeleter deletes from hub + all agents
```

**New `skills centralize` options:**
```markdown
**Options:**
- `--copy` — Copy skills (keep originals in agent directories)
- `--push` — Push to GitHub after centralizing
- `--dry-run` — Preview without changing anything
```

---

## Topic 3 — Outdated `README.md`

### Investigation Result

`README.md` (267 lines) contains:
```markdown
- `skills centralize` - Move skills from agent directories to global hub (with safety TUI)
```

"with safety TUI" is **wrong** — the TUI was removed in v0.24.5. The command is now fully automatic.

### Resolution

**Update `README.md`** skills section to reflect current behavior.

**Steps:**
1. Find line with "skills centralize" and "safety TUI"
2. Replace with: `- `skills centralize` - Move skills from agent directories to global hub (fully automatic)`
3. Verify: `rg "safety TUI" README.md` should return 0 results

---

## Topic 4 — Missing Test for `skills list` TUI

### Investigation Result

`test_cli_integration.py` has:
- `test_cli_skills_centralize_help` ✅ (tests `--help` output)
- `test_cli_skills_centralize_dry_run` ✅ (tests non-crash)

But **no test** for the new interactive `skills list` TUI. The `list_skills()` function (120+ lines) has zero test coverage.

Current: `def test_cli_skills_list` does NOT exist.

### Resolution

**Add `test_cli_skills_list_help` and `test_cli_skills_list_non_crash`** to `test_cli_integration.py`.

Since TUI input testing is complex (requires mocking `Prompt.ask`), we focus on:
1. `--help` output verification
2. Non-crash on empty hub
3. Non-crash on populated hub (basic)

**Steps:**
1. Add `test_cli_skills_list_help` — verify `--help` shows new options
2. Add `test_cli_skills_list_no_crash` — `runner.invoke(main, ["skills", "list"])` should not error on empty hub
3. Add `test_cli_skills_list_shows_skills` — verify table output when skills exist
4. Run full suite: `python3 -m pytest tests/test_cli_integration.py -v` — must pass

**Note:** Full TUI interaction testing (pressing keys, entering remove mode) requires deeper mocking. The planned tests cover the basic contract.

---

## Topic 5 — Large Files: 10 Files > 300 Lines

### Investigation Result

This is a **structural debt** issue. After the 4 dead methods are removed, `skills.py` goes from 1024 → ~888 lines — still above limit. The 300-line rule exists to prevent "god functions" and maintain separation of concerns, but:

**Not all files are equal:**

| File | Lines | Nature | Verdict |
|------|-------|--------|---------|
| `sync.py` | 1700 | Single class, single responsibility | ✅ Acceptable — `SyncManager` IS the core orchestration class |
| `cli.py` | 1138 | 34 commands, dispatcher pattern | ✅ Acceptable — Click CLI files are inherently large; 73 decorators + 35 imports = 108 lines overhead |
| `skills.py` | 888+ | 26 methods, ~6 responsibilities | ⚠️ Should be split after dead methods removed |
| `publish.py` | 985 | Thin wrapper, 0 classes, 0 functions | ⚠️ Should be split — imports 12 submodules, has 1 function |
| `publish/setup.py` | 599 | Single responsibility | ⚠️ Consider splitting |
| `setup.py` | 489 | Single responsibility | ✅ Acceptable — setup logic |
| `git_publish.py` | 412 | Single responsibility | ✅ Acceptable — git publish logic |
| `config.py` | 356 | Single class | ✅ Acceptable — `Config` class |
| `security_scanner.py` | 358 | Single class | ✅ Acceptable |
| `models.py` | 305 | Data classes | ✅ Acceptable |

### Resolution

**Priority targets for splitting:**

#### 1. `publish.py` (985 lines → ~200 lines)
**Currently:** `publish.py` is a thin wrapper that imports from 12 submodules and exports a single function `has_significant_issues()`. Everything else is re-exported from `publish/__init__.py`.

**Option A (Recommended):** Delete `publish.py` entirely. Move `has_significant_issues()` to `publish/__init__.py`. Update `cli.py` import to `from .publish import has_significant_issues`. Savings: **~985 lines** removed.

**Option B:** Refactor `publish.py` into `run_publish()`, `add_source()`, `remove_source()` — but it's already split in `publish/`. Just clean up the re-exports.

#### 2. `skills.py` (888 lines → ~600 lines) after dead method removal
**Currently:** 26 methods across 6 responsibilities: scanning, orphan detection, conflict resolution, centralizing, configuring agents, distributing.

**Proposed split:**
- `skills/scanner.py` — `scan_all_agents()`, `_scan_extension_subdirs()`, `_is_valid_skill()`, `_is_extension_symlink()`, `_find_orphans()`, `_pick_best_source()`, `find_conflicts()`
- `skills/centralizer.py` — `centralize()`, `_sync_from_repo()`
- `skills/configurer.py` — `configure_agents()`, `_configure_agent()`, `_copy_skills_to_agent()`, `_cleanup_agent_local_skills()`, `_apply_config_method()`
- `skills.py` — orchestrator only: imports from submodules, `SkillsManager.__init__`, `get_summary()`, `distribute_to_all_agents()`

**Note:** This is a **larger refactoring** (3-4 hours) with potential for regressions. Recommend doing it as a separate task after the quick wins (Topics 1-4).

#### 3. `publish/setup.py` (599 lines → ~400 lines)
**Currently:** Single file with `run_publish_setup()` function (~400 lines) plus helpers. Consider extracting helpers to `publish/setup_helpers.py`.

**Recommended action:** Low priority — only split if it becomes a maintenance burden.

### Resolution Summary for Topic 5

| Action | File | Savings | Risk | Priority |
|--------|------|---------|------|----------|
| Delete `publish.py` | `publish.py` | ~985 lines | Low | 🔴 Do now |
| Extract skill submodules | `skills.py` | ~300 lines | Medium | 🟡 Next |
| Low priority | 7 others | — | — | 🟢 Later/never |

---

## Execution Order

```
Priority 1 (Quick wins — ~30 min total)
  Topic 1: Remove dead methods from skills.py      (~5 min)
  Topic 2: Update docs/cli.md                      (~10 min)
  Topic 3: Update README.md                         (~5 min)
  Topic 4: Add skills list tests                   (~10 min)

Priority 2 (Structural refactor — ~2 hours)
  Topic 5: Delete publish.py + extract skill submodules

Release v0.24.7 with Topics 1-4
Release v0.25.0 with Topic 5
```

---

## Verification Checklist

After all topics are resolved:

- [ ] `rg "_orphan_selection_tui|_post_selection_prompt|_find_conflicts|_remove_orphans_from_agents" src/agent_sync/skills.py` → 0 results
- [ ] `rg "--distribute|--yes|--import-all" docs/` → 0 results
- [ ] `rg "safety TUI" README.md` → 0 results
- [ ] `def test_cli_skills_list` exists in `tests/test_cli_integration.py`
- [ ] `python3 -m pytest tests/ -q` → 347+ passed, 0 failed
- [ ] `wc -l src/agent_sync/publish.py` → 0 lines (deleted) or minimal
- [ ] `wc -l src/agent_sync/skills.py` → <900 lines
- [ ] `python3 -c "from agent_sync.cli import main; print('OK')"` → OK
- [ ] `python3 -c "from agent_sync.publish import has_significant_issues; print('OK')"` → OK (if publish.py deleted, check publish/__init__.py)

---

## Open Questions

1. **publish.py deletion:** Should we verify the import chain first? `cli.py` imports from `publish.py` — need to confirm `has_significant_issues` is the only used symbol.
2. **skills.py extraction:** Is the 6-responsibility split accurate? What are the actual boundaries?
3. **Test scope for skills list TUI:** Full interaction testing (pressing keys, remove mode) requires deeper mocking. Is basic non-crash testing sufficient for now?