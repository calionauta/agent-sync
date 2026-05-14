# 🔄 agent-sync

![Tests](https://github.com/renatocaliari/agent-sync/actions/workflows/tests.yml/badge.svg)

**One tool to rule them all: Sync, Centralize, and Share AI Agent configurations and skills.**

`agent-sync` solves the fragmentation of the AI agent ecosystem by providing a unified workflow for your CLI tools.

> 🔗 **DotAgents Protocol compatible** — agent-sync's `~/.agents/skills/` hub follows the [DotAgents Protocol](https://dotagentsprotocol.com/) convention for portable, version-controlled agent configuration. See [docs/dotagents.md](docs/dotagents.md).

---

## 🎯 Why agent-sync?

*   **Unified Skills Hub**: Stop duplicating skills across different agents. Centralize everything in `~/.agents/skills/` and let every agent (Claude, Gemini, Opencode, etc.) use them.
*   **Private Backup & Sync**: Keep your agent configurations and custom skills safely backed up in a **private GitHub repository**. Seamlessly sync your entire environment between multiple machines.
*   **Share with the World**: Effortlessly publish your best custom skills to a **public repository**, allowing the community to benefit from your specialized agent tools.
*   **Extension Support**: Automatically detects and backs up skills from agent extensions (e.g., Opencode Superpowers, Cursor extensions) with their symlink structures preserved.

---

## 🤖 Supported Agents

### CLI Agents

| Agent | Config Files | Skills Path | Method |
|-------|-------------|-------------|--------|
| **claude-code** | `settings.json` | `~/.claude/commands/` | Copy |
| **gemini-cli** | `settings.json` | `~/.gemini/tools/` | Copy |
| **opencode** | `opencode.json` | `~/.config/opencode/skills/` | Config |
| **pi.dev** | `settings.json`, `models.json` | `~/.pi/agent/skills/` | Native |
| **qwen-code** | `settings.json` | `~/.qwen/skills/` | Copy |

### VS Code Extensions & IDEs

| Agent | Config Files | Skills Path | Method |
|-------|-------------|-------------|--------|
| **cline** | `state.json` | `~/.cline/skills/` | Copy |
| **cursor** | `settings.json` | `~/.cursor/skills/` | Native |
| **roocode** | `custom_modes.yaml` | `~/.roo/skills/`, `~/.agents/skills/` | Native |
| **windsurf** | `config.json` | `~/.codeium/windsurf/skills/` | Copy |

---

## ⚡ Quick Start

### Install CLI
```bash
# Recommended (isolated install)
pipx install agent-sync

# Or via pip
pip install agent-sync
```

### First Machine — Create Repo
```bash
agent-sync init                    # Create repo + wizard
agent-sync push                    # Backup to GitHub
```

### Additional Machines — Link
```bash
agent-sync link https://github.com/user/repo.git
agent-sync pull                    # Restore configs
```

### Reconfigure
```bash
agent-sync setup                   # Change agents/options
agent-sync config show             # View current config
```

---

## 📁 Recommended Repository Names

Use these standard names for consistency:

| Purpose | Repository Name | Example |
|---------|----------------|---------|
| **CLI Tool** | `agent-sync` | `renatocaliari/agent-sync` |
| **Private Configs** | `agent-sync-private-configs` | `renatocaliari/agent-sync-private-configs` |
| **Public Skills** | `agent-sync-public-skills` | `renatocaliari/agent-sync-public-skills` |

**Why these names?**
- ✅ **Consistent** - All start with `agent-sync-`
- ✅ **Clear** - "private" and "public" make purpose obvious
- ✅ **Discoverable** - Easy to find via GitHub search
- ✅ **Standard** - Follows common naming patterns

**Example Setup:**
```bash
# Initialize private configs (first machine)
agent-sync init --name agent-sync-private-configs

# Link on additional machines
agent-sync link https://github.com/YOUR_USERNAME/agent-sync-private-configs.git

# Publish skills to public repo
agent-sync skills publish --repo https://github.com/YOUR_USERNAME/agent-sync-public-skills
```

---

## 🛠️ CLI Commands

`agent-sync` uses a categorized help structure. Run `agent-sync --help` to see all options.

#### 🔄 Sync & Backup
- `init` - Initialize a new sync repository (first machine)
- `link <url>` - Connect to an existing repository (other machines)
- `push` - Backup local changes to GitHub `[-m, --skills-only, --configs-only, --agents-only]`
- `pull` - Download and apply changes from GitHub `[--force, --skills-only, --configs-only, --agents-only]`
- `status` - Check sync state per agent

#### 🤖 Agent Management
- `agents` - List supported agents and their sync method
- `enable <agent>` / `disable <agent>` - Toggle sync for a specific agent
- `setup` - Interactive wizard to reconfigure agents and options

#### 📚 Skills
- `skills list` - List all centralized skills in `~/.agents/skills/`
- `skills centralize` - Move skills from agent directories to global hub (with safety TUI)
  - `--yes` - Non-interactive: skip all orphan skills
  - `--import-all` - Import all orphans without TUI (old behavior)
  - `--dry-run` - Preview changes without modifying anything
  - `--copy` - Copy instead of move
  - `--distribute` - After centralizing, copy all skills to all agent directories

  > 🛡️ **Safety features** (v0.15+): Interactive TUI selects which orphans to import (default: none). Content comparison via hash detects divergent copies. Post-selection prompt: Keep or Remove unselected.
  > 🔗 **DotAgents Protocol**: Structure automatically follows `.agents/` convention (https://dotagentsprotocol.com/)
- `skills diff` - Show differences between local and remote skills
- `skills reconcile` - Resolve divergences between local and remote
- `skills delete` - Delete skills from hub and all agent directories (interactive)

#### 📤 Publish
- `publish` - Publish skills and/or agent instructions to public GitHub
  - `publish` (default) — Publish both skills AND agent instructions
  - `publish --skills` — Publish only skills
  - `publish --agents` — Publish only agent instructions (AGENTS.md, GEMINI.md, etc.)
  - `--dry-run` — Preview without publishing
  - `--repo <url>` — Specify target repository

  **Security Scanner:** Scans for sensitive content before publishing:
  - Absolute paths (`/Users/`, `/home/`, `/root/`)
  - API tokens (`sk-`, `ghp_`)
  - Internal commands (`/skill:`, `ctx_batch_execute()`)
  - Server paths (`server.`, `.renatocaliari.com`)

  **⚠️ Deprecated:** `skills publish` → Use `publish --skills` instead

  **Unified Flow (v0.20+):**
  - Discovery → Summary table → Security scan → Confirm → Publish
  - Security warnings are contextual based on --skills/--agents/--all

#### 🛠️ System
- `config show` - View current configuration
- `config edit` - Open configuration file in editor
- `config repo` - View, set, or remove repository URL
- `config reset` - Reset config to defaults (keeps repo linked)
- `generate-config` - Generate default config file (useful as starting point)
- `update` - Check for and install CLI updates
- `version` - Show version information
- `secrets` - Manage secrets sync (disabled by default)

---

## 🔌 Extension Support

agent-sync supports agent extensions that create subdirectories with skills (e.g., Opencode Superpowers, Cursor extensions).

**Example structure:**
```
~/.config/opencode/
├── superpowers/
│   └── skills/              # Extension skills
└── skills/
    └── superpowers  →  symlink → ../superpowers/skills/
```

**Supported:**
- Extension subdirectories (e.g., `~/.config/opencode/superpowers/skills/`)
- Internal symlinks (preserved)
- External symlinks (removed)
- Multiple extensions simultaneously
- Skills with special characters (`__`, `-`)

**How it works:**
- `push` - Detects extensions, backs up skills + symlinks, creates `.agent-sync-manifest.json`
- `pull` - Reads manifest, restores extension skills and symlinks to original locations

See full documentation: [Extension Support](docs/extensions.md)

---

## 🤝 Contributing

I welcome contributions to keep this project growing and stable. You don't need to be a Python expert to help.

### How to help:
-   **Add New Agents**: Support for new AI CLIs is data-driven. Just add a few lines to [src/agent_sync/agent_registry.yaml](src/agent_sync/agent_registry.yaml).
-   **Bug Fixes & UX**: Found a clunky TUI flow or a bug? Open a PR!
-   **Improve Docs**: Help me make these guides clearer.

If you are an AI model (LLM) contributing to this project, please read [AGENTS.md](AGENTS.md) for versioning and architectural mandates.

---

## 🙏 Inspiration

Inspired by [opencode-synced](https://github.com/iHildy/opencode-synced), expanded to support multiple agent CLIs and other powerful features.

---

## 🔗 DotAgents Protocol

This project aligns with the [DotAgents Protocol](https://dotagentsprotocol.com/) for AI agent configuration.

### What we follow

| Aspect | Status | Details |
|--------|--------|---------|
| `~/.agents/skills/` hub | ✅ Applied | Vendor-neutral skills directory |
| `.agents/` directory structure | ✅ Applied | Skills and agents organized under `.agents/` |
| Git-friendly config | ✅ Applied | Version-controllable via private GitHub repo |
| Vendor-neutral skills | ✅ Applied | All skills share `~/.agents/skills/` as source of truth |

### What's different (and why)

| Aspect | DotAgents | agent-sync | Why |
|--------|-----------|------------|-----|
| Sub-agents | `~/.agents/agents/` (unified) | Per-vendor paths | Agents store profiles in vendor-specific formats; unifying would lose features |
| MCP config | `~/.agents/mcp.json` (unified) | Per-vendor MCPs | Each vendor has unique MCP capabilities; merging would lose features |
| Workspace override | `./.agents/` (overlay) | Not supported | Would require complex merge semantics; not a priority |
| Config format | JSON | YAML | YAML is more readable for humans; JSON is optional in the spec |
| Public bundles | hub.dotagentsprotocol.com | Not integrated | Would require separate publishing workflow |

### What we'd need to change for 100% compliance

These are **not planned** because they would reduce functionality:

1. **Unified `~/.agents/agents/`** — Would require converting Claude/Cursor/etc. agent formats to a standard format
2. **Unified `~/.agents/mcp.json`** — Would lose vendor-specific MCP features
3. **Workspace overrides** — Complex merge semantics for marginal benefit

The current approach (DotAgents for skills, vendor-specific for everything else) gives you the best of both: standard skills management + full vendor features.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
