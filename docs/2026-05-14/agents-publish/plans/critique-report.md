# Critique Report: spec-product.md vs interfaces_v1.md

**Date:** 2026-05-14  
**Reviewer:** code-review subagent  
**Files Analyzed:**
- `docs/2026-05-14/agents-publish/plans/spec-product_v1.md`
- `docs/2026-05-14/agents-publish/plans/interfaces_v1.md`
- `src/agent_sync/agent_registry.yaml`
- `src/agent_sync/publish.py`

---

## 🎯 Executive Summary

Two critical disconnects identified between the spec and the implementation baseline:

1. **The spec describes a feature that doesn't exist yet**: `agent-sync agents publish` is the core deliverable, but only `skills publish` exists in `publish.py`. The entire discovery/dispatch infrastructure for agent instructions is absent.

2. **Security scanning is specced but unimplemented**: The spec dedicates significant detail to content scanning (paths, secrets, SSH), but no scanning logic exists in the codebase for agent instruction files.

---

## 🚨 Critical Questions (Blocking)

### Q1. No `agents publish` command exists
**Evidence:** `publish.py` only exports `publish_skills()`. No `publish_agents()` function exists. The CLI in `cli.py` has no `agents publish` command.

**Impact:** The entire spec describes a feature that requires greenfield development. There is no implementation baseline to extend.

**Decision needed:** Should the plan describe a full new command (`agents publish`) or attempt to refactor `skills publish` into a unified `publish` command with categories?

---

### Q2. No discovery mechanism for agent instruction files
**Evidence:** 
- `agent_registry.yaml` defines `config_patterns: ["AGENTS.md", "SYSTEM.md", "GEMINI.md", ...]` per agent
- `publish.py` only scans `~/.agents/skills/` via `get_available_skills()`
- No code scans agent config directories (`~/.pi/agent/`, `~/.gemini/`, etc.) for instruction files

**Impact:** Even if `agents publish` existed, it couldn't find the files to publish.

**Decision needed:** Should we reuse `BaseAgent` infrastructure from `sync.py` (which scans agent dirs), or build a separate lightweight scanner?

---

### Q3. Security scanning is unimplemented
**Evidence:** 
- Spec section "Sanitização de segurança" (linchpin #2) describes scanning for absolute paths, tokens, server SSH paths
- `publish.py` has no security scanning logic at all
- `sync.py` only has `EXCLUDE_PATTERNS` for generic patterns, not content scanning

**Impact:** Users could accidentally publish sensitive paths without any warning.

**Decision needed:** 
- Scanner heuristic approach vs deferring AI-assisted scanning (Proposal C) to v2?
- What's the minimum viable scanner for v1?

---

### Q4. Repo organization spec vs implementation mismatch
**Evidence:**
- Spec describes `agents/` directory structure (`agents/pi.dev/AGENTS.md`)
- Spec workflow `--dry-run`, `--all`, `--repo <url>` options
- `publish.py` only creates `skills/` and `README.md`

**Impact:** The directory structure and CLI interface in the spec don't map to existing code.

**Decision needed:** Should v1 implement the full directory structure, or simplify to flat publish per file?

---

## 🤔 Important Questions (Refinement)

### Q5. Config persistence spec mismatch
**Evidence:**
- Spec: "assim como `published_skills`, salvar `published_agents` no config"
- `Config` class has `published_skills` field
- No `published_agents` field exists

**Clarification:** Should `published_agents` be a new config field, or should we reuse `published_skills` with prefixed keys (e.g., `agents:pi.dev:AGENTS.md`)?

---

### Q6. Global vs per-agent instruction detection
**Evidence:**
- Spec mentions "AGENTS.md global (se detectado)" and "per-agent (gemini, opencode, claude, pi, qwen)"
- `agent_registry.yaml` has `pi.dev`, `gemini-cli`, `opencode`, `claude-code`, `qwen-code` defined
- No code differentiates global vs per-agent instructions

**Clarification:** Where is the "global" AGENTS.md? Is it `~/.pi/agent/AGENTS.md` (pi.dev's config_dir)? Or a separate location like `~/.agents/AGENTS.md`?

---

### Q7. Spec's Alternative C conflicts with "Out of Scope"
**Evidence:**
- Alternative C proposes unified `publish` command as long-term approach
- "Out of Scope" explicitly defers "Unificar `skills publish` e `agents publish` em `publish`" to v2

**Clarification:** If Alternative C is rejected now, should Alternative A (same command, same repo) be the chosen approach for v1? Or Alternative B (new command, same repo)?

---

### Q8. Proposal E CLI flags not in existing implementation
**Evidence:**
- Spec Proposal E suggests `--include=pi,gemini`, `--exclude=pi`, `--force`, `--dry-run`
- Existing `skills publish` only has `dry_run`, `repo_url`, `interactive` params
- No `--include`/`--exclude` infrastructure exists

**Clarification:** Should we align the new `agents publish` CLI with existing `skills publish` patterns (which uses interactive TUI by default), or introduce the dense table approach from Proposal E?

---

## 🔎 Minor Clarifications

### Q9. VS Code Extensions not in spec
**Evidence:**
- `agent_registry.yaml` defines `roocode`, `cline`, `cursor`, `windsurf` as full agents
- Spec only mentions `pi.dev`, `gemini`, `opencode`, `claude` (and `qwen` briefly)

**Clarification:** Should VS Code extensions be included in `agents publish` scope? They have `config_patterns` that include `*.md` files.

---

### Q10. "out-of-scope" AGENTS.md de Projeto needs definition
**Evidence:**
- Spec excludes "AGENTS.md de projetos" (inside git repos)
- But doesn't define the boundary clearly

**Clarification:** If AGENTS.md exists in both `~/.pi/agent/` (agent config) AND `~/projects/myapp/` (project repo), should we scan both? Only the first?

---

### Q11. `publish.yaml` vs `config.json` persistence
**Evidence:**
- Spec: "salvar `published_agents` no config"
- `publish.py` uses separate `publish.yaml` for repo URL persistence
- `Config` class uses `config.json`

**Clarification:** Should agent instruction selection be stored in `publish.yaml` (alongside repo URL) or in `Config` with other agent-sync state?

---

## ✅ Strengths

### Strength 1: Comprehensive threat modeling in spec
**Evidence:** Spec thoroughly identifies security risks (absolute paths, tokens, SSH paths, internal commands like `/skill:cali-product-planner`). This is mature threat modeling.

### Strength 2: Well-structured multi-proposal UX exploration
**Evidence:** interfaces_v1.md evaluates 5 distinct approaches (A-E) with clear trade-off tables. This provides excellent decision material for the design review.

### Strength 3: Registry architecture ready for extension
**Evidence:** `agent_registry.yaml` already defines `config_patterns` per agent, making file discovery theoretically implementable by iterating registry entries.

### Strength 4: Hybrid recommendation justified
**Evidence:** The "A + D hybrid" recommendation explicitly explains why B, C, and E are rejected with clear reasoning. This shows the design decision process is documented.

### Strength 5: Linchpins provide implementation roadmap
**Evidence:** The three linchpins (discovery, sanitization, selection) break down the problem into digestible chunks that map to implementable components.

---

## 📋 Recommended Next Steps

1. **Resolve Q1 (blocking):** Decide if `agents publish` is a new command or refactored `publish`
2. **Build discovery baseline:** First implement scanning `config_patterns` from registry
3. **Define minimum scanner:** Decide if v1 gets heuristic-based or no security scanning
4. **Align CLI flags:** Choose between Proposal E density or existing TUI approach

---

*Report generated by code-review subagent*  
*Classification: SPEC ANALYSIS - NOT YET IMPLEMENTED*