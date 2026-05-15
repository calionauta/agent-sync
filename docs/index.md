# agent-sync

**One tool to rule them all: Sync, Centralize, and Share AI Agent configurations and skills.**

agent-sync solves the fragmentation of the AI agent ecosystem by providing a unified workflow for your CLI tools.

## Features

- **Unified Skills Hub** - Stop duplicating skills across different agents. Centralize everything in `~/.agents/skills/`
- **Private Backup & Sync** - Keep your agent configurations safely backed up in a private GitHub repository
- **Share with the World** - Effortlessly publish your best custom skills to a public repository
- **Extension Support** - Automatically detects and backs up skills from agent extensions

## Supported Agents

| Agent | Config Files | Skills Path |
|-------|-------------|-------------|
| claude-code | `settings.json` | `~/.claude/commands/` |
| gemini-cli | `settings.json` | `~/.gemini/tools/` |
| opencode | `opencode.json` | `~/.config/opencode/skills/` |
| pi.dev | `settings.json` | `~/.pi/agent/skills/` |
| qwen-code | `settings.json` | `~/.qwen/skills/` |

## Quick Start

```bash
# Install
pipx install agent-sync

# First machine - create repo
agent-sync init
agent-sync push

# Other machines - link to existing repo
agent-sync link https://github.com/user/repo.git
agent-sync pull
```

## Protocol Support

agent-sync supports two protocols:

- **DotAgents Protocol** (default) - Vendor-neutral skills hub
- **GitAgent Protocol** (opt-in) - Comprehensive agent definitions

[Learn more about DotAgents Protocol](protocols/dotagents.md)

## License

MIT License