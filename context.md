# Code Context

## Files Retrieved

1. `src/agent_sync/agent_registry.yaml` (lines 1-175) - Agent definitions with NO `type` field
2. `src/agent_sync/cli.py` (lines 374-399) - `agents list` command using `agent_data.get("type", "unknown")`
3. `src/agent_sync/agents/base.py` (lines 1-213) - BaseAgent class with NO `type` property
4. `src/agent_sync/agents/__init__.py` (lines 1-68) - Agent factory, specialized handlers map
5. `src/agent_sync/agents/registry_loader.py` (lines 1-50) - YAML registry loader with validation

## Key Code

**The bug is in `cli.py` lines 394-397:**
```python
agent_type = agent_data.get("type", "unknown")  # <-- Looking for non-existent "type" field
location = agent_data.get("config_dir", "N/A")
table.add_row(agent_name, agent_type, location)
```

**The registry (`agent_registry.yaml`) only has `method` field, not `type`:**
```yaml
opencode:
  method: config          # NOT "type"
  config_dir: "~/.config/opencode"
  skills_dir_name: "skills"

pi.dev:
  method: native          # NOT "type"
  config_dir: "~/.pi/agent"
  skills_dir_name: "skills"
```

**BaseAgent class has no `type` property** (only `method`, `name`, `skills_dir_name`, etc.)

## Architecture

```
cli.py (list_agents)
    └── load_registry() from agents/
            └── agents/registry_loader.py → parses agent_registry.yaml
            
Registry YAML structure:
  - Each agent has: method, config_dir, skills_dir_name, check, etc.
  - NO "type" field exists
  - No fallback/type derivation logic
```

**Available specialized handlers** (in `agents/__init__.py`):
- `roocode` → RooCodeAgent
- `cline` → ClineAgent  
- `cursor` → CursorAgent
- `windsurf` → WindsurfAgent
- All others → BaseAgent (no type property)

## Start Here

To understand and fix the issue:
1. Open `src/agent_sync/cli.py` at line 390 - the bug location
2. Open `src/agent_sync/agent_registry.yaml` - source of truth that lacks `type` field

## Fix Options

1. **Quick fix**: Change `agent_data.get("type", "unknown")` to `agent_data.get("method", "unknown")` 
   - But "method" values (native/config/copy) aren't user-friendly type names

2. **Proper fix**: Add `type` field to registry YAML entries:
   ```yaml
   opencode:
     type: cli
     method: config
     ...
   
   pi.dev:
     type: cli
     method: native
     ...
   
   cursor:
     type: ide
     method: native
     ...
   ```

3. **Inheritance fix**: Add `type` property to `BaseAgent`:
   ```python
   @property
   def type(self) -> str:
       """Derive type from method and handler class."""
       if self.method == "native":
           return "ide"  # vscode, cursor, roocode, etc.
       return "cli"  # claude, opencode, gemini, pi
   ```
   And update specialized handlers to override `type` appropriately.

## Supervisor coordination

The registry schema needs a decision: should `type` be added to YAML (data-driven) or derived in Python code (logic-driven)? The AGENTS.md mentions DotAgents protocol alignment but doesn't specify a type taxonomy. Recommend YAML field for explicit control, with derived fallback.