# Tech Plan: Safe Centralize

## 0. Product Context

**Problema**: `centralize` escaneia agentes e importa skills de volta pro hub sem diferenciação, causando ressurreição de skills deletadas, importação de cópias velhas, e destruição silenciosa de skills não-selecionadas.

**Solução**: 3 camadas de proteção no pipeline do `centralize()`:
1. TUI de seleção de órfãos (Híbrido A+E, default vazio)
2. Content comparison via hash MD5 recursivo
3. Pós-seleção Keep/Remove com cleanup controlado

**Flags**: `--yes`, `--import-all`, `--dry-run`

**Interface**: Híbrido A+E (tabela única + atalhos de teclado + ⚠️ diverge)

**Scopes adicionais**:
- Scope A: Testes, Documentação, README
- Scope B: Padronização DotAgents Protocol

---

## 1. Identified Scopes

| # | Nome | Tipo | Descrição |
|---|------|------|-----------|
| 1 | `centralize-safe-mode` | **feature** | Pipeline reordenado + 3 camadas de proteção no `skills.py` |
| 2 | `centralize-tests-docs` | **feature** | Testes para novos cenários + README + SKILL.md |
| 3 | `dotagents-protocol` | **spike** | Pesquisar DotAgents Protocol e consolidar agent_registry.yaml |

---

## 2. High-Level Sequence

1. **`centralize-safe-mode`** (feature) — Implementação core.
2. **`centralize-tests-docs`** (feature) — Após implementação.
3. **`dotagents-protocol`** (spike) — Independente.

---

## 3. Detailed Scopes

### SCOPE 1: `centralize-safe-mode`
**Type**: feature
**Dependencies**: Nenhuma

#### Definition of Done
- [ ] Pipeline reordenado (scan → TUI → import → keep/remove → cleanup → configure)
- [ ] `_sync_from_repo()` movido para depois da verificação de hub vazio
- [ ] Fresh setup detectado (hub vazio) → auto-import
- [ ] Orphans detectados e categorizados por skill name + agentes
- [ ] Hash MD5 recursivo implementado para content comparison
- [ ] TUI interativa com checkboxes (default vazio), atalhos a/n, ⚠️ diverge
- [ ] `--yes` skip todos os órfãos
- [ ] `--import-all` comportamento antigo
- [ ] Passo pós-seleção Keep/Remove com cleanup controlado
- [ ] `configure_agents()` SEM `_cleanup_agent_local_skills()`
- [ ] Fallback para terminal não-interativo
- [ ] `--dry-run` mostra planejado sem executar

### SCOPE 2: `centralize-tests-docs`
**Type**: feature
**Dependencies**: Scope 1

#### Definition of Done
- [ ] Tests para fresh setup, TUI, --yes, --import-all, hash comparison, Keep/Remove, dry-run, terminal não-interativo
- [ ] README.md atualizado com novas flags e fluxo
- [ ] `skills/agent-sync/SKILL.md` atualizado

### SCOPE 3: `dotagents-protocol`
**Type**: spike
**Dependencies**: Nenhuma

#### Definition of Done
- [ ] Fetch DotAgents Protocol spec
- [ ] Mapear registry atual vs protocolo
- [ ] Identificar gaps e propor migrations
- [ ] Atualizar agent_registry.yaml
- [ ] Documentar em CHANGELOG.md

---

## 4. Final Summary

1. **`centralize-safe-mode`** — feature core
2. **`centralize-tests-docs`** — feature
3. **`dotagents-protocol`** — spike
