# Execution Report: agents-publish Feature

**Date:** 2026-05-14  
**Spec:** `docs/2026-05-14/agents-publish/plans/spec-product_v2.md` (approved)  
**Tech Plan:** `docs/2026-05-14/agents-publish/plans/spec-tech.md`

---

## ✅ Scope Completion Summary

| # | Scope | Type | Status | Files Created |
|---|-------|------|--------|---------------|
| S1 | Agent Discovery Spike | spike | ✅ Complete | `agent_discovery.py` |
| S2 | Security Scanner | feature | ✅ Complete | `security_scanner.py` |
| S3 | TUI + publish_agents() | feature | ✅ Complete | `publish.py` updated |
| S4 | Config Persistence | feature | ✅ Complete | `config.py` updated |
| S5 | CLI Integration | feature | ✅ Complete | `cli.py` updated |
| S6 | publish.py Refactoring | feature | ✅ Complete | helpers extracted |

---

## 📁 New Files Created

### `src/agent_sync/agent_discovery.py`
- `AgentInstructionFile` dataclass
- `discover_agent_instructions()` — scans config_patterns from registry
- `get_available_agents()` — returns dict format for TUI

### `src/agent_sync/security_scanner.py`
- `Issue` TypedDict
- `ScanResult` dataclass
- `scan_file()` — regex patterns for abs paths, tokens, commands, server paths
- `scan_multiple()` — batch scanning
- 12 detection patterns

### `tests/test_agent_discovery.py`
- 17 test cases for discovery module

### `tests/test_security_scanner.py`
- 26 test cases for security scanner

---

## 🔧 Files Modified

### `src/agent_sync/publish.py`
**Added:**
- Agent discovery integration (`get_available_agents`)
- `render_agents_table()` — TUI table with security indicators
- `interactive_agents_selection()` — selection TUI
- `show_security_panel()` — security warning panel
- `publish_agents()` — main publish function
- `_push_agents_to_repo()` — git push for agents/
- `_generate_readme_for_agents()` — README generation
- Shared helpers: `_resolve_repo_url`, `_check_repo_visibility`, `_git_clone_or_init`, `_git_push`

### `src/agent_sync/config.py`
**Added:**
- `published_agents` property (getter/setter)
- Persists as `["agent:filename", ...]` format

### `src/agent_sync/cli.py`
**Added:**
- New `publish` command with `--skills`, `--agents`, `--all` flags
- Default: `--all` (both skills and agents)
- Cross-reference notices between skills/agents publish

**Updated:**
- `skills publish` command → deprecated notice, use `publish --skills`

---

## 🧪 Test Results

```
============================= 210 passed in 1.70s ==============================
```

All existing tests pass. New tests added:
- 17 tests for `agent_discovery.py`
- 26 tests for `security_scanner.py`

---

## 🎯 CLI Commands

```bash
# Publish BOTH skills and agent instructions (default)
agent-sync publish

# Publish only skills (alias for old skills publish)
agent-sync publish --skills

# Publish only agent instructions (NEW!)
agent-sync publish --agents

# Preview what would be published
agent-sync publish --agents --dry-run

# Publish to specific repository
agent-sync publish --agents --repo https://github.com/user/my-repo
```

---

## 🔒 Security Scanner Patterns

| Pattern | Severity | Example |
|---------|----------|---------|
| `ABS_PATH_UNIX` | high | `/Users/cali/` |
| `ABS_PATH_HOME` | medium | `/home/user/` |
| `ABS_PATH_ROOT` | high | `/root/` |
| `ABS_PATH_WINDOWS` | high | `C:\Users\` |
| `TOKEN_OPENAI` | critical | `sk-...` |
| `TOKEN_GITHUB` | critical | `ghp_...` |
| `KEY_API` | critical | `api_key=...` |
| `KEY_SECRET` | critical | `secret=...` |
| `INTERNAL_CMD_SKILL` | high | `/skill:cali-product-planner` |
| `INTERNAL_CMD_CTX` | high | `ctx_batch_execute(` |
| `SERVER_PATH` | medium | `server.renatocaliari.com` |

---

## 📦 Repo Structure After Publish

```
<repo>/
├── skills/           # (existing)
├── agents/            # (NEW!)
│   ├── pi.dev/
│   │   └── AGENTS.md
│   ├── opencode/
│   │   └── AGENTS.md
│   ├── qwen-code/
│   │   └── output-language.md
│   └── ...
└── README.md         # (updated)
```

---

## 🚀 Next Steps

1. **Run end-to-end test:**
   ```bash
   agent-sync publish --agents --dry-run
   ```

2. **Test interactive flow:**
   ```bash
   agent-sync publish --agents
   ```

3. **Commit changes:**
   ```bash
   git add -A
   git commit -m "feat: add publish --agents command for agent instructions"
   ```