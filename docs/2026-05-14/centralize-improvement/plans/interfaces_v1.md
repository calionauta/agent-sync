# Interface Brainstorming — TUI de Seleção de Skills Órfãs

## Contexto

O comando `agent-sync skills centralize` precisa de uma TUI (CLI terminal) para:
1. Listar skills órfãs (skills em agentes mas não no hub)
2. Permitir seleção com checkbox (default vazio)
3. Mostrar divergência de conteúdo entre cópias
4. Perguntar "manter ou remover" não-selecionadas pós-seleção

Todas as propostas abaixo são TUI-rich (Rich library, já usada no projeto).

---

## Proposta A — Conventional Standard (Tabela Única)

**Layout**: Uma tabela única com todas as skills, metadados inline.

```
╭─ Skills órfãs encontradas ─────────────────────────────────────╮
│   Nenhuma selecionada por padrão — importe apenas o que quiser │
│                                                                 │
│  #  Sel  Skill              Agentes            Status           │
│ ─────────────────────────────────────────────────────────────── │
│  1  [ ]  my-skill-a        claude-code, gemini  ✓ igual         │
│  2  [ ]  my-skill-b        claude-code          ✓ igual         │
│  3  [ ]  my-skill-c        gemini               ⚠️ diverge       │
│  4  [ ]  my-skill-d        qwen                 ✓ igual         │
│                                                                 │
│  4 skills | Selecionadas: 0                                     │
│                                                                 │
│  Controls: números pra toggle | 'all' | 'none' | Enter = done   │
╰─────────────────────────────────────────────────────────────────╯
```

**Pós-seleção**:
```
╭─ Skills não importadas ───────────────────────────────╮
│   3 skills não foram importadas (my-skill-a, -b, -d)  │
│                                                       │
│   O que fazer com elas nos agentes?                   │
│   [k] Keep nos agentes (default)                      │
│   [r] Remover dos agentes                             │
│                                                       │
│   [Enter] para confirmar                              │
╰───────────────────────────────────────────────────────╯
```

**Trade-offs**:
- ✅ Familiar, baixo risco de aprendizado
- ✅ Coluna de Status mostra divergência claramente
- ❌ Nomes longos de skill + agentes podem ficar apertados
- ❌ Não diferencia "skill X em agente Y tem conteúdo diferente de skill X em agente Z"

---

## Proposta B — Agrupamento por Agente

**Layout**: Seções separadas por agente, cada uma com sua lista.

```
╭─ Skills órfãs encontradas em agentes ──────────────────────────╮
│   Nenhuma selecionada por padrão                               │
│                                                                │
│  claude-code (~/.claude/commands/)                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ #1  [ ]  my-skill-a  ✓ igual                             │  │
│  │ #2  [ ]  my-skill-b  ✓ igual                             │  │
│  │ #3  [ ]  my-skill-d  ⚠️ diverge do hub                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  gemini-cli (~/.gemini/tools/)                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ #4  [ ]  my-skill-a  ✓ igual                             │  │
│  │ #5  [ ]  my-skill-c  ✓ igual                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  Selecionadas: 0 / 5  |  Enter = done  |  'all' | 'none'      │
╰────────────────────────────────────────────────────────────────╯
```

**Pós-seleção** (mesmo padrão da A, mas por agente):
```
╭─ Skills não importadas ────────────────────────────────────────╮
│   3 skills não foram selecionadas para o hub.                  │
│   Mantê-las nos agentes?                                       │
│                                                                │
│   Agente         Skills mantidas                               │
│  ────────────────────────────────────────────────────────────  │
│   claude-code    my-skill-a, my-skill-b, my-skill-d            │
│   gemini-cli     my-skill-a, my-skill-c                        │
│                                                                │
│   [k] Keep (default)  |  [r] Remove das agentes                │
╰────────────────────────────────────────────────────────────────╯
```

**Trade-offs**:
- ✅ Clara correlação: "o que está onde"
- ✅ Fácil ver se um agente específico tem skills que o hub não tem
- ❌ Mesma skill aparece várias vezes (my-skill-a em claude + gemini)
- ❌ Mais vertical scrolling

---

## Proposta C — Technological Vanguard (Auto-resolve com Diff)

**Layout**: Usa hash comparison para mostrar diff summary e sugerir resolução.

```
╭─ Skills órfãs — Análise Automática ───────────────────────────╮
│                                                                 │
│  ⋮ Verificando conteúdo em 3 agentes...                         │
│  ✓ 3 skills idênticas ao hub (nada a fazer)                    │
│  ⚠️ 2 skills divergem entre agentes                             │
│                                                                 │
│  Divergências detectadas:                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ my-skill-c:                                              │  │
│  │   claude-code:   abc123def  (modificado há 3 dias)       │  │
│  │   gemini-cli:    789ghi012  (idêntico ao hub)            │  │
│  │                                                          │  │
│  │   Recomendação: importar do gemini (mais recente = hub)  │  │
│  │   [?] Importar mesmo assim  [s] Pular (default)          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ my-skill-d:                                              │  │
│  │   claude-code:   (não existe no hub)                     │  │
│  │                                                          │  │
│  │   Recomendação: skill nova — importar?                    │  │
│  │   [i] Importar  [s] Pular (default)                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Pressione Enter para aplicar as decisões acima                │
╰────────────────────────────────────────────────────────────────╯
```

**Pós-seleção**: automático — skills não selecionadas são mantidas nos agentes.

**Trade-offs**:
- ✅ Reduz atrito — mostra só o que precisa de decisão
- ✅ Recomendação guiada reduz carga cognitiva
- ❌ Mais complexo de implementar (precisa de analysis engine)
- ❌ Usuário perde visão geral de "tudo que está espalhado"
- ❌ Se recomendação estiver errada, usuário pode não perceber

---

## Proposta D — Radical Simplicity (Flags-only)

**Layout**: Sem TUI. Só perguntas de confirmação.

```
📦 Scanning agents for orphan skills...

  Found 4 orphan skills in 3 agents.
  (run with --list-orphans to see details)

  Import all? [y/N] n
  Remove orphans from agents? [y/N] n

  ✓ No orphans imported. Skills remain in agents.

  (Run with --import-all to import all, or --list-orphans to inspect)
```

**Novo comando auxiliar**:
```
$ agent-sync skills list-orphans

  claude-code:  my-skill-a, my-skill-b, my-skill-d
  gemini-cli:   my-skill-a, my-skill-c
  qwen:         my-skill-e
```

**Trade-offs**:
- ✅ Minimalista, zero complexidade
- ✅ Funciona em CI/headless sem flags especiais
- ❌ Sem granularidade — ou importa tudo ou nada
- ❌ Usuário não vê quais skills têm conteúdo divergente
- ❌ "Onde está o checkbox?" — perde poder de seleção fina

---

## Proposta E — Expert / Command-First (Keyboard-only)

**Layout**: Tabela densa com atalhos de teclado, sem prompts.

```
╭─ Skills Órfãs ─────────────────────────────────────────────────╮
│   ID  Status   Skill              Agents             Sel        │
│ ─────────────────────────────────────────────────────────────── │
│   01  ✓ eq     my-skill-a        claude,gemini      ·          │
│   02  ✓ eq     my-skill-b        claude             ·          │
│   03  ⚠ div    my-skill-c        gemini             ·          │
│   04  ✓ eq     my-skill-d        qwen               ·          │
│   05  ✓ eq     my-skill-e        gemini             ·          │
│                                                                 │
│   [5 skills] [0 sel]  [/search] [a]ll [n]one [r]efresh [d]one  │
╰────────────────────────────────────────────────────────────────╯
```

**Pós-seleção**: inline, sem prompt separado.

```
╭─ 3 skills não importadas ──────────────────────────────────────╮
│   [K]eep | [R]emove | [Enter]=done                             │
│   Current: Keep (default)                                       │
╰────────────────────────────────────────────────────────────────╯
```

**Atalhos**:
- `1-5` → toggle skill
- `/texto` → filtrar skills na lista
- `a` → all, `n` → none
- `d` → done (confirma seleção)
- `k` / `r` → keep/remove não-selecionadas
- Tab entre seleção e pós-seleção

**Trade-offs**:
- ✅ Máxima velocidade para usuário experiente
- ✅ Denso, cabe muita informação
- ❌ Curva de aprendizado (atalhos não são óbvios)
- ❌ Discoverability baixa — novo usuário não sabe o que fazer
- ❌ Rich Table com foco em teclado requer implementação mais complexa

---

## Recomendação Híbrida

**Combinar A (familiar) + elementos de E (atalhos):**

- **Layout base**: Proposta A — tabela única com skill + agentes + status
- **Atalhos**: Proposta E — `a`/`n` pra all/none, números pra toggle, `/` pra filtro
- **Pós-seleção**: Proposta A — prompt `[k] Keep | [r] Remove` com default Keep
- **Indicador de divergência**: Proposta A — `⚠️ diverge` na coluna Status

**Por que esta combinação:**
- Tabela única é o formato já usado em `publish` e `delete` — padrão consistente
- Atalhos adicionam potência sem poluir a interface inicial
- Pós-seleção em prompt separado (não inline) é mais claro e menos propenso a erro
- O indicador de divergência na tabela é informativo sem requerer ação imediata

**ASCII Mockup Final (Recomendado):**

```
╭─ Skills órfãs encontradas em agentes ───────────────────────────────╮
│   Nenhuma selecionada por padrão — importe apenas o que quiser      │
│                                                                      │
│   #  Sel  Skill                Agentes          Status               │
│  ─────────────────────────────────────────────────────────────────── │
│   1  [ ]  my-skill-a           claude, gemini   ✓                    │
│   2  [ ]  my-skill-b           claude           ✓                    │
│   3  [ ]  my-skill-c           gemini           ⚠️ diverge            │
│   4  [ ]  my-skill-d           qwen             ✓                    │
│   5  [ ]  sketchy-tool-v2     claude           ⚠️ diverge            │
│                                                                      │
│   5 skills | 0 selecionadas | [/filter]                              │
│   [a]ll  [n]one  [Enter]=done                                        │
╰──────────────────────────────────────────────────────────────────────╯

╭─ Skills não importadas ─────────────────────────────────────────────╮
│   3 skills não foram selecionadas para o hub.                       │
│   O que fazer com elas nos agentes?                                 │
│                                                                      │
│   [K] Keep (default)  — mantém nos agentes                          │
│   [R] Remove          — apaga dos agentes (não afeta o hub)         │
│                                                                      │
│   Skills afetadas: my-skill-a, my-skill-b, my-skill-d               │
╰──────────────────────────────────────────────────────────────────────╯
```

**Para dry-run**, adicionar badge `[DRY RUN]` no cabeçalho e substituir ações por "would":

```
╭─ [DRY RUN] Skills órfãs encontradas ────────────────────────────────╮
│   ... mesma tabela ...                                               │
│                                                                      │
│   (DRY RUN: nada será alterado)                                     │
╰──────────────────────────────────────────────────────────────────────╯

╭─ [DRY RUN] Pós-seleção ─────────────────────────────────────────────╮
│   3 skills não seriam importadas                                    │
│   Seriam mantidas nos agentes (Keep)                                │
│                                                                      │
│   (Passe --yes no comando real para este comportamento)             │
╰──────────────────────────────────────────────────────────────────────╯
```
