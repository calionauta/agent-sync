# Configuration

## Configuration File

agent-sync uses a YAML configuration file located at:

- **Linux/macOS**: `~/.config/agent-sync/config.yaml`
- **Windows**: `%APPDATA%\agent-sync\config.yaml`

## Structure

```yaml
# Repository URL (required)
repo_url: https://github.com/username/repo.git

# Enabled agents
agents:
  - opencode
  - claude-code
  - pi.dev
  - qwen-code

# Agent-specific configuration
agents_config:
  opencode:
    enabled: true
    skills_method: config
    sync:
      configs: true
```

## Commands

### View Configuration

```bash
agent-sync config show
```

### Edit Configuration

```bash
agent-sync config edit
```

### Set Repository

```bash
agent-sync config repo https://github.com/user/repo.git
```

### Reset Configuration

```bash
agent-sync config reset
```

## Protocol Support

### DotAgents Protocol (default)

Always enabled. Skills live in `~/.agents/skills/`.

### GitAgent Protocol (opt-in)

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

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AGENT_SYNC_HOME` | Override config directory |
| `AGENT_SYNC_REPO` | Override repository URL |