# Skills Lifecycle

Skills in agent-sync exist in three layers:

- **Hub** (`~/.agents/skills/`) — the source of truth
- **Private repo** (GitHub backup) — version-controlled mirror
- **Agent directories** (`~/.claude/commands/`, etc.) — deployment targets

The hub is the source of truth. `push` mirrors the hub to the repo working tree,
then `git add` + commit persists the change. There is no manifest file.

---

## Concrete Flows

### Adding a Skill

1. Place the skill directory in `~/.agents/skills/<name>/SKILL.md`
2. Run `agent-sync backup` (or `agent-sync push` if still available)
3. The skill is copied to the private repo, committed, and pushed

### Removing a Skill (Retirement)

1. Delete the skill directory from `~/.agents/skills/<name>/`
2. Run `agent-sync backup`
3. `_stage_skills` mirrors the hub to the repo — the deletion is staged
4. You see the diff (including `D` entries) plus a pre-confirmation warning
5. Press Enter to confirm
6. Commit → deletion is in `git log -D`. HEAD no longer has the skill
7. The skill is now **retired** — `_sync_from_repo` checks
   `ever_deleted - current_head` and will not re-import it.
   Stale copies in agent directories are also ignored.

### Restoring a Retired Skill (Unretirement)

1. Put the skill back in `~/.agents/skills/<name>/SKILL.md`
2. Run `agent-sync backup`
3. `_stage_skills` copies hub → repo. Skill is back in HEAD
4. `ever_deleted - current_head` empties it → NOT retired
5. `centralize` re-imports on other machines. Full backup restored.

### Pruning Orphans

`agent-sync backup --prune` does the same as a default backup, plus
`_prune_orphan_skills` runs `git rm --cached` for index edge cases.
The flag is about index cleanup, not the deletion itself.

---

## Key Implementation Details

- **Retirement detection:** `_get_retired_skill_names()` does
  `git log --all --diff-filter=D` → parses deleted paths →
  subtract `git ls-tree -d HEAD skills/`.
- **Sync safety:** `_sync_from_repo` filters by retired — never
  resurrects deleted skills.
- **Prune scope:** `_prune_orphan_skills` does NOT filter by retired.
- **Default safety:** (a) you see the complete diff before confirming,
  (b) pre-confirmation warning lists orphans, (c) `--strict` flag
  exits 2 for CI.
- **Audit output:** shows `in_sync` | `in_hub_only` | `in_repo_only`.
  No retired column — that's an implementation detail.

!!! warning
    Do **not** re-introduce a `RETIRED.md` manifest. The git-history
    approach is KISS (zero files), testable (12 integration tests),
    and avoids sync confusion across machines. Re-adding a skill to
    the hub immediately unretires it.

## Verification

```bash
# Preview prune before executing
agent-sync skills prune --dry-run

# Full audit of all skills
agent-sync skills audit

# Lifecycle of one specific skill (when added, last modified, current state)
agent-sync skills explain <name>
```
