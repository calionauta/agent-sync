---
title: "Publishing Agent Instructions (AGENTS.md, GEMINI.md, etc.)"
slug: "agents-publish"
date: "2026-05-14"
status: "draft"
version: 3
approved: true
approved_at: "2026-05-14T19:15:00-03:00"
approved_via: plannotator --gate
---

# Publishing Agent Instructions to Public Repositories

## Resolved Gaps (Plan Critique)

| # | Gap | Resolution |
|---|-----|------------|
| Q1 | Scanner de segurança | **Heurístico com regex patterns** (v1). Padrões para caminhos absolutos, tokens, comandos internos. Sem LLM externo. |
| Q2 | Estrutura de comando | **`agent-sync publish --agents\|--skills\|--all`** com umbrella UI. `skills publish` continua como alias para `--skills`. |
| Q3 | Escopo de agentes | **CLI + VS Code extensions**. Inclui roocode, cline, cursor, windsurf. |
| Q4 | Discovery mechanism | Reutilizar `BaseAgent` infrastructure de `sync.py` para escanear `config_patterns` dos agentes. |
| Q5 | Repo organization | `agents/<agent-name>/<file>` — estrutura aninhada. v1 implementa completa. |
| Q6 | Config persistence | `published_agents` como novo campo em `Config` (lista de `agent:filename`). |
| Q7 | CLI flags vs TUI | TUI interativa como default (espelha `skills publish`). Flags `--all`, `--dry-run`, `--repo <url>` disponíveis. |
| Q8 | AGENTS.md global | **Não existe "global"**. Todos são per-agent. O do pi.dev é o mais completo mas ainda per-agent. |

---

## 1. 🤔 Unanswered Questions and Unexplored Issues

### Unresolved Tensions

1. **Command naming vs mental model**: `publish --agents` vs `agents publish`. Compatibilidade retroativa vs clareza.

2. **Segurança vs utilidade**: AGENTS.md contém caminhos absolutos, comandos internos. Scanner heurístico alerta, usuário decide.

3. **Público vs privado**: Push/pull já sincroniza para repo PRIVADO. Publish vai para repo PÚBLICO. Propósitos diferentes.

4. **CLI + VS Code extensions**: Incluir todos agentes do registry com config_patterns. Complexidade adicionada mas cobertura completa.

### Hidden Assumptions

- Assumimos que usuários QUEREM publicar AGENTS.md
- Assumimos que o mesmo repo serve (skills + agents juntos)
- Assumimos que AGENTS.md não contém secrets — conteúdo é arbitrário

### Validation Unknowns

- Quantos usuários têm AGENTS.md customizado que vale publicar?
- Qual a proporção de AGENTS.md útil para outros vs muito específico?

### Missing Rules

- AGENTS.md do projeto (dentro de repositórios git) é diferente do AGENTS.md de configuração de agente
- Se AGENTS.md contém paths de servidor, publicar é arriscado

---

## 2. 🧭 Strategic Shaping Alternatives

### Alternative A: Expand skills publish (REJEITADO)

**Abordagem:** Colocar agentes na mesma TUI de skills.

**Rejeitado porque:** Quebra a expectativa do comando "skills publish". Arquivos .md de instrução não são skills.

### Alternative B: New command agents publish (REJEITADO)

**Rejeitado porque:** Decidimos pelo umbrella `publish` com flags (Alternative C).

### Alternative C: Umbrella publish com flags (ESCOLHIDO)

**Abordagem:** 
- `agent-sync publish` → umbrella UI (mostra categorias, seleção)
- `agent-sync publish --agents` → publicação de agent instructions
- `agent-sync publish --skills` → publicar skills (alias para comando atual)
- `agent-sync publish --all` → ambos na mesma execução
- `agent-sync skills publish` → continua funcionando (compatibilidade retroativa)

**O que sacrifica:** Mais flags para aprender (mas preserva compatibilidade).

**Trade-offs:**
- ✅ Compatibilidade retroativa total
- ✅ Estrutura escalável para futuras categorias
- ✅ Um entry point para todos os publishes
- ✅ Separação clara via flags

---

## 3. 📝 Structured Shape Up Proposal

### Problem

**Affected Actors:** Usuários de agent-sync que criam skills e configuram agentes.

**Context:** Hoje, um usuário pode:
1. Sincronizar skills + configs + AGENTS.md via `push` para repo **privado** (backup multi-máquina)
2. Publicar skills seletivamente via `skills publish` para repo **público** (compartilhamento comunitário)

O que NÃO pode fazer:
- Publicar AGENTS.md, GEMINI.md, SYSTEM.md publicamente
- Compartilhar suas "instruções de agente" com a comunidade

**Impact:** O ecossistema de compartilhamento é incompleto. Skills são publicáveis, mas as instruções que orquestram essas skills ficam presas no escopo privado.

---

### Solution

**Core Approach:** Adicionar **`agent-sync publish`** como umbrella command com flags **`--agents`**, **`--skills`**, **`--all`**.

**Nomenclatura:**
- **Não existe "global AGENTS.md"**. Todos são per-agent.
- O AGENTS.md do pi.dev é o mais completo (governa configuração integral), mas ainda é per-agent.
- A organização no repo usa o nome do agente como subdiretório: `agents/<agent-name>/<file>`

**Architecture:**

```
agent-sync publish [--agents|--skills|--all] [flags]

agent-sync publish           # default: --all (skills + agents)
agent-sync publish --agents  # publicar agent instructions
agent-sync publish --skills  # publicar skills (mantém compatibilidade)
agent-sync publish --all     # ambos na mesma execução
```

**Default é `--all`**: `publish` sem flags publica ambos (skills + agents instructions).

**Nomenclatura:**
- **Não existe "global AGENTS.md"**. Todos são per-agent.
- O AGENTS.md do pi.dev é o mais completo (governa configuração integral), mas ainda é per-agent.
- A organização no repo usa o nome do agente como subdiretório: `agents/<agent-name>/<file>`

**Linchpins:**

1. **Discovery de arquivos**: Varrer `config_patterns` de cada agente no `agent_registry.yaml`. Usar `BaseAgent` de `sync.py` como base. Arquivos .md nos diretórios de config de cada agente.

2. **Scanner de segurança (heurístico)**: Regex patterns para detectar:
   - Caminhos absolutos: `/Users/`, `/home/`, `C:\`, `/root/`
   - Tokens: `sk-`, `api_`, `secret`, `token`, `key`, `ghp_`, `gho_`
   - Comandos internos: `/skill:`, `/ctx-`, `ctx_batch_execute`, `ctx_search`
   - Server paths: `server.`, `.renatocaliari.com`

3. **Seleção interativa (TUI)**: 
   - Rich Table mostrando agentes + arquivos
   - Indicadores ⚠️ para arquivos com conteúdo sensível
   - Toggle de seleção

4. **Persistência**: Salvar `published_agents` no config (formato: `["pi.dev:AGENTS.md", "gemini-cli:GEMINI.md"]`)

5. **Organização no repo**: 
   ```
   <repo>/
   ├── skills/          # (existente)
   ├── agents/          # (novo)
   │   ├── pi.dev/
   │   │   ├── AGENTS.md      # per-agent (o mais completo do ecossistema)
   │   │   └── SYSTEM.md
   │   ├── gemini-cli/
   │   │   ├── AGENTS.md
   │   │   └── GEMINI.md
   │   ├── opencode/
   │   │   ├── AGENTS.md
   │   │   └── SYSTEM.md
   │   ├── claude-code/
   │   │   ├── AGENTS.md
   │   │   └── CLAUDE.md
   │   ├── qwen-code/
   │   │   ├── AGENTS.md
   │   │   └── output-language.md
   │   ├── roocode/AGENTS.md
   │   ├── cline/AGENTS.md
   │   ├── cursor/AGENTS.md
   │   └── windsurf/AGENTS.md
   └── README.md       # (atualizado)
   ```
   **Nota:** Não existe "AGENTS.md global". Todos são per-agent.

**Workflows:**

5. `agent-sync publish` (sem flags) → assume `--all` (publica skills + agents)
5. `agent-sync publish --skills` → publicar skills
5. `agent-sync publish --agents` → publicação de agent instructions
5. `agent-sync publish --all` → publica todos sem TUI (non-interactive)
5. `agent-sync publish --agents --dry-run` → preview sem executar
5. `agent-sync publish --agents --repo <url>` → override do repo

**Critical Constraints:**

- **Só publicar arquivos .md** — AGENTS.md, SYSTEM.md, GEMINI.md, CLAUDE.md, output-language.md
- **NUNCA publicar .json, .yaml, .env** — esses continuam só no push/pull privado
- **Scanner heurístico** — alertar se detectar caminhos/absolutos ou secrets
- **Persistir seleção** — salvar `published_agents` no config
- **Compatibilidade retroativa**: `skills publish` continua funcionando como alias para `publish --skills`

---

### Risks and Uncertainties

#### 🔴 CRITICAL — Content Security

**Risco:** AGENTS.md contém caminhos absolutos, comandos internos. Publicar sem sanitização expõe informação do ambiente.

**Mitigação:** Scanner heurístico antes do push. Interface alertando "⚠️ Este arquivo contém caminhos absolutos. Revise antes de publicar."

**Residual:** Scanner é heurístico — pode não pegar tudo. Falso positivo também irrita.

#### 🟡 HIGH — Discovery Gap

**Risco:** Usuário que só descobre `skills publish` pode nunca saber que `publish --agents` existe.

**Mitigação:** Cross-reference na UI de ambos os comandos.

#### 🟠 MED — AGENTS.md de Projeto

**Risco:** Cada projeto tem seu próprio AGENTS.md (no repositório do projeto). Publicar seria confuso.

**Mitigação:** Só escanear AGENTS.md nos diretórios de config de agentes (`~/.pi/agent/`, `~/.gemini/`, etc.). Ignorar AGENTS.md dentro de projetos git.

---

### Out of Scope

1. **Publicar AGENTS.md de projetos** — AGENTS.md dentro de repositórios git de projetos não entra no escopo.

2. **Edição inline de AGENTS.md** — Na v1, usuário edita manualmente se precisar sanitizar.

3. **Publicar custom agents (.md files em agents directories)** — Foco é em AGENTS.md/SYSTEM.md/etc. Custom agents ficam para outro escopo.

4. **Unificar `skills publish` e `agents publish`** — feito via umbrella (v1). Breaking changes são evitados.

5. **Publicar extra_paths** (prompts, themes, extensions) — Fora de escopo. Só arquivos de instrução.

6. **Transformação automática de caminhos** — Substituir `/Users/user/` por `$HOME/` automaticamente é arriscado. Deferido.

7. **Repositório separado para instructions** — O usuário pode customizar via `--repo`, mas o default é o mesmo repo das skills.

---

## 4. 📋 Implementation Scope for Tech Planning

### Scope 1: publish.py refactoring
- Criar `publish_agents()` parallel to `publish_skills()`
- Criar `PublishManager` ou refatorar para usar dispatch pattern
- Reutilizar engine de git (init/commit/push) existente

### Scope 2: agent discovery
- Criar função que varre `config_patterns` do registry
- Localiza arquivos .md nos diretórios de config de cada agente
- Retorna lista de `{"agent": "...", "filename": "...", "path": "..."}`

### Scope 3: security scanner
- Criar `security_scanner.py` com regex patterns
- Funções: `scan_file(path) -> {"safe": bool, "issues": [...]}`
- Padrões: abs paths, tokens, internal commands, server paths

### Scope 4: CLI integration
- Adicionar `publish` command em `cli.py`
- Subcommands: `--agents`, `--skills`, `--all`
- `skills publish` vira alias para `publish --skills`
- Flags: `--all`, `--dry-run`, `--repo`, `--simple`

### Scope 5: TUI components
- Reutilizar Rich table pattern de `skills publish`
- Adicionar security panel component
- Cross-reference notices

### Scope 6: config persistence
- Adicionar `published_agents` em `Config`
- Salvar/load seleção como lista de strings

---

## 5. 🎯 Acceptance Criteria

### AC1: Discovery
- [ ] Detecta todos os arquivos .md de instrução (config_patterns) em todos os agentes do registry
- [ ] Ignora arquivos que não existem localmente
- [ ] Mostra caminho completo na UI

### AC2: Security Scanner
- [ ] Detecta caminhos absolutos (`/Users/`, `/home/`, `C:\`, `/root/`)
- [ ] Detecta tokens/keys (`sk-`, `api_`, `secret`, `ghp_`)
- [ ] Detecta comandos internos (`/skill:`, `/ctx-`)
- [ ] Flag UI mostra ⚠️ para arquivos com issues

### AC3: TUI Interaction
- [ ] Rich table com seleção toggle
- [ ] Security panel aparece após seleção
- [ ] Opções: editar, skip, continuar
- [ ] Cross-reference notices entre skills/agents

### AC4: Publish Execution
- [ ] Clona repo existente (se existir) antes de push
- [ ] Cria `agents/` directory structure
- [ ] Copia arquivos selecionados
- [ ] Git add/commit/push com mensagem descritiva

### AC5: Persistence
- [ ] Salva seleção de agentes publicados no config
- [ ] Na próxima execução, mostra seleção salva como default
- [ ] Persiste repo URL em `publish.yaml`

### AC6: CLI Flags
- [ ] `publish --agents --all` seleciona todos
- [ ] `publish --agents --dry-run` mostra preview
- [ ] `publish --agents --repo <url>` override
- [ ] `publish` (sem args) abre umbrella UI

### AC7: Compatibility
- [ ] `skills publish` continua funcionando
- [ ] Nenhum breaking change para scripts existentes
- [ ] `publish --skills` funciona como alias