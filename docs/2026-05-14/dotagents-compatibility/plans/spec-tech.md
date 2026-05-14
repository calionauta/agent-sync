# Plan: DotAgents Compatibility Features

## Context

agent-sync follows the DotAgents Protocol for skills (`~/.agents/skills/`), but uses proprietary formats for agent registry (YAML) and doesn't generate a DotAgents-compatible `config.json`. This plan adds optional compatibility layers without changing the core architecture.

## What We're Building

| Feature | Type | DotAgents Aspect |
|---------|------|-----------------|
| JSON config export | **feature** | `~/.agents/config.json` generation |
| MCP unified export | **feature** | `~/.agents/mcp.json` merge command |

## Scope 1: JSON Config Export

### Problem
DotAgents expects `~/.agents/config.json` for model/agent defaults. agent-sync uses `agent_registry.yaml` internally, which is not DotAgents-compatible.

### Solution
Add `agent-sync config export` command that generates `~/.agents/config.json` from our registry. Does NOT replace our internal YAML — just creates an optional compatibility layer.

### Commands

```bash
# Export current registry to DotAgents JSON format
agent-sync config export

# Dry-run preview
agent-sync config export --dry-run

# Specify output path
agent-sync config export --output /custom/path/config.json
```

### Output Format (`~/.agents/config.json`)

```json
{
  "version": "1.0",
  "generated_by": "agent-sync",
  "skills_hub": "~/.agents/skills",
  "model": {
    "default": "claude-sonnet-4",
    "fallback": "claude-haiku-4"
  },
  "agents": {
    "claude-code": {
      "enabled": true,
      "method": "copy",
      "skills_dir": "~/.claude/commands/"
    },
    "pi.dev": {
      "enabled": true,
      "method": "native",
      "skills_dir": "~/.pi/agent/skills/"
    }
  },
  "sync": {
    "method": "git",
    "repo_url": "https://github.com/user/agent-sync-config"
  }
}
```

### Implementation

| Step | Task | File |
|------|------|------|
| 1 | Create `ConfigExporter` class | `src/agent_sync/config_exporter.py` |
| 2 | Add `config export` CLI command | `src/agent_sync/cli.py` |
| 3 | Add `--dry-run` and `--output` options | `src/agent_sync/cli.py` |
| 4 | Add tests for `ConfigExporter` | `tests/test_config_exporter.py` |
| 5 | Update README with new command | `README.md` |

---

## Scope 2: MCP Unified Export (Optional)

### Problem
Each vendor has its own `mcp.json`. agent-sync doesn't currently manage MCP config at all. DotAgents wants a unified `~/.agents/mcp.json`.

### Solution
Add `agent-sync mcp export` command that:
1. Scans vendor MCP configs
2. Merges them into `~/.agents/mcp.json`
3. Detects conflicts and reports them
4. Does NOT auto-replace — user must approve

### Commands

```bash
# Scan and show merge preview
agent-sync mcp export --dry-run

# Export and overwrite
agent-sync mcp export --force

# Show conflict report
agent-sync mcp export --conflicts
```

### Output Format (`~/.agents/mcp.json`)

```json
{
  "version": "1.0",
  "generated_by": "agent-sync",
  "sources": [
    "~/.claude/mcp.json",
    "~/.cursor/mcp.json"
  ],
  "servers": {
    "filesystem": { ... },
    "github": { ... }
  },
  "conflicts": [
    {
      "server": "duplicate-server",
      "sources": ["~/.claude/mcp.json", "~/.cursor/mcp.json"],
      "resolution": "first"  // or "manual"
    }
  ]
}
```

### Conflict Resolution

| Strategy | Behavior |
|-----------|----------|
| `first` | Use first found, skip duplicates |
| `merge` | Merge server configs (may conflict) |
| `manual` | Report conflicts, don't include |

### Implementation

| Step | Task | File |
|------|------|------|
| 1 | Create `MCPMerger` class | `src/agent_sync/mcp_merger.py` |
| 2 | Add `mcp export` CLI command | `src/agent_sync/cli.py` |
| 3 | Add `--dry-run`, `--force`, `--conflicts` options | `src/agent_sync/cli.py` |
| 4 | Add tests for `MCPMerger` | `tests/test_mcp_merger.py` |
| 5 | Update README with new command | `README.md` |

---

## Not In Scope

- Replacing `agent_registry.yaml` with JSON
- Auto-updating vendor MCP configs
- Workspace overrides (`./.agents/`)
- Public hub integration

---

## Acceptance Criteria

### JSON Config Export
- [ ] `config export --dry-run` shows preview without creating file
- [ ] `config export` creates valid JSON at `~/.agents/config.json`
- [ ] Exported config includes all registered agents
- [ ] Exported config includes skills hub path
- [ ] Tests pass

### MCP Unified Export
- [ ] `mcp export --dry-run` shows merge preview
- [ ] `mcp export --force` creates `~/.agents/mcp.json`
- [ ] Conflicts are detected and reported
- [ ] No vendor MCP configs are modified
- [ ] Tests pass

### General
- [ ] Both features are optional (don't break existing behavior)
- [ ] README updated with new commands
- [ ] CHANGELOG updated