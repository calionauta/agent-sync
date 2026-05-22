# Code Context: agent-sync Discovery & Publish

## Files Retrieved

### Skills Discovery
1. `src/agent_sync/publish/local_source.py` (lines 15-91) - Descoberta de skills locais em `~/.agents/skills/`
2. `src/agent_sync/publish/external_source.py` (lines 21-209) - Descoberta de skills de repositórios GitHub externos
3. `src/agent_sync/publish/discovery.py` (lines 29-165) - Orquestração da descoberta de skills e agents

### Agents Discovery
4. `src/agent_sync/agent_discovery.py` (lines 30-146) - Descoberta de arquivos .md de instrução de agents
5. `src/agent_sync/agent_registry.yaml` (lines 1-188) - Registry de agentes com padrões de configuração

### Publish
6. `src/agent_sync/publish/git_publish.py` (lines 1-443) - Operações git e copy para publish

---

## Key Code

### Skills Discovery (local_source.py)
```python
SKILLS_DIR = Path.home() / ".agents" / "skills"

def discover_local_skills() -> list[SkillSource]:
    """Descobre skills de ~/.agents/skills/."""
    for item in SKILLS_DIR.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            skill_paths.append(item)
        elif item.is_file() and item.suffix == ".md":
            # Root .md files são ignorados
            pass
```

**Padrão de estrutura de skill:**
```
~/.agents/skills/{skill-name}/
├── SKILL.md          # Obrigatório
├── references/       # Opcional
└── ...               # Outros arquivos
```

### Skills Discovery (external_source.py)
```python
def _find_skills_in_repo(cache_path: Path, source: SourceConfig) -> list[SkillSource]:
    """Encontra skills por git ls-files."""
    # Procura por arquivos SKILL.md
    if f.endswith("/SKILL.md"):
        skill_dir = f.replace("/SKILL.md", "")
        skill_name = skill_dir.split("/")[-1]
        # Também verifica skills/ subdiretório
```

**Padrões aceitos:**
- `skills/{name}/SKILL.md`
- `{name}/SKILL.md` (na raiz)
- `SKILL.md` (repo inteiro é uma skill)

### Agents Discovery (agent_discovery.py)
```python
@dataclass
class AgentInstructionFile:
    agent_name: str      # e.g., "pi.dev", "gemini-cli"
    filename: str       # e.g., "AGENTS.md", "GEMINI.md"
    full_path: Path     # e.g., Path("/Users/cali/.pi/agent/AGENTS.md")
    exists: bool

def discover_agent_instructions(...) -> list[AgentInstructionFile]:
    """Escaneia config_patterns do registry e encontra arquivos .md."""
    # Type 1: Arquivos na raiz do config_dir (AGENTS.md, GEMINI.md, etc.)
    for pattern in all_patterns:
        for match in config_dir.glob(pattern):
            # Type 2: Custom agents em agents/ subdiretórios
            for md_file in agents_dir.rglob("*.md"):
```

**Padrões do registry para agents:**
```yaml
pi.dev:
  config_dir: "~/.pi/agent"
  config_patterns: ["*.json", "*.yaml", "AGENTS.md", "SYSTEM.md"]
  config_filename: "settings.json"

claude-code:
  config_dir: "~/.claude"
  config_patterns: ["*.json", "AGENTS.md", "SYSTEM.md", "CLAUDE.md"]
  agents_dir_name: "agents"        # Custom agents em ~/.claude/agents/*.md
```

### Publish (git_publish.py)
```python
DEFAULT_IGNORE_PATTERNS = [
    '.git', '.gitignore', '.github',
    'sessions', 'blob', 'cache', '.cache',
    '*.jsonl', '*.log', '*.sqlite', '*.db',
    'models.json', 'models.yaml', 'config_local.json',
    '.env', '.env.*', '*.pem', '*.key',
]

def do_git_publish(items, subdir, ...):
    # Copia skills/agents para tmp_dir/subdir
    # Gera README.md
    # git init, commit, push --force
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     discovery.py                             │
│  discover_skills_sources() → LocalSource + ExternalSources  │
│  discover_agents_sources() → AgentSource                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  local_source.py    external_source.py   agents_source.py
  ~/.agents/skills/   GitHub repos        ~/.pi/agent/*.md
                           │                  ~/.claude/agents/*.md
                           ▼                  ~/.gemini/AGENTS.md
                      git_publish.py           ...
                           │
                           ▼
                  git commit + push --force
                  para published_repo
```

---

## File Structure Examples

### Skills (local)
```
~/.agents/skills/
├── dogfood/
│   ├── SKILL.md
│   └── references/
├── plannning/
│   ├── SKILL.md
│   └── templates/
└── ...

~/.agents/skills/dogfood/SKILL.md
~/.agents/skills/plannning/SKILL.md
```

### Skills (external repo)
```
owner/repo/
├── skills/
│   ├── pi-subagents/
│   │   └── SKILL.md
│   └── agent-sync/
│       └── SKILL.md
└── README.md
```

### Agents
```
~/.pi/agent/
├── AGENTS.md              # pi.dev main config
├── SYSTEM.md              # system prompt
└── settings.json

~/.claude/
├── AGENTS.md              # claude-code root
├── SYSTEM.md
├── settings.json
└── agents/
    ├── test-reviewer.md   # custom agents
    └── code-reviewer.md

~/.gemini/
├── AGENTS.md              # gemini-cli
├── GEMINI.md
└── settings.json
```

---

## Start Here

1. **`src/agent_sync/agent_registry.yaml`** - Registry central de todos os agentes suportados. Define onde procurar skills e agents para cada agent.

2. **`src/agent_sync/agent_discovery.py`** - Usa o registry para descobrir arquivos de instrução .md dos agents.

3. **`src/agent_sync/publish/local_source.py`** - Descoberta de skills locais em `~/.agents/skills/`.

4. **`src/agent_sync/publish/git_publish.py`** - Como os items selecionados são copiados e publicados via git.