# GitAgent Protocol (Open GAP)

> agent-sync supports GitAgent Protocol files for comprehensive agent backup.

## Overview

The **GitAgent Protocol** (Open GAP) is a framework-agnostic, git-native standard for defining AI agents. It provides comprehensive agent definitions including identity, personality, compliance, and more.

**Important:** agent-sync is NOT an implementation of GitAgent Protocol. It is a **backup and sync tool** that can include GitAgent files in its backup targets.

## GitAgent File Structure

```
agent-repo/
├── agent.yaml              # Agent manifest (name, version, model)
├── SOUL.md                 # Identity and personality
├── RULES.md                # Hard constraints and boundaries
├── DUTIES.md               # Segregation of duties policy
├── AGENTS.md               # Framework-agnostic fallback instructions
├── skills/                 # Reusable capability modules
├── tools/                  # MCP-compatible tool definitions
├── knowledge/              # Reference documents
├── memory/                 # Cross-session memory
├── workflows/              # Multi-step procedures
├── hooks/                  # Lifecycle event handlers
└── compliance/             # Regulatory compliance artifacts
```

## GitAgent vs DotAgents

| Aspect | DotAgents | GitAgent |
|--------|-----------|----------|
| **Purpose** | Skills hub + config sync | Full agent definition |
| **Complexity** | Simple, focused | Comprehensive |
| **Compliance** | None | FINRA, SEC, CFPB mapping |
| **Required Files** | SKILL.md | agent.yaml + SOUL.md |

## What agent-sync Backs Up

agent-sync currently backs up:

| GitAgent File | Supported? |
|--------------|-----------|
| `AGENTS.md` | ✅ Yes |
| `GEMINI.md` | ✅ Yes |
| `agent.yaml` | ❌ Not yet |
| `SOUL.md` | ❌ Not yet |
| `RULES.md` | ❌ Not yet |
| `DUTIES.md` | ❌ Not yet |
| `knowledge/` | ❌ Not yet |
| `memory/` | ❌ Not yet |

## Future: GitAgent Support

If you use GitAgent Protocol and want agent-sync to back up those files:

```yaml
# ~/.config/agent-sync/config.yaml (future)
gitagent:
  sync_enabled: true
  manifest_path: "~/.pi/agent/agent.yaml"
```

## Resources

- [GitAgent Protocol](https://github.com/open-gitagent/gitagent-protocol)
- [Specification](https://github.com/open-gitagent/gitagent-protocol/blob/main/spec/SPECIFICATION.md)
- [GapMan CLI](https://www.npmjs.com/package/@open-gitagent/gapman)