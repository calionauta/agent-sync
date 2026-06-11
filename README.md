# 🔄 agent-sync

![Tests](https://github.com/renatocaliari/agent-sync/actions/workflows/tests.yml/badge.svg)

**One tool to rule them all: Sync, Centralize, and Share AI Agent configurations and skills.**

`agent-sync` solves the fragmentation of the AI agent ecosystem by providing a unified workflow for your CLI tools.

> 🔗 **Protocol Support** — agent-sync supports **DotAgents Protocol** (`~/.agents/skills/` hub) for portable skills. Optional **GitAgent Protocol** support can be enabled in config.

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
agent-sync backup                  # Backup to GitHub
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
| **Private Configs** | `agent-sync-configs` | `renatocaliari/agent-sync-configs` |
| **Public Skills** | `agent-sync-public` | `renatocaliari/agent-sync-public` |

**Why these names?**
- ✅ **Consistent** - All start with `agent-sync-`
- ✅ **Clear** - "private" and "public" make purpose obvious
- ✅ **Discoverable** - Easy to find via GitHub search
- ✅ **Standard** - Follows common naming patterns

**Example Setup:**
```bash
# Initialize private configs (first machine)
agent-sync init --name agent-sync-configs

# Link on additional machines
agent-sync link https://github.com/YOUR_USERNAME/agent-sync-configs.git

# Share your skills with the community
# Note: agent-sync share is for CREATING a public repo, not installing from one.
# To install skills from a public repo, use npx skills:
#
#   npx skills add renatocaliari/agent-sync-public
#   npx skills add https://github.com/user/skill-repo

agent-sync share add https://github.com/YOUR_USERNAME/agent-sync-public.git
```

---

## 🛠️ CLI Commands

`agent-sync` uses a categorized help structure. Run `agent-sync --help` to see all options.

#### 🔄 Sync & Backup
- `init` - Initialize a new sync repository (first machine)
- `link <url>` - Connect to an existing repository (other machines)
- `backup` - Full backup of configs, skills, and agents to private repo `[-m, --skills-only, --configs-only]`
- `push` - Legacy alias for `backup` (still works)
- `pull` - Download and apply changes from GitHub `[--force, --skills-only, --configs-only]`
- `status` - Check sync state per agent

#### 🤖 Agent Management
- `agents` - List supported agents and their sync method
- `enable <agent>` / `disable <agent>` - Toggle sync for a specific agent
- `setup` - Interactive wizard to reconfigure agents and options

#### 📚 Skills
- `skills list` - List all centralized skills in `~/.agents/skills/`
- `skills centralize` - Auto-import scattered skills from agents to hub
  - `--yes` - Non-interactive: skip all orphan skills
  - `--import-all` - Import all orphans without TUI (old behavior)
  - `--dry-run` - Preview changes without modifying anything
  - `--copy` - Copy instead of move
  - `--distribute` - After centralizing, copy all skills to all agent directories

  > 🛡️ **Safety features** (v0.15+): Interactive TUI selects which orphans to import (default: none). Content comparison via hash detects divergent copies. Post-selection prompt: Keep or Remove unselected.
  > 🔗 **DotAgents Protocol**: Structure automatically follows `.agents/` convention (https://dotagentsprotocol.com/)
- `skills audit` - Show every skill's status across hub, repo, and `RETIRED.md` (use `--json` for machine-readable)
- `skills explain <name>` - Lifecycle of a single skill (when added, last modified, current state)
- `skills prune` - Remove orphan skills from the remote repo
  - `--dry-run` - Preview only
  - `--yes` / `-y` - Skip the confirmation prompt

  > 🛡️ **Safe-by-default backup** (v0.35+): `agent-sync backup` is additive — it does NOT delete orphan skills from the remote repo. Use `backup --prune` or the dedicated `skills prune` subcommand for explicit destruction. See [Skills Lifecycle](docs/skills-lifecycle.md).
- `skills diff` - Show differences between local and remote skills
- `skills reconcile` - Resolve divergences between local and remote
- `skills delete` - Delete skills from hub and all agent directories (interactive)

#### 📤 Share
- `share run` - Interactive TUI to select skills/agents and publish to public repo
- `share add <url>` - Add a public repository
- `share list` - List configured public repositories
- `share remove <url>` - Remove a public repository

> 💡 **Install skills from public repos**: Use `npx skills add <source>` from [vercel-labs/skills](https://github.com/vercel-labs/skills). Example: `npx skills add renatocaliari/agent-sync-public`

#### 📦 Repositories
- `repos list` - Show ALL repositories (sync + publish) with status

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
- `backup` - Detects extensions, backs up skills + symlinks, creates `.agent-sync-manifest.json`
- `push` - Legacy alias (same as `backup`)
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

## 🩺 Troubleshooting

### "A skill disappeared from my hub / repo"

```bash
# 1. See the full state across hub, repo, and retirement manifest
agent-sync skills audit

# 2. Drill into one specific skill
agent-sync skills explain cali-coding-go-stack
```

The audit table shows the status of every skill. The explain command
shows the git lifecycle (first added, last modified, commit count)
and current location.

### "I want to retire a skill permanently"

Add its name to `~/.agents/skills/RETIRED.md` (one per line, `#` for
comments). The skill is no longer re-imported by `centralize`, and
won't be pruned from the repo by `push --prune` or `skills prune`.

See [Skills Lifecycle](docs/skills-lifecycle.md) for the full flow.

### "I want to UN-retire a skill"

Delete its line from `~/.agents/skills/RETIRED.md`, then run
`agent-sync skills centralize`. The skill will be re-imported to the
hub on the next sync.

### "I accidentally pruned a skill from the repo"

If you have the skill in your local `~/.agents/skills/`, just run
`agent-sync backup` (without `--prune`) — the skill will be re-committed.

If you DON'T have it locally, restore from the repo's git history:

```bash
cd ~/Library/Application\ Support/agent-sync/repo
git log --diff-filter=D --name-only --pretty=format: -- 'skills/cali-skill/'
# Find the deletion commit, restore from its parent:
git checkout <commit>^ -- skills/cali-skill/
git add skills/cali-skill/
git commit -m "fix: restore cali-skill after accidental prune"
git push origin main
```

## 🔗 Protocol Support

agent-sync supports two protocols for AI agent configuration.

### DotAgents Protocol (default)

The DotAgents Protocol provides a **vendor-neutral skills hub** — all your skills in one place, usable across agents.

| Your Benefit | How It Works |
|--------------|-------------|
| **One skills folder** | All skills live in `~/.agents/skills/` |
| **Cross-agent sharing** | Skills work with Claude, Gemini, Opencode, etc. |
| **Version controlled** | Backed up in your private GitHub repo |

**Quick start:**
```bash
# Move scattered skills to hub
agent-sync skills centralize

# Your skills are now in ~/.agents/skills/
# Push to backup
agent-sync backup
```

Learn more at [dotagentsprotocol.com](https://dotagentsprotocol.com/)

---

### GitAgent Protocol (opt-in)

The GitAgent Protocol provides comprehensive agent definitions with identity, constraints, and compliance mapping.

**Enable in your config:**
```yaml
protocols:
  gitagent:
    enabled: true
    patterns:
      - "agent.yaml"
      - "SOUL.md"
      - "RULES.md"
      - "DUTIES.md"
```

Your agent definitions are backed up alongside your other configs.

Learn more at [gitagent.sh](https://www.gitagent.sh/)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
