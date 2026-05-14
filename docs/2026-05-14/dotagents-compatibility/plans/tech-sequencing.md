# Tech Sequencing Plan: DotAgents Compatibility Features

## Tech-Sequencing-Planning

### Scope 1: JSON Config Export (`config export`)

---

#### 1.1 Technical Analysis

**Inputs:**
- `load_registry()` from `agents/registry_loader.py` → agent definitions (YAML)
- `Config` class from `config.py` → repo_url, sync options
- `GLOBAL_SKILLS_DIR` from `agents/__init__.py` → `~/.agents/skills/`

**Dependencies:**
- `json` (stdlib)
- `load_registry()` already exists
- `Config.get_sync_options()` already exists

**Output format:**
```json
{
  "version": "1.0",
  "generated_by": "agent-sync",
  "skills_hub": "~/.agents/skills",
  "generated_at": "2024-01-01T00:00:00Z",
  "model": {},
  "agents": {
    "claude-code": {
      "enabled": true,
      "method": "copy",
      "skills_dir": "~/.claude/commands/"
    }
  },
  "sync": {
    "method": "git",
    "repo_url": "https://github.com/user/repo"
  }
}
```

**Gaps identified:**
- ❌ No `model` field in current config → leave empty or read from env
- ❌ No `generated_at` timestamp utility → use `datetime.utcnow().isoformat()`
- ❌ No `ConfigExporter` class → need to create

**Tech sequence:**
```
Step 1: Create src/agent_sync/config_exporter.py
  - class ConfigExporter
  - __init__(self, config: Config)
  - export() -> dict
  - to_json() -> str
  - save(path: Path)

Step 2: Add CLI command @config.command() def export()
  - @click.option("--dry-run", ...)
  - @click.option("--output", ...)
  - handler function

Step 3: Add tests in tests/test_config_exporter.py
```

---

#### 1.2 Detailed Implementation

**File: `src/agent_sync/config_exporter.py`**

```python
"""Export agent-sync config to DotAgents JSON format."""
from datetime import datetime
from pathlib import Path
import json

from agent_sync.config import Config
from agent_sync.agents import get_agents, GLOBAL_SKILLS_DIR


class ConfigExporter:
    """Export configuration to DotAgents-compatible JSON."""

    VERSION = "1.0"

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.registry = {}
        self.agents_data = []

    def load(self) -> None:
        """Load registry and agents data."""
        from agent_sync.agents.registry_loader import load_registry
        self.registry = load_registry()
        self.agents_data = get_agents()

    def export(self) -> dict:
        """Export to DotAgents config format."""
        self.load()

        return {
            "version": self.VERSION,
            "generated_by": "agent-sync",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "skills_hub": str(GLOBAL_SKILLS_DIR),
            "model": {},  # No model config yet
            "agents": self._export_agents(),
            "sync": self._export_sync(),
        }

    def _export_agents(self) -> dict:
        """Export agent configurations."""
        agents = {}
        for agent in self.agents_data:
            if agent.name in ("global-skills",):
                continue
            agents[agent.name] = {
                "enabled": agent.enabled,
                "method": agent.method,
                "skills_dir": str(agent.get_skills_dir()),
            }
        return agents

    def _export_sync(self) -> dict:
        """Export sync configuration."""
        return {
            "method": "git",
            "repo_url": self.config.repo_url or "",
        }

    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string."""
        return json.dumps(self.export(), indent=indent)

    def save(self, path: Path) -> None:
        """Save to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())
```

---

### Scope 2: MCP Unified Export (`mcp export`)

---

#### 2.1 Technical Analysis

**Inputs:**
- Vendor MCP configs: `~/.claude/mcp.json`, `~/.cursor/mcp.json`, etc.
- Need to find these from registry

**Problem:** The registry doesn't track MCP config locations!

**Gap identified:**
- ❌ `agent_registry.yaml` has no `mcp_config` field
- ❌ No way to know where vendor MCP configs are

**Solutions (in order of preference):**
1. **Known locations** — Assume standard paths (most vendors follow conventions)
2. **Config scan** — Scan common locations
3. **User input** — Let user specify with `--source`

**Decision:** Go with option 1 + 3 (known locations + user can override)

**Known MCP locations:**
```yaml
claude-code: ~/.claude/mcp.json
cursor: ~/.cursor/mcp.json
# Others: scan common locations
```

**Tech sequence:**
```
Step 1: Create src/agent_sync/mcp_merger.py
  - KNOWN_MCP_LOCATIONS dict (registry of known paths)
  - class MCPMerger
  - __init__(sources: list[Path])
  - find_mcp_configs() -> list[Path]
  - merge() -> dict
  - detect_conflicts() -> list[Conflict]
  - save(path: Path)

Step 2: Add CLI command @main.command() def mcp()
  - @click.option("--dry-run", ...)
  - @click.option("--force", ...)
  - @click.option("--conflicts", ...)
  - @click.option("--source", multiple=True)
  - handler function

Step 3: Add tests in tests/test_mcp_merger.py
```

---

#### 2.2 Detailed Implementation

**File: `src/agent_sync/mcp_merger.py`**

```python
"""MCP config merger for DotAgents compatibility."""
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any

from rich.console import Console

console = Console()

# Known MCP config locations by vendor
KNOWN_MCP_LOCATIONS: dict[str, Path] = {
    "claude-code": Path.home() / ".claude" / "mcp.json",
    "cursor": Path.home() / ".cursor" / "mcp.json",
    "windsurf": Path.home() / ".codeium" / "windsurf" / "mcp.json",
}


@dataclass
class MCPServer:
    """Represents an MCP server definition."""
    name: str
    config: dict[str, Any]
    source: Path


@dataclass
class MCPConflict:
    """Represents a server name conflict."""
    server_name: str
    sources: list[Path]
    resolution: str = "first"  # first | manual


class MCPMerger:
    """Merge multiple MCP configs into unified format."""

    VERSION = "1.0"
    DEFAULT_OUTPUT = Path.home() / ".agents" / "mcp.json"

    def __init__(self, sources: list[Path] | None = None):
        self.sources = sources or []
        self.servers: dict[str, MCPServer] = {}
        self.conflicts: list[MCPConflict] = []

    def find_mcp_configs(self) -> list[Path]:
        """Find MCP configs in known locations."""
        found = []
        for path in KNOWN_MCP_LOCATIONS.values():
            if path.exists():
                found.append(path)
        return found

    def merge(self, conflict_strategy: str = "first") -> dict:
        """Merge all MCP configs into unified format."""
        sources = self.sources or self.find_mcp_configs()

        for source in sources:
            if not source.exists():
                continue
            try:
                data = json.loads(source.read_text())
                servers = data.get("mcpServers", data.get("servers", {}))
                for name, config in servers.items():
                    if name in self.servers:
                        self.conflicts.append(MCPConflict(
                            server_name=name,
                            sources=[self.servers[name].source, source],
                            resolution=conflict_strategy,
                        ))
                        if conflict_strategy == "first":
                            continue  # Keep first
                    self.servers[name] = MCPServer(
                        name=name,
                        config=config,
                        source=source,
                    )
            except (json.JSONDecodeError, OSError):
                pass

        return self._build_output(sources)

    def _build_output(self, sources: list[Path]) -> dict:
        """Build output dictionary."""
        return {
            "version": self.VERSION,
            "generated_by": "agent-sync",
            "sources": [str(s) for s in sources],
            "servers": {s.name: s.config for s in self.servers.values()},
            "conflicts": [
                {
                    "server": c.server_name,
                    "sources": [str(s) for s in c.sources],
                    "resolution": c.resolution,
                }
                for c in self.conflicts
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string."""
        return json.dumps(self.merge(), indent=indent)

    def save(self, path: Path) -> None:
        """Save to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())
```

---

## Gaps Summary

| Gap | Severity | Solution |
|-----|----------|----------|
| No model config in our system | Low | Leave empty in export |
| Registry has no `mcp_config` paths | Medium | Use known locations + `--source` override |
| MCP JSON format varies by vendor | Medium | Handle both `mcpServers` and `servers` keys |

---

## Implementation Order

```
1. config_exporter.py      (Scope 1)
2. config export CLI       (Scope 1)
3. tests_config_exporter.py (Scope 1)
4. mcp_merger.py           (Scope 2)
5. mcp export CLI          (Scope 2)
6. tests_mcp_merger.py     (Scope 2)
7. README + CHANGELOG      (both)
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/agent_sync/config_exporter.py` | Create |
| `src/agent_sync/mcp_merger.py` | Create |
| `src/agent_sync/cli.py` | Modify |
| `tests/test_config_exporter.py` | Create |
| `tests/test_mcp_merger.py` | Create |
| `README.md` | Modify |
| `CHANGELOG.md` | Modify |