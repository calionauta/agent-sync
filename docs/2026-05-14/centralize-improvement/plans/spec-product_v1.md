---
approved: true
approved_at: "2026-05-14T14:35:00-03:00"
approved_via: plannotator --gate
---

# Spec: Safe Centralize — Proteção contra importação não-intencional de skills

## 1. Unanswered Questions & Hidden Assumptions

### Tensions identificadas na conversa

- **Direção de importação**: `centralize` é bidirecional (agentes → hub + hub → agentes). O usuário só quer hub → agentes no dia a dia. A coleta de agentes → hub só deveria acontecer em setup inicial ou com confirmação explícita.
- **Órfãos vs. duplicatas**: Skill que existe no hub e em agente → hub vence. Skill que só existe em agente → é órfã, precisa de decisão.
- **Destruição silenciosa**: `_cleanup_agent_local_skills` apaga skills de agentes durante centralize, incluindo órfãos não selecionados — sem aviso ou confirmação.

### Assumptions

- O usuário faz manutenção APENAS em `~/.agents/skills/` (hub).
- Skills em agentes (`~/.claude/commands/`, `~/.gemini/tools/`, etc.) são sempre cópias do hub — nunca a versão original.
- Se o hash de uma skill difere entre hub e agente, o agente está desatualizado (pois toda edição é no hub).
- Fresh setup (hub vazio) é o único caso seguro para importação automática de todas as skills.

### Operational Ambiguities

- E se o usuário editar RARAMENTE skills em agentes (ex: claude-code commands customizados)? O centralize proposto vai sugerir importação, mas essas skills não deveriam ir pro hub?
- Conflito de nomes: e se existir `my-skill` no hub e uma `my-skill` completamente diferente num agente (mesmo nome, conteúdo totalmente diverso)?
- O passo pós-seleção "remover skills não importadas" — e se o usuário não quiser nem manter nem remover? Talvez queira mover para outro lugar?

---

## 2. Strategic Shaping Alternatives

### Alternativa A — Safe Mode com TUI (ESCOLHIDA)

Fluxo seguro com proteções progressivas:
- Fresh setup → importação automática
- Hub populado → TUI com checkbox (default vazio) + content comparison + passo pós-seleção
- Mais seguro, mais transparente, mas mais passos

### Alternativa B — Manifest-based Tracking

Manter manifesto em `~/.agents/skills/.hub-manifest.json` com hashs. Só importar se hash do agente divergir do manifesto. Sem TUI — apenas log.

- Vantagem: zero atrito, totalmente automático
- Desvantagem: assume que hub é sempre fonte da verdade, sem chance de correção manual
- Risco: se o manifesto corromper, decisões erradas podem ser tomadas

### Alternativa C — Separação total de comandos

`centralize` vira comando de setup apenas (uma vez). `sync` ou `distribute` novo comando exclusivamente hub→agentes.

- Vantagem: semântica clara, sem risco de reverse sync
- Desvantagem: quebra compatibilidade, exige migração de hábitos

### Por que A foi escolhida

A combinação de **safe TUI + content comparison + passo pós-seleção** ataca todas as arestas:
- **Resurrection** → resolvida (default vazio)
- **Versões divergentes** → resolvida (hash diff + aviso)
- **Órfãos persistentes** → resolvida (passo "manter ou remover")
- **Fresh setup** → resolvida (auto-import)
- **CI/script** → resolvida (flags `--yes` e `--import-all`)

---

## 3. Structured Shape Up Proposal

### 🎯 Problem

**Ator**: Usuário de agent-sync que mantém skills exclusivamente em `~/.agents/skills/`.

**Contexto**: O comando `agent-sync skills centralize` existe para consolidar skills de todos os agentes num único hub. Porém, ele também escaneia diretórios de agentes (`~/.claude/commands/`, `~/.gemini/tools/`, `~/.qwen/skills/`) e importa skills encontradas de volta para o hub — sem diferenciação entre "skill nova" e "cópia velha de skill deletada".

**Current Failure Modes**:
1. **Ressurreição de skills deletadas**: Usuário deleta skill do hub, rodar `centralize` traz ela de volta (estava num agente).
2. **Importação de cópias velhas**: Após `--distribute`, skills copiadas para agentes são re-importadas como se fossem novas.
3. **Destruição não-confirmada**: `_cleanup_agent_local_skills` apaga skills locais sem perguntar — skills que o usuário optou por não importar são perdidas.
4. **Zero visibilidade**: Usuário não tem ideia de quais skills existem em agentes mas não no hub.

**Impacto**: Perda de controle sobre o hub. O usuário não confia em rodar `centralize` no dia a dia.

### 💡 Solution

**Core Approach**: Adicionar 3 camadas de proteção ao comando `centralize`, com pipeline reordenado.

#### Pipeline Reordenado

O pipeline do `centralize()` é reestruturado para:

```
 1. Scan inventário (listar skills por agente, sem mover nada)
 2. Verificar hub vazio → se sim, fresh setup (importação automática)
 3. Sync do repo → hub (AGORA, após verificação de fresh setup)
 4. Se hub populado + sem órfãos → segue direto
 5. Se hub populado + com órfãos:
    a. --yes: skip todos (apenas log)
    b. --import-all: importa todos (comportamento antigo)
    c. Default: TUI de seleção
 6. Importar skills selecionadas (move/copy para hub)
 7. Passo pós-seleção: Keep ou Remove skills não-selecionadas
 8. Cleanup: SÓ skills que usuário mandou remover + skills importadas (move=True)
 9. configure_agents() (SEM cleanup destrutivo)
10. [--distribute] cópia para backup
```

#### 3 Camadas de Proteção

##### Layer 1 — TUI de seleção de órfãos (importação segura)

Layout: **Híbrido A + E** (definido na Interface Brainstorming):
- Tabela única com colunas: ID, checkbox, skill name, agentes, status
- Atalhos de teclado: `a`=all, `n`=none, números=toggle, `/`=filtro
- `⚠️ diverge` quando conteúdo difere entre agentes (via hash)
- **Nenhuma selecionada por padrão**
- Enter para confirmar

```
╭─ Skills órfãs encontradas em agentes ──────────────────────────────╮
│   Nenhuma selecionada — importe apenas o que quiser               │
│                                                                    │
│   #  Sel  Skill              Agentes          Status               │
│  ───────────────────────────────────────────────────────────────── │
│   1  [ ]  my-skill-a         claude, gemini   ✓                    │
│   2  [ ]  my-skill-b         claude           ✓                    │
│   3  [ ]  my-skill-c         gemini           ⚠️ diverge            │
│   4  [ ]  my-skill-d         qwen             ✓                    │
│                                                                    │
│   4 skills | 0 selecionadas | [/filter]                            │
│   [a]ll  [n]one  [Enter]=done                                      │
╰────────────────────────────────────────────────────────────────────╯
```

Regras:
- Se hub vazio (antes do sync): fresh setup, importa tudo automaticamente, sem TUI
- Se hub populado + sem órfãos: segue direto, sem TUI
- Se hub populado + com órfãos: aplica lógica acima
- `--yes`: skip todos os órfãos (apenas log)
- `--import-all`: importa todos sem perguntar (comportamento antigo)

##### Layer 2 — Content comparison entre cópias

Calcular hash MD5 recursivo do diretório de cada skill (função utilitária nova):
- Se hashes idênticos entre agentes → mostra `✓`
- Se hashes divergem entre agentes → mostrar `⚠️ diverge` na coluna Status
- Se todas as cópias divergem do hub → mostrar `⚠️ diverge from hub`
- Durante importação: se `--import-all`, importa da primeira ocorrência. Se TUI, o que o usuário selecionar.

##### Layer 3 — Pós-seleção: manter ou remover não-selecionadas

Após a TUI de seleção (ou skip via `--yes`):
- Skills não selecionadas permanecem intactas nos agentes
- Prompt: "O que fazer com as [N] skills não importadas?"
  - [K] Keep (default) — mantém nos agentes
  - [R] Remove — apaga dos agentes (não afeta o hub)
- Com `--yes`: default Keep, só loga
- Com `--import-all`: cleanup normal (skills deletadas de agentes conforme comportamento atual)
- Se Remove: skills apagadas dos agentes NÃO entram no hub
- Cleanup no pipeline SÓ executa para:
  - Skills que o usuário marcou como Remove
  - Skills que foram importadas com move=True (remoção da origem)
- `configure_agents()` NÃO chama `_cleanup_agent_local_skills()` — cleanup é gerenciado pelo pipeline, não pelo configure

#### Flags do comando

```
agent-sync skills centralize [--copy] [--push] [--distribute]
                           [--yes] [--import-all] [--dry-run]
```

- `--yes`: modo não-interativo. Skip todos órfãos + Keep não-selecionadas. Apenas log.
- `--import-all`: comportamento antigo (importa todos órfãos sem TUI).
- `--dry-run`: mostra TUI (se aplicável) ou resumo estático, sem alterar nada.
- Demais flags: mantidas (--copy, --push, --distribute).

### ⚠️ Dangers & Uncertainties

**Assumptions**:
- Usuário faz toda edição de skills apenas no hub (não em agentes)
- Skills em agentes são sempre cópias (não originais)
- Fresh setup = hub vazio (detectado ANTES do sync do repo)

**Undefined Rules**:
- Se o usuário editou skill no agente (não apenas copiou), hash difere do hub — o que isso significa?
- Conflito de nomes: skill no hub com mesmo nome de skill diferente em agente
- TUI em terminal não-interativo (pipe): fallback para erro claro sugerindo `--yes` ou `--import-all`

**Risks**:
- **Técnico (médio)**: Reordenar pipeline do `centralize()` requer mexer no core flow. Mudanças localizadas mas impactam fluxo principal.
- **Técnico (médio)**: TUI interativa com Rich não é trivial. Rich suporta Table/Panel, mas checkbox interativo + teclado requer `rich.live` + leitura de teclas.
- **UX (baixo)**: Fluxo de 3 camadas pode ser confuso se mal explicado. Mensagens CLI claras mitigam.
- **Adoção (baixo)**: `--yes` e `--import-all` cobrem usuários que não querem interação.
- **Rollback (baixo)**: Skills importadas vão para o hub (git tem histórico). Skills removidas de agentes são loss — por isso passo Keep/Remove é crítico.

### 🚫 Out of Scope

- **Não** mudar o fluxo de `push`/`pull` (skills continuam sendo sincronizadas com repo)
- **Não** adicionar novo comando (`sync`, `distribute`) — tudo dentro do `centralize` existente
- **Não** mexer em agentes com `method: native` (pi.dev, roocode, cursor) — cleanup não afeta eles
- **Não** implementar diff linha-a-linha de skills (hash MD5 recursivo é suficiente)
- **Não** adicionar merge automático de conteúdo divergente
- **Não** refatorar o `_configure_agents` flow

---

## 4. Resolved Gaps (Plan Critique)

### 🚨 B1 — Pipeline reordenado ✅
Scan separado em 2 fases: inventário (lista skills) → TUI (seleção) → import/copy (execução). Cleanup só após decisão do usuário. Ver "Pipeline Reordenado" na seção 3.

### 🚨 B2 — Fresh setup detection ✅
`_sync_from_repo()` movido para DEPOIS da verificação de hub vazio. A checagem conta skills em `~/.agents/skills/` ANTES do sync do repo.

### 🚨 B3 — Cleanup protegido ✅
`_cleanup_agent_local_skills()` removido de `configure_agents()`. Cleanup gerenciado pelo pipeline: só apaga skills que usuário mandou remover + skills importadas com move=True.

### 🟡 R3 — Hash MD5 recursivo ✅
Implementado como função utilitária nova em `skills.py`. Não depende de `distribute_to_all_agents`.

### 🟡 R4 — Conflito de nomes ✅
Tabela única (Híbrido A+E). Se mesma skill existe em múltiplos agentes com hash diferente, mostra `⚠️ diverge`. Importação da primeira ocorrência.

### 📝 M1 — TUI complexity ✅
Usar `rich.live` com loop de renderização + leitura de teclas para TUI interativa.

### 📝 M4 — Fallback não-interativo ✅
Se stdout não é TTY, erro claro: "Terminal não-interativo. Use --yes ou --import-all."

---

## 5. Interface Direction

Escolha confirmada: **Híbrido A + E** (ver interfaces_v1.md para propostas completas)
- Layout: tabela única (skill + agentes + status) — Proposta A
- Atalhos: `a`=all, `n`=none, números=toggle, `/`=filtro — Proposta E
- Indicador: `⚠️ diverge` para conteúdo divergente
- Pós-seleção: prompt separado `[K]eep | [R]emove` com default Keep
- Dry-run: badge `[DRY RUN]` no cabeçalho + resumo estático sem ações

---

## 6. Additional Scopes

### Scope A: Testes, Documentação e README

Após implementação do safe centralize:
- Revisar testes existentes em `tests/test_skills_logic.py` para cobrir novos cenários:
  - Fresh setup (hub vazio) → auto-import
  - Hub populado + órfãos → TUI (mockada)
  - `--yes` → skip todos
  - `--import-all` → comportamento antigo
  - Hash comparison entre cópias divergentes
  - Passo Keep vs Remove
  - Dry-run não modifica nada
  - Terminal não-interativo → fallback
- Atualizar README.md com:
  - Novas flags (`--yes`, `--import-all`, `--dry-run`)
  - Fluxo de segurança explicado
  - Exemplo de TUI
- Atualizar `skills/agent-sync/SKILL.md` com novos parâmetros

### Scope B: Padronização com DotAgents Protocol

Consolidar agent registry (`agent_registry.yaml`) com os standards definidos em https://dotagentsprotocol.com/:
- Verificar se campos como `method`, `config_dir`, `skills_dir_name` seguem convenções do protocolo
- Identificar gaps entre o registry atual e o protocolo
- Propor migrations necessárias
