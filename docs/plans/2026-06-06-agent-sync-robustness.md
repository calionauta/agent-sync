# Plan: agent-sync robustness & architectural cleanup

**Date:** 2026-06-06
**Author:** pi (with user cali)
**Status:** Draft — pending user approval
**Scope:** `agent-sync` v0.35.x → next minor

## Background

The 2026-06-06 incident exposed an architectural fragility: 12 skills
(`cali-coding-*`, `cali-ops-*`, `cali-questions-quality`) were silently
pruned from `agent-sync-private` because of a multi-step bug in the
retirement-and-prune flow. The proximate cause was fixed in commit
`77d722a` (single-process fix to `_get_retired_skill_names()`), but the
underlying design has several structural issues that need a more thorough
cleanup.

### What actually went wrong (recap)

1. Skills were temporarily deleted in commit `d7dd78a` and re-added later.
2. `_get_retired_skill_names()` used `git log --all --diff-filter=D`
   without checking whether the skill was back in HEAD.
3. The hub (`~/.agents/skills/`) was missing those 12 for unrelated reasons.
4. `_prune_orphan_skills()` in `push()` saw "12 in HEAD, 0 in hub" and
   `git rm --cached` + `shutil.rmtree` them. Commit `af52bc6`.
5. Retirement still flagged them as retired → no re-import.

## Goals

1. **No silent data loss.** Destructive operations require explicit opt-in.
2. **Single source of truth for "is this skill alive?"** Stop using git
   history archaeology.
3. **Auditable retirement state.** A user can list, edit, and review what
   is considered retired without reading source code.
4. **Reduce duplicated logic.** Consolidate magic paths and filter
   predicates that currently appear in multiple files.
5. **Cover the integration, not just the unit.** Tests must exercise the
   full `centralize` → `push` → `pull` loop, not just `_get_retired_*`.

## Non-goals

- Rewriting the entire sync engine. The push/pull mechanics are not the
  problem.
- Changing the on-disk hub layout (`~/.agents/skills/`). That is a
  protocol-level commitment.
- Adding a database or external state. The git repo + manifest file is
  enough.
- Multi-user / multi-machine collaboration features. Out of scope.

## Architecture decisions

### AD-1: Retirement becomes an explicit manifest, not git history

**Decision:** Add `~/.agents/skills/RETIRED.md` (or `.retired.yaml`) as
the source of truth for retired skill names. The git history is no longer
consulted for retirement state.

**Rationale:**
- KISS: "is this skill retired?" = "is its name in this manifest?"
- Audit: user can read, edit, and commit the file with normal git tools.
- Convention over configuration: a file with one skill name per line is
  a familiar Unix convention.
- No more "deleted in a past commit, re-added later" confusion.

**Format (proposed):**
```yaml
# ~/.agents/skills/RETIRED.md or .retired.yaml
# One skill name per line. Comments start with #.
# Removed from this file to unretire.
cali-boilerplate-go      # 2026-05-01: renamed to cali-coding-go-stack
cali-codebase-spec       # 2026-05-15: merged into cali-coding-codebase-spec
cali-go-stack            # 2026-05-15: renamed
```

### AD-2: `--prune` becomes opt-in, not default

**Decision:** `agent-sync push` no longer prunes by default. Pruning
requires `agent-sync push --prune` or the dedicated
`agent-sync skills prune` subcommand with an explicit confirmation.

**Rationale:**
- The user must never lose data without warning. Prune is a destructive
  operation and should be one keystroke away, not zero.
- Most users want the safer "mirror hub → repo" semantics. Advanced users
  opt in to prune.

**Behavior change:**
| Before | After |
|--------|-------|
| `push` (default) = prune + commit + push | `push` (default) = commit + push only |
| `push --prune` (same as default) | `push --prune` = explicit destructive flag |
| n/a | `skills prune` = dry-run + interactive confirm |

### AD-3: Centralize `GLOBAL_SKILLS_DIR` constant

**Decision:** `GLOBAL_SKILLS_DIR` lives in one module
(`src/agent_sync/paths.py` or extend `config.py`). All other modules
import it from there.

**Current duplication:**
- `src/agent_sync/skills.py:25` — module constant
- `src/agent_sync/sync.py:878` — re-derived as `Path.home() / ".agents" / "skills"`
- `src/agent_sync/centralize/*` (need to audit)

### AD-4: Single "active skills" predicate

**Decision:** Replace `_get_retired_skill_names()` and
`_is_retired(skill_name)` with `_get_active_skill_names()` returning the
set of skills currently in `HEAD:skills/`. Any other check is an error.

**Rationale:** KISS. "Active" is the positive concept; "retired" was
the negation of a fuzzy historical query. One `git ls-tree` call.

### AD-5: Observability commands

**Decision:** Add three subcommands to `agent-sync skills`:

| Subcommand | Purpose |
|------------|---------|
| `skills list --retired` | Show retired skills (read manifest) |
| `skills audit` | Compare hub ↔ repo ↔ manifest; show drift |
| `skills explain <name>` | Show lifecycle of a skill: who added/modified/deleted, current state, retirement status |

**Rationale:** The user must be able to see why a skill disappeared
without reading source code.

## Phases

### Phase 1 — Manifest-based retirement (AD-1, AD-4)

**Files:**
- `src/agent_sync/skills.py` — add `_load_retired_manifest()`,
  replace `_get_retired_skill_names()` with `_get_active_skill_names()`
  backed by manifest + `git ls-tree HEAD skills/`.
- `src/agent_sync/sync.py` — update callers
  (`_find_orphans`, `_sync_from_repo`) to use new API.
- `tests/test_skills_retirement.py` — update to use temp manifest file.
- `tests/test_skills_active.py` — new: covers active vs retired split.
- `~/.agents/skills/RETIRED.md` — initial content seeded from the 75
  currently-flagged retired skills (with comments for each rename).

**Test impact:**
- Existing retirement tests need a small refactor (write manifest
  instead of relying on git history).
- Add new tests: empty manifest, malformed manifest, missing file,
  manifest in working tree but not yet committed.

**Risks:**
- The 75 currently-retired skills need to be migrated to the manifest.
  Some are renames (visible in commit history), some are old names that
  no longer exist anywhere. A migration script should classify and
  write each with a comment.

**Acceptance criteria:**
- `_get_active_skill_names()` returns the same set as current
  `_get_retired_skill_names()` would have, *given* an empty manifest,
  for the live repo at HEAD. (Property test, not exact equality.)
- User can edit `RETIRED.md` and re-run centralize to see effect.
- No call to `git log --all --diff-filter=D` remains in the codebase.

**Estimated complexity:** Medium. Touches retirement logic in 2
modules + new manifest migration utility.

---

### Phase 2 — DRY refactor (AD-3)

**Files:**
- `src/agent_sync/paths.py` — new module with `GLOBAL_SKILLS_DIR`,
  `REPO_DIR`, `MANIFEST_PATH`, `RETIRED_MANIFEST_PATH`.
- `src/agent_sync/skills.py:25` — remove local constant.
- `src/agent_sync/sync.py:878` — remove re-derivation.
- Audit `src/agent_sync/centralize/*` for the same pattern.

**Test impact:** None expected. Pure refactor.

**Risks:** Low. Pure import shuffle.

**Acceptance criteria:**
- `grep -r "Path.home() / \".agents\" / \"skills\"" src/` returns
  only `paths.py`.
- All tests still pass.

**Estimated complexity:** Small. Mechanical.

---

### Phase 3 — Prune opt-in (AD-2)

**Files:**
- `src/agent_sync/cli.py` — `push` command gains `--prune/--no-prune`
  flag (default `--no-prune`).
- `src/agent_sync/cli.py` — new `skills prune` subcommand with
  `--dry-run` and interactive confirm.
- `src/agent_sync/sync.py` — split `push()` into `commit_and_push()`
  and `prune_orphans()`. Compose in CLI.

**Test impact:**
- New `tests/test_prune_optin.py`:
  - `push` (default) does NOT delete orphan skills from repo.
  - `push --prune` does delete (with explicit assertion of count).
  - `skills prune --dry-run` does not modify anything.
  - `skills prune` without `--yes` prompts for confirmation.
- Update `tests/test_push_command.py` to expect default-no-prune.

**Risks:**
- **Behavior change.** Users with CI scripts relying on auto-prune will
  silently accumulate orphans. Mitigation: log a WARNING the first
  time a push would have pruned something, telling the user to use
  `--prune` explicitly.
- The `centralize` flow also needs a review: does it still call prune?
  If yes, the same opt-in flag should apply.

**Acceptance criteria:**
- `agent-sync push` on a divergent hub/repo does not delete anything
  from the repo.
- `agent-sync push --prune` shows exactly what will be deleted, asks
  for confirmation (or `--yes`), and only then deletes.
- A regression test simulates the 2026-06-06 incident and asserts the
  12 skills are NOT deleted.

**Estimated complexity:** Medium. Touches CLI surface area.

---

### Phase 4 — Observability commands (AD-5)

**Files:**
- `src/agent_sync/cli.py` — add `skills list --retired`, `skills audit`,
  `skills explain <name>`.
- New `src/agent_sync/skills_audit.py` — diff logic between hub, repo,
  manifest.
- New `src/agent_sync/skills_explain.py` — git log query for a skill's
  lifecycle.

**Test impact:**
- `tests/test_skills_audit.py`:
  - Hub has X, repo has X, manifest empty → `audit` says "OK".
  - Hub missing X, repo has X, manifest empty → `audit` says
    "X is in repo but not in hub; centralize would import it".
  - Hub has X, repo missing X, manifest empty → `audit` says
    "X is in hub but not in repo; push would commit it".
  - Hub has X, repo missing X, manifest has X → `audit` says
    "X is retired; do not import".
- `tests/test_skills_explain.py`:
  - `skills explain cali-coding-go-stack` returns add/modify/delete
    log entries with commit hashes and dates.

**Risks:** Low. Pure additive.

**Acceptance criteria:**
- `agent-sync skills audit` runs in <1s on the live repo.
- `agent-sync skills explain <name>` shows at minimum: first added,
  last modified, current location (hub/repo/both/neither), retirement
  status.
- Output is Rich-formatted, copy-pasteable into a bug report.

**Estimated complexity:** Medium. New CLI surface, but no behavior
change.

---

### Phase 5 — Integration test for the full loop

**Files:**
- `tests/integration/test_sync_loop.py` — new directory, new file.
- `tests/integration/conftest.py` — shared fixtures: temp home, temp
  repo, fake remote.

**Scenario coverage (one test each):**
1. Hub missing X, repo has X, manifest empty → `centralize` imports
   X to hub. `push` commits nothing new. `pull` on a fresh clone
   reproduces X. **(Regression for 2026-06-06.)**
2. Hub has X, repo missing X, manifest empty → `centralize` does
   nothing (X is in hub, the question is one-way). `push` commits X
   to repo.
3. Hub has X, repo missing X, manifest has X → `centralize` deletes
   X from hub. `push` no-op.
4. Hub empty, repo has X with SKILL.md, manifest empty → `centralize`
   Phase 2 imports X. `push` commits nothing.
5. Hub has X, repo has X, hub is locally modified, `push` → conflict
   (existing behavior, document with test).
6. `push` after hub deleted X (via `centralize` with retirement)
   → repo also loses X. **(This is the only path that should delete
   from the repo, and it is explicit.)**

**Risks:** Tests may be flaky if they depend on git or network
behavior. Mitigations: use `tmp_path` repos, fake remotes via
`git daemon` or local bare repos, deterministic timestamps.

**Acceptance criteria:**
- All 6 scenarios pass on `pytest tests/integration/`.
- Test 1 fails on the pre-Phase-1 code (regression evidence).

**Estimated complexity:** Large. Real git fixtures, real sync, real
timing concerns.

---

### Phase 6 — Documentation

**Files:**
- `docs/skills-lifecycle.md` — new: explain retire/unretire flow with
  the manifest file.
- `docs/cli.md` — update with new flags (`--prune`, `--no-prune`),
  new subcommands (`skills prune`, `skills audit`, `skills explain`).
- `README.md` — add a "Troubleshooting: a skill disappeared" section
  pointing to `skills audit` and `skills explain`.
- `AGENTS.md` — refresh tool guide, mention new commands.

**Risks:** None.

**Acceptance criteria:**
- `docs/skills-lifecycle.md` walks through: adding a skill, retiring
  a skill, unretiring a skill, recovering from a prune accident.
- All new CLI flags are documented in `docs/cli.md`.
- `README.md` has a "Skills" section that links to the lifecycle doc.

**Estimated complexity:** Small.

---

## PR breakdown

The phases have natural dependency edges:

```
Phase 1 (manifest) ─┬─► Phase 4 (observability)
                    │
Phase 2 (DRY paths)─┤
                    │
Phase 3 (prune opt-in) ─► Phase 5 (integration tests)
                                                    │
                                                    ▼
                                            Phase 6 (docs)
```

### PR 1: Retirement refactor + DRY paths

**Includes:** Phase 1 + Phase 2
**Why first:** Foundational. Other phases depend on the new active/retired
API. Pure refactor plus behavior preservation.

**Risk:** The migration of 75 currently-retired skills into the manifest
could be lossy if the migration script misclassifies.

**Rollback:** `git revert`. The git-history-based retirement is still
in git history if needed; the manifest is additive.

### PR 2: Prune opt-in + safety prompts

**Includes:** Phase 3
**Why second:** Behavior change, should land on its own for clean review.
Independent of retirement internals (only requires the new
`_get_active_skill_names()` from PR 1).

**Risk:** CI scripts that rely on auto-prune. Documented in changelog
with a migration note.

**Rollback:** Flip default back to `prune=True`. Add deprecation
warning cycle (1 minor version) before making it the final default.

### PR 3: Observability + integration tests

**Includes:** Phase 4 + Phase 5
**Why together:** Both are about *seeing* what the system is doing.
Pairing them gives reviewers a clear "we can now explain it AND prove
it works" story.

**Risk:** Integration tests may be flaky in CI. Mitigations documented
in test file headers.

**Rollback:** Subcommands are additive. Tests are additive. No rollback
needed.

### PR 4: Documentation

**Includes:** Phase 6
**Why last:** Docs describe the final state. Land after all behavior is
settled.

**Risk:** None.

---

## Rollback strategy (overall)

| PR | Rollback mechanism |
|----|--------------------|
| 1  | Revert commits. Manifest is git-tracked, so removing it falls back to "nothing retired" (safer default). |
| 2  | Flip CLI default. Keep `--no-prune` flag, just make `--prune` the default again. |
| 3  | Hide subcommands behind a feature flag if needed. Tests are CI-only. |
| 4  | Docs revert. No code impact. |

---

## Open questions for the user

1. **Manifest format.** Plain `RETIRED.md` (markdown) or
   `.retired.yaml` (structured, supports metadata like retirement date
   and reason)? YAML is more parseable; MD is more human-friendly.
   **My recommendation:** YAML. It's machine-parseable for tooling
   like `skills audit` and `skills explain`, and YAML comments are
   just as readable.

2. **Default for `--prune`.** Should the default be `--no-prune` (safe)
   or `--prune` (legacy) with a one-version deprecation cycle? **My
   recommendation:** `--no-prune` immediately, with a loud warning
   log when push would have pruned something. Avoid silent accumulation
   of orphans by warning prominently.

3. **Where to put the manifest in the repo.** Two options:
   - `skills/RETIRED.md` (inside the skills/ tree, gets committed and
     pushed) — single source of truth across machines.
   - `~/.agents/skills/RETIRED.md` (local to the hub, not in repo) —
     per-machine state.
   **My recommendation:** In the repo. Skills are shared across
   machines; retirement is a property of the skill, not the install.

4. **Integration test runtime.** The new test suite will involve real
   git operations and may take 10-30s. Acceptable for CI? **My
   recommendation:** Yes, but mark them with `@pytest.mark.integration`
   so they can be skipped locally with `-m "not integration"`.

5. **Should the 12 restored skills get an entry in the manifest
   "already retired" list?** They are alive in HEAD and in the hub
   after the restore. **My recommendation:** No. They should not
   appear in the manifest. The manifest is for skills that are
   *intentionally* retired, not for ones that were accidentally
   pruned and restored.

---

## Definition of done

- [ ] All 6 phases merged.
- [ ] `pytest tests/` green.
- [ ] `pytest tests/integration/` green.
- [ ] `agent-sync skills audit` shows the live hub and repo in sync.
- [ ] `agent-sync skills explain cali-coding-go-stack` shows full
      lifecycle.
- [ ] `agent-sync push` (default) does not delete anything from
      the repo even if hub is missing skills.
- [ ] User can retire a skill by adding its name to
      `skills/RETIRED.md` and committing.
- [ ] User can unretire by removing the name from
      `skills/RETIRED.md` and committing.
- [ ] A regression test simulates the 2026-06-06 incident and
      passes.
- [ ] Documentation updated: `docs/skills-lifecycle.md`,
      `docs/cli.md`, `README.md`, `AGENTS.md`.

---

## Estimated effort

| Phase | Effort | Calendar (with review) |
|-------|--------|-------------------------|
| 1 | 2-3 days | 1 week |
| 2 | 0.5 day | same week |
| 3 | 1-2 days | 1 week |
| 4 | 2 days | 0.5 week |
| 5 | 2-3 days | 1 week |
| 6 | 1 day | same week as 4-5 |

**Total: ~2-3 weeks calendar time, 8-12 days focused work.**

---

## Approval

- [ ] User approves plan as-is
- [ ] User approves with modifications: ___
- [ ] User defers to a later date

Once approved, this plan becomes the source of truth and individual
phases are tracked in the GitHub issue tracker.
