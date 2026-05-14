---
approved: true
approved_at: "2026-05-14T19:35:00-03:00"
approved_via: plannotator --gate
version: "1.0"
date: "2026-05-14"
slug: agent-sync-website
owner: cali
tags: [website, landing-page, terminal-simulation]
---

# Spec: agent-sync Landing Website

## 1. Problem Statement

agent-sync is a Python CLI to sync configs and skills across multiple AI agents (Claude Code, Gemini CLI, RooCode, Cline, Cursor, Qwen, Pi). Problem: each agent has its own config directory, users manually maintain everything.

**We need an elegant website** that:
1. Shows what agent-sync does visually and hands-on
2. Lets developers see the CLI in action BEFORE installing
3. Projects professional credibility (not a hacky bash script)

## 2. Assumptions

- **Target:** Developers using multiple AI agents
- **Visitors:** Arrive via GitHub, Twitter/X, Hacker News, or referrals
- **Decision:** Already considering the tool; site must CONVINCE, not explain from scratch
- **Stack:** Vanilla HTML/CSS/JS (zero dependencies, instant load)
- **Deploy:** GitHub Pages (same repo, `gh-pages` branch)
- **Maintenance:** Easy — 1 main HTML file

## 3. Out of Scope

- Full documentation (goes to `/docs`)
- Blog or changelog
- Comments or complex analytics
- Multi-language
- Dark/light mode toggle (dark only — aligned with terminal theme)

## 4. In Scope

1. **Terminal Simulation** — In-browser functional terminal with xterm.js
2. **Quick Install Section** — Copy-paste commands (curl, pip, brew)
3. **Agent Showcase** — Grid with logos and descriptions
4. **Feature List** — Clear list with benefits
5. **How It Works** — Simplified flow diagram
6. **GitHub CTA** — Repo link + stars count
7. **Responsive** — Works on mobile (terminal scrollable)

## 5. Visual Direction

**Hybrid: Terminal + Clean Explanations**

- **Language:** 100% English (all UI text, labels, descriptions)
- **Animations:** Rare but fantastic — 2-3 key moments that delight. Not a circus of motion.
  - **Terminal typing effect:** Characters appear one-by-one on first load (typewriter, 40ms/char)
  - **Scroll-triggered reveals:** Cards fade-in + slight upward translate (400ms ease-out, staggered 100ms)
  - **CTA hover glow:** Subtle radial gradient pulse on button hover
  - **NO continuous animations:** No floating, pulsing, or spinning that distracts
- **Typography:** JetBrains Mono (terminal), Inter (UI text)
- **Colors:** 
  - Background: #0d1117
  - Terminal chrome: #161b22
  - Primary accent: #58a6ff
  - Success: #3fb950
  - Text: #c9d1d9
  - Muted: #8b949e

## 6. Technical Decisions

### Why Vanilla HTML/CSS/JS?

| Alternative | Problem |
|------------|---------|
| Next.js | Overkill for static landing page |
| Astro | Build step = more friction |
| Eleventy | Another build step |
| Hugo | Go templates = more complex |

Vanilla = 1 `index.html` file anyone can edit with Ctrl+F.

### Terminal Library: xterm.js

- Mature, well-maintained, lightweight (~500KB bundle)
- Supports themes, addons (fit, search, web links)
- Mobile-friendly with touch support

### Fonts

- **JetBrains Mono** via Bunny Fonts (GDPR-compliant CDN)
- Fallback: `Consolas, Monaco, monospace`

## 7. Content Structure

### Hero Section
```
🤖 agent-sync
Sync your AI agents configs & skills — from one repo, everywhere.

[curl install command] [pip install command]

⬇️ See it in action below
```

### Terminal Demo Section
```
# Interactive terminal simulation
# Pre-programmed demo sequence:
1. agent-sync list-agents
2. agent-sync sync --dry-run
3. agent-sync sync
4. Shows config files being copied

# User can also type commands manually
```

### Features Section
```
⚡ One Command Setup
agent-sync init && agent-sync link <repo>

🔄 Real-time Sync
Changes in one machine? Push and pull instantly.

🛡️ Safe by Default
Dry-run first, rollback on failure.

🌍 Multi-Agent Support
Claude, Gemini, RooCode, Cline, Cursor, Qwen, Pi...
```

### Supported Agents Section
```
[Logo Grid]
Claude Code | Gemini CLI | RooCode | Cline | Cursor | Qwen | Pi
```

### Quick Install Section
```
# Option 1: curl (fastest)
curl -fsSL https://agent-sync.dev/install.sh | sh

# Option 2: pip
pip install agent-sync

# Option 3: brew
brew install agent-sync

# Verification
agent-sync --version
```

### CTA
```
⭐ Star on GitHub | 📦 PyPI | 📖 Docs
```

## 8. Performance Targets

- **First Contentful Paint:** < 1.5s
- **Total Blocking Time:** < 200ms
- **Bundle Size:** < 1MB total (xterm.js ~500KB)
- **Lighthouse Score:** > 90 (Performance, Accessibility)

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Terminal simulation feels "fake" | Use real xterm.js, realistic output |
| Mobile terminal unreadable | Min font size 14px, horizontal scroll |
| GitHub Pages custom domain | CNAME file, DNS config |
| xterm.js compatibility | Polyfill for older browsers |

## 10. Dependencies (CDN)

```html
<!-- xterm.js -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.css">
<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.js"></script>

<!-- Fonts -->
<link href="https://fonts.bunny.net/css?family=jetbrains-mono:400,500,700">

<!-- No JS frameworks needed -->
```

## 11. File Structure

```
/
├── index.html          # Main landing page (single file)
├── docs/              # Full documentation
│   └── ...
├── src/               # CLI source code
│   └── agent_sync/
├── pyproject.toml
└── README.md          # Short, links to landing + docs
```

## 12. Success Metrics

- GitHub stars: +50 in first month
- Lighthouse Performance: > 90
- Bounce rate: < 40%
- Terminal demo engagement: > 30% of visitors interact with terminal