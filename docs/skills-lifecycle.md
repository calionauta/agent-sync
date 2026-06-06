# Skills Lifecycle

How skills flow through their lifecycle in `agent-sync`: from creation,
to retirement, to recovery.

## States

A skill can be in one of these states at any time:

| State | In `~/.agents/skills/`? | In private repo? | In `RETIRED.md`? |
|-------|------------------------|------------------|------------------|
| **active** | yes | yes | no |
| **new (in hub only)** | yes | no | no |
| **orphan (in repo only)** | no | yes | no |
| **retired (in repo + manifest)** | no | yes | yes |
| **retired (clean)** | no | no | yes |
| **conflict (in hub + manifest)** | yes | no | yes |
| **conflict (everywhere + manifest)** | yes | yes | yes |

See `agent-sync skills audit` for a live view.

## The Manifest

`~/.agents/skills/RETIRED.md` is the single source of truth for retirement.
It's a plain text file, one skill per line, with `#` for comments:

```markdown
# Retired Skills
#
# Skills listed here are intentionally retired. They will NOT be
# imported to the hub by `agent-sync skills centralize` and will
# be excluded from `agent-sync push --prune`.
#
# To unretire a skill: delete its line below, save, and re-run
# `agent-sync skills centralize`.
#
# Format: one skill name per line. Lines starting with `#` are
# comments. Trailing text after the skill name is also a comment
# (use it for the reason and date of retirement).

cali-boilerplate-go    # renamed to cali-coding-go-stack  2026-05-01
cali-codebase-spec     # renamed to cali-coding-codebase-spec  2026-05-15
```

**The hub's `RETIRED.md` is authoritative.** The repo's `RETIRED.md`
(if committed) is a mirror; it does not override the hub. If the hub
has no `RETIRED.md`, no skill is retired.

## Workflows

### Retiring a skill

```bash
# 1. Edit the manifest
echo "cali-old-skill   # replaced by cali-new-skill  $(date -I)" \
    >> ~/.agents/skills/RETIRED.md

# 2. Remove from hub (if present)
rm -rf ~/.agents/skills/cali-old-skill

# 3. Push to keep repo in sync (the manifest will be pushed too)
agent-sync push

# 4. Verify with audit
agent-sync skills audit | grep cali-old-skill
# cali-old-skill    ·    ✓      ✓       retired (in repo)
```

### Unretiring a skill

```bash
# 1. Edit the manifest, removing the line
sed -i '' '/^cali-old-skill/d' ~/.agents/skills/RETIRED.md

# 2. Re-import to hub
agent-sync skills centralize

# 3. Verify
agent-sync skills audit | grep cali-old-skill
# cali-old-skill    ✓    ✓      ·       in sync
```

### Recovering from accidental prune

If a skill was deleted from the repo by accident (e.g. the previous
git-history-based retirement bug, see 2026-06-06 incident):

```bash
# 1. Find the deletion commit in the repo
git log --diff-filter=D --name-only --pretty=format: -- 'skills/cali-skill/'

# 2. Restore the skill from history
git checkout <commit-hash>^ -- skills/cali-skill/

# 3. Stage and commit the restoration
cd ~/Library/Application\ Support/agent-sync/repo
git add skills/cali-skill/
git commit -m "fix: restore cali-skill after accidental prune"

# 4. Push
git push origin main

# 5. The skill will appear in `agent-sync skills audit` as "in sync"
```

### Investigating "where did this skill go?"

```bash
# Show full lifecycle of a skill
agent-sync skills explain cali-coding-go-stack
```

Output includes:
- Current state across hub / repo / manifest
- When it was first added (commit + date)
- When it was last modified (commit + date)
- Total commits affecting it
- File count in the local hub
- Raw manifest line (if retired)

## Push behavior (since v0.35)

The `push` command is **safe by default**:

| Command | Behavior |
|---------|----------|
| `agent-sync push` | Commits and pushes. Orphan skills in the repo STAY there. |
| `agent-sync push --prune` | Also removes orphan skills from the repo. |
| `agent-sync skills prune` | Dedicated subcommand with `--dry-run` and `--yes`. |
| `agent-sync skills prune --dry-run` | Preview only. |

If `push` (default) detects orphan skills, it logs a yellow warning
listing them and suggesting the right cleanup command.

## Manifest vs git history

**Before v0.35:** Retirement was derived from `git log --diff-filter=D`,
treating any historical deletion as permanent. This caused the
2026-06-06 incident where 12 skills were silently pruned.

**Since v0.35:** Retirement is declared in `~/.agents/skills/RETIRED.md`.
No more git archaeology. A skill that exists in the repo HEAD and is
not in the manifest is *active*, regardless of past deletions.

## See also

- [CLI Reference](cli.md) — full command documentation
- [Configuration](configuration.md) — config file options
- [Troubleshooting in README](../README.md#troubleshooting)
