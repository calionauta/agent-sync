# Progress

## Status
In Progress

## Tasks

### CLI Analysis - Data Flow & YAML Schema

**Completed:** Comprehensive analysis of agent-sync CLI commands and data flow.

**Files Analyzed:**
- `src/agent_sync/cli.py` (~1900 lines)
- `src/agent_sync/sync.py` (~1500 lines)
- `src/agent_sync/skills.py` (~1000 lines)
- `src/agent_sync/config.py` (~300 lines)
- `src/agent_sync/agent_registry.yaml` (~200 lines)

**Key Findings:**

| YAML File | Purpose | Schema |
|-----------|---------|--------|
| `config.yaml` | User preferences | repo_url, agents, sync settings |
| `agent_registry.yaml` | Agent definitions | method, paths, patterns (shipped, not user) |

**Commands & Data Flow:**
- `push` → stages configs + skills + agents → git commit + push
- `pull` → git fetch + pull → apply configs/skills/agents
- `centralize` → scan agents → detect orphans → move/copy to ~/.agents/skills/
- `config` → read/write `~/.config/agent-sync/config.yaml`

**GitAgent Gap Identified:**
- ❌ `agent.yaml`, `SOUL.md`, `RULES.md`, `DUTIES.md` NOT backed up
- ❌ `memory/`, `knowledge/` NOT backed up
- ⚠️ These files don't exist on user's system (using DotAgents, not GitAgent)

**Full Analysis:** `/tmp/scouts/cli-analysis.md`

### High Priority Tests to Add (from analysis)

1. **`push` with mock** - Test correct files staged
2. **`pull` with mock** - Test correct files restored
3. **`skills centralize`** - Test orphan detection
4. **`config repo`** - Test repo_url saved correctly

### Protocol Documentation

**Completed:** `docs/protocol-comparison.md` comparing:
- DotAgents Protocol (agent-sync's hub)
- GitAgent Protocol (comprehensive agent definition)

**Key insight:** Protocols are complementary, not competing.

## Files Changed

## Notes

**Questions for user:**
1. Should agent-sync track GitAgent files (agent.yaml, SOUL.md, etc.)?
2. Should agent-sync have its own manifest or reference existing standards?
3. What YAML schema makes sense for backup/restore purposes?