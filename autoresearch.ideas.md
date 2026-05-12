# Autoresearch — agent-sync push & pull

## Implemented Fixes (✅ Done — 6 experimentos)

| # | Problema | Onde | Impacto | Correção |
|---|----------|------|---------|----------|
| 1 | **O(n²)**: `_stage_agent_configs()` chamada 10× | `push` | **58s → 2.2s** (26×) | Mover para antes do loop |
| 1 | **`~/.pi/agent/git/`**: 21k arquivos (222MB) copiados | `push` | **8s → 0.3s** | Skip: é cache, não config |
| 2 | **`_run_git()` sem timeout**: hang infinito | `push/pull` | **segurança** | Timeout 60s + erro claro |
| 2 | **Sem `.gitignore`**: git clones re-adicionados | `push` | **recontaminação** | `configs/pi.dev/git/` no .gitignore |
| 5 | **`read_text()` em binário**: crash `UnicodeDecodeError` | `pull` | **🔴 crash** | `_same_content()` com `read_bytes()` |
| 6 | **Código morto de git restore** no `pull` | `pull` | **manutenção** | Substituído por skip message |

## Estado Final

| Comando | Before | After |
|---------|--------|-------|
| `agent-sync push` | **58s** hang | **2.3s** ✅ |
| `agent-sync pull` | **crash** 🔴 | **2.2s** ✅ |
| `--skills-only` | lento | **2.0s** ✅ |
| `--configs-only` | lento | **0.6s** ✅ |
| `--agents-only` | lento | **0.0s** ✅ |
| `status, skills, agents, config` | OK | **0.2s** ✅ |
| Espaço do repositório | 343MB | **~5MB** 💾 |
