# Risk Analysis: Publishing AGENTS.md (Global + Per-Agent) to Public Repository

**Date:** 2026-05-14
**Feature:** Extend `agent-sync skills publish` (or create parallel command) to publish AGENTS.md, SYSTEM.md, CLAUDE.md, GEMINI.md files to a public repository.
**Current state:** `publish.py` only publishes from `~/.agents/skills/`. Private sync (`sync.py`) pushes configs including AGENTS.md to a *private* repo under `configs/<agent>/`.

---

## Risk 1 — Exposure of Internal Workflows, Paths, and Infrastructure

**Severity: HIGH | Probability: HIGH**

### What's at risk

The AGENTS.md files for pi, opencode, gemini, and claude contain **operational internals** intended only for the user's own AI agents:

**pi's ~/.pi/agent/AGENTS.md:**
- Internal commands: `/skill:cali-product-planner`, `/parallel-review`, `/parallel-cleanup`
- Internal tool names: `ctx_batch_execute`, `ctx_execute`, `ctx_search`, `ctx_fetch_and_index`
- Internal workflows: Testing Protocol with specific reviewer launch patterns
- Personal tool stack (Plannotator, audit, critique, agent-browser, dogfood skills)
- File references: `cali-product-planner/references/tech-planning/generation-principles.md`

**opencode's ~/.config/opencode/AGENTS.md:**
- Absolute server path: `/Users/cali/Development/SERVER_GUIDE.md`
- SSH root path: `/root/SERVER_GUIDE.md`
- Internal tool names: `search_graph`, `trace_path`, `get_code_snippet`, `query_graph`
- Server infrastructure hints (Cloudflare Tunnel, Zero Trust, Docker networks, Caddy)

**gemini's ~/.gemini/GEMINI.md (174 lines):**
- MCP server orchestration rules (SERENA, PROBE, Context7, InstantDB, Chrome-DevTools)
- Detailed workflow phases with tool hierarchy
- Personal technology stack and preferences

**agent-sync project's own AGENTS.md:**
- Hatch-VCS versioning internals
- Architecture mandates (agent_registry.yaml, no symlinks)
- Distribution details (pipx vs pip --break-system-packages)

### Why it matters
- **Reconnaissance:** A public repo exposes the user's exact agent stack, tool preferences, MCP servers, and infrastructure layout
- **Attack surface expansion:** Server paths (`server.renatocaliari.com`) + infrastructure details (Cloudflare Tunnel, Docker networks) provide attackers with targeted entry points
- **Workflow plagiarism:** Internal workflows (product-planner orchestration, parallel-review patterns) are valuable IP
- **Temporal exposure:** Once published to a public git repo, deleted content remains in git history forever

### Current safety gap
- `publish.py` currently only copies from `~/.agents/skills/` — AGENTS.md files are NOT in scope today
- The `.gitignore` in the publish temp repo blocks `*auth*`, `*token*`, `*key*`, `*secret*`, `*credentials*`, `.env`, `*.json`, `*.yaml`, `*.yml` — but **AGENTS.md and *.md files are NOT excluded**
- The security warning in publish.py claims "NEVER publish config files" but the code **has no active filter** preventing AGENTS.md from being published if the scope expands

### Recommendations
1. **Auto-detect** AGENTS.md/GEMINI.md/CLAUDE.md/SYSTEM.md by filename and warn explicitly before publish
2. **Require explicit opt-in** — never auto-include these files even if scanning broader directory
3. **Add a content scanner** that detects absolute paths, `ssh`, `token`, `key` patterns in .md files before publish
4. **Consider a dedicated manifest** of "safe-to-publish" agent instructions (curated subset)

---

## Risk 2 — Product Confusion: Is AGENTS.md a "Skill" or a "Config"?

**Severity: MEDIUM | Probability: HIGH**

### The confusion

The term "publish" today means: share a **skill** (a reusable, portable capability) from `~/.agents/skills/` to a public repo.

AGENTS.md files are **not skills**. They are:
- **pi's AGENTS.md:** Platform-wide operational rules (how to plan, code, test)
- **opencode's AGENTS.md:** Agent-specific behavioral instructions
- **gemini's GEMINI.md:** Architectural mandates + tool orchestration

Users naturally think of these as **config/instructions**, not content for a **skill marketplace**. If we merge AGENTS.md into the same `publish` command:
- Users may accidentally publish their entire agent instruction set thinking they're just "sharing a skill"
- The mental model breaks: "I'm publishing a skill" vs "I'm publishing my agent's identity"

### UX risk scenarios

| Scenario | Effect |
|----------|--------|
| User runs `skills publish --all` | All skills + all AGENTS.md published without realizing |
| User sees AGENTS.md in TUI selection | Might not distinguish between a skill directory and a config file |
| User thinks "someone can use my agent's instructions" | May not realize the full operational exposure |

### Recommendations
1. **Separate command:** `agent-sync configs publish` (or `agent-sync publish configs`) — never mix with `skills publish`
2. **Different confirmation flow:** Even stronger warnings for config publishing than skills
3. **Clear terminology:** Use "publish agent instructions" not "publish configs" — differentiate from sync's "configs" (private)
4. **Opt-in list:** User must explicitly tag which AGENTS.md files are shareable (not auto-discovered)

---

## Risk 3 — Secret/Credential Leakage via AGENTS.md

**Severity: HIGH | Probability: LOW (on its own) | MEDIUM (cumulative)**

### The threat

AGENTS.md files are plain markdown. They can contain:
- Inline API keys or tokens (anthropic keys, gemini keys, github tokens)
- Environment variable names that hint at credential locations
- File paths to credential files (e.g., `/Users/cali/.config/gemini/credentials.json`)
- MCP server configurations with embedded auth

### Current protection analysis

| Protection Layer | Present? | Covers AGENTS.md? |
|-----------------|----------|-------------------|
| `.gitignore` patterns (`*auth*`, `*token*`, `*key*`, `*secret*`) | ✅ publish.py | ❌ — only blocks files, not content |
| `_should_exclude()` in sync.py | ✅ private sync | ❌ — only for private sync, not publish |
| Content scanning for secrets | ❌ | ❌ |
| Security warning panel in publish.py | ✅ | ⚠️ — claims to block "config files" but has no active enforcement |
| `EXCLUDE_PATTERNS` | ✅ sync.py | ❌ — applies to config_patterns matching, not publish |

### The gap
AGENTS.md files with names like `*auth*` or `*token*` or `*key*` would be blocked by the `.gitignore`, but the actual per-agent filenames are:
- `AGENTS.md` — NOT blocked
- `GEMINI.md` — NOT blocked
- `CLAUDE.md` — NOT blocked
- `SYSTEM.md` — NOT blocked

A user could **accidentally paste a token into their AGENTS.md** (common practice for quick setup), run `publish`, and the token goes public.

### Recommendations
1. **Content scan** markdown files for regex patterns matching API keys before allowing publish
2. **Git hook integration** — warn before commit if AGENTS.md contains known credential patterns
3. **Feature flag:** require explicit `--include-configs` flag before publishing AGENTS.md
4. **Documentation:** warn users to review AGENTS.md for secrets before publishing

---

## Risk 4 — UX Confusion: "Publish Skills" vs "Publish Agent Configs"

**Severity: MEDIUM | Probability: HIGH**

### The confusion surface

The current `agent-sync` CLI has two conceptually separate domains:

| Domain | Command | Target | Privacy | Purpose |
|--------|---------|--------|---------|---------|
| Skills | `skills publish` | `~/.agents/skills/` | PUBLIC | Share capabilities |
| Configs | `push` / `pull` | `configs/<agent>/` | PRIVATE | Backup/sync settings |

If we add AGENTS.md publishing, it blurs the line between these domains:

1. **"I published my skills, did my instructions go too?"** — unclear scope
2. **"I want to share my OpenCode setup"** — does that mean skills? Instructions? Both?
3. **"I ran `skills publish --all` and now my AGENTS.md is public"** — irreversible mistake

### Cognitive load problem

The user must now track **three** mental models:

| Action | What goes where | Privacy |
|--------|----------------|---------|
| `skills publish` | Skills only (today) | Public |
| `skills publish` + AGENTS.md | Skills + instructions | Public |
| `push` | Everything (skills + configs + instructions) | Private |

This creates a **leaky abstraction**: "Why does `push` (private) send everything but `publish` (public) only sends skills? But wait, now publish sends instructions too?"

### Recommendations
1. **Never add AGENTS.md to `skills publish` scope.** Always use a separate subcommand
2. **Distinct naming:** `agent-sync publish instructions` (not "configs", because configs = private sync)
3. **Dry-run by default:** Show exactly what files would be published before confirming
4. **Parallel mental model:** If publishing instructions, the flow should mirror `push` in structure but with PUBLIC destination and STRICTER filtering

---

## Risk 5 — Scope Intuitiveness: Will Users Expect AGENTS.md in the Same Command?

**Severity: LOW | Probability: MEDIUM**

### The natural expectation

Users who understand the DotAgents protocol might reasonably expect:
- `~/.agents/` is the global agent configuration directory
- `~/.agents/skills/` contains skills
- `~/.agents/agents/` might contain agent definitions
- AGENTS.md doesn't have a standardized home yet

The DotAgents protocol doesn't (yet) define a standard location for AGENTS.md files. They're scattered:
- `~/.pi/agent/AGENTS.md`
- `~/.config/opencode/AGENTS.md`
- `~/.config/opencode/profiles/default/AGENTS.md`
- `~/.gemini/GEMINI.md`
- `~/.claude/CLAUDE.md`

**User might ask:** "Why is OpenCode's AGENTS.md publishable but not pi's?" or "Should I move my AGENTS.md to `~/.agents/` first?"

### Recommendation
1. **Define a canonical location** for shareable agent instructions (e.g., `~/.agents/instructions/`)
2. Only publish AGENTS.md files that have been **explicitly placed** or **tagged** as publishable
3. Provide a `agent-sync publish instructions --collect` command that gathers per-agent AGENTS.md files into the canonical location for review before publishing

---

## Risk 6 — Maintenance Complexity: Multiple Repositories

**Severity: MEDIUM | Probability: LOW (if same repo) | MEDIUM (if separate repo)**

### Scenario analysis

**Option A: Same public repo for skills + instructions**
- Pro: Single URL, single `git remote`, simpler mental model
- Con: git history is larger; deleting instructions requires git history rewrite
- Con: Harder to differentiate "skill" vs "instruction" contributions

**Option B: Separate public repos**
- Pro: Clear separation of concerns; instructions can evolve independently
- Pro: Different contribution guidelines, licenses, review processes possible
- Con: User must manage TWO public repo URLs in config
- Con: Two `publish` commands, two clone/checkout workflows
- Con: Increased testing surface for agent-sync maintainers

**Existing repo problem:** Currently `publish.py` only creates/updates one public repo. Adding a second URL introduces:
- `publish_config.yaml` now has `repo_url` AND `config_repo_url` OR `instruction_repo_url`
- Backward compatibility: existing users' `publish_config.yaml` has only `repo_url`
- Migration logic: "Does `repo_url` mean skills-only or both?"

### Recommendations
1. **Default to same repo** with a `instructions/` subdirectory (mirrors the private repo's structure)
2. **Support separate repo** via second config key (`instruction_repo_url`) for power users
3. **Do NOT auto-detect** — require explicit configuration
4. **Repo URL validation** must check both URLs are public (or warn if private)

---

## Risk 7 — Inconsistent File Formats Across Agents

**Severity: LOW | Probability: LOW (for publish) | MEDIUM (for consumption)**

### Format diversity

| Agent | File | Format |
|-------|------|--------|
| pi.dev | `AGENTS.md` | Plain Markdown |
| opencode | `AGENTS.md` | Plain Markdown |
| gemini-cli | `GEMINI.md` | Plain Markdown (was YAML frontmatter? see `.bak`) |
| claude-code | `CLAUDE.md` | Plain Markdown |
| VS Code IDE agents | `AGENTS.md` | Plain Markdown |

Currently all appear to be plain markdown. However:
- Some agents support YAML frontmatter for structured metadata
- `SYSTEM.md` files may have different conventions per agent
- Cursor's rules use `.cursorrules` (not AGENTS.md)
- Windsurf uses `.windsurfrules`

### Risk if formats change

If a future version of an agent adopts structured frontmatter:
- Publishing raw markdown without frontmatter might feel inconsistent
- Consumers of the public repo can't easily tell which format a file uses
- Merging/reconciling two agents' AGENTS.md files is non-trivial

### Recommendations
1. **Publish as-is** — don't try to normalize formats. Markdown is universal
2. **Add a metadata file** (e.g., `instructions-manifest.yaml`) that lists each published file, its source agent, and format
3. **Document** the file provenance: "This file came from ~/.gemini/GEMINI.md, published by agent-sync"

---

## Summary Matrix

| # | Risk | Severity | Probability | Risk Score | Mitigation Priority |
|---|------|----------|-------------|------------|---------------------|
| 1 | Exposure of internals (workflows, paths, infra) | **HIGH** | **HIGH** | **CRITICAL** | 🚨 **BLOCKER** |
| 2 | Product confusion: skill vs config | MEDIUM | HIGH | HIGH | Design decision needed |
| 3 | Secret/credential leakage in AGENTS.md | **HIGH** | LOW-MEDIUM | MEDIUM-HIGH | Implement scanner |
| 4 | UX confusion: publish skills vs publish configs | MEDIUM | HIGH | HIGH | Separate UX flow |
| 5 | Scope intuitiveness | LOW | MEDIUM | LOW | Documentation |
| 6 | Multiple repo maintenance | MEDIUM | LOW-MEDIUM | LOW-MEDIUM | Same repo default |
| 7 | Inconsistent file formats | LOW | LOW | LOW | Manifest metadata |

---

## Design Principles for the Feature

1. **Do NOT extend `skills publish`.** Create a separate command/subcommand.
2. **Default to OFF.** Publishing instructions requires explicit intent.
3. **Content-aware security.** Scan for secrets, paths, and infrastructure details.
4. **One repo default.** Use `instructions/` subdirectory in the existing public skills repo.
5. **Immutable history warning.** AGENTS.md published = permanently on the internet.
6. **Canonical location later.** Consider `~/.agents/instructions/` for v2.

---

## Files Referenced

| File | Purpose |
|------|---------|
| `src/agent_sync/publish.py` (full) | Current publish flow — only handles `~/.agents/skills/` |
| `src/agent_sync/sync.py` (lines 590-685) | Private sync — copies AGENTS.md via `config_patterns` |
| `src/agent_sync/agent_registry.yaml` (lines 41-101) | Defines `config_patterns` with AGENTS.md per agent |
| `~/.pi/agent/AGENTS.md` (full ~123 lines) | pi's global agent instructions |
| `~/.config/opencode/AGENTS.md` (~50 lines) | opencode's agent instructions |
| `~/.gemini/GEMINI.md.bak` (~174 lines) | gemini's architectural mandates |
| `src/agent_sync/sync.py` (lines 972-1000) | `_should_exclude()` — filters for private sync only |

## Start Here

Open `src/agent_sync/publish.py` — understand the full `publish_skills()` flow. This is the file that must be modified (or complemented) to support AGENTS.md publishing. Decisions about separation of concerns (#Risk2, #Risk4) must be resolved before implementation.
