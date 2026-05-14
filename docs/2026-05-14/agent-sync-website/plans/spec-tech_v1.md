---
approved: true
approved_at: "2026-05-14T19:45:00-03:00"
approved_via: plannotator --gate
version: "1.0"
date: "2026-05-14"
slug: agent-sync-website
owner: cali
parent: "spec-product_v1"
tags: [website, landing-page, terminal-simulation]
---

# Tech Planning: agent-sync Landing Website

## 0. Product Context

From [spec-product_v1.md](../spec-product_v1.md).

**Problem:** agent-sync needs an elegant landing page that showcases the CLI in action BEFORE users install it.

**Scope IN:**
- Terminal simulation with xterm.js
- Quick install section
- Agent showcase grid
- Feature list
- Responsive dark theme

**Scope OUT:**
- Full documentation site
- Blog/changelog
- Multi-language
- Dark/light toggle

**Key Technical Decisions:**
- Vanilla HTML/CSS/JS (1 `index.html` file)
- xterm.js via CDN
- JetBrains Mono via Bunny Fonts
- GitHub Pages deploy (`gh-pages` branch)

---

## 1. Identified Scopes

| # | Scope | Type | Rationale |
|---|-------|------|-----------|
| S1 | Terminal Simulation Research | spike | Research xterm.js vs alternatives, typing effect approach, mobile compatibility |
| S2 | Base HTML/CSS Structure | feature | Foundation for all other sections |
| S3 | Hero Section | feature | First impression, above-the-fold |
| S4 | Terminal Demo Section | feature | Core differentiator |
| S5 | Features Section | feature | Benefits communication |
| S6 | Agent Showcase Section | feature | Visual proof of multi-agent support |
| S7 | Quick Install Section | feature | Conversion to install |
| S8 | CTA + Footer | feature | Final push to action |
| S9 | Performance Optimization | optimization | Lighthouse > 90, bundle < 1MB |

---

## 2. High-Level Sequence

```
S1 (spike) → S2 (base) → S3 (hero) → S4 (terminal) → S5 (features) → S6 (agents) → S7 (install) → S8 (CTA) → S9 (perf)
```

**Justification:**
- **S1 first:** Need to validate terminal approach before building around it
- **S2 second:** Foundation needed before any section
- **S3 early:** Hero is above-the-fold, must load fast
- **S4 after hero:** Terminal is the main draw, needs base + hero context
- **S5-S8 sequential:** Each section builds on CSS foundation
- **S9 last:** Measure actual performance after full implementation

---

## 3. Detailed Development Sequence

---

### [S1] Terminal Simulation Research

**Type:** spike  
**Objective:** Validate terminal implementation approach before committing to code

#### Tasks

**T1.1: xterm.js Research**
- Review xterm.js v5.5.0 API
- Test CDN loading speed
- Verify mobile touch support
- Check font rendering quality

**T1.2: Typing Effect Approach**
- Option A: Pre-generated ANSI output
- Option B: xterm.js Typewriting addon (custom)
- Option C: Character-by-character JS injection
- Pick winner based on realism vs complexity

**T1.3: Demo Command Sequence**
- Define realistic 4-5 command demo
- Design mock output for each command
- Plan auto-execute timing

**Definition of Done:**
- [ ] Documented xterm.js integration approach
- [ ] Selected typing effect method
- [ ] Defined demo command sequence with mock outputs
- [ ] Verified CDN availability

---

### [S2] Base HTML/CSS Structure

**Type:** feature  
**Objective:** Create foundation with CSS variables, typography, colors, responsive grid

#### Tasks

**T2.1: HTML Skeleton**
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>agent-sync — Sync your AI agents configs & skills</title>
  <meta name="description" content="...">
  <!-- Preload fonts -->
  <!-- xterm.js CSS -->
</head>
<body>
  <main>
    <!-- Sections will be added here -->
  </main>
  <script src="xterm.js"></script>
</body>
</html>
```

**T2.2: CSS Variables**
```css
:root {
  --bg-primary: #0d1117;
  --bg-secondary: #161b22;
  --bg-tertiary: #21262d;
  --text-primary: #c9d1d9;
  --text-muted: #8b949e;
  --accent-blue: #58a6ff;
  --accent-green: #3fb950;
  --accent-yellow: #d29922;
  --accent-red: #f85149;
  --radius: 8px;
  --shadow: 0 8px 32px rgba(0,0,0,0.4);
}
```

**T2.3: Typography Setup**
- JetBrains Mono via Bunny Fonts
- Inter fallback for UI text
- Font display: swap

**T2.4: Responsive Grid**
- Mobile-first
- Breakpoints: 640px, 1024px
- Container max-width: 1200px

**T2.5: Utility Classes**
- `.container`
- `.section`
- `.visually-hidden`
- `.gradient-text`

**Definition of Done:**
- [ ] Valid HTML5 semantic structure
- [ ] All CSS variables defined
- [ ] Fonts loading correctly
- [ ] Responsive at mobile/tablet/desktop
- [ ] No console errors

---

### [S3] Hero Section

**Type:** feature  
**Objective:** First impression — title, tagline, install commands, scroll indicator

#### Tasks

**T3.1: Title + Tagline**
```html
<section class="hero">
  <h1 class="gradient-text">🤖 agent-sync</h1>
  <p class="tagline">Sync your AI agents configs & skills — from one repo, everywhere.</p>
</section>
```

**T3.2: Install Commands**
- curl command (primary, highlighted)
- pip command (secondary)
- brew command (tertiary)
- Copy button for each

**T3.3: Scroll Indicator**
- Animated arrow pointing down
- Smooth scroll to terminal section
- Appears after 2s delay

**T3.4: Hero Animation**
- Fade-in on load (300ms)
- Title slides up (400ms ease-out)

**Definition of Done:**
- [ ] Title and tagline visible above fold
- [ ] All 3 install commands displayed
- [ ] Copy buttons functional
- [ ] Scroll indicator animates once
- [ ] Mobile: commands stack vertically

---

### [S4] Terminal Demo Section

**Type:** feature  
**Objective:** In-browser terminal showing agent-sync in action

#### Tasks

**T4.1: Terminal Window Chrome**
- macOS-style traffic lights (red/yellow/green)
- Window title bar with "Terminal"
- Rounded corners, shadow
- Dark background (#161b22)

**T4.2: xterm.js Integration**
```javascript
const term = new Terminal({
  theme: {
    background: '#161b22',
    foreground: '#c9d1d9',
    cursor: '#58a6ff',
  },
  fontFamily: 'JetBrains Mono',
  fontSize: 14,
  lineHeight: 1.4,
});
```

**T4.3: Demo Sequence**
1. `agent-sync list-agents` → shows 7 agents
2. `agent-sync sync --dry-run` → shows what would be copied
3. `agent-sync sync` → shows files being copied
4. Success message

**T4.4: Typing Effect**
- Characters appear at 40ms intervals
- Cursor blinks during typing
- Auto-advance to next command after 500ms pause

**T4.5: Interactive Mode**
- After demo, enable manual input
- Filter to valid agent-sync commands
- Show help on `help` or `?`

**Definition of Done:**
- [ ] Terminal window looks native macOS
- [ ] Demo plays automatically on scroll into view
- [ ] Typing effect is smooth (40ms, no lag)
- [ ] User can type commands after demo
- [ ] Mobile: terminal scrolls horizontally

---

### [S5] Features Section

**Type:** feature  
**Objective:** Communicate key benefits with visual cards

#### Tasks

**T5.1: Section Header**
- "Why agent-sync?" title
- Subtle underline accent

**T5.2: Feature Cards (4)**
1. ⚡ One Command Setup
2. 🔄 Real-time Sync
3. 🛡️ Safe by Default
4. 🌍 Multi-Agent Support

**T5.3: Scroll-Triggered Animation**
```css
.feature-card {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 400ms ease-out, transform 400ms ease-out;
}

.feature-card.visible {
  opacity: 1;
  transform: translateY(0);
}
```

**T5.4: Staggered Reveal**
- Card 1: 0ms delay
- Card 2: 100ms delay
- Card 3: 200ms delay
- Card 4: 300ms delay

**Definition of Done:**
- [ ] 4 feature cards with icons
- [ ] Cards animate on scroll into view
- [ ] Staggered timing correct
- [ ] Mobile: cards stack, same animation

---

### [S6] Agent Showcase Section

**Type:** feature  
**Objective:** Visual proof of supported agents

#### Tasks

**T6.1: Section Header**
- "Supported Agents" title
- "Sync configs for all your AI assistants" subtitle

**T6.2: Agent Logo Grid**
- 7 logos in responsive grid (3 columns desktop, 2 tablet, 1 mobile)
- Agent names below logos
- Subtle hover effect (scale 1.05)

**Supported agents:**
- Claude Code
- Gemini CLI
- RooCode
- Cline
- Cursor
- Qwen
- Pi

**T6.3: Agent Cards**
- Each card: logo, name, brief description
- CLI agents vs IDE extensions visual distinction

**Definition of Done:**
- [ ] All 7 agents displayed with logos
- [ ] Grid responsive at all breakpoints
- [ ] Hover effects smooth
- [ ] Mobile: single column

---

### [S7] Quick Install Section

**Type:** feature  
**Objective:** Easy conversion to install

#### Tasks

**T7.1: Code Blocks**
- Syntax highlighting (green prompt, white text)
- Copy button in top-right corner
- Hover highlight

**T7.2: Install Methods**
```bash
# Fastest — curl
curl -fsSL https://agent-sync.dev/install.sh | sh

# Python users
pip install agent-sync

# macOS — Homebrew
brew install agent-sync

# Verify
agent-sync --version
```

**T7.3: Verification Command**
- Highlight `agent-sync --version`
- Show expected output: `agent-sync vX.X.X`

**Definition of Done:**
- [ ] All 4 code blocks with copy buttons
- [ ] Copy button shows "Copied!" feedback
- [ ] Code blocks styled consistently
- [ ] Mobile: horizontal scroll with padding

---

### [S8] CTA + Footer

**Type:** feature  
**Objective:** Final push to action + navigation

#### Tasks

**T8.1: CTA Section**
- Large "Get Started" button
- GitHub star count (if feasible, else static number)
- Links to docs

**T8.2: CTA Button Animation**
```css
.cta-button:hover {
  box-shadow: 0 0 20px rgba(88, 166, 255, 0.4);
  transition: box-shadow 300ms ease-out;
}
```

**T8.3: Footer**
- GitHub repo link
- PyPI link
- Docs link
- MIT License
- Author credit

**Definition of Done:**
- [ ] CTA button with glow effect on hover
- [ ] All footer links functional
- [ ] Footer aligned properly
- [ ] Mobile: stacked layout

---

### [S9] Performance Optimization

**Type:** optimization  
**Metric:** Lighthouse Performance score > 90 (higher is better)

#### Tasks

**T9.1: Bundle Optimization**
- Verify xterm.js lazy loading
- Preload critical fonts
- Inline critical CSS

**T9.2: Font Loading**
- `font-display: swap` already set
- Verify no FOUT (Flash of Unstyled Text)

**T9.3: Image Optimization**
- Logos as inline SVG (no external requests)
- No large images to load

**T9.4: Accessibility**
- All interactive elements keyboard accessible
- Color contrast ratios met
- Screen reader labels

**T9.5: Lighthouse Audit**
- Run lighthouse audit
- Address any issues
- Target: Performance > 90, Accessibility > 90

**Definition of Done:**
- [ ] Lighthouse Performance score >= 90
- [ ] Lighthouse Accessibility score >= 90
- [ ] First Contentful Paint < 1.5s
- [ ] No render-blocking resources

---

## 4. Final Summary — Scope Names

| # | Scope | Type | Executor |
|---|-------|------|----------|
| S1 | Terminal Simulation Research | spike | worker |
| S2 | Base HTML/CSS Structure | feature | worker |
| S3 | Hero Section | feature | worker |
| S4 | Terminal Demo Section | feature | worker |
| S5 | Features Section | feature | worker |
| S6 | Agent Showcase Section | feature | worker |
| S7 | Quick Install Section | feature | worker |
| S8 | CTA + Footer | feature | worker |
| S9 | Performance Optimization | optimization | autoresearch |

---

## 5. File Output

All code outputs to:
```
index.html          # Single-file landing page (incrementally built)
```

No separate CSS or JS files — everything inline for simplicity.

---

## 6. Dependencies

| Dependency | Source | Purpose |
|------------|--------|---------|
| xterm.js | jsdelivr CDN | Terminal emulator |
| JetBrains Mono | Bunny Fonts CDN | Monospace font |
| Inter | Bunny Fonts CDN | UI font (fallback) |

---

## 7. Rollout

1. **Branch:** `feat/landing-page`
2. **Testing:** Local file open + GitHub Pages preview
3. **Deploy:** Merge to `main` → GitHub Actions deploys to `gh-pages`
4. **Domain:** Configure `agent-sync.dev` CNAME