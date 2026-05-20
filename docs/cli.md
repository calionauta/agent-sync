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
Manage global skills.

**Subcommands:**
- `list` — List all skills in `~/.agents/skills/`
- `centralize` — Consolidate scattered skills to `~/.agents/skills/`

### `agent-sync skills centralize`
Centralize skills from all agents to `~/.agents/skills/`.

**Options:**
- `--copy` — Copy skills (keep originals in agent directories)
- `--push` — Push to GitHub after centralizing
- `--distribute` — Copy all skills to all agent directories
- `--yes` — Skip orphan skills (non-interactive)
- `--import-all` — Import all orphan skills without TUI
- `--dry-run` — Preview without changing anything

---

## Publishing

### `agent-sync publish`
Publish skills and agents to a public GitHub repository.

Run without options to select and publish interactively.

**Options:**
- `--dry-run` — Preview without publishing
- `--repo <URL>` — Set GitHub repository URL
- `--add-source <URL>` — Add external skill source
- `--remove-source <URL>` — Remove external skill source
- `--list-sources` — List configured sources
- `--clear-cache` — Clear cached repositories
- `--reset-selection` — Reset saved selections

---

## Agents

### `agent-sync agents`
List supported agents and their sync status.

---

### `agent-sync enable` / `agent-sync disable`
Enable or disable sync for a specific agent.

---

## System

### `agent-sync version`
Show version information.

### `agent-sync update`
Check for and install CLI updates.

