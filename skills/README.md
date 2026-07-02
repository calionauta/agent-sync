# Skills for AI Agent CLIs

These skills enable `agent-sync` to be used **inside** AI agent CLIs.

## Installation

```bash
# Install the skill (documentation for AI agents)
npx skills add calionauta/agent-sync -g
```

**Note:** This installs the skill documentation only. You still need to install the CLI separately:

```bash
# Install CLI tool (required)
pipx install git+https://github.com/calionauta/agent-sync.git
```

## What It Does

Once installed, AI agents like Claude Code, Opencode, and Gemini CLI can:
- Understand `agent-sync` commands
- Help you sync configurations
- Assist with skills management
- Guide you through setup

## Usage

Inside your AI agent CLI:

```
/agent-sync setup
/agent-sync push
/agent-sync pull
```

Or via shell command:

```bash
agent-sync setup
agent-sync push
agent-sync pull
```

## Supported Agents

- ✅ Claude Code
- ✅ Opencode
- ✅ Gemini CLI
- ✅ Pi.dev
- ✅ Qwen Code
- ✅ Any agent that supports npx skills

## Learn More

- Main repository: https://github.com/calionauta/agent-sync
- Documentation: See `/docs/` folder in repository
