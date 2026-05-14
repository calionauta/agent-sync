# Current State: AGENTS.md & Per-Agent Config Publishing

> Mapeamento completo do fluxo de publicacao de AGENTS.md e arquivos de configuracao per-agent no agent-sync.
> Gerado em: 2026-05-14

---

## 1. Fluxo Completo de publish.py

**Arquivo:** `src/agent_sync/publish.py` (linhas 1-299)

### 1.1 Skill Selection Flow

```
get_available_skills() → scan ~/.agents/skills/
    ↓
interactive_selection() OR saved selection from Config.published_skills
    ↓
Selected skills are copied to temp directory
    ↓
README.md + .gitignore generated
    ↓
git init → git add → git commit → git push --force to public repo
```

**Detalhamento:**

1. **`get_available_skills()`** (linha 31): Escaneia `~/.agents/skills/` — considera **qualquer item** (diretorio ou arquivo .md/.py/.sh) como publicavel. Nao ha filtro por SKILL.md.

2. **Selecao interativa** (linhas 54-134): TUI com tabela que permite toggle de skills. Suporta `all`/`none`/numeros individuais.

3. **Persistencia de selecao**: Salva em `config.published_skills` que persiste em `~/.config/agent-sync/config.yaml` como `published_skills: [list]`.

4. **Execucao** (linhas 249-279):
   - Cria tempdir
   - Copia cada skill selecionada (shutil.copytree para dirs, shutil.copy2 para files)
   - Gera README.md + .gitignore
   - git init → add → commit → push --force para origin/main

### 1.2 Seguranca em publish.py

- Gitignore no repo publicado: `*.json`, `*.yaml`, `*.yml`, `.env`, `*auth*`, `*token*`, `*key*`, `*secret*`, `*credentials*`
- Security warning panel exibe o que sera e nao sera publicado (linhas 193-214)
- Apenas skills de `~/.agents/skills/` sao publicadas — config files **NAO** sao incluidos

### 1.3 Limite: publish.py publica apenas skills

Publicar AGENTS.md ou arquivos de configuracao per-agent **nao existe**. O fluxo de publish:
- So le de `~/.agents/skills/`
- So copia skills selecionadas
- Nao referencia `config_patterns`, `extra_paths`, nem arquivos de configuracao per-agent

---

## 2. Onde AGENTS.md e Arquivos Per-Agent Sao Referenciados

### 2.1 agent_registry.yaml — Declaracao de config_patterns

Cada agente declara quais padroes de arquivo sincronizar:

| Agente | config_patterns | Extra |
|--------|----------------|-------|
| **opencode** | `*.json`, `*.jsonc`, `AGENTS.md`, `SYSTEM.md` | — |
| **claude-code** | `*.json`, `AGENTS.md`, `SYSTEM.md`, `CLAUDE.md` | — |
| **gemini-cli** | `*.json`, `AGENTS.md`, `SYSTEM.md`, `GEMINI.md` | — |
| **pi.dev** | `*.json`, `*.yaml`, `AGENTS.md`, `SYSTEM.md` | extra_paths extenso |
| **qwen-code** | `*.json`, `AGENTS.md`, `SYSTEM.md`, `output-language.md` | — |
| **roocode** | `*.yaml`, `*.json`, `*.md` | extra_paths: rules |
| **cline** | `*.md`, `*.json` | — |
| **cursor** | `*.md` | — |
| **windsurf** | `*.md` | — |

**Arquivos Per-Agent na pratica:**
- `AGENTS.md` — declarado para TODOS os agentes CLI (opencode, claude-code, gemini-cli, pi.dev, qwen-code)
- `SYSTEM.md` — igualmente abrangente
- `GEMINI.md` — apenas gemini-cli
- `CLAUDE.md` — apenas claude-code
- `output-language.md` — apenas qwen-code

### 2.2 Onde config_patterns e Usado no Codigo

**Unico uso:** `sync.py` linha 599, dentro de `SyncManager._stage_agent_configs()`:

```python
patterns = agent.data.get("config_patterns", [agent.config_filename])

# 1. Remove config files from repo that no longer exist locally
for pattern in patterns:
    for repo_config in agent_config_dir.glob(pattern):
        ...

# 2. Copy current config files to repo
for pattern in patterns:
    for config_file in agent.config_path.parent.glob(pattern):
        ...
```

**Como funciona:**
- `config_path.parent` = diretorio de config do agente (ex: `~/.config/opencode/`)
- Faz `glob(pattern)` com cada pattern naquele diretorio
- Copia os arquivos que match para `configs/<agent-name>/` no repo
- **Nao usado em nenhum outro lugar** (nem pull, nem publish, nem centralize)

---

## 3. Como Config Patterns Sao Usados no Fluxo Sync (Push/Pull)

### 3.1 Push (stage)

O fluxo de `agent-sync push` passa por:

```
cli.py push → SyncManager.push()
    ↓
push() chama _stage_all_agent_files()
    ↓
chama _stage_agent_configs() UMA VEZ para todos os agentes
    ↓
Para cada agente:
  1. Pega config_patterns do registry
  2. Remove do repo arquivos que sumiram localmente
  3. Copia arquivos do config_dir que match o pattern para configs/<agent>/ no repo
  4. Processa extra_paths (pi.dev especial, outros generico)
    ↓
Depois: _stage_skills() + _stage_agents()
```

**Importante:** `config_patterns` define quais arquivos sao copiados do diretorio de config do agente para o repo. AGENTS.md, SYSTEM.md, GEMINI.md, CLAUDE.md entram nesse fluxo **como arquivos de config**, nao como skills.

### 3.2 Pull (restore)

```
cli.py pull → SyncManager.pull()
    ↓
_apply_synced_configs()
    ↓
Para cada agente:
  source = repo/configs/<agent-name>/*
  dest = agent.config_path.parent/
  shutil.copy2 for each file
  ↓
Restaura extra_paths (pi.dev primeiro, depois generico)
```

**Notavel:** No pull, `_apply_synced_configs()` faz `glob("*")` no diretorio inteiro (`synced_config_dir`), **ignorando config_patterns**. Ele restaura tudo que esta no diretorio do repo independente do pattern original. Isso significa que se um arquivo foi adicionado manualmente ao repo, ele sera restaurado mesmo sem estar no config_patterns.

### 3.3 O que e sincronizado

Quando `agent-sync push` executa completo (`--skills-only`, `--configs-only`, `--agents-only` nao setados):

1. **Configs**: Arquivos que match `config_patterns` + `extra_paths`
2. **Skills**: Diretorios/arquivos de `~/.agents/skills/` + extension skills
3. **Custom Agents**: `.md` files de agents directories (project + global)

---

## 4. Relacao extra_paths vs Skills

### 4.1 pi.dev extra_paths

Definido em `agent_registry.yaml` (linhas 79-97), `extra_paths` do pi.dev mapeia:

```
extensions:       ~/.pi/agent/extensions, ~/.pi/extensions
prompts:          ~/.pi/agent/prompts, ~/.pi/prompts  
themes:           ~/.pi/agent/themes, ~/.pi/themes
bin:              ~/.pi/agent/bin
git:              ~/.pi/agent/git
lsp:              ~/.pi/agent/lsp-settings.json
models:           ~/.pi/agent/models.json
global_extensions: ~/.pi/extensions
global_prompts:    ~/.pi/prompts
global_skills_local: ~/.pi/skills
global_themes:     ~/.pi/themes
pyrightconfig:    ~/.pi/pyrightconfig.json
```

**Tratamento especial no codigo:**

- **`BaseAgent`** (agents/base.py linhas 128-179): Cada chave vira uma property (ex: `extensions_paths`, `prompts_paths`, `bin_paths`, etc.)
- **`_stage_pi_extra_paths`** (sync.py linha 646): Copia cada categoria para `configs/pi.dev/<categoria>/` no repo
- **`_restore_pi_extra_paths`** (sync.py linha 712): Restaura de volta do repo
- **roocode tambem tem extra_paths**: `rules: ~/.roo/rules/`

### 4.2 Como pi.dev trata AGENTS.md vs skills

- **AGENTS.md**: tratado como config file via `config_patterns` → sincronizado como `configs/pi.dev/AGENTS.md`
- **Skills** (`~/.pi/agent/skills/`): tratado como skills via `_stage_skills()` → `skills/` no repo
- **global_skills_local** (`~/.pi/skills`): tratado como extra_path → `configs/pi.dev/global_skills/` no repo

**Separacao clara:** AGENTS.md e skills sao tratados por caminhos completamente diferentes no codigo. AGENTS.md nao tem relacao com publish nem com o fluxo de skills.

---

## 5. Logica Existente de Publish de Configs vs Skills

### 5.1 Publish de configs: NAO EXISTE

O comando `agent-sync skills publish` (cli.py linha ~340 → publish.py) **so publica skills**. Nao ha:
- Comando `agent-sync configs publish`
- Comando `agent-sync publish --configs`
- Nenhuma logica que publique AGENTS.md ou arquivos per-agent

### 5.2 Publish de skills: EXISTE

Fluxo completo:
```
agent-sync skills publish
  → cli.py: publish command
  → publish_skills() in publish.py
  → Scan ~/.agents/skills/
  → Interactive TUI selection
  → Copy selected skills to temp
  → git push --force to public repo
```

### 5.3 Separacao conceitual

O projeto tem DOIS repositorios possiveis:

| Repo | Conteudo | Visibilidade | Comando |
|------|----------|-------------|---------|
| **agent-sync-private-configs** | Configs + skills + agents | Privado | push/pull |
| **agent-sync-public-skills** | Apenas skills selecionadas | Publico | skills publish |

Skills sao a unica ponte entre os dois. AGENTS.md e configs **nunca** vao para o repo publico.

---

## 6. Fluxo de Push com AGENTS.md

### 6.1 Push completo

```
agent-sync push (sem flags)
  ↓
_stage_all_agent_files()
  ↓
_stage_agent_configs()
  ↓
Para opencode: glob("*.json"), glob("*.jsonc"), glob("AGENTS.md"), glob("SYSTEM.md")
  em ~/.config/opencode/
  → copia AGENTS.md para configs/opencode/AGENTS.md no repo
  ↓
Para claude-code: glob("*.json"), glob("AGENTS.md"), glob("SYSTEM.md"), glob("CLAUDE.md")
  em ~/.claude/
  → copia AGENTS.md para configs/claude-code/AGENTS.md no repo
  → copia CLAUDE.md para configs/claude-code/CLAUDE.md no repo
  ↓
Para gemini-cli: glob("*.json"), glob("AGENTS.md"), glob("SYSTEM.md"), glob("GEMINI.md")
  em ~/.gemini/
  → copia AGENTS.md para configs/gemini-cli/AGENTS.md no repo
  → copia GEMINI.md para configs/gemini-cli/GEMINI.md no repo
  ↓
Para pi.dev: glob("*.json"), glob("*.yaml"), glob("AGENTS.md"), glob("SYSTEM.md")
  em ~/.pi/agent/
  → copia AGENTS.md para configs/pi.dev/AGENTS.md no repo
  + extra_paths: extensions, prompts, themes, bin, git, lsp, models, ...
  ↓
_stage_skills()
  → copia skills de ~/.agents/skills/ + extensions para skills/ no repo
  ↓
_stage_agents()
  → copia .md files de agents dirs para agents/ no repo
```

### 6.2 Importante: AGENTS.md e tratado como config, nao como skill

- Sincronizado via `_stage_agent_configs()` → `configs/<agent>/AGENTS.md`
- Restaurado via `_apply_synced_configs()` → `~/.config/opencode/AGENTS.md`
- **Nao** vai para `~/.agents/skills/` (a menos que o usuario manualmente copie)
- **Nao** e publicado via `skills publish`

### 6.3 Estrutura no repo apos push

```
repo/
├── configs/
│   ├── opencode/
│   │   ├── opencode.json
│   │   └── AGENTS.md          ← via config_patterns
│   ├── claude-code/
│   │   ├── settings.json
│   │   ├── AGENTS.md
│   │   ├── SYSTEM.md
│   │   └── CLAUDE.md
│   ├── gemini-cli/
│   │   ├── settings.json
│   │   ├── AGENTS.md
│   │   ├── SYSTEM.md
│   │   └── GEMINI.md
│   ├── pi.dev/
│   │   ├── settings.json
│   │   ├── AGENTS.md
│   │   ├── SYSTEM.md
│   │   ├── extensions/
│   │   ├── prompts/
│   │   ├── themes/
│   │   ├── bin/
│   │   ├── lsp/lsp-settings.json
│   │   ├── models/models.json
│   │   ├── global_skills/
│   │   └── ...
│   └── qwen-code/
│       ├── settings.json
│       ├── AGENTS.md
│       └── output-language.md
├── skills/
│   ├── my-skill/
│   ├── opencode-superpowers/  ← extension skill
│   └── ...
├── agents/
│   ├── claude-code/
│   │   ├── project/
│   │   └── global/
│   └── opencode/
│       ├── project/
│       └── global/
├── .agent-sync-manifest.json
├── .gitignore
└── README.md
```

---

## 7. Arquivos e Suas Localizacoes Fisicas

### AGENTS.md global do pi

- **Local:** `~/.pi/agent/AGENTS.md`
- **Sincronizado como:** config file de pi.dev via `config_patterns`
- **Destino no repo:** `configs/pi.dev/AGENTS.md`

### Per-agent

| Arquivo | Local Fisico | Agente | Sync Via |
|---------|-------------|--------|----------|
| `GEMINI.md` | `~/.gemini/GEMINI.md` | gemini-cli | config_patterns |
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | claude-code | config_patterns |
| `AGENTS.md` | `~/.pi/agent/AGENTS.md` | pi.dev | config_patterns |
| `AGENTS.md` | `~/.config/opencode/AGENTS.md` | opencode | config_patterns |
| `AGENTS.md` | `~/.claude/AGENTS.md` | claude-code | config_patterns |
| `AGENTS.md` | `~/.gemini/AGENTS.md` | gemini-cli | config_patterns |
| `AGENTS.md` | `~/.qwen/AGENTS.md` | qwen-code | config_patterns |
| `SKILL.md` | `~/.agents/skills/<skill>/SKILL.md` | todos | skills flow |

### Arquivos de configuracao do projeto

| Arquivo | Proposito |
|---------|-----------|
| `~/.config/agent-sync/config.yaml` | Configuracao do agent-sync (repo_url, agents, published_skills) |
| `~/.config/agent-sync/publish.yaml` | Config de publicacao (repo_url do repo publico) |
| `~/.config/agent-sync/overrides.yaml` | Overrides locais (nao sincronizados) |

---

## 8. Observacoes e Riscos

### 8.1 Gaps identificados

1. **Nao ha publicacao de AGENTS.md/configs**: A unica forma de compartilhar AGENTS.md entre maquinas e via push/pull com o repo privado. Nao ha fluxo de "publish configs" publicamente.

2. **config_patterns nao e usado no pull**: `_apply_synced_configs()` faz `glob("*")` e restaura **tudo** no diretorio de config, independente do pattern. Isso pode restaurar arquivos que nunca deveriam estar la.

3. **publish.py ignora config_patterns completamente**: Skills sao publicadas como estao em `~/.agents/skills/`. Nao ha filtro por tipo de arquivo.

4. **AGENTS.md pode ser tratado como skill se colocado em `~/.agents/skills/`**: Se um usuario colocar AGENTS.md dentro de `~/.agents/skills/`, o `publish.py` o considerara publicavel (linha 39: `"name": item.name`).

5. **extra_paths do roocode**: `rules: ~/.roo/rules/` e sincronizado como extra_path, mas nao ha tratamento especializado como existe para pi.dev.

### 8.2 Fluxos que NAO existem (e podem ser desejados)

- Publicar AGENTS.md para repo publico
- Sincronizar seletivamente quais config_patterns publicar vs manter privados
- Flag `--include-configs` no comando `skills publish`
- Validacao de que AGENTS.md na skills dir nao vaze para publish

### 8.3 Arquivos-chave para modificacao

| Se precisar modificar... | Arquivo | Linhas relevantes |
|------------------------|---------|-------------------|
| config_patterns | `agent_registry.yaml` | 41, 55, 66, 75, 101 |
| Fluxo de stage de configs | `sync.py` | 577-644 (_stage_agent_configs) |
| Fluxo de restore de configs | `sync.py` | 1180-1218 (_apply_synced_configs) |
| Publish de skills | `publish.py` | 1-299 (todo) |
| Definicao de agentes | `agents/base.py` | 1-200 (todo) |
| Propriedades extra_paths | `agents/base.py` | 128-179 |
| CLI entry points | `cli.py` | publish command ~340 |

---

## 9. Diagrama de Fluxo (Texto)

```
AGENTS.md / Per-Agent Configs Flow:

LOCAL                                      REPO (PRIVADO)                    REPO (PUBLICO)
─────                                      ───────────────                   ──────────────
~/.config/opencode/AGENTS.md ──push──▶ configs/opencode/AGENTS.md
~/.claude/AGENTS.md          ──push──▶ configs/claude-code/AGENTS.md
~/.claude/CLAUDE.md          ──push──▶ configs/claude-code/CLAUDE.md
~/.gemini/AGENTS.md          ──push──▶ configs/gemini-cli/AGENTS.md
~/.gemini/GEMINI.md          ──push──▶ configs/gemini-cli/GEMINI.md
~/.pi/agent/AGENTS.md        ──push──▶ configs/pi.dev/AGENTS.md
~/.pi/agent/SYSTEM.md        ──push──▶ configs/pi.dev/SYSTEM.md
~/.qwen/AGENTS.md            ──push──▶ configs/qwen-code/AGENTS.md
                                       
Restore: ◀──pull───
  (copia de volta para local)

Skills Flow:

~/.agents/skills/my-skill/  ──push──▶ skills/my-skill/  ──publish──▶ github.com/user/repo/skills/my-skill/
```

---

## 10. Resumo para Desenvolvedores

1. **AGENTS.md** e sincronizado como **arquivo de configuracao** via `config_patterns` no fluxo push/pull
2. **Skills** sao sincronizadas via `_stage_skills()` e publicadas via `publish.py`
3. **Nao ha sobreposicao** entre os dois fluxos — sao tratados por codigo completamente separado
4. **Extra paths** (pi.dev, roocode) sao sincronizados como configs, nao como skills
5. **Publish publico** so cobre skills de `~/.agents/skills/` — configs nunca sao publicadas
6. **config_patterns** e lido do registry a cada operacao de stage, mas **ignorado no restore**
