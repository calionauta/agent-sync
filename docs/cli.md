# CLI Reference

Complete reference for all agent-sync commands.

## Overview

agent-sync is a unified CLI tool to sync, centralize, and share AI agent configurations and skills.

## Sync & Backup

### `agent-sync init`
Initialize agent-sync in the current directory.

**Options:**
- `--name <STRING> [default: Sentinel.UNSET] — Repository name`
- `--agents <STRING> [default: Sentinel.UNSET] — Agents to sync`
- `--no-wizard — Skip interactive prompts`
- `--force — Force overwrite existing config`

---

### `agent-sync backup`
Backup all configs, skills, and agents to the private repository.

This sends everything (configs, skills, agents) to the private GitHub repo
as a full backup. Configs may contain API keys and secrets, so this is
NOT published to public repos.

For sharing individual skills to public repos, use 'agent-sync share'.

Examples:
  agent-sync backup                     # Full backup (default)
  agent-sync backup --skill dogfood     # Specific skill
  agent-sync backup --dry-run           # Preview
  agent-sync backup --prune             # Remove remote orphans too


**Options:**
- `--dry-run — Show what would be backed up without backing up`
- `--message, -m <STRING> — Commit message`
- `--skills-only — Only back up skills`
- `--configs-only — Only back up configs`
- `--skill, -s <STRING> [default: Sentinel.UNSET] — Specific skill to back up (can repeat)`
- `--agent, -a <STRING> [default: Sentinel.UNSET] — Specific agent config to back up (can repeat)`
- `--exclude-skill <STRING> [default: Sentinel.UNSET] — Skill to exclude (can repeat)`
- `--exclude-agent <STRING> [default: Sentinel.UNSET] — Agent to exclude (can repeat)`
- `--prune — Remove orphan skills from the remote repo (in HEAD but not in local hub). Default: kept additively.`
- `--strict — Exit with code 2 if orphan skills were detected (for CI/scripts).`

---

### `agent-sync pull`
Pull changes from the remote repository.

Default behavior is additive (no local skill is deleted). Local skills
that are missing from the private repo are always shown in the preview
so you can see the cleanup opportunity. Pass --prune to actually
remove them (mirror-pull, makes local a mirror of private).

Examples:
  agent-sync pull                    # Pull all (additive, safe)
  agent-sync pull --skill cali-product-workflow   # Specific skill
  agent-sync pull --agent pi.dev     # Specific agent config
  agent-sync pull --exclude-skill deprecated-skill # Exclude skill
  agent-sync pull --dry-run          # Preview changes
  agent-sync pull --prune            # Mirror: also remove local orphans


**Options:**
- `--force — Apply all remote (no confirmation)`
- `--dry-run — Show what would change`
- `--interactive [default: True] — Interactive conflict resolution`
- `--skills-only — Only pull skills`
- `--configs-only — Only pull configs`
- `--skill, -s <STRING> [default: Sentinel.UNSET] — Specific skill to pull (can repeat)`
- `--agent, -a <STRING> [default: Sentinel.UNSET] — Specific agent config to pull (can repeat)`
- `--exclude-skill <STRING> [default: Sentinel.UNSET] — Skill to exclude (can repeat)`
- `--exclude-agent <STRING> [default: Sentinel.UNSET] — Agent to exclude (can repeat)`
- `--prune — Remove local skills that are missing from the private repo (mirror-pull). Default: preview only.`

---

### `agent-sync status`
Show sync status.

---

### `agent-sync diff`
Show differences between local and remote.

**Options:**
- `--skills — Show skills diff`
- `--configs — Show configs diff`

---

### `agent-sync sync`
Sync skills and configs with the remote repository.

**Options:**
- `--force — Force pull even if up to date`
- `--skills-only — Only sync skills`
- `--configs-only — Only sync configs`
- `--agents-only — Only sync agent configs`

---

## Repositories

### `agent-sync repos`
Manage repositories (sync, publish, and sources).

Subcommands:
  list     Show all target repositories (sync + publish)
  target   Configure sync and publish targets
  source   Manage skill sources (external repos to import from)

Examples:
  agent-sync repos list
  agent-sync repos target private https://github.com/user/private.git
  agent-sync repos source add https://github.com/user/skills


**Subcommands:**
- `list`
- `target`
- `source`

---

## Share

### `agent-sync share`
Publish skills and agents to a public repository.

Commands:
  add <url>     Add a public repository
  list          List all configured repositories
  remove <url>  Remove a repository
  run           Run interactive publish flow (TUI)

Examples:
  agent-sync share add https://github.com/user/repo
  agent-sync share list
  agent-sync share remove https://github.com/user/repo
  agent-sync share run



**Subcommands:**
- `add`
- `list`
- `remove`
- `run`

---

## Configuration

### `agent-sync config`
Manage configuration (view, edit, reset).

**Subcommands:**
- `show`
- `repo`
- `edit`
- `reset`

---

### `agent-sync generate-config`
Generate configuration files for agents.

**Options:**
- `--agent, -a <STRING> [default: Sentinel.UNSET] — Agents to generate config for`

---

## Skills

### `agent-sync skills`
Manage skills.

**Subcommands:**
- `list`
- `audit`
- `explain`
- `prune`
- `centralize`

---

## Agents

### `agent-sync agents`
Manage agent configurations.

**Subcommands:**
- `list`

---

### `agent-sync enable`
Enable an agent for syncing.

**Options:**
- `agent_name <STRING> [default: Sentinel.UNSET]`

---

### `agent-sync disable`
Disable an agent from syncing.

**Options:**
- `agent_name <STRING> [default: Sentinel.UNSET]`

---

### `agent-sync export`
Export agent config to JSON format.

**Options:**
- `--output <<click.types.Path object at 0x10a071e80>> — Output path`

---

## System

### `agent-sync secrets`
Manage secrets and environment variables.

Note: agent-sync does not scrub secrets. Config files are synced as-is.
ALWAYS use a private repository.


**Subcommands:**
- `list`
- `edit`
- `enable`
- `disable`

---

### `agent-sync mcp`
Export unified MCP configuration.


Scans vendor MCP configs and merges them into ~/.agents/mcp.json.
Does NOT modify vendor configs - creates a unified DotAgents-compatible file.



**Options:**
- `--dry-run — Show merge preview without creating file`
- `--force — Overwrite existing ~/.agents/mcp.json`
- `--conflicts — Show only conflict report`
- `--source, -s <<click.types.Path object at 0x10a0e2e90>> [default: Sentinel.UNSET] — Additional MCP config sources`
- `--output <<click.types.Path object at 0x10a0e2fd0>> — Output path`

---

### `agent-sync update`
Update agent-sync to the latest version.

Shows before/after version to confirm the upgrade worked.


**Options:**
- `--check — Check for updates only`

---

### `agent-sync version`
Show version information.

---

