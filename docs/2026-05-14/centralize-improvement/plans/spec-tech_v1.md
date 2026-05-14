# Tech Plan: Safe Centralize

## 0. Product Context (from spec-product_v1.md)

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

1. **`centralize-safe-mode`** (feature) — Implementação core. Deve vir primeiro porque os outros scopes dependem dele.
2. **`centralize-tests-docs`** (feature) — Testes e docs após implementação. Só possível depois do scope 1.
3. **`dotagents-protocol`** (spike) — Independente, pode rodar em paralelo ou depois.

---

## 3. Detailed Development Sequence per Scope

### SCOPE 1: `centralize-safe-mode`

**Type**: feature
**Objective**: Reestruturar o pipeline do `centralize()` com as 3 camadas de proteção
**Dependencies**: Nenhuma (código existente)
**Technical Considerations**: TUI interativa requer `rich.live`; hash MD5 recursivo precisa de função utilitária; pipeline reordenado muda o fluxo principal

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
- [ ] Testes unitários passando
- [ ] Todos os testes existentes continuam passando

#### Detailed Task Sequence

**Task 1.1: Funções utilitárias (hash + orphan detection)**
- Criar `_compute_dir_hash(path)` → hash MD5 recursivo de diretório
- Modificar `scan_all_agents()` ou criar `_categorize_orphans(hub_skills, skills_found)` que retorna `{skill_name: {agents: [(agent, path)], hash, content_differs}}`
- Justificativa: base para todas as outras tasks

**Task 1.2: Reordenar pipeline centralize()**
- Quebrar `centralize()` em fases separadas
- Mover `_sync_from_repo()` para depois da verificação de hub vazio
- Inserir verificação de fresh setup antes do sync
- Justificativa: o pipeline precisa estar reordenado antes de adicionar a TUI

**Task 1.3: TUI de seleção**
- Implementar `_orphan_selection_tui(orphans)` com rich.live
- Tabela única (Híbrido A+E) com checkboxes
- Atalhos: números toggle, a=all, n=none, /filter, Enter=done
- ⚠️ diverge quando hash difere entre agentes
- Default: nenhuma selecionada
- Justificativa: TUI é o coração da Layer 1

**Task 1.4: Flags --yes, --import-all, --dry-run**
- `--yes`: skip órphãos + auto-Keep, só log
- `--import-all`: importa todos sem TUI (comportamento antigo)
- `--dry-run`: mostra TUI sem executar, ou resumo
- Atualizar CLI `skills.py` command entry
- Justificativa: cobrir CI/script e migração

**Task 1.5: Layer 3 — Keep/Remove + Cleanup protegido**
- Implementar passo pós-seleção com prompt [K]eep/[R]emove
- Cleanup só executa para: usuário escolheu Remove + skills importadas (move=True)
- `configure_agents()` NÃO chama `_cleanup_agent_local_skills()`
- Justificativa: proteger dados do usuário

---

### SCOPE 2: `centralize-tests-docs`

**Type**: feature
**Objective**: Cobertura de testes para todos os novos cenários + docs atualizadas
**Dependencies**: Scope 1 completo

#### Definition of Done
- [ ] Tests para fresh setup (hub vazio → auto-import)
- [ ] Tests para hub populado + órphãos → TUI (mockada)
- [ ] Tests para `--yes` → skip todos
- [ ] Tests para `--import-all` → comportamento antigo
- [ ] Tests para hash comparison entre cópias divergentes
- [ ] Tests para passo Keep vs Remove
- [ ] Tests para dry-run não modificar nada
- [ ] Tests para terminal não-interativo → fallback
- [ ] README.md atualizado com novas flags e fluxo
- [ ] `skills/agent-sync/SKILL.md` atualizado

---

### SCOPE 3: `dotagents-protocol`

**Type**: spike
**Objective**: Pesquisar DotAgents Protocol e consolidar agent_registry.yaml
**Dependencies**: Nenhuma

#### Definition of Done
- [ ] Fetch DotAgents Protocol spec da URL
- [ ] Mapear campos do registry atual vs protocolo
- [ ] Identificar gaps e propor migrations
- [ ] Atualizar agent_registry.yaml conforme necessário
- [ ] Documentar decisões no CHANGELOG.md

---

## 4. Final Summary

1. **`centralize-safe-mode`** — feature core (reordenar pipeline + 3 camadas)
2. **`centralize-tests-docs`** — feature (testes + docs + README)
3. **`dotagents-protocol`** — spike (pesquisa + consolidação registry)
