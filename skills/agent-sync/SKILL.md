---
name: agent-sync
description: Sync AI agent configurations and skills across machines and agents. Requires agent-sync CLI installed separately. Use when managing multiple AI agents or setting up agent configurations on a new machine.
---

# Agent Sync

Centralize and synchronize your AI agent configurations and skills across multiple machines and agents.

## Prerequisites

**This skill requires the agent-sync CLI to be installed:**

```bash
# Install CLI first (required)
pipx install agent-sync
# or
pip install agent-sync

# Then install this skill (for AI agents)
npx skills add renatocaliari/agent-sync -g
```

## When to Use

Use agent-sync when:
- Setting up agent configurations on a new machine
- Centralizing skills from multiple agents into one location
- Syncing configs between machines via GitHub
- Managing skills across opencode, claude-code, gemini-cli, pi.dev, or qwen-code

## Quick Start

```bash
# First machine
agent-sync setup    # Interactive wizard
agent-sync push     # Sync to GitHub

# Other machines
agent-sync link <repo-url>
agent-sync pull
```

## Core Commands

### Setup & Sync
- `agent-sync setup` - Interactive setup wizard (asks to push after)
- `agent-sync push` - Upload changes to GitHub
- `agent-sync pull` - Download changes from GitHub
- `agent-sync link <url>` - Connect to existing repository

### Skills Management
- `agent-sync skills list` - List all centralized skills
- `agent-sync skills centralize` - Move skills to `~/.agents/skills/`
  - `--copy` - Copy instead of move
  - `--push` - Auto-push to GitHub after centralizing

### Configuration
- `agent-sync config show` - View current configuration
- `agent-sync config edit` - Edit configuration manually
- `agent-sync config reset` - Reset to defaults
- `agent-sync agents` - List agents and status

### Secrets
- `agent-sync secrets` - View secrets sync status (enabled/disabled)

## Skills Flow

```
1. Centralize (first time)
   ~/.config/opencode/skills/ ──┐
   ~/.claude/commands/          │
   ~/.gemini/tools/             ├──► ~/.agents/skills/
   ~/.pi/agent/skills/          │    (source of truth)
   ~/.qwen/skills/              ──┘
   
   → Moves all skills to central location
   → Removes user symlinks from agent directories
   → Creates fallback symlinks only when needed

2. Configure agents (automatic)
   Opencode:    config update
   Qwen Code:   copy method
   Pi.dev:      native support
   Claude Code: copy method
   Gemini CLI:  copy method

3. Sync to GitHub
   ~/.agents/skills/ ──push──► GitHub ──pull──► Other machines
```

## Installation

### Recommended (Global)
```bash
npx skills add renatocaliari/agent-sync -g
```

### Alternative
```bash
pipx install agent-sync
# or
pip install agent-sync
```

### Verify
```bash
agent-sync --version
# If not found: export PATH="$HOME/.local/bin:$PATH"
```

## Common Workflows

### New Machine Setup
```bash
# 1. Install
pipx install agent-sync

# 2. Link to your repo
agent-sync link https://github.com/username/agent-sync-configs.git

# 3. Pull configs
agent-sync pull
```

### Centralize Existing Skills
```bash
# Move all skills from agent directories to central location
agent-sync skills centralize

# Review what will be pushed
agent-sync skills list

# Push to GitHub
agent-sync push
```

### Add New Agent
```bash
# Enable agent sync
agent-sync enable gemini-cli

# Push configuration
agent-sync push -m "feat: add gemini-cli sync"
```

## Security

- **Private repository required** for configs with secrets
- **Secrets sync disabled by default** (secure by design)
- **Auth files excluded** (`*auth*.json`, `*accounts*.json`)

## Supported Agents

| Agent | Config Files | Skills Path | Method |
|-------|-------------|-------------|--------|
| opencode | `opencode.json`, `opencode.jsonc` | `~/.config/opencode/skills/` | Config |
| claude-code | `settings.json`, `claude.json` | `~/.claude/commands/` | Copy |
| gemini-cli | `settings.json` | `~/.gemini/tools/` | Copy |
| pi.dev | `settings.json`, `models.json`, `*.yaml` | `~/.pi/agent/skills/` | Native |
| qwen-code | `settings.json` | `~/.qwen/skills/` | Copy |

## Troubleshooting

### Command not found
```bash
# Add to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Skills not detected
```bash
# List centralized skills
agent-sync skills list

# Re-centralize if needed
agent-sync skills centralize
```

### Config not found
```bash
# Show current config
agent-sync config show

# Reconfigure
agent-sync setup
```

## Learn More

- GitHub: https://github.com/renatocaliari/agent-sync
- Docs: `docs/` folder in repository
