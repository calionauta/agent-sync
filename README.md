# 🔄 agent-sync

![Tests](https://github.com/renatocaliari/agent-sync/actions/workflows/tests.yml/badge.svg)

**One tool to rule them all: Sync, Centralize, and Share AI Agent configurations and skills.**

`agent-sync` solves the fragmentation of the AI agent ecosystem by providing a unified workflow for your CLI tools.

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
pipx install git+https://github.com/renatocaliari/agent-sync.git
```

### Setup & Sync
```bash
agent-sync setup    # Interactive wizard
agent-sync push     # Backup to GitHub
```

### Other Machines
```bash
agent-sync link <your-private-repo-url>
agent-sync pull
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
- `push` - Backup local changes to GitHub `[-m, --skills-only, --configs-only]`
- `pull` - Download and apply changes from GitHub `[--force]`
- `status` - Check sync state

#### 🤖 Agents & Skills
- `agents` - List supported agents and their sync method
- `enable` / `disable` - Toggle sync for specific agents
- `skills list` - List all centralized skills
- `skills diff` - Show differences between local and remote skills
- `skills reconcile` - Resolve local vs remote divergences
- `skills centralize` - Move skills from agents to global hub
- `skills delete` - Delete skills from hub and agents (interactive)
- `skills publish` - Share selected skills to a public repo

#### 🛠️ System
- `update` - Interactive CLI self-update
- `config edit` - Manual configuration override

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

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
