# Autoresearch — agent-sync push & pull — COMPLETE

## 9 Experimentos — Todas as causas raiz eliminadas

O `agent-sync push` não finalizava por **múltiplas causas combinadas** que se amplificavam mutuamente. Cada uma foi encontrada e corrigida.

### Bugs de Performance

| # | Problema | Local | Antes | Depois |
|---|----------|-------|-------|--------|
| 1 | **O(n²)** em `_stage_agent_configs()` — chamada 10× | `push` | **58s** | **2.3s** |
| 1 | **`~/.pi/agent/git/`** — 21k arquivos (222MB) copiados a cada push | `push` | +40s | Skip |
| 5 | **`read_text()` em binários** — crash `UnicodeDecodeError` em pull | `pull` | **crash** 🔴 | `_same_content(read_bytes)` |

### Bugs de Robustez (Hangs)

| # | Problema | Local | Antes | Depois |
|---|----------|-------|-------|--------|
| 2 | **`_run_git()` sem timeout** — hang infinito se git prompta | `push/pull` | ∞ | Timeout 60s |
| 8 | **`GIT_TERMINAL_PROMPT`** não definido — git prompta sem resposta | `push/pull` | ∞ | `GIT_TERMINAL_PROMPT=0` → 0.7s |
| 9 | **`subprocess.run` sem timeout** — init/link podem hangar | `setup` | ∞ | Timeouts 30-120s |

### Bugs de Manutenção

| # | Problema | Local | Correção |
|---|----------|-------|----------|
| 4 | **Sem `.gitignore`** para git clones | repo | `configs/pi.dev/git/` no .gitignore |
| 6 | **Código morto de git restore** no pull | `pull` | Removido |
| 7 | **Tipos binários** `.node`, `.wasm`, `.mp4` em extra_paths | `pull` | Coberto pelo fix #5 |

### Estado Final

```
agent-sync push:    58s  ⏳  →  2.3s  ✅  (26× mais rápido)
agent-sync pull:    crash 🔴  →  2.2s  ✅  
Auth failure:       ∞ hang   →  0.7s  ✅  
Setup/Link:         ∞ hang   →  30s timeout  ✅
Espaço do repo:     343MB    →  ~5MB  💾
```
