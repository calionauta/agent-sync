# DotAgents Protocol vs agent-sync: Comparação Completa

## O que é o DotAgents Protocol?

O [DotAgents Protocol](https://dotagentsprotocol.com/) é uma **especificação aberta** (draft) que define convenções para configuração de agentes AI em um diretório padronizado `.agents/`.

- **dotagentsprotocol.com** → Especificação do protocolo (documentação)
- **hub.dotagentsprotocol.com** → Catálogo público de bundles instaláveis (6 bundles disponíveis)

A especificação é aberta e em evolução, similar a um RFC.

---

## Estrutura de Diretórios

### DotAgents Protocol (`~/.agents/`)

```
~/.agents/                      # Raiz global (canonical config)
├── skills/                     # Skills definitions
│   ├── skill-a/
│   │   └── SKILL.md
│   └── skill-b/
│       └── SKILL.md
├── agents/                    # Sub-agent profiles
│   └── my-agent/
│       └── AGENT.md          # Frontmatter + system prompt
├── mcp.json                   # MCP server configuration
├── config.json                # Model and agent defaults
├── memories/                  # Agent memories (future)
└── tasks/                    # Repeat tasks (future)

<project>/.agents/            # Workspace overrides (overlay)
├── skills/
├── agents/
└── mcp.json
```

**Merge semântico:** Workspace (./.agents/) sobrepõe Global (~/.agents/)

---

### agent-sync (atual)

```
~/.agents/skills/              # Hub central de skills (fonte de verdade)
├── skill-a/
│   └── SKILL.md
└── skill-b/
    └── SKILL.md

~/.claude/                     # Config por agente
├── commands/                  # claude-code skills
└── agents/                   # custom agents

~/.config/opencode/skills/     # opencode skills
~/.gemini/tools/               # gemini-cli skills
~/.roo/skills/                # roocode skills
~/.pi/agent/                  # pi.dev config
```

---

## Comparação Detalhada

| Aspecto | DotAgents Protocol | agent-sync | Compatível? |
|---------|------------------|------------|-------------|
| **Diretório global** | `~/.agents/` | `~/.agents/skills/` (skills) | ⚠️ Parcial |
| **Diretório workspace** | `./.agents/` (overlay) | ❌ Não suportado | ❌ |
| **Skills format** | `SKILL.md` | `SKILL.md` | ✅ Sim |
| **Skills location** | `~/.agents/skills/` | `~/.agents/skills/` | ✅ Sim |
| **Sub-agents** | `~/.agents/agents/` | `~/.claude/agents/`, etc. | ⚠️ Vendor-specific |
| **MCP config** | `~/.agents/mcp.json` | ❌ Não centralizado | ❌ |
| **Config format** | JSON | YAML (`agent_registry.yaml`) | ⚠️ Diferente |
| **Agent registry** | `config.json` (DotAgents style) | `agent_registry.yaml` | ⚠️ Proprietário |
| **Vendor-neutral** | Sim (spec) | Sim (multi-agente) | ✅ |
| **Git-friendly** | Sim | Sim (via repo) | ✅ |
| **Overlay semantics** | Workspace > Global | ❌ Não suportado | ❌ |
| **Public hub** | hub.dotagentsprotocol.com | ❌ Não tem | ❌ |
| **Installable bundles** | Sim (.dotagents) | ❌ Não suportado | ❌ |

---

## Componentes DotAgents vs agent-sync

### 1. Skills

| Aspect | DotAgents | agent-sync |
|--------|-----------|-----------|
| Location | `~/.agents/skills/<name>/` | `~/.agents/skills/<name>/` |
| Format | `SKILL.md` + assets | `SKILL.md` + assets |
| Index | `skills/` index | `skills/` list |
| **Status** | ✅ Identical | ✅ |

### 2. Sub-Agents (Agent Profiles)

| Aspect | DotAgents | agent-sync |
|--------|-----------|-----------|
| Location | `~/.agents/agents/<name>/` | `~/.claude/agents/`, `~/.config/opencode/agents/` |
| Format | Frontmatter + Markdown | Proprietary per vendor |
| **Status** | ⚠️ Different locations | ⚠️ Vendor-specific |

### 3. MCP Configuration

| Aspect | DotAgents | agent-sync |
|--------|-----------|-----------|
| Location | `~/.agents/mcp.json` | ❌ Não existe |
| Format | JSON | — |
| Content | Server definitions | — |
| **Status** | ❌ Not implemented | ❌ |

### 4. Agent Registry

| Aspect | DotAgents | agent-sync |
|--------|-----------|-----------|
| Location | `~/.agents/config.json` | `src/agent_sync/agent_registry.yaml` |
| Format | JSON | YAML |
| Content | Model defaults, agent config | Agent methods, paths, checks |
| **Status** | ⚠️ Different approach | ⚠️ Proprietary |

### 5. Workspace Overrides

| Aspect | DotAgents | agent-sync |
|--------|-----------|-----------|
| Location | `<project>/.agents/` | ❌ Não suportado |
| Semantics | Override global | — |
| Merge | Shallow-merge by key | — |
| **Status** | ❌ Not implemented | ❌ |

---

## O que agent-sync faz bem (em relação ao DotAgents)

1. **Multi-vendor support** — Suporta Claude, Gemini, Opencode, RooCode, Cursor, Windsurf, pi.dev
2. **Bidirectional sync** — Push/pull para repositório Git
3. **Skills centralization** — Importa skills de múltiplos agentes para hub único
4. **Extension detection** — Detecta skills de extensões (Superpowers, etc.)
5. **Safe centralize** — TUI de proteção contra importação acidental

---

## O que falta (gaps)

| Gap | Impacto | Complexidade |
|-----|---------|--------------|
| Workspace overlay (`./.agents/`) | Alta — permite config por projeto | Média |
| `mcp.json` centralization | Média — unifica config MCP | Alta |
| JSON config option | Baixa — interoperabilidade | Baixa |
| Public hub integration | Baixa — comunidade | Alta |
| Installable bundles (.dotagents) | Média — distribuição | Alta |

---

## Recomendações de Alinhamento

### Curto prazo (fácil)
- [x] Documentar alinhamento DotAgents no `agent_registry.yaml` ✅
- [x] Adicionar `--dot-agents` flag para garantir estrutura `.agents/` ✅
- [ ] Criar `~/.agents/mcp.json` como configuração centralizada de MCP

### Médio prazo (moderado)
- [ ] Adicionar suporte a `./.agents/` workspace override
- [ ] JSON como formato alternativo para config

### Longo prazo (complexo)
- [ ] Integrar com hub.dotagentsprotocol.com para bundles públicos
- [ ] Suporte a `.dotagents` bundles instaláveis

---

## Conclusão

agent-sync e DotAgents Protocol são **compatíveis mas não idênticos**:

- ✅ agent-sync **já usa** `~/.agents/skills/` como hub (alinhado)
- ⚠️ agent-sync tem registry proprietário (YAML), DotAgents usa JSON
- ⚠️ DotAgents tem workspace overlay, agent-sync não
- ❌ DotAgents tem MCP centralizado, agent-sync não
- ✅ Ambos são vendor-neutral e git-friendly

**agent-sync é uma ferramenta de sync/centralização**, enquanto DotAgents é uma **especificação de estrutura**. Eles podem coexistir — agent-sync pode gerenciar a estrutura `.agents/` conforme o protocolo evolui.
