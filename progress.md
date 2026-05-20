# Progress: Agent Type Detection Investigation

## Status: COMPLETE - Root Cause Found

### Issue
The `agent-sync agents list` command shows "unknown" for all agent types because:
1. CLI code looks for `type` field in registry YAML
2. Registry YAML has no `type` field - only `method` (native/config/copy)
3. BaseAgent class has no `type` property to derive from

### Root Cause
`cli.py` line 394:
```python
agent_type = agent_data.get("type", "unknown")  # Always returns "unknown"
```

### Files Analyzed
- `src/agent_sync/cli.py` - agents list command
- `src/agent_sync/agent_registry.yaml` - registry definitions (no type field)
- `src/agent_sync/agents/base.py` - BaseAgent (no type property)
- `src/agent_sync/agents/__init__.py` - agent factory
- `src/agent_sync/agents/registry_loader.py` - YAML loader

### Next Steps (pending decision)
1. Add `type` field to registry YAML entries
2. OR add `type` property to BaseAgent class with derivation logic
3. Test fix with `agent-sync agents list`