# CLI Reference

Complete reference for all agent-sync commands.

## Sync & Backup

### `agent-sync push`
Commit and push local changes.

Backs up global skills, configs, and custom agents automatically.

**Options:**
- `-m, --message <STRING>` — Commit message [default: chore: sync config updates]
- `--skills-only` — Push only skills (not configs)
- `--configs-only` — Push only configs (not skills)

---

### `agent-sync pull`
Fetch and apply remote configuration.

Restores global skills, configs, symlinks, and custom agents automatically.

**Options:**
- `--force` — Force pull even with local changes
- `--skills-only` — Pull only skills (not configs)
- `--configs-only` — Pull only configs (not skills)

---

### `agent-sync link`
Link to an existing sync repository (additional machines).

---

### `agent-sync status`
Show sync status and last sync times.

---

## Configuration

### `agent-sync init`
Initialize a new sync repository (first machine).

**Options:**
- `--name <STRING>` — Repository name
- `--agents <STRING>` — Agents to sync
- `--no-wizard` — Skip interactive wizard
- `--force` — Force initialization even if already configured

---

### `agent-sync setup`
Run the interactive setup wizard.

---

### `agent-sync config`
Manage configuration (view, edit, reset).

---

## Skills

### `agent-sync skills`
Manage skills in `~/.agents/skills/`.

**Subcommands:**
- `list` — Interactive skill management console
- `centralize` — Auto-import scattered skills from agents to hub

### `agent-sync skills list`
Interactive skill management with multi-select and delete.

**Features:**
- Numbered table with file count
- Multi-select: `(1-N)` toggle, `(a)` all, `(n)` none, `(d)` deselect
- Preview: `(p)` cycles through SKILL.md descriptions
- Delete: `(r)` toggles REMOVE MODE (skills shown in red), `[Enter]` confirms

**Remove mode flow:**
1. Press `(r)` to enter REMOVE MODE
2. Select skills to delete with `(1-N)`
3. Press `[Enter]` → confirmation prompt → deleted from hub + all agents

### `agent-sync skills centralize`
Auto-import scattered skills from agent directories into `~/.agents/skills/`.

Pipeline: scan agents → sync from repo → auto-import orphans → configure agents.

No interaction needed — centralizes everything automatically.

**Options:**
- `--copy` — Copy skills instead of moving (keep originals in agents)
- `--push` — Push to GitHub after centralizing
- `--dry-run` — Preview without changing anything

### `agent-sync publish`

### `agent-sync publish`
Publish skills and agents to a public GitHub repository.

**Subcommands:**
- `add <url>` — Add a publish repository (validates GitHub access)
- `list` — List all configured publish repositories
- `remove <url>` — Remove a publish repository
- `run` — Run interactive publish flow (select skills/agents)

**Examples:**
```bash
agent-sync publish add https://github.com/user/repo
agent-sync publish list
agent-sync publish remove https://github.com/user/repo
agent-sync publish run
```

**Legacy Options (use subcommands instead):**
- `--repo <URL>` — Set GitHub repository URL
- `--add-source <URL>` — Add external skill source
- `--remove-source <URL>` — Remove external skill source
- `--list-sources` — List configured sources
- `--clear-cache` — Clear cached repositories
- `--reset-selection` — Reset saved selections

---

### `agent-sync repos`
Show all configured repositories (sync + publish).

**Subcommands:**
- `list` — Display all repos with status

**Examples:**
```bash
agent-sync repos list
```

---

## Agents

---

### `agent-sync enable` / `agent-sync disable`
Enable or disable sync for a specific agent.

---

## System

### `agent-sync version`
Show version information.

### `agent-sync update`
Check for and install CLI updates.

