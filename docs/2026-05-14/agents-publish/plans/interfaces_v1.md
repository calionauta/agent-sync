# Interface Brainstorming: agent-sync agents publish

## Proposal A — Conventional Standard

### Philosophy
Maximize familiarity by mirroring the existing `skills publish` TUI. Same pattern, different content. Users who already know `skills publish` immediately understand `agents publish`.

**Intended feeling:** "I already know how to use this."

### Breadboarding
- **Components:** Rich Table (agent list), Confirm prompt, Security Warning Panel, Progress indicator
- **Primary loop:** Scan → Select → Review warnings → Confirm → Push
- **Navigation:** Linear flow, no branching
- **States:** Scanning, Selection, Security Review, Confirmation, Publishing, Done
- **Density:** Medium — shows all detected files, warns on sensitive content
- **Copy:** Direct, neutral, action-oriented ("Publishing...", "Security warning")

### Main Interface

```
╭────────────────────────────────────────────────────────────╮
│  📤 Agent Instructions Publish                              │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  Detected agent instructions in your config directories:    │
│                                                              │
│   ID │ Pub  │ Agent        │ File         │ Status          │
│  ────┼──────┼──────────────┼──────────────┼────────────────│
│    1 │ [✓]  │ pi.dev       │ AGENTS.md    │ ⚠️  sensitive  │
│    2 │ [ ]  │ gemini-cli   │ GEMINI.md    │ ✓  safe        │
│    3 │ [ ]  │ opencode     │ AGENTS.md    │ ✓  safe        │
│    4 │ [ ]  │ claude-code  │ CLAUDE.md    │ ✓  safe        │
│                                                              │
│  Controls:                                                   │
│    • Enter numbers to toggle (e.g. '1,3,5')                │
│    • Type 'all' or 'none'                                   │
│    • Press Enter when done                                   │
│                                                              │
╰────────────────────────────────────────────────────────────╘

  Selection: 1 (AGENTS.md of pi.dev) marked ⚠️

╭────────────────────────────────────────────────────────────╮
│  ⚠️  SECURITY WARNING                                       │
│                                                              │
│  The following file may contain sensitive information:       │
│                                                              │
│  📄 pi.dev AGENTS.md                                        │
│                                                              │
│  Detected:                                                   │
│    • Absolute paths: /Users/cali/..., /root/...              │
│    • Internal commands: /skill:cali-product-planner         │
│                                                              │
│  Review the content before publishing.                       │
│                                                              │
│  [Edit before publish]  [Publish anyway]  [Cancel]          │
│                                                              │
╰────────────────────────────────────────────────────────────╘

╭────────────────────────────────────────────────────────────╮
│  📋 Publication Summary                                    │
│                                                              │
│  Repository: github.com/cali/agent-sync-public-skills       │
│                                                              │
│  Will publish:                                               │
│    • pi.dev / AGENTS.md ⚠️                                  │
│                                                              │
│  Destination in repo:                                        │
│    • agents/pi.dev/AGENTS.md                                │
│                                                              │
│  Confirm? [y/N]:                                             │
│                                                              │
╰────────────────────────────────────────────────────────────╘
```

### Interaction Flow

```
agent-sync agents publish
        │
        ▼
┌───────────────────┐
│  Scan config dirs │
│  (via registry)   │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐     ┌──────────────────┐
│  List available   │────▶│  Security scan   │
│  .md files        │     │  (paths/secrets) │
└─────────┬─────────┘     └────────┬─────────┘
          │                        │
          │                        ▼
          │              ┌──────────────────┐
          │              │  Flag sensitive  │
          │              │  files ⚠️         │
          │              └────────┬─────────┘
          │                       │
          ▼                       ▼
┌───────────────────┐     ┌──────────────────┐
│  TUI selection    │     │  Show warning    │◀────┐
│  (toggle items)   │────▶│  panel + edit    │     │
└─────────┬─────────┘     └──────────────────┘     │
          │                        │                │
          │              ┌─────────┴─────────┐      │
          │              │  User choice:    │      │
          │              │  edit/cancel/proceed     │
          │              └─────────┬─────────┘      │
          │                        │                │
          └────────────────────────┘ (if sensitive) │
          │                        │
          ▼                        ▼
┌───────────────────┐     ┌──────────────────┐
│  Summary panel    │     │  Clone existing  │
│  + confirm        │     │  repo (if exists)│
└─────────┬─────────┘     └─────────┬─────────┘
          │                        │
          ▼                        ▼
┌───────────────────┐     ┌──────────────────┐
│  Confirm [y/N]    │────▶│  Copy to agents/│
└─────────┬─────────┘     │  subdir          │
          │                └─────────┬─────────┘
          ▼                          │
┌───────────────────┐                ▼
│  git add/commit   │     ┌──────────────────┐
│  + push --force   │────▶│  Done + URL      │
└───────────────────┘     └──────────────────┘
```

### Trade-Offs
| Pros | Cons |
|------|------|
| Familiar for existing users | Conservative, no innovation |
| Low usability risk | Feels like copy-paste |
| Easy to implement | Doesn't address discovery gap |
| Consistent with ecosystem | No differentiation |

---

## Proposal B — Conversation-First

### Philosophy
Reframe the interaction from "form to answer." The system asks questions, user responds naturally. Scanner results are presented as conversational context, not table rows.

**Intended feeling:** "The tool is helping me think through this."

### Breadboarding
- **Components:** Rich Text with inline styling, Prompt-based questions, Inline warning blocks
- **Primary loop:** Question → Context reveal → Answer → Next question
- **Navigation:** Guided conversation, one step at a time
- **States:** Scanning (animated), Question, Context, Warning (inline), Confirmation
- **Density:** Low — one concept at a time
- **Copy:** Conversational, empathetic ("I found some instructions...", "This one looks safe...")

### Main Interface

```
╭────────────────────────────────────────────────────────────╮
│                                                              │
│  Looking for agent instructions across your config dirs...  │
│                                                              │
│  ████████████████░░░░░░░░  Scanning ~/.pi/agent/...       │
│  ████████████████████████  Found: AGENTS.md                │
│                                                              │
│  ██████████████████████░░  Scanning ~/.gemini/...          │
│  ████████████████████████  Found: GEMINI.md                │
│                                                              │
╰────────────────────────────────────────────────────────────╘

╭────────────────────────────────────────────────────────────╮
│                                                              │
│  I found 4 agent instruction files across your system.      │
│                                                              │
│  Let me show you each one:                                  │
│                                                              │
╰────────────────────────────────────────────────────────────╘

╭────────────────────────────────────────────────────────────╮
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. pi.dev / AGENTS.md                              │  │
│  │                                                      │  │
│  │  This is your global agent instructions for pi.dev. │  │
│  │                                                      │  │
│  │  🔍 Security check: I noticed this file has some   │  │
│  │     absolute paths and internal commands.           │  │
│  │                                                      │  │
│  │     Example: /Users/cali/.pi/agent/                 │  │
│  │     Example: /skill:cali-product-planner            │  │
│  │                                                      │  │
│  │  ⚠️  Would you like to review this before sharing? │  │
│  │                                                      │  │
│  │  [ ] Publish without changes                        │  │
│  │  [x] Review first (opens in $EDITOR)                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
╰────────────────────────────────────────────────────────────╘

╭────────────────────────────────────────────────────────────╮
│                                                              │
│  For the other 3 files, they look clean and safe to share. │
│                                                              │
│  Here's the quick summary:                                  │
│    ✓ gemini-cli / GEMINI.md — safe                          │
│    ✓ opencode / AGENTS.md — safe                            │
│    ✓ claude-code / CLAUDE.md — safe                         │
│                                                              │
│  Should I include all of them?                              │
│                                                              │
│  [Y] Yes, publish all                                       │
│  [E] Let me edit the selection                               │
│  [N] Cancel                                                 │
│                                                              │
╰────────────────────────────────────────────────────────────╘
```

### Interaction Flow

```
agent-sync agents publish
        │
        ▼
┌─────────────────────────┐
│  Animated scan         │
│  "Looking for..."      │
│  Progress bars         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Reveal findings        │
│  "I found X files"      │
│  "Let me check each"   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Per-file review        │◀──────┐
│  (for sensitive ones)   │       │ (loop)
└───────────┬─────────────┘       │
            │                     │
            ▼                     │
┌─────────────────────────┐       │
│  Quick summary of      │       │
│  remaining files       │───────┘
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Confirmation           │
│  "Should I publish all?"│
└───────────┬─────────────┘
```

### Trade-Offs
| Pros | Cons |
|------|------|
| Reduces cognitive load | Slower for expert users |
| Guides through security | Verbose — many prompts |
| Empathetic tone | May feel patronizing to some |
| Handles sensitive content gracefully | More code to maintain |

---

## Proposal C — AI-Assisted Security Scan

### Philosophy
Use AI to analyze each file's content, understand what it contains, and provide intelligent warnings. Not just regex patterns — actual semantic understanding of what might be sensitive.

**Intended feeling:** "The tool really understands my content."

### Breadboarding
- **Components:** Rich Panel with AI analysis, Risk score visualization, Inline suggestions
- **Primary loop:** Scan → AI analyze → Present risk assessment → User decides → Publish
- **Navigation:** Dashboard-like, see all at once
- **States:** Scanning, AI Analysis (animated), Assessment View, Action
- **Density:** High — detailed analysis per file
- **Copy:** Technical but accessible ("Content fingerprint: operational_rules, skill_triggers...")

### Main Interface

```
╭──────────────────────────────────────────────────────────────────────╮
│  📤 Publish Agent Instructions                                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Repository: github.com/cali/agent-sync-public-skills               │
│  Status: Connected ✓                                                 │
│                                                                      │
│  ┌─── ANALYSIS RESULTS ───────────────────────────────────────────┐ │
│  │                                                                  │ │
│  │  File                     │ Risk    │ Category        │ Action   │ │
│  │  ─────────────────────────┼─────────┼─────────────────┼──────────│ │
│  │  pi.dev / AGENTS.md      │ ████░░  │ MEDIUM          │ Review    │ │
│  │  gemini-cli / GEMINI.md   │ ░░░░░░  │ NONE            │ OK       │ │
│  │  opencode / AGENTS.md     │ ░░░░░░  │ NONE            │ OK       │ │
│  │  claude-code / CLAUDE.md  │ █░░░░░  │ LOW             │ OK       │ │
│  │                                                                  │ │
│  │  Risk score: ████░░ (medium)                                     │ │
│  │  AI suggests: Review pi.dev/AGENTS.md before publishing          │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─── DETAILS: pi.dev / AGENTS.md ────────────────────────────────┐ │
│  │                                                                  │ │
│  │  Content Analysis:                                              │ │
│  │    • Contains skill triggers (/skill:cali-product-planner)     │ │
│  │    • Contains context-mode rules (ctx_batch_execute hierarchy)  │ │
│  │    • Contains absolute path: /Users/cali/...                    │ │
│  │    • No secrets or tokens detected                              │ │
│  │                                                                  │ │
│  │  Recommendation:                                                 │ │
│  │    Publishing is safe if you accept absolute paths being public.│ │
│  │    The skill triggers help others understand your workflow.     │ │
│  │                                                                  │ │
│  │  [View full content] [Sanitize] [Proceed] [Skip]                │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Publish 2 selected files? [y/N]:                                    │
│                                                                      │
╰──────────────────────────────────────────────────────────────────────╯
```

### Interaction Flow

```
agent-sync agents publish
        │
        ▼
┌─────────────────────────┐
│  Scan + Collect files   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  AI Content Analysis   │◀── Could call local LLM or
│  (semantic scan)       │    use patterns + heuristics
└───────────┬─────────────┘    in v1
            │
            ▼
┌─────────────────────────┐
│  Risk Dashboard         │
│  All files at once     │
│  Expandable details    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Per-file decisions    │◀──────┐
│  (expand → action)    │        │ (if needed)
└───────────┬───────────┘        │
            │                    │
            ▼                    │
┌─────────────────────────┐      │
│  Summary + Confirm    │──────▶│
└─────────────────────────┘      │
            │                    │
            ▼                    │
┌─────────────────────────┐      │
│  Publish               │      │
└─────────────────────────┘      │
```

### Trade-Offs
| Pros | Cons |
|------|------|
| Most intelligent UX | Requires AI integration (cost/complexity) |
| Semantic understanding | May have false positives/negatives |
| Excellent guidance | v1 without AI is weaker |
| Differentiated experience | |

---

## Proposal D — Radical Simplicity

### Philosophy
Remove everything that isn't essential. One question: "Want to publish what I found?" That's it.

**Intended feeling:** "Effortless. Done."

### Breadboarding
- **Components:** Single Panel, simple list, single Confirm
- **Primary loop:** Scan → List → Confirm → Done
- **Navigation:** Zero navigation
- **States:** Scanning, Ready, Done
- **Density:** Minimal — just the facts
- **Copy:** Ultra short ("Found X. Publish? [y/N]")

### Main Interface

```
╭────────────────────────────────────────────────────────────╮
│                                                              │
│  Found 4 agent instruction files:                           │
│                                                              │
│    • pi.dev / AGENTS.md                                     │
│    • gemini-cli / GEMINI.md                                 │
│    • opencode / AGENTS.md                                   │
│    • claude-code / CLAUDE.md                                │
│                                                              │
│  Publish all? [y/N]:                                        │
│                                                              │
╰────────────────────────────────────────────────────────────╘

╭────────────────────────────────────────────────────────────╮
│  ✓ Published 4 files to agents/                            │
│    github.com/cali/agent-sync-public-skills                │
│                                                              │
╰────────────────────────────────────────────────────────────╘
```

### Interaction Flow

```
agent-sync agents publish
        │
        ▼
┌─────────────────────────┐
│  Scan                   │
│  (background)           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  "Found X. Publish?"    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐     ┌─────────────────────┐
│  [y] → Publish + Done  │────▶│  Done panel        │
│  [N] → Cancel           │     └─────────────────────┘
└─────────────────────────┘
```

### Trade-Offs
| Pros | Cons |
|------|------|
| Minimal cognitive load | No security scanning |
| Fastest execution | User must review manually |
| Zero learning curve | No customization |
| Perfect for "just works" | Too simple for power users |

**⚠️ CRITICAL:** This proposal has no security handling. Only suitable if we enforce pre-publish content guidelines or skip this flow entirely.

---

## Proposal E — Expert/Command-First

### Philosophy
Optimize for users who know exactly what they want. Dense information, keyboard-driven, batch actions, minimal interactivity.

**Intended feeling:** "I have full control. Fast."

### Breadboarding
- **Components:** Dense table, flag selectors, dry-run by default, batch confirmation
- **Primary loop:** Dry-run review → Flags adjust → Confirm execute
- **Navigation:** Keyboard-only, no prompts
- **States:** Dry-run, Configured, Executing, Done
- **Density:** Maximum — everything visible at once
- **Copy:** Technical shorthand ("--include=pi,gemini --skip=gemma")

### Main Interface

```
╭──────────────────────────────────────────────────────────────────────╮
│  agents publish — DRY RUN                                            │
├──────────────────────────────────────────────────────────────────────┤
│  repo: github.com/cali/agent-sync-public-skills                     │
│                                                                      │
│  Agents  Mode   Size  Security  Status                               │
│  ──────  ─────  ────  ────────  ──────                               │
│  pi      AGENTS.md  2.1K  ⚠️ ABSPATH  pending                         │
│  gemini  GEMINI.md  1.2K  ✓        pending                           │
│  openc   AGENTS.md  0.8K  ✓        pending                           │
│  claude  CLAUDE.md  0.5K  ✓        pending                           │
│                                                                      │
│  Options:                                                            │
│    --include=pi,gemini,openc,claude   (default: all detected)        │
│    --exclude=pi                       (skip sensitive files)         │
│    --force                            (skip all prompts)             │
│    --dry-run=false                    (actually execute)             │
│                                                                      │
│  [Press ENTER to execute, or add --exclude flags above]               │
│                                                                      │
╰──────────────────────────────────────────────────────────────────────╯
```

### Interaction Flow

```
agent-sync agents publish --dry-run
        │
        ▼
┌─────────────────────────┐
│  Dense scan output     │
│  All files at once     │
│  Security flags        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  User adjusts with     │
│  --include/--exclude   │
│  (or ENTER to proceed) │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Execute (if not dry)   │
│  or stay in dry-run    │
└─────────────────────────┘
```

### Trade-Offs
| Pros | Cons |
|------|------|
| Maximum control | Steep learning curve |
| Fast for experts | Intimidating for beginners |
| Batch actions | No guidance for new users |
| Keyboard-only option | Less discoverable |

---

## Hybrid Recommendation

### Selected: **A + D hybrid** (Conventional Standard with optional simplicity)

**Rationale:**
- `agent-sync` targets CLI users who value predictability
- Existing `skills publish` uses Pattern A — consistency matters
- Users need security scanning — pure D is unsafe
- But the workflow should be simple, not complex

**What to implement:**

1. **Default flow mirrors `skills publish`** (Pattern A)
   - Rich Table with selection
   - Security panel for flagged files
   - Confirmation step

2. **Security scanning is non-blocking but visible**
   - Files with sensitive content show ⚠️ indicator
   - User can still publish (with warning)
   - No forced stop, just informed decision

3. **Optional `--simple` flag for power users** (Pattern D)
   - `agent-sync agents publish --simple`
   - Single prompt: "Found X. Publish? [y/N]"

4. **Cross-reference with `skills publish`**
   - After `agents publish` → "💡 You can also publish skills: agent-sync skills publish"
   - After `skills publish` → "💡 You can also publish agent instructions: agent-sync agents publish"

**Why not B?** Conversational is slower. Our users are comfortable with tables and prompts (proven by skills publish).

**Why not C?** AI analysis is nice but requires external dependency. Defer to v2.

**Why not E?** Too complex for the problem. We want approachable, not expert-only.

### UI Integration Points

```
┌──────────────────────────────────────────────────────────┐
│  In TUI:                                                │
│                                                          │
│  After showing available agents:                        │
│    • Each row has [Pub] toggle                          │
│    • Sensitive files flagged with ⚠️                     │
│    • Security panel appears AFTER selection (not before)│
│                                                          │
│  Security Panel (shown after selection):                │
│    • Lists files with concerns                           │
│    • Shows detected patterns (abs paths, internal cmds)  │
│    • Options: [Edit] [Skip this file] [Continue anyway] │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Key interactions:**

| Action | Result |
|--------|--------|
| Toggle item | Marks for publish |
| Enter `all` | Select all safe items (skips ⚠️) |
| Enter `all --include-unsafe` | Select everything |
| After selection | Security panel appears |
| In security panel: `e` | Opens file in $EDITOR |
| In security panel: `s` | Removes file from selection |
| In security panel: `c` | Continues despite warnings |
| After security | Summary + confirm |

This keeps the familiar pattern while adding safety checks where they matter.