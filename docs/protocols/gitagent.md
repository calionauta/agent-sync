# GitAgent Protocol (Open GAP)

> agent-sync supports GitAgent Protocol files for comprehensive agent backup (opt-in).

## Overview

The **GitAgent Protocol** (Open GAP) is a git-native, framework-agnostic standard for defining AI agents. It provides version-controlled agent definitions with compliance support.

**Important:** agent-sync is NOT an implementation of GitAgent Protocol. It is a **backup tool** that can include GitAgent files in its backup targets.

## Structure

```
agent-repository/
├── agent.yaml              # Agent manifest (name, version, model)
├── SOUL.md                # Identity and personality
├── RULES.md               # Hard constraints and boundaries
├── DUTIES.md              # Segregation of duties policy
├── AGENTS.md              # Framework-agnostic fallback instructions
├── INSTRUCTIONS.md         # Additional instructions
├── skills/                # Reusable capability modules
│   └── code-review/
│       └── SKILL.md
├── tools/                 # MCP-compatible tool definitions
├── knowledge/             # Reference documents
├── memory/                 # Cross-session memory
│   └── runtime/
├── workflows/             # Multi-step procedures (SkillsFlow)
├── hooks/                  # Lifecycle event handlers
│   ├── bootstrap.md
│   └── teardown.md
└── compliance/            # Regulatory compliance artifacts
```

## How agent-sync Uses GitAgent

agent-sync can back up GitAgent files if you enable it:

```yaml
# ~/.config/agent-sync/config.yaml
protocols:
  gitagent:
    enabled: true
    patterns:
      - "agent.yaml"
      - "SOUL.md"
      - "RULES.md"
      - "DUTIES.md"
      - "skills/"
      - "knowledge/"
      - "memory/"
```

## Core Files

| File | Purpose | Required |
|------|---------|---------|
| `agent.yaml` | Agent manifest with model, version, skills | Yes |
| `SOUL.md` | Identity, personality, values | Yes |
| `RULES.md` | Hard constraints, boundaries | Recommended |
| `DUTIES.md` | Segregation of duties policy | Optional |

## Benefits

| Benefit | Description |
|---------|-------------|
| **Git-native** | Version control, branching, diffing built in |
| **Framework-agnostic** | Export to Claude Code, OpenAI, CrewAI, etc. |
| **Compliance-ready** | FINRA, SEC, CFPB support out of the box |
| **SkillsFlow** | Deterministic multi-step workflows via YAML |

## Comparison with DotAgents

| Aspect | DotAgents | GitAgent |
|--------|-----------|----------|
| **Focus** | Skills hub + config sync | Full agent definition |
| **Complexity** | Simple, focused | Comprehensive |
| **Compliance** | None | Built-in regulatory support |
| **Skills** | SKILL.md format | SKILL.md + workflows |
| **Identity** | AGENTS.md | SOUL.md + RULES.md |

## Resources

- [GitAgent Protocol](https://gitagent.sh/)
- [GitHub Repository](https://github.com/open-gitagent/gitagent-protocol)
- [GapMan CLI](https://www.npmjs.com/package/@open-gitagent/gapman)