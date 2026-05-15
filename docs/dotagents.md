# DotAgents Protocol

> agent-sync follows the DotAgents Protocol for skills hub management.

## Overview

The **DotAgents Protocol** (`~/.agents/`) is a vendor-neutral, git-friendly convention for storing and sharing AI agent configurations and skills. It was created to solve the problem of skills being locked to specific agents/frameworks.

## Structure

```
~/.agents/                          # Root of DotAgents hub
├── skills/                        # Shared skills directory
│   ├── skill-name/               # Individual skill
│   │   └── SKILL.md               # Skill definition (Agent Skills standard)
│   └── another-skill/
│       └── SKILL.md
├── agents/                        # Agent instruction files
│   ├── opencode/AGENTS.md         # Opencode instructions
│   ├── pi.dev/AGENTS.md          # Pi agent instructions
│   └── custom-agent/SOUL.md       # (future) Agent identity
└── config/                        # DotAgents configuration
    └── manifest.yaml              # (future) Agent manifest
```

## Key Principles

1. **Single Source of Truth**: Skills live in `~/.agents/skills/` — not duplicated across agents
2. **Vendor-Neutral**: Skills use the Agent Skills standard (SKILL.md format) — works across all agents
3. **Git-Friendly**: The `~/.agents/` directory is version-controlled and synced via agent-sync
4. **Composable**: Agents can reference shared skills without copying them

## Comparison with GitAgent Protocol

| Aspect | DotAgents | GitAgent |
|--------|-----------|----------|
| **Focus** | Skills hub + config sync | Full agent definition + compliance |
| **Required Files** | SKILL.md (for skills) | agent.yaml + SOUL.md |
| **Compliance** | None (focus on sync) | FINRA, SEC, CFPB mapping |
| **Agent Identity** | AGENTS.md (framework instructions) | SOUL.md + RULES.md |
| **Interop** | Skills work across agents | Portable to any framework |

## How agent-sync Uses DotAgents

agent-sync uses `~/.agents/skills/` as the central hub:

```bash
# Centralize skills from all agents
agent-sync skills centralize

# Push to GitHub for backup
agent-sync push

# Pull on new machine
agent-sync pull
```

### Skills Discovery

When an agent requests skills, agent-sync looks in order:

1. `~/.agents/skills/<skill-name>/SKILL.md` (global hub)
2. Agent-specific skills directories (for local-only skills)

## Related: GitAgent Protocol

The **GitAgent Protocol** is a more comprehensive standard for defining agents with:
- Identity/personality (SOUL.md)
- Hard constraints (RULES.md)
- Compliance mapping (FINRA, SEC)
- Knowledge base (knowledge/)
- Cross-session memory (memory/)

If you use GitAgent Protocol, agent-sync can still back up your agent definitions:

```yaml
# In agent-sync config (future feature)
gitagent:
  sync_gitagent_files: true
  patterns:
    - "agent.yaml"
    - "SOUL.md"
    - "RULES.md"
```

## Resources

- [DotAgents Protocol Specification](https://dotagentsprotocol.com/)
- [Agent Skills Standard](https://agentskills.io)
- [GitAgent Protocol](https://github.com/open-gitagent/gitagent-protocol) (complementary)