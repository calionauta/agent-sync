# Protocol Comparison: DotAgents vs GitAgent

> Analysis of agent-sync's alignment with the GitAgent Protocol (Open GAP)

## Executive Summary

**agent-sync** follows the **DotAgents Protocol** (`~/.agents/` hub), which is conceptually aligned with GitAgent's "repository as agent" vision but differs in scope and focus:

| Aspect | DotAgents (agent-sync) | GitAgent (Open GAP) |
|--------|----------------------|---------------------|
| **Core Focus** | Multi-agent config sync | Full agent definition + compliance |
| **Portability** | Skills hub portability | Framework-agnostic export |
| **Compliance** | Security scanner (basic) | Regulatory mapping (FINRA, SEC) |
| **Agent Files** | AGENTS.md, GEMINI.md | agent.yaml, SOUL.md, RULES.md |
| **Versioning** | Git tags on repos | Git-native agent versioning |
| **Skills** | `~/.agents/skills/` hub | `skills/` per agent repo |

---

## What agent-sync Already Follows

### 1. Repository as Agent Definition ✅
Both protocols use the git repository as the source of truth for agent configuration.

```
# DotAgents / agent-sync
~/.agents/
├── skills/
│   └── my-skill/SKILL.md
└── agents/
    └── opencode/AGENTS.md

# GitAgent
my-agent/
├── agent.yaml
├── SOUL.md
├── RULES.md
├── skills/
│   └── code-review/SKILL.md
└── agents/
    └── fact-checker/
```

### 2. Skills as Modular Units ✅
Both treat skills as reusable, composable units.

| DotAgents | GitAgent |
|-----------|----------|
| `~/.agents/skills/skill-name/SKILL.md` | `skills/skill-name/SKILL.md` |

### 3. Version Control Built-in ✅
Git history, branching, and tagging apply to agent configurations.

### 4. Agent Instruction Files ✅
| File | DotAgents | GitAgent |
|------|----------|----------|
| Framework-agnostic instructions | `AGENTS.md` | `AGENTS.md` |
| Identity/personality | — | `SOUL.md` |

### 5. Sub-agent Composition ✅
Both support hierarchical agent structures.

| DotAgents | GitAgent |
|-----------|----------|
| `~/.agents/agents/opencode/` | `agents/fact-checker/` |

---

## What's Different

### 1. Agent Manifest Format

| Aspect | DotAgents | GitAgent |
|--------|----------|----------|
| **Manifest** | Registry YAML | `agent.yaml` |
| **Required files** | None (flexible) | `agent.yaml` + `SOUL.md` |
| **Schema validation** | No | `gapman validate` |

**Gap:** agent-sync lacks a formal `agent.yaml` schema for agent metadata.

### 2. Identity & Personality

| Aspect | DotAgents | GitAgent |
|--------|----------|----------|
| **Identity doc** | ❌ Missing | ✅ `SOUL.md` |
| **Communication style** | ❌ Implicit | ✅ Defined |
| **Values/boundaries** | ❌ Implicit | ✅ `RULES.md` |

**Gap:** No structured way to define agent personality or communication style.

### 3. Compliance Model

| Aspect | DotAgents | GitAgent |
|--------|----------|----------|
| **Compliance block** | ❌ Missing | ✅ YAML mapping |
| **Regulatory fields** | ❌ Missing | ✅ FINRA, SEC, CFPB |
| **Segregation of duties** | ❌ Missing | ✅ SOD matrix |
| **Audit trail** | Basic | Full `gapman audit` |

**Gap:** No compliance mapping. Security scanner is basic (no regulatory context).

### 4. Knowledge & Memory

| Aspect | DotAgents | GitAgent |
|--------|----------|----------|
| **Knowledge base** | ❌ Not structured | ✅ `knowledge/` |
| **Memory folder** | ❌ Missing | ✅ `memory/` |
| **Runtime state** | ❌ Not supported | ✅ `runtime/` |

**Gap:** No knowledge retrieval or cross-session memory.

### 5. Tools/Tool Definitions

| Aspect | DotAgents | GitAgent |
|--------|----------|----------|
| **Tool schemas** | MCP via `mcp.json` | `tools/*.yaml` |
| **Tool registry** | Via MCP | Native |
| **Workflow definitions** | ❌ Missing | ✅ `workflows/` |

**Gap:** No native workflow definitions.

### 6. Lifecycle Hooks

| Aspect | DotAgents | GitAgent |
|--------|----------|----------|
| **Bootstrap** | ❌ Missing | ✅ `hooks/bootstrap.md` |
| **Teardown** | ❌ Missing | ✅ `hooks/teardown.md` |

**Gap:** No lifecycle event handlers.

---

## Recommendations

### High Priority (Alignment)

1. **Adopt `agent.yaml` schema**
   - Define agent metadata: name, version, model, capabilities
   - Enable `gapman`-like validation

2. **Create `SOUL.md` for identity**
   - Define communication style, values, boundaries
   - Move from implicit to explicit personality

### Medium Priority (Feature Parity)

3. **Add `RULES.md` for constraints**
   - Define must/must-never rules
   - Safety boundaries for agent behavior

4. **Add compliance block**
   - Map to DotAgents security requirements
   - Support for regulated industries

### Low Priority (Advanced)

5. **Knowledge folder structure**
   - `knowledge/` with index.yaml
   - Entity relationships for reasoning

6. **Lifecycle hooks**
   - Bootstrap/teardown scripts
   - Event-driven automation

---

## Architecture Comparison

```
┌─────────────────────────────────────────────────────────────┐
│                    DotAgents (agent-sync)                   │
├─────────────────────────────────────────────────────────────┤
│ ~/.agents/                     # Skills hub                  │
│ ├── skills/                    # Shared skills               │
│ ├── agents/                    # Agent instruction files    │
│ │   └── {agent}/AGENTS.md       # Framework instructions    │
│ └── config/                    # DotAgents config           │
├─────────────────────────────────────────────────────────────┤
│ Features:                                                │
│ ✅ Multi-agent sync                                        │
│ ✅ Security scanning                                        │
│ ✅ Skills centralization                                    │
│ ✅ Publish workflow                                         │
│ ❌ Agent manifest schema                                   │
│ ❌ Compliance mapping                                       │
│ ❌ Identity/personality docs                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  GitAgent (Open GAP)                       │
├─────────────────────────────────────────────────────────────┤
│ agent-repo/                    # Agent definition           │
│ ├── agent.yaml                 # Manifest                  │
│ ├── SOUL.md                    # Identity                  │
│ ├── RULES.md                   # Constraints               │
│ ├── DUTIES.md                  # SOD policy              │
│ ├── skills/                    # Capabilities             │
│ ├── tools/                     # MCP tool defs            │
│ ├── knowledge/                 # Reference docs           │
│ ├── memory/                    # Cross-session memory     │
│ └── hooks/                     # Lifecycle events        │
├─────────────────────────────────────────────────────────────┤
│ Features:                                                │
│ ✅ Portable definition (any framework)                    │
│ ✅ Compliance mapping (FINRA, SEC)                       │
│ ✅ Agent versioning (git tags)                             │
│ ✅ SOD segregation                                         │
│ ✅ CI/CD integration                                       │
│ ✅ Human-in-the-loop                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Conclusion

**agent-sync** (DotAgents Protocol) focuses on **configuration synchronization** across agents — keeping skills, AGENTS.md files, and configs in sync.

**GitAgent Protocol** focuses on **agent definition** — comprehensive identity, behavior, compliance, and deployment.

The protocols are **complementary, not competing**:
- Use DotAgents for multi-agent config management
- Use GitAgent for comprehensive agent definition
- Both use git as the storage layer
- Both support skills as modular units

### Potential Integration

agent-sync could adopt GitAgent's file structure for agent definitions while keeping its sync capabilities:

```
~/.agents/
├── skills/                    # Shared skills (current)
├── agents/
│   └── opencode/
│       ├── agent.yaml         # GitAgent manifest
│       ├── SOUL.md            # Identity
│       ├── RULES.md           # Constraints
│       └── skills/            # Agent-specific skills
└── config/                   # DotAgents config
```

---

*Generated: 2026-05-14*
*Protocol sources: [DotAgents](https://dotagentsprotocol.com), [GitAgent](https://github.com/open-gitagent/gitagent-protocol)*