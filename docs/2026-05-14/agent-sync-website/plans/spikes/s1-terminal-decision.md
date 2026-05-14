# Spike Decision: Terminal Simulation

**Date:** 2026-05-14  
**Scope:** S1 - Terminal Simulation Research  
**Status:** ✅ Complete

---

## Research Summary

### Option A: xterm.js (Winner)

| Aspect | Details |
|--------|---------|
| **Pros** | Mature (v5.5.0), well-documented, npm + CDN, mobile touch support, themeable, addon ecosystem |
| **Cons** | ~500KB bundle (but loadable via CDN with defer), requires more JS code |
| **Bundle** | 498KB minified (gzipped ~150KB) |
| **CDN** | `https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/` |
| **Use case** | Interactive terminal where users can type commands |

### Option B: asciinema-player

| Aspect | Details |
|--------|---------|
| **Pros** | Tiny, plays pre-recorded sessions, beautiful |
| **Cons** | Read-only playback, can't interact with terminal |
| **Bundle** | ~50KB |
| **Use case** | Demo videos, not interactive |

### Option C: ttty (lightweight)

| Aspect | Details |
|--------|---------|
| **Pros** | Tiny (~5KB), zero dependencies, pure JS |
| **Cons** | Less mature, limited features |
| **Use case** | Simple command output display |

---

## Decision

**Use xterm.js** for the landing page because:

1. ✅ Enables interactive mode (user can type after demo)
2. ✅ Mature and well-maintained
3. ✅ CDN availability (no npm build needed)
4. ✅ Mobile-friendly
5. ✅ Rich theming matches our dark theme

**Rationale:** The landing page needs both:
- Auto-playing demo sequence (typing effect)
- Interactive mode (user types commands)

xterm.js handles both. asciinema-player is only playback. ttty is too limited.

---

## Typing Effect Approach

Using xterm.js built-in `write()` method with a custom typewriter helper:

```javascript
async function typeText(term, text, delay = 40) {
  for (const char of text) {
    term.write(char);
    await sleep(delay);
  }
}
```

**Timing:** 40ms per character (adjustable)

---

## Demo Command Sequence

```
$ agent-sync list-agents
🤖 Claude Code       [CLI] 📁 ~/.claude/
🤖 Gemini CLI        [CLI] 📁 ~/.gemini/
🤖 RooCode           [IDE] 📁 ~/.roocode/
🤖 Cline             [IDE] 📁 ~/.cline/
🤖 Cursor            [IDE] 📁 ~/.cursor/
🤖 Qwen               [CLI] 📁 ~/.qwen/
🤖 Pi                 [CLI] 📁 ~/.pi/

$ agent-sync sync --dry-run
🔍 Scanning for changes...
📝 Would sync: 12 files
  ├── skills/cali-product-planner/SKILL.md
  ├── skills/audit/SKILL.md
  └── ...

$ agent-sync sync
✅ Synced 12 files in 3.2s
📦 Pushed to: github.com/renatocaliari/agent-sync-configs

$ agent-sync --version
agent-sync v1.2.0
```

---

## Implementation Notes

### CDN Loading Strategy

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.css">
<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.js" defer></script>
```

### Terminal Theme

```javascript
const term = new Terminal({
  theme: {
    background: '#161b22',
    foreground: '#c9d1d9',
    cursor: '#58a6ff',
    cursorAccent: '#0d1117',
    selectionBackground: '#388bfd40',
    black: '#0d1117',
    red: '#f85149',
    green: '#3fb950',
    yellow: '#d29922',
    blue: '#58a6ff',
    magenta: '#bc8cff',
    cyan: '#39c5cf',
    white: '#c9d1d9',
  },
  fontFamily: '"JetBrains Mono", Consolas, Monaco, monospace',
  fontSize: 14,
  lineHeight: 1.4,
  cursorBlink: true,
  cursorStyle: 'bar',
});
```

### Auto-advance Logic

1. Type command → wait 500ms
2. Show output → wait 800ms
3. Next command → repeat
4. After last command → enable interactive mode

---

## Files Updated by S1

- `docs/2026-05-14/agent-sync-website/plans/spikes/s1-terminal-decision.md` (this file)

---

## Ready for S2 (Base HTML/CSS Structure)

S1 findings will be incorporated into the base structure in S2.