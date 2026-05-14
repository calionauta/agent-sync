# Progress — agent-sync v0.16+

## Status
✅ Complete — All features implemented

---

## Features Implemented

### publish --agents Command (v0.16)

**Publish agent instructions (AGENTS.md, GEMINI.md, etc.) to public GitHub.**

**New CLI commands:**
```bash
agent-sync publish                    # Publish both skills + agents (default)
agent-sync publish --skills          # Publish only skills
agent-sync publish --agents            # Publish only agent instructions (NEW!)
```

**Components:**
- `agent_discovery.py` — scans config_patterns from registry
- `security_scanner.py` — detects sensitive content (paths, tokens, commands)
- `publish.py` — updated with `publish_agents()` function
- `config.py` — added `published_agents` property
- `cli.py` — new `publish` command with `--agents` flag

**Security Scanner patterns:**
- Absolute paths: `/Users/`, `/home/`, `/root/`, `C:\`
- Tokens: OpenAI `sk-`, GitHub `ghp_`
- Internal commands: `/skill:`, `ctx_batch_execute()`
- Server paths: `server.`, `.renatocaliari.com`

**Security flow:**
1. Discover agent instruction files
2. Scan for sensitive content
3. TUI selection with security indicators
4. Security panel (edit, skip, continue, cancel)
5. Summary with icons (⚠️ or ✓)
6. Git push to `agents/<agent>/<file>`

**New files:**
- `src/agent_sync/agent_discovery.py`
- `src/agent_sync/security_scanner.py`
- `tests/test_agent_discovery.py` (17 tests)
- `tests/test_security_scanner.py` (26 tests)

### Safe Centralize (v0.15)

**3 camadas de proteção no pipeline do `centralize()`:**

1. **TUI de seleção de órfãos** (Hybrid A+E)
   - Interactive TUI com checkboxes
   - Default: nenhum selecionado (seguro)
   - Atalhos: `a`=all, `n`=none, Enter=done

2. **Content comparison via hash**
   - `_compute_dir_hash()` — recursive MD5 hash
   - Detecta cópias divergentes (⚠️ diverge)

3. **Pós-seleção Keep/Remove**
   - Mantém ou remove órfãos não-selecionados
   - Controlled cleanup

**New CLI flags:**
- `--yes` — Non-interactive: skip all orphans
- `--import-all` — Import all orphans (old behavior)
- `--dry-run` — Preview without modifying

### DotAgents Protocol Compatibility (v0.15+)

**Implemented:**
- `~/.agents/skills/` como hub canônico (DotAgents compliant)
- `~/.agents/` estrutura automática (sem flag)
- `DotAgentsHandler` com `fmt:.agents` para normalização de paths

**Files:**
- `src/agent_sync/centralize/handlers/dot_agents_handler.py`
- `src/agent_sync/centralize/handlers/__init__.py`

**Config export (`config export`):**
- `agent-sync config export` → `~/.agents/config.json`
- Formato JSON compatível com DotAgents

**MCP export (`mcp`):**
- `agent-sync mcp --dry-run` — preview merge
- `agent-sync mcp --force` — export unified MCP config
- Detecta e reporta conflitos entre vendors

### Documentation

- **AGENTS.md**: Seção DotAgents Protocol Alignment adicionada
- **README.md**: Seção DotAgents Protocol com tabela comparativa
- **docs/dotagents-comparison.md**: Comparação completa agent-sync vs DotAgents
- **docs/dotagents.md**: Análise do protocolo
- **CHANGELOG.md**: Todas as features documentadas

---

## Test Coverage

| Metric | Value |
|--------|-------|
| Total tests | 210 |
| Test files | 19 |
| LOC | 7,228 |
| Exit code | 0 failures |

---

## Files Changed (v0.15 release)

| File | Changes |
|------|---------|
| `src/agent_sync/skills.py` | +512 lines (safe centralize pipeline) |
| `src/agent_sync/cli.py` | +17 lines (config export, mcp commands) |
| `src/agent_sync/config_exporter.py` | New (JSON export) |
| `src/agent_sync/mcp_merger.py` | New (MCP merge) |
| `src/agent_sync/centralize/handlers/dot_agents_handler.py` | New |
| `tests/test_config_exporter.py` | New (13 tests) |
| `tests/test_mcp_merger.py` | New (13 tests) |
| `tests/test_dotagents_handler.py` | New (9 tests) |
| `README.md` | Updated (DotAgents section) |
| `AGENTS.md` | Updated (DotAgents section) |
| `CHANGELOG.md` | Updated |