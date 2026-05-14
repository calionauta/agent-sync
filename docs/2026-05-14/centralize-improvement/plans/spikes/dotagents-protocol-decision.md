# DotAgents Protocol Analysis

## Protocol Spec (https://dotagentsprotocol.com/)

### Core Concepts
- **Directory**: `.agents/` at global (`~/.agents/`) and workspace (`./.agents/`) levels
- **Merge**: Workspace overrides global (shallow-merge by key, merge by ID for skills/agents)
- **Formats**: Frontmatter + markdown for content, plain JSON for config (no YAML dependency)
- **Components**: MCP, AGENTS.md, Skills, Sub-Agents, Tasks, Memories, model config
- **Design**: Vendor-neutral, git-friendly, layered

### Directory Structure
```
~/.agents/              # Global (canonical config)
  skills/               # Skills directory
  agents/               # Sub-agent definitions
  mcp.json              # MCP server config
  memories/             # Agent memories
  tasks/                # Repeat tasks
  config.json           # Model and agent defaults

<project>/.agents/      # Workspace overrides
  skills/
  agents/
  mcp.json
```

## Current agent-sync Registry vs Protocol

| Aspect | DotAgents Protocol | agent-sync Current | Gap |
|--------|-------------------|-------------------|-----|
| Global dir | `~/.agents/` | `~/.agents/skills/` (skills only) | ✅ Compatible (skills is subset) |
| Config format | JSON (plain) | YAML | ⚠️ agent-sync uses YAML, protocol prefers JSON |
| Agent configs | Per-agent in `config.json` | `agent_registry.yaml` per agent | ⚠️ Different approach |
| Skills | `~/.agents/skills/<name>/SKILL.md` | Same format | ✅ Aligned |
| Sub-agents | `~/.agents/agents/` with frontmatter | `~/.claude/agents/`, etc. per vendor | ⚠️ Vendor-specific paths |
| MCP config | `~/.agents/mcp.json` | Not tracked as single file | 📝 Could add |
| Tasks | `~/.agents/tasks/` | Not supported | 📝 Future |
| Memories | `~/.agents/memories/` | Not supported | 📝 Future |
| Vendor-neutral | Yes | Yes (multiple agents) | ✅ |
| Git-friendly | Yes | Yes (via repo) | ✅ |
| Overlay (workspace) | `./.agents/` overrides `~/.agents/` | Not supported | ⚠️ Missing |

## Changes Made

### agent_registry.yaml
- No structural changes needed — the registry already follows the vendor-neutral spirit
- Added comments mapping each agent to DotAgents conventions where applicable
- The `method` field (native/config/copy) aligns with the protocol's flexible approach

### Next Steps (Future)
1. Support `./.agents/` workspace-level sync (overlay semantics)
2. Add `mcp.json` merging from multiple agents into unified `~/.agents/mcp.json`
3. Consider JSON config option alongside YAML for protocol alignment
4. Document `.agents/` structure in README as recommended layout
