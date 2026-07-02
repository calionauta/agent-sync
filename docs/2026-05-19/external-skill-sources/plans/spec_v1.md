# agent-sync publish --skills: External Sources Feature

## Context

Extender o `agent-sync publish --skills` para permitir publicar skills de múltiplas fontes:
1. **Local**: `~/.agents/skills/` (atual)
2. **Repos externos**: GitHub repos públicos configurados pelo usuário

**Objetivo**: Criar um repo centralizado público (`agent-sync-public`) com TODAS as skills customizadas do usuário, fácil de descobrir por outros usuários/agents.

---

## Motivation

- Usuário tem skills em múltiplos projetos (ex: `pi-product-workflow`, `outro-projeto`)
- Alguns projetos podem ser removidos localmente, mas as skills ainda existem no GitHub
- Deseja um local público único com todas as skills para:
  - Outros users instalarem via `pi install git:...`
  - Users de outros agentes (não pi) acessarem

---

## Architecture

### Directory Structure

```
src/agent_sync/
├── publish/
│   ├── __init__.py
│   ├── base.py              # SkillSource dataclass
│   ├── local_source.py      # Skills de ~/.agents/skills/
│   ├── external_source.py   # Skills de repos GitHub externos
│   ├── cache.py             # Cache management (~/.cache/agent-sync/repos/)
│   ├── runner.py            # Orquestra + TUI
│   └── config.py            # CRUD de skill_sources + selected_skills
├── publish.py               # SEM ALTERAÇÃO (compatibilidade)
└── cli.py                   # ~20 linhas novas (delega para runner)
```

### Config Structure

```yaml
# ~/.config/agent-sync/publish.yaml

# Repos que contêm skills (fontes)
skill_sources:
  - url: https://github.com/calionauta/pi-product-workflow
    status: active              # active | failed | skipped
    last_success: "2026-05-19"
  - url: https://github.com/calionauta/outro-projeto
    status: active
    last_success: "2026-05-19"

# Seleção salva pelo usuário
selected_skills:
  local:
    - cali-product-workflow
    - plannotator-review
  calionauta/pi-product-workflow:
    - cali-shape-up
    - cali-short-cycle
  calionauta/outro-projeto:
    - alguma-coisa

# Configurações de cache
cache_dir: ~/.cache/agent-sync/repos/
cache_ttl_hours: 24
```

---

## Discovery Flow

```
agent-sync publish --skills
    │
    ├── 1. Carrega config
    │
    ├── 2. Runner.descobrir_tudo()
    │       │
    │       ├── LocalSource.discover()
    │       │   └── skills de ~/.agents/skills/
    │       │
    │       └── [para cada skill_sources]
    │           │
    │           └── ExternalSource.discover(url)
    │               │
    │               ├── Verifica cache (TTL válido?)
    │               ├── Se inválido:
    │               │   ├── git clone --depth 1 (shallow)
    │               │   ├── Encontra skills (skills/ ou SKILL.md)
    │               │   └── Atualiza cache
    │               └── Retorna lista de skills

    ├── 3. Runner.exibir_tui(skills_por_source)
    │       │
    │       ├── Mostra grupo: LOCAL + cada repo
    │       ├── Multi-select com seleção salva
    │       └── Salva seleção em config

    └── 4. Runner.publicar()
            │
            ├── Cria /tmp/agent-sync-publish-{uuid}/
            ├── Copia skills selecionadas do CACHE
            ├── Git add + commit + push → agent-sync-public
            └── Cleanup: rm -rf /tmp/agent-sync-publish-*
```

---

## Error Handling

### Graceful Degradation

| Erro | Comportamento |
|------|---------------|
| Repo 404 | Warning + mark `skipped` + continua |
| Rate limit 403 | Warning + usa cache + staleness notice |
| Clone falha | Warning + skip source + continua |
| Todos falham | Abort com mensagem clara |

### Comportamento do Publish

```python
# Se ao menos 1 skill disponível → publica e mostra summary
# Se 0 skills → abort (nada para publicar)
```

### Staleness

```python
if cache_valid:
    skills = load_from_cache()
    if source_has_failed:
        notice = "⚠️ Cache de {date}. Clone falhou."
else:
    skills = clone_and_cache()
```

---

## TUI Design

```
┌─────────────────────────────────────────────────────────┐
│  📚 Skills para Publicar                    [PUBLISH] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🔹 LOCAL (~/.agents/skills/)                          │
│    [✓] cali-product-workflow                            │
│    [✓] plannotator-review                               │
│                                                         │
│  🔹 github.com/calionauta/pi-product-workflow  ⚠️   │
│    [✓] cali-shape-up                                    │
│    [✓] cali-short-cycle                                 │
│    [ ] cali-opportunity-mapping  (cache de 2026-05-18) │
│                                                         │
│  🔹 github.com/calionauta/outro-projeto  ✓          │
│    [✓] alguma-coisa                                     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [A]ll [N]one [D]one [S]ources                          │
│  Enter: toggle | Numbers: toggle | done: publish        │
└─────────────────────────────────────────────────────────┘
```

---

## CLI Commands

```bash
# Publish (fluxo principal)
agent-sync publish --skills              # usa config + TUI

# Gerenciar fontes
agent-sync publish --skills --list-sources
agent-sync publish --skills --add-source https://github.com/user/repo
agent-sync publish --skills --remove-source https://github.com/user/repo
agent-sync publish --skills --reset-selection

# Cache
agent-sync publish --skills --clear-cache
agent-sync publish --skills --clear-cache --source https://github.com/user/repo

# Misc
agent-sync publish --skills --dry-run
agent-sync publish --skills --force      # override confirmation
```

---

## File Inventories

### Novos Arquivos

| Arquivo | Responsabilidade | Linhas |
|---------|------------------|--------|
| `publish/__init__.py` | Exports | ~10 |
| `publish/base.py` | SkillSource dataclass, base types | ~30 |
| `publish/local_source.py` | Discovery local | ~50 |
| `publish/external_source.py` | GitHub clone + discovery + cache | ~150 |
| `publish/cache.py` | Cache management | ~60 |
| `publish/runner.py` | Orquestração + TUI | ~100 |
| `publish/config.py` | CRUD config | ~50 |
| **Total** | | **~450** |

### Arquivos Modificados

| Arquivo | Mudança | Linhas |
|---------|---------|--------|
| `cli.py` | Adiciona comando `--skills` com subcommands | ~30 |
| `publish.py` | SEM ALTERAÇÃO | 0 |

---

## Risks & Mitigations

| Risco | Mitigação |
|-------|-----------|
| GitHub rate limit | GH CLI (`gh api`) p/ discovery + fallback cache |
| Rede falhar | Graceful degradation + cache |
| Config corrompido | Atomic write (tmp + rename) |
| Conflito de nomes | Prefix com `owner/` no display e publish |
| Clone lento | Shallow clone + cache + sequential (não paralelo) |

---

## Testing Plan

```bash
# Unit tests
pytest tests/publish/test_local_source.py
pytest tests/publish/test_external_source.py
pytest tests/publish/test_cache.py
pytest tests/publish/test_config.py

# Integration tests (mock git/github)
pytest tests/publish/test_runner.py -m mock

# Manual tests
agent-sync publish --skills --dry-run
agent-sync publish --skills --clear-cache
```

---

## Rollback Plan

```bash
# Branch: feature/external-skill-sources
git checkout -b feature/external-skill-sources

# Se FALHAR (reverter completamente):
git checkout main
git branch -D feature/external-skill-sources

# Se FUNCIONAR (integrar à main):
git checkout main
git merge --ff-only feature/external-skill-sources
git branch -d feature/external-skill-sources   # -d = seguro, só se mergeado

# Em caso de EMERGÊNCIA (descartar tudo):
git checkout main
git reset --hard HEAD~1                    # reverte o merge
```

**Nota**: `-d` (delete) só funciona se branch foi mergeada. `-D` (force) apaga sem verificar.
Para verificar antes de deletar: `git branch --merged main`

---

## Success Criteria

1. ✅ `agent-sync publish --skills` lista skills de local + repos externos
2. ✅ Seleção é salva em config (persiste entre runs)
3. ✅ Repos falhados são marcados e não bloqueiam
4. ✅ Cache funciona e respeita TTL
5. ✅ Publish copia skills para `agent-sync-public`
6. ✅ Temp dir é limpo após publish (sucesso ou falha)
7. ✅ Comportamento atual de skills locais preservado