# Quick Start

## Installation

```bash
# Recommended (isolated install)
pipx install agent-sync

# Or via pip
pip install agent-sync
```

## First Machine Setup

### 1. Create Repository

```bash
agent-sync init
```

This will:
- Create a new private GitHub repository
- Initialize git in your config directory
- Configure agent-sync settings

### 2. Back Up Your Configs

```bash
agent-sync backup
```

This backs up:
- Agent configurations (settings, AGENTS.md, etc.)
- Your skills in `~/.agents/skills/`
- Agent-specific files

## Additional Machines

### 1. Link to Repository

```bash
agent-sync link https://github.com/yourusername/your-repo.git
```

### 2. Pull Your Configs

```bash
agent-sync pull
```

Your configs are now restored on this machine.

## Daily Workflow

### Back Up Changes

```bash
agent-sync backup -m "Update my skills"
```

### Pull Changes

```bash
agent-sync pull
```

### Check Status

```bash
agent-sync status
```

## Skills Centralization

Move scattered skills to the central hub:

```bash
agent-sync skills centralize
```

Your skills will be available to all supported agents.

## Next Steps

- [CLI Reference](cli.md) - Full command documentation
- [Configuration](configuration.md) - Customize agent-sync
- [Adding Agents](agents/adding-agents.md) - Support for new agents