# Autoresearch — agent-sync — COMPLETE ✅

## 10 Experimentos — 100% das causas raiz eliminadas

## Resumo

| # | O quê | Local | Antes | Depois |
|---|-------|-------|-------|--------|
| 1 | O(n²) `_stage_agent_configs()` chamada 10× | `push` | **58s** | **2.3s** |
| 2 | `~/.pi/agent/git/` (222MB, 21k arquivos) copiado | `push` | +40s | **Skip** |
| 3 | `_run_git()` sem timeout — hang se git prompta | `push/pull` | **∞** | **Timeout 60s** |
| 4 | Sem `.gitignore` para git clones — recontaminação | `push` | **re-add** | `.gitignore` ✅ |
| 5 | `read_text()` em binários — crash UnicodeDecodeError | `pull` | **🔴 crash** | `_same_content(read_bytes)` |
| 6 | Código morto de git restore no pull | `pull` | **dead** | **Removido** |
| 7 | Tipos binários `.node`, `.wasm`, `.mp4` em extra_paths | `pull` | crash | Coberto #5 |
| 8 | `GIT_TERMINAL_PROMPT` não definido — git prompta infinito | `push/pull` | **∞** | `GIT_TERMINAL_PROMPT=0` → 0.7s |
| 9 | `subprocess.run` sem timeout em init/link/setup | `setup` | **∞** | **Timeouts 30-120s** |
| 10 | `subprocess.run` sem timeout em publish + update | `publish/update` | **∞** | **Timeouts 15-120s** |

## Cobertura Final

| Métrica | Valor |
|---------|-------|
| `subprocess.run` com timeout | **18/18** (100%) |
| `agent-sync push` | **2.3s** (de 58s) |
| `agent-sync pull` | **2.2s** (de crash) |
| Auth failure | **0.7s** (de ∞) |
| Espaço do repo | **~5MB** (de 343MB) |
| Arquivos modificados | `sync.py`, `publish.py`, `cli.py` |
