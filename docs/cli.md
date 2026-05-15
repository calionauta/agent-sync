# CLI Reference

Complete reference for all agent-sync commands.

## Overview

agent-sync is a unified CLI tool to sync, centralize, and share AI agent configurations and skills.

## Sync & Backup

### `agent-sync push`
Commit and push local changes.

Backs up global skills, extension skills, symlinks, and custom agents automatically.

Examples:
  # Push everything (default)
  agent-sync push

  # Push only skills
  agent-sync push --skills-only

  # Push only configs
  agent-sync push --configs-only

  # Push only custom agents
  agent-sync push --agents-only

  # Push with custom message
  agent-sync push -m "feat: add new skill"


**Options:**
- `-m, --message <STRING> [default: chore: sync config updates] — Commit message`
- `--skills-only — Push only skills (not configs)`
- `--configs-only — Push only configs (not skills)`
- `--agents-only — Push only custom agents (not configs or skills)`

---

### `agent-sync pull`
Fetch and apply remote configuration.

Restores global skills, extension skills, symlinks, and custom agents automatically.

Examples:
  # Pull everything (default)
  agent-sync pull

  # Pull only skills
  agent-sync pull --skills-only

  # Pull only configs
  agent-sync pull --configs-only

  # Pull only custom agents
  agent-sync pull --agents-only

  # Force pull (overwrite local changes)
  agent-sync pull --force


**Options:**
- `--force — Force pull even with local changes`
- `--skills-only — Pull only skills (not configs)`
- `--configs-only — Pull only configs (not skills)`
- `--agents-only — Pull only custom agents (not configs or skills)`

---

### `agent-sync link`
Link to an existing sync repository (additional machines).

**Options:**
- `repo_url <STRING> [default: Sentinel.UNSET]`

---

### `agent-sync status`
Show sync status and last sync times.

---

## Configuration

### `agent-sync init`
Initialize a new sync repository (first machine).

Runs the setup wizard and creates a new GitHub repository.


Examples:
  # Interactive wizard (creates new repo)
  agent-sync init

  # Create specific repo name (non-interactive)
  agent-sync init --name agent-sync-private-configs

  # Force re-initialize (overwrites existing config)
  agent-sync init --name new-configs --force


⚠️ SECURITY:
  - Repositories are ALWAYS PRIVATE for configs
  - Configs may contain API keys and tokens
  - GitHub private repos are FREE for personal use


**Options:**
- `--name <STRING> [default: Sentinel.UNSET] — Repository name (skips wizard if provided)`
- `--agents <STRING> [default: Sentinel.UNSET] — Agents to sync (skips wizard if provided)`
- `--no-wizard — Skip interactive wizard`
- `--force — Force initialization even if already configured`

---

### `agent-sync setup`
Run the interactive setup wizard to configure or reconfigure.

This can be used:
- On first time setup
- To add/remove agents
- To change sync options
- To reconfigure repository settings


---

### `agent-sync config`
Manage configuration (view, edit, reset).

**Subcommands:**
- `show`
- `export`
- `repo`
- `edit`
- `reset`

---

### `agent-sync generate-config`
Generate initial configuration file.

**Options:**
- `--agent <STRING> [default: Sentinel.UNSET] — Specific agents to include`

---

## Skills

### `agent-sync skills`
Manage global skills.

**Subcommands:**
- `list`
- `diff`
- `reconcile`
- `delete`
- `centralize`
- `publish`

---

## Publishing

### `agent-sync publish`

Publish skills and/or agent instructions to a public GitHub repository.


Default: publishes BOTH skills and agent instructions (--all).
Use --skills or --agents to publish only one type.



Examples:
  # Publish both skills AND agent instructions (default)
  agent-sync publish

  # Publish only skills
  agent-sync publish --skills

  # Publish only agent instructions
  agent-sync publish --agents

  # Preview what would be published
  agent-sync publish --dry-run

  # Publish to a specific repository
  agent-sync publish --repo https://github.com/user/my-repo


**Options:**
- `--skills — Publish skills`
- `--agents — Publish agent instructions (AGENTS.md, GEMINI.md, etc.)`
- `--all [default: True] — Publish both skills and agent instructions (default)`
- `--dry-run — Show what would be published without actually publishing`
- `--repo <STRING> [default: Sentinel.UNSET] — GitHub repository URL`

---

## Agents

### `agent-sync agents`
List supported agents and their status.

---

### `agent-sync enable`
Enable sync for a specific agent.

**Options:**
- `agent_name <STRING> [default: Sentinel.UNSET]`

---

### `agent-sync disable`
Disable sync for a specific agent.

**Options:**
- `agent_name <STRING> [default: Sentinel.UNSET]`

---

### `agent-sync custom-agents`
Manage custom agents (.claude/agents/, .opencode/agents/).

**Subcommands:**
- `list`

---

## System

### `agent-sync update`
Check for available updates and install them.

---

### `agent-sync version`
Show version information.

---

### `agent-sync mcp`
Export unified MCP configuration.

Scans vendor MCP configs and merges them into ~/.agents/mcp.json.
Does NOT modify vendor configs — creates a unified DotAgents-compatible file.


Examples:
  # Scan and preview merge
  agent-sync mcp --dry-run

  # Export unified MCP config
  agent-sync mcp --force

  # Show only conflicts
  agent-sync mcp --conflicts

  # Add custom sources
  agent-sync mcp --force -s ~/.custom/mcp.json


**Options:**
- `--dry-run — Show merge preview without creating file`
- `--force — Overwrite existing ~/.agents/mcp.json`
- `--conflicts — Show only conflict report`
- `--source, -s <<click.types.Path object at 0x107f6c690>> [default: Sentinel.UNSET] — Additional MCP config sources`
- `--output <<click.types.Path object at 0x107f6c7d0>> — Output path`

---

### `agent-sync secrets`
Manage secrets and environment variables.

Subcommands:
  list     List all secrets/environment variables
  edit     Edit secrets in your $EDITOR
  enable   Enable secrets synchronization
  disable  Disable secrets synchronization

Note: agent-sync does not scrub secrets. Config files are synced as-is.
ALWAYS use a private repository.


**Subcommands:**
- `list`
- `edit`
- `enable`
- `disable`

---

