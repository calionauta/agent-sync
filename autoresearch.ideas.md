# Autoresearch — agent-sync push & pull

## Implemented Fixes (✅ Done — 8 experimentos)

| # | Problema | Onde | Antes | Depois |
|---|----------|------|-------|--------|
| 1 | **O(n²)**: `_stage_agent_configs()` chamada 10× (uma por agent) | `push` | **58s** | **2.3s** ✅ |
| 2 | **222MB de git clones** copiados a cada push (`~/.pi/agent/git/`) | `push` | **+40s** | Skip ✅ |
| 3 | **`_run_git()` sem timeout**: hang infinito em prompts | `push/pull` | **∞** | Timeout 60s ✅ |
| 4 | **Sem `.gitignore`**: git clones readicionados | `push` | **recontaminação** | `.gitignore` ✅ |
| 5 | **`read_text()` em binários**: crash `UnicodeDecodeError` | `pull` | **🔴 crash** | `_same_content(read_bytes)` ✅ |
| 6 | **Código morto de git restore** no pull | `pull` | **dead code** | Removido ✅ |
| 7 | **Varredura tipos binários**: `.node`, `.wasm`, `.mp4`, git packs | `pull` | **potencial crash** | Coberto pelo fix #5 ✅ |
| 8 | **`GIT_TERMINAL_PROMPT` não definido**: git promptava sem resposta | `push/pull` | **∞ hang** | `GIT_TERMINAL_PROMPT=0` → **0.7s** ✅ |

## Estado Final

| Comando | Before | After |
|---------|--------|-------|
| `agent-sync push` | **58s** hang | **2.3s** ✅ |
| `agent-sync pull` | **crash** 🔴 | **2.2s** ✅ |
| Auth failure (`GIT_TERMINAL_PROMPT`) | **∞** hang | **0.7s** fail ✅ |
| `--skills-only` | lento | **2.0s** ✅ |
| `--configs-only` | lento | **0.6s** ✅ |
| `--agents-only` | lento | **0.0s** ✅ |
| Espaço do repositório | **343MB** | **~5MB** 💾 |
