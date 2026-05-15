# agent-sync-public

Public repository for sharing AI agent skills and configuration with the community.

## What's Here?

This repository is organized into:

```
├── skills/          # AI agent skills (installable via npx skills)
├── agents/          # Agent instruction files (AGENTS.md, GEMINI.md, etc.)
└── README.md
```

## Repository Structure

### 📚 `skills/`

AI agent skills that can be installed using the [`npx skills`](https://www.skills.sh/) CLI.

**Install all skills:**
```bash
npx skills add renatocaliari/agent-sync-public
```

**Install a specific skill:**
```bash
npx skills add renatocaliari/agent-sync-public/cali-product-workflow
```

See [skills/README.md](skills/README.md) for details.

### 🤖 `agents/`

Agent instruction files for various AI agents. Each agent has its own folder.

Currently supported:
- Instructions for configuring AI agents with shared skills and workflows

## About

Published using [agent-sync](https://github.com/renatocaliari/agent-sync) — a CLI tool for synchronizing AI agent configurations and skills across multiple machines.

## License

MIT