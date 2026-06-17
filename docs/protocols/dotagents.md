# DotAgents Protocol

> agent-sync supports DotAgents Protocol for vendor-neutral skills management.

## Overview

The **DotAgents Protocol** (`~/.agents/`) provides a vendor-neutral, git-friendly convention for storing and sharing AI agent configurations and skills.

## Structure

```
~/.agents/
├── skills/                        # Shared skills directory
│   ├── skill-name/
│   │   └── SKILL.md               # Skill definition
│   └── another-skill/
│       └── SKILL.md
└── (agents-specific files)
```

## How agent-sync Uses DotAgents

agent-sync uses `~/.agents/skills/` as the central hub:

```bash
# Move scattered skills to hub
agent-sync skills centralize

# Back up to private repo
agent-sync backup

# Pull on new machine
agent-sync pull
```

## Benefits

| Benefit | Description |
|---------|-------------|
| **One source of truth** | Skills live in `~/.agents/skills/` - not duplicated |
| **Cross-agent sharing** | Skills work with Claude, Gemini, Opencode, etc. |
| **Git-friendly** | Version-controlled and synced via agent-sync |
| **Composable** | Agents reference shared skills without copying |

## Resources

- [DotAgents Protocol](https://dotagentsprotocol.com/)
- [Agent Skills Standard](https://agentskills.io)