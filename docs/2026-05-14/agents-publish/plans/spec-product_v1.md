---
title: "Publishing Agent Instructions (AGENTS.md, GEMINI.md, etc.)"
slug: "agents-publish"
date: "2026-05-14"
status: "draft"
version: 1
approved: false
---

# Publishing Agent Instructions to Public Repositories

## 1. 🤔 Unanswered Questions and Unexplored Issues

### Unresolved Tensions

1. **Command naming vs mental model**: `agent-sync skills publish` publica skills. AGENTS.md não é skill. Colocar no mesmo comando quebra a expectativa.

2. **Segurança vs utilidade**: AGENTS.md contém caminhos absolutos (`/Users/cali/...`), comandos internos (`/skill:cali-product-planner`), caminhos de servidor SSH. Publicar raw é arriscado. Mas sanitizar automaticamente é complexo e pode quebrar instruções.

3. **Público vs privado**: O push/pull já sincroniza AGENTS.md para o repo PRIVADO. O publish iria para o repo PÚBLICO. Esses arquivos SERVEM propósitos diferentes em cada contexto.

4. **Global vs per-agent**: O AGENTS.md global (pi) contém regras operacionais gerais. GEMINI.md contém architectural mandates específicos do Gemini. SYSTEM.md do opencode contém instruções de skill. Cada um tem audiência e sensibilidade diferentes.

5. **README.md do repo público**: Atualmente descreve skills. Se agent instructions entrarem, o README precisa evoluir para um diretório de "ferramentas do ecossistema de agentes".

### Hidden Assumptions

- Assumimos que usuários QUEREM publicar AGENTS.md — talvez poucos queiram
- Assumimos que o mesmo repo serve — talvez o usuário prefira dois repos separados (skills + instructions)
- Assumimos que AGENTS.md não contém secrets — na prática, o conteúdo é arbitrário (markdown livre)
- Assumimos que skills e instruções de agente são coisas diferentes — do ponto de vista do usuário, talvez tudo seja "coisas que configuram meu agente"

### Validation Unknowns

- Quantos usuários têm AGENTS.md customizado que vale publicar?
- Qual a proporção de AGENTS.md útil para outros vs muito específico do setup individual?
- Os usuários entendem a diferença entre "skill" e "agent instruction"?

### Missing Rules

- AGENTS.md do projeto (dentro do repo git do projeto) é diferente do AGENTS.md global (fora do projeto)?
- Se um AGENTS.md referencia um path absoluto, devemos sugerir sanitarizar?
- Se AGENTS.md contém paths de servidor (ex: SERVER_GUIDE.md), publicar é seguro?

---

## 2. 🧭 Strategic Shaping Alternatives

### Alternative A: Same Command, Same Repo

**Abordagem:** Expandir `agent-sync skills publish` para incluir uma seção "Agent Instructions" na TUI de seleção. O mesmo comando publica skills + agent instructions no mesmo repo público.

**O que sacrifica:** Clareza de escopo. O comando faz mais de uma coisa. O nome "skills publish" fica impreciso.

**Trade-offs:**
- ✅ Uma única interface para o usuário aprender
- ✅ Skills e instructions ficam juntas (orquestração natural)
- ❌ Comando com nome errado fazendo algo que não está no nome
- ❌ Usuário pode não perceber que AGENTS.md também é publicável
- ❌ Risco de vazar acidentalmente o AGENTS.md global sem revisão

### Alternative B: New Command, Same Repo

**Abordagem:** Novo comando `agent-sync agents publish` que publica AGENTS.md, GEMINI.md, SYSTEM.md, CLAUDE.md etc. no MESMO repo público que skills, mas em diretório separado (`agents/`).

**O que sacrifica:** Simplicidade (mais um comando). Coerência com o que já existe (skills publish vs agents publish).

**Trade-offs:**
- ✅ Nome claro: "agents publish" publica configurações de agentes
- ✅ Espelha a estrutura existente do push (`--skills-only`, `--configs-only`, `--agents-only`)
- ✅ Mesmo repo = skills + instructions juntos para orquestração
- ✅ Reaproveita a engine de publish (git init/commit/push)
- ❌ Um comando novo para aprender
- ❌ Possível confusão: "agentes" significa o quê exatamente?

### Alternative C: Rename/Unify to Top-Level `publish`

**Abordagem:** Novo comando `agent-sync publish` que substitui `skills publish`. Oferece TUI com categorias: Skills, Agent Instructions. `skills publish` vira alias/deprecation.

**O que sacrifica:** Compatibilidade retroativa (skills publish muda). Simplicidade (refatoração maior).

**Trade-offs:**
- ✅ Entry point único para PUBLICAÇÃO pública
- ✅ Categorias claras na TUI: usuário vê o que pode publicar
- ✅ Escalável: outras categorias no futuro (extensions, prompts, themes)
- ❌ Breaking change para scripts que usam `skills publish`
- ❌ Maior esforço de refatoração

### Alternative D: Same Command, Separate Repo

**Abordagem:** Expandir `skills publish` para publicar agent instructions, mas em REPO SEPARADO do usuário (ex: `agent-sync-public-instructions`).

**O que sacrifica:** Coerência (dois repos para gerenciar). Conveniência (o usuário tem que lembrar onde cada coisa está).

**Trade-offs:**
- ✅ Skills e instructions em isolamento conceitual completo
- ✅ Cada repo tem propósito claro (skills vs instructions)
- ❌ Duas URLs, dois clones, dois updates
- ❌ Skills e instructions se orquestram mutuamente — separar fisicamente dificulta descobrimento
- ❌ Mais setup para o usuário

---

## 3. 📝 Structured Shape Up Proposal

### Problem

**Affected Actors:** Usuários de agent-sync que criam skills e configuram agentes.

**Context:** Hoje, um usuário pode:
1. Sincronizar skills + configs + AGENTS.md via `push` para repo **privado** (backup multi-máquina)
2. Publicar skills seletivamente via `skills publish` para repo **público** (compartilhamento comunitário)

O que NÃO pode fazer:
- Publicar AGENTS.md, GEMINI.md, SYSTEM.md publicamente — esses arquivos nunca saem do repo privado
- Compartilhar suas "instruções de agente" com a comunidade
- Separar o que é instrução pessoal (que fica privado) do que é instrução genérica útil (que poderia ser público)

**Impact:** O ecossistema de compartilhamento é incompleto. Skills são publicáveis, mas as instruções que orquestram essas skills — os AGENTS.md que dizem "dispare o product-planner antes de codar" — ficam presas no escopo privado. A comunidade não pode ver como os power users configuram seus agentes.

**Current Failure Mode:** Se um usuário quer compartilhar como configurou o Gemini para orquestrar suas skills, ele precisa manualmente copiar/colar o GEMINI.md para um README ou criar um gist. Não há fluxo integrado.

---

### Solution

**Core Approach:** Adicionar **`agent-sync agents publish`** como novo comando, publicando agent instructions no MESMO repo público das skills, em diretório `agents/`.

**Why this approach:**
- `skills publish` é maduro e tem TUI, segurança, persistência de seleção — não mexer nele
- `agents publish` espelha naturalmente `skills publish`: mesma engine, mesma UX, mesmo repo
- Skills e instructions moram no mesmo repo porque se orquestram — um AGENTS.md pode referenciar skills
- O usuário mantém a escolha de qual repo público: se quiser tudo junto (default), se quiser separado (custom repo URL)

**Linchpins:**

1. **Descoberta de arquivos publicáveis**: Varrer `config_patterns` de cada agente no `agent_registry.yaml`, localizar AGENTS.md, SYSTEM.md, GEMINI.md, CLAUDE.md nos diretórios de config de cada agente.

2. **Sanitização de segurança**: Antes de publicar, escanear conteúdo para detectar:
   - Caminhos absolutos (`/Users/`, `/home/`, `C:\`)
   - Tokens, chaves, secrets
   - Paths de servidor SSH
   - Alertar o usuário e sugerir sanitização manual

3. **Seleção interativa**: TUI apresentando:
   - AGENTS.md global (se detectado)
   - Instruções per-agent (gemini, opencode, claude, pi, qwen)
   - Cada um com indicador de segurança (⚠️ se detectar conteúdo sensível)

4. **Organização no repo**: 
   ```
   <repo>/
   ├── skills/          # (existente)
   ├── agents/          # (novo)
   │   ├── global/
   │   │   └── AGENTS.md
   │   ├── gemini/
   │   │   ├── AGENTS.md
   │   │   └── GEMINI.md
   │   ├── opencode/
   │   │   ├── AGENTS.md
   │   │   └── SYSTEM.md
   │   └── ...
   └── README.md       # (atualizado)
   ```

**Workflows:**

1. `agent-sync agents publish` → escaneia, mostra TUI, confirma, publica
2. `agent-sync agents publish --all` → publica todos (non-interactive)
3. `agent-sync agents publish --dry-run` → mostra o que seria publicado sem executar
4. `agent-sync agents publish --repo <url>` → override do repo

**Critical Constraints:**

- **Só publicar arquivos .md** — AGENTS.md, SYSTEM.md, GEMINI.md, CLAUDE.md, e futuros config_patterns .md
- **NUNCA publicar .json, .yaml, .env** — esses continuam só no push/pull privado
- **Sempre sanitizar** — alertar se detectar caminhos absolutos ou secrets
- **Persistir seleção** — assim como `published_skills`, salvar `published_agents` no config

---

### Risks and Uncertainties

#### 🔴 CRITICAL — Content Security

**Risco:** AGENTS.md contém caminhos absolutos (`/Users/cali/...`), comandos internos (`/skill:cali-product-planner`), paths de servidor SSH. Publicar sem sanitização expõe informação do ambiente do usuário.

**Mitigação:** Scanner de segurança antes do push que detecta padrões. Interface alertando "⚠️ Este arquivo contém caminhos absolutos. Revise antes de publicar."

**Residual:** Scanner é heurístico — pode não pegar tudo. Falso positivo também irrita.

#### 🟡 HIGH — Product Confusion

**Risco:** "Publish agents" pode ser interpretado como "publicar meus custom agents" (arquivos .md de agentes em `~/.config/opencode/agents/`) ao invés de "publicar instruções de agente" (AGENTS.md).

**Mitigação:** Nomear comando como `instructions publish` ou `agent-instructions publish` ao invés de `agents publish`.

**Decisão a tomar:** Nome do comando.

#### 🟡 HIGH — Discovery Gap

**Risco:** Usuário que só descobre `skills publish` pode nunca saber que `agents publish` existe. Ou vice-versa.

**Mitigação:** Na TUI de `skills publish` e de `agents publish`, mostrar nota "💡 Quer publicar também [skills/agent instructions]? Use `agent-sync [agents/skills] publish`."

**Decisão a tomar:** Cross-reference na UI ou unificar no publish único.

#### 🟠 MED — AGENTS.md do Projeto

**Risco:** Cada projeto tem seu próprio AGENTS.md (no repositório do projeto). Publicar no repo público de agent-sync seria duplicação ou fora de contexto.

**Mitigação:** Só escanear AGENTS.md nos diretórios de config de agentes (~/.pi/agent/, ~/.gemini/, ~/.config/opencode/, ~/.claude/). Ignorar AGENTS.md dentro de projetos.

#### 🟠 MED — Sanitização sem ferramenta de "edit before publish"

**Risco:** Se o scanner detecta conteúdo sensível, a única ação do usuário é "cancelar e editar manualmente". Não há uma ferramenta de "sanitizar automaticamente".

**Mitigação:** Na v1, alertar e sugerir edição manual. Na v2+, permitir edição inline na TUI ou gerar versão sanitizada automaticamente.

#### 🟢 LOW — Clones do repo

**Risco:** Se o usuário já publicou skills, o repo existe com skills/ e README. Adicionar agents/ requer git pull antes do push (ou force push).

**Mitigação:** Clonar repo existente em vez de init fresh, adicionar agents/ ao tree, commit + push (não force).

---

### Out of Scope

1. **Publicar AGENTS.md de projetos** — AGENTS.md dentro de repositórios git de projetos não entra no escopo. Cada projeto gerencia seu próprio AGENTS.md via versionamento normal.

2. **Edição inline de AGENTS.md** — Na v1, usuário edita manualmente se precisar sanitizar. Sem editor embutido.

3. **Publicar custom agents (.md files em agents directories)** — Foco é em AGENTS.md/SYSTEM.md/GEMINI.md/CLAUDE.md. Custom agents (files em `~/.config/opencode/agents/`) ficam para outro escopo.

4. **Unificar `skills publish` e `agents publish` em `publish`** — Deferido para v2. Na v1, comandos separados.

5. **Publicar extra_paths** (prompts, themes, extensions) — Fora de escopo. Só arquivos de instrução.

6. **Transformação automática de caminhos** — Substituir `/Users/user/` por `$HOME/` automaticamente parece óbvio mas é arriscado (falsos positivos). Deferido.

7. **Repositório separado para instructions** — O usuário pode customizar via `--repo`, mas o default é o mesmo repo das skills.
