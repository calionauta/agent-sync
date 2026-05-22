# Security Incident Analysis: agent-sync Publish

**Date:** 2026-05-22  
**Severity:** CRITICAL  
**Status:** Root cause identified

---

## Executive Summary

The OpenRouter API key exposure in the public repository was caused by TWO issues in the `publish` command:

1. **No file filtering** - `shutil.copytree()` copies ENTIRE skill directories including:
   - `sessions/` - conversation logs
   - `blob/` - cached data  
   - `*.jsonl` - session recordings (contained API keys)
   - `models.json` - configuration files

2. **Security scanner not integrated** - `security_scanner.py` exists but is NEVER called during publish

---

## Root Causes

### Issue 1: No Ignore Patterns in copytree

```python
# git_publish.py lines 131-136
if skill.path.is_dir():
    shutil.copytree(skill.path, dest, dirs_exist_ok=True)  # ← NO ignore!
```

Same issue at line 62 in `do_git_publish()`.

### Issue 2: Security Scanner Dead Code

The `security_scanner.py` module was created but never integrated into the publish flow. It's a complete, well-tested scanner that detects:

- `sk-or-` (OpenRouter) ✅ Added now
- `sk-ant-` (Anthropic/Claude) ✅ Added now
- `sk-` (OpenAI)
- `ghp_` (GitHub PAT)
- `AIza...` (Google AI)
- And 20+ more patterns ✅ Extended

---

## What Was Exposed

From OpenRouter security alert emails:

| File | Content |
|------|---------|
| `sessions/.../2026-05-13T15-16-48-258Z.jsonl` | Session with API key |
| `models.json` | Configuration with API key |
| `projects/.../b9cdaa5a-2d31...jsonl` | Session with API key |
| `projects/.../f6e113f5-7cd4...jsonl` | Session with API key |

---

## Fix Applied

### 1. Extended Security Scanner Patterns

Added detection for:
- OpenRouter (`sk-or-`)
- Anthropic Claude (`sk-ant-`)
- Cohere (`cohere-`)
- Groq (`gsk_`)
- HuggingFace (`hf_`)
- Perplexity (`pplx-`)
- AWS (`AKIA`, `ASIA`)
- Stripe (`sk_live_`, `sk_test_`)
- GitHub fine-grained PAT (`github_pat_`)
- Telegram Bot Token

### 2. Next Steps (pending)

1. **Add ignore patterns to copytree** in `git_publish.py`:
   ```python
   shutil.copytree(src_path, dest, dirs_exist_ok=True,
                   ignore=ignore_patterns('.git', 'sessions', 'blob', '*.jsonl', '*.log'))
   ```

2. **Integrate security scanner as gate** before commit:
   - Scan all files before git add
   - Block publish if critical issues found
   - Show detailed report of what was found

3. **Define publish scope**:
   - Skills: Only publish the skill's directory content
   - Agents: Only publish `agents.md`, `claude.md` and other agent definition files
   - Never: sessions/, blob/, models.json, .git/

---

## Security Recommendations

1. **Never auto-copy**: Don't copy entire skill directories
2. **Explicit scope**: Only copy known safe files (*.md, *.yaml, *.json for configs)
3. **Scan before commit**: Use security_scanner before any git add
4. **Alert on secrets**: Warn user immediately if any API key pattern detected

---

## Files to Modify

1. `src/agent_sync/publish/git_publish.py` - Add ignore patterns + scanner integration
2. `src/agent_sync/security_scanner.py` - Already enhanced with new patterns

---

## Related Todo Items

- #2: Fix publish security: add ignore patterns + integrate security scanner
- #3: Add API key detection to security scanner for publish gate  
- #4: Document security incident analysis (this file)
- #5: Add API key patterns for more providers ✅ Completed