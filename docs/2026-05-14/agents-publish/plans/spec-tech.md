---
title: "Tech Plan: agent-sync publish --agents"
slug: "agents-publish"
date: "2026-05-14"
spec_version: 2
status: "draft"
approved: false
---

# Tech Planning — publish --agents

## 0. Product Context

**From spec-product_v2.md:**

| Decisão | Valor |
|---------|-------|
| CLI | `agent-sync publish --agents|--skills|--all` (default: `--all`) |
| Repo | Mesmo repo público das skills (`agent-sync-public-skills`) |
| Estrutura no repo | `agents/<agent-name>/<file>` |
| Scanner | Heurístico com regex patterns |
| Escopo | Todos os 10 agentes (CLI + VS Code extensions) |

**Interface direction:** A+D hybrid — TUI espelha `skills publish`, flag `--simple` opcional.

---

## 1. High-Level Sequence

```
Sequencing strategy: riskiest-first
Justification: agent discovery é o desconhecido mais crítico. Se a varredura de
config_patterns não funcionar como esperado, todo o resto falha.
```

| # | Scope | Type | Dependência | Justificativa |
|---|-------|------|-------------|---------------|
| S1 | **Agent Discovery Spike** | spike | nenhuma | Descobre quais arquivos existem antes de construir qualquer coisa |
| S2 | **Security Scanner** | feature | S1 | Módulo independente; funciona com output de S1 |
| S3 | **TUI + publish_agents()** | feature | S1, S2 | Depende de ambos; integra discovery + scanner + seleção |
| S4 | **Config Persistence** | feature | S3 | Salva seleção; só faz sentido após TUI existir |
| S5 | **CLI Integration** | feature | S3, S4 | CLI chama functions de S3+S4 |
| S6 | **publish.py Refactoring** | feature | S5 | Refatora dispatcher; só faz sentido após tudo pronto |

**Rollout strategy:** Scoped rollout — S1-S2 primeiro (fundação), depois S3-S4 (experiência completa), depois S5-S6 (integração CLI final).

---

## 2. Scope S1 — Agent Discovery Spike

**[TYPE]** spike

### Objective

Criar `src/agent_sync/agent_discovery.py` que varre `agent_registry.yaml` para descobrir arquivos de instrução (.md) nos diretórios de config de cada agente.

### Why spike first

Não sabemos se `config_patterns` cobre todos os arquivos que queremos. Não sabemos se o registry está completo para todos os agentes. Spike primeiro para validar antes de investir em TUI e CLI.

### Implementation

**Arquivo novo:** `src/agent_sync/agent_discovery.py`

```python
"""
Agent instruction file discovery.

Scans agent_registry.yaml to find instruction files (.md) in agent
config directories based on config_patterns.
"""

from pathlib import Path
import yaml
from dataclasses import dataclass


@dataclass
class AgentInstructionFile:
    agent_name: str      # e.g., "pi.dev", "gemini-cli"
    filename: str        # e.g., "AGENTS.md", "GEMINI.md"
    full_path: Path      # e.g., Path("/Users/cali/.pi/agent/AGENTS.md")
    exists: bool         # False se arquivo não existe


def load_registry() -> dict:
    """Load agent_registry.yaml."""
    registry_path = Path(__file__).parent / "agent_registry.yaml"
    with open(registry_path) as f:
        return yaml.safe_load(f)


def discover_agent_instructions() -> list[AgentInstructionFile]:
    """
    Scan config_patterns from registry and find .md files.

    Returns list of AgentInstructionFile for all matching .md files
    across all agents. Only returns files that actually exist on disk.
    """
    registry = load_registry()

    # Agents to scan (exclude global-skills — no config_dir)
    agents_to_scan = [k for k in registry.keys() if k != "global-skills"]

    results: list[AgentInstructionFile] = []

    for agent_name in agents_to_scan:
        agent_data = registry[agent_name]
        config_dir_raw = agent_data.get("config_dir", "")
        config_patterns: list[str] = agent_data.get("config_patterns", [])
        config_filename = agent_data.get("config_filename", "")

        # Resolve ~ in config_dir
        config_dir = Path(config_dir_raw).expanduser()

        # Also add the config_filename itself (e.g., settings.json)
        all_patterns = config_patterns.copy()
        if config_filename:
            all_patterns.append(config_filename)

        for pattern in all_patterns:
            # Only care about .md files for publish --agents
            if not pattern.endswith(".md"):
                continue

            for match in config_dir.glob(pattern):
                if match.is_file() and not match.name.startswith("."):
                    results.append(AgentInstructionFile(
                        agent_name=agent_name,
                        filename=match.name,
                        full_path=match,
                        exists=True,
                    ))

    # Deduplicate by (agent_name, filename)
    seen: set[tuple] = set()
    unique: list[AgentInstructionFile] = []
    for item in results:
        key = (item.agent_name, item.filename)
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return sorted(unique, key=lambda x: (x.agent_name, x.filename))
```

**Tarefas:**
1. Criar `agent_discovery.py` com `discover_agent_instructions()`
2. Usar `Path.expanduser()` para resolver `~`
3. Deduplicar por (agent, filename)
4. **Não incluir** `global-skills` (sem config_dir)
5. **Testar** com dados reais: listar todos os arquivos encontrados

### Definition of Done

- [ ] `discover_agent_instructions()` retorna lista de `AgentInstructionFile`
- [ ] Cada arquivo tem `agent_name`, `filename`, `full_path`, `exists`
- [ ] Filtra apenas `.md` files
- [ ] Deduplica por (agent, filename)
- [ ] Teste manual confirma arquivos encontrados correspondem aos esperados

### Acceptance Criteria

```
AC-S1: Executar discover_agent_instructions() e listar todos os .md
       encontrados em ~/.pi/agent/, ~/.gemini/, ~/.config/opencode/, etc.

AC-S1: Nenhum arquivo .json, .yaml, .env aparece nos resultados

AC-S1: Arquivos inexistentes não aparecem na lista
```

---

## 3. Scope S2 — Security Scanner

**[TYPE]** feature

### Objective

Criar `src/agent_sync/security_scanner.py` com scanner heurístico que detecta conteúdo sensível em arquivos de instrução.

### Implementation

**Arquivo novo:** `src/agent_sync/security_scanner.py`

```python
"""
Security scanner for agent instruction files.

Detects potentially sensitive content before public publishing:
- Absolute paths (/Users/, /home/, /root/, C:\)
- API tokens and keys (sk-, ghp_, api_, secret)
- Internal commands (/skill:, /ctx-, ctx_batch_execute)
- Server paths (server., .renatocaliari.com)
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import TypedDict


class Issue(TypedDict):
    rule: str
    severity: str  # "critical" | "high" | "medium" | "low"
    snippet: str


@dataclass
class ScanResult:
    safe: bool
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""


# Regex patterns for detection
PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # Absolute paths
    ("ABS_PATH_UNIX", "high", re.compile(r"/Users/\w+/")),
    ("ABS_PATH_HOME", "medium", re.compile(r"/home/\w+/")),
    ("ABS_PATH_ROOT", "high", re.compile(r"/root/")),
    ("ABS_PATH_WINDOWS", "high", re.compile(r"[A-Z]:\\[\w\\]+")),
    # Tokens and keys
    ("TOKEN_OPENAI", "critical", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("TOKEN_GITHUB", "critical", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("TOKEN_GITHUB_ALT", "critical", re.compile(r"gho_[A-Za-z0-9]{36}")),
    ("KEY_API", "critical", re.compile(r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[\w-]{20,}['\"]?")),
    ("KEY_SECRET", "critical", re.compile(r"(?i)(secret|password|passwd)\s*[=:]\s*['\"]?[\w!@#$%^&*]{8,}['\"]?")),
    # Internal commands
    ("INTERNAL_CMD_SKILL", "high", re.compile(r"/skill:[a-z0-9-]+")),
    ("INTERNAL_CMD_CTX", "high", re.compile(r"(ctx_batch_execute|ctx_search|ctx_execute)\(")),
    # Server paths
    ("SERVER_PATH", "medium", re.compile(r"(?i)(server\.|renatocaliari\.com|SSH|cat ~/\\.ssh/)")),
]


def scan_file(path: Path) -> ScanResult:
    """Scan a single file for sensitive content."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return ScanResult(safe=False, issues=[], summary=f"Could not read file: {e}")

    issues: list[Issue] = []
    for rule, severity, pattern in PATTERNS:
        for match in pattern.finditer(content):
            snippet = match.group(0)
            # Truncate snippet for display
            if len(snippet) > 60:
                snippet = snippet[:60] + "..."
            issues.append(Issue(rule=rule, severity=severity, snippet=snippet))

    # Deduplicate by rule+snippet
    seen: set[tuple] = set()
    unique: list[Issue] = []
    for issue in issues:
        key = (issue["rule"], issue["snippet"])
        if key not in seen:
            seen.add(key)
            unique.append(issue)

    has_critical = any(i["severity"] == "critical" for i in unique)
    safe = len(unique) == 0 or not has_critical

    return ScanResult(safe=safe, issues=unique, summary="")


def scan_and_report(files: list[tuple[str, Path]]) -> dict[Path, ScanResult]:
    """Scan multiple files and return results per file."""
    return {path: scan_file(path) for _, path in files}
```

**Tarefas:**
1. Criar `security_scanner.py` com `ScanResult` dataclass
2. Implementar todos os regex patterns do spec
3. `scan_file(path) -> ScanResult`
4. `scan_multiple(files) -> dict[path, ScanResult]`
5. Deduplicar issues por rule+snippet
6. Adicionar testes unitários com arquivos de mock

### Definition of Done

- [ ] `scan_file()` retorna `ScanResult` com `safe`, `issues`, `summary`
- [ ] Todos os 8 padrões implementados (abs paths, tokens, commands, server)
- [ ] Deduplicação funciona (mesmo issue não aparece 2x)
- [ ] Arquivos ilegíveis retornam safe=False com error summary
- [ ] Testes unitários com mock content

### Acceptance Criteria

```
AC-S2: scan_file("/caminho/que/existe") detecta /Users/cali/ e retorna Issue

AC-S2: scan_file("/caminho/sem/problemas") retorna safe=True, issues=[]

AC-S2: scan_file com conteúdo "sk-1234567890abcdefghijklmnop" retorna
       severity="critical", rule="TOKEN_OPENAI"

AC-S2: scan_file com "/skill:cali-product-planner" retorna rule="INTERNAL_CMD_SKILL"
```

---

## 4. Scope S3 — TUI + publish_agents()

**[TYPE]** feature

### Objective

Criar `publish_agents()` em `publish.py` com TUI completa: Rich table, security panel, cross-reference notices. Reutilizar ao máximo o padrão de `publish_skills()`.

### Implementation

**Modificar:** `src/agent_sync/publish.py`

**Tarefas:**

#### 4.1 Estrutura base

```python
# Adicionar no início de publish.py, após os imports existentes:
from .agent_discovery import discover_agent_instructions, AgentInstructionFile
from .security_scanner import scan_file, ScanResult


def get_available_agents() -> list[dict]:
    """
    Scan for available agent instruction files.
    Returns list of dicts compatible with TUI selection pattern.
    """
    files = discover_agent_instructions()
    return [
        {
            "name": f"{info.agent_name}/{info.filename}",
            "agent": info.agent_name,
            "filename": info.filename,
            "path": info.full_path,
        }
        for info in files
    ]
```

#### 4.2 Render agents table (espelha render_selection_table)

```python
def render_agents_table(agents: list, selected_names: set) -> Table:
    """Render TUI table for agent instruction selection."""
    table = Table(box=box.ROUNDED, show_header=True,
                  header_style="bold cyan", expand=True)
    table.add_column("ID", justify="right", style="dim", width=4)
    table.add_column("Pub", justify="center", width=5)
    table.add_column("Agent", style="green")
    table.add_column("File", style="cyan")

    for i, agent in enumerate(agents, 1):
        key = f"{agent['agent']}:{agent['filename']}"
        is_selected = key in selected_names
        status = "[bold green]✓[/]" if is_selected else "[red]○[/]"
        table.add_row(str(i), status, agent["agent"], agent["filename"])

    return table
```

#### 4.3 Interactive agents selection (espelha interactive_selection)

```python
def interactive_agents_selection(agents: list, initial_selected: set) -> set:
    """TUI for selecting agent instructions to publish."""
    from ._selection import parse_multiselect_input

    selected = set(initial_selected)
    item_names = [f"{a['agent']}:{a['filename']}" for a in agents]

    while True:
        console.clear()
        console.print("\n[bold cyan]📤 Select Agent Instructions to Publish[/bold cyan]\n")

        table = render_agents_table(agents, selected)
        console.print(table)

        console.print("\n[bold]Controls:[/bold]")
        console.print("  • Enter numbers to toggle (e.g. [green]'1,3,5'[/green])")
        console.print("  • Type [cyan]'all'[/cyan] or [cyan]'none'[/cyan]")
        console.print("  • Press [bold white]Enter[/] when done")

        choice = Prompt.ask("\nSelection", default="done")
        result = parse_multiselect_input(choice, item_names, selected)
        if result is None:
            break
        selected = result

    return selected
```

#### 4.4 Security panel (NOVO — não existe em publish_skills)

```python
def show_security_panel(results: dict[Path, ScanResult]) -> list[Path]:
    """
    Show security panel for files with issues.
    Returns list of paths the user chose to SKIP.
    """
    unsafe_files = {
        path: result for path, result in results.items()
        if not result.safe
    }

    if not unsafe_files:
        return []

    panel_content = []
    for path, result in unsafe_files.items():
        issues_text = "\n".join(
            f"  • [{i['severity']}]{i['rule']}[/]: `{i['snippet']}`"
            for i in result.issues
        )
        panel_content.append(
            f"[bold]{path.name}[/] ([yellow]{path.parent.name}[/])\n{issues_text}"
        )

    console.print(Panel(
        "\n\n".join(panel_content),
        title="[bold yellow]⚠️  Security Warnings Detected[/bold yellow]",
        border_style="yellow",
    ))

    console.print("\n[bold]What would you like to do?[/]")
    console.print("  [[bold green]c[/]] Continue publishing (you've been warned)")
    console.print("  [[bold cyan]e[/]] Edit files before publishing (opens $EDITOR)")
    console.print("  [[bold magenta]s[/]] Skip unsafe files from selection")
    console.print("  [[bold red]q[/]] Cancel publish")

    choice = Prompt.ask("\nChoice", choices=["c", "e", "s", "q"], default="s")

    if choice == "q":
        return "cancel"
    elif choice == "s":
        return list(unsafe_files.keys())
    elif choice == "e":
        for path in unsafe_files:
            console.print(f"\n[bold]Editing {path}[/]")
            subprocess.run(["$EDITOR", str(path)])
        return []
    else:
        return []
```

#### 4.5 publish_agents() principal

```python
def publish_agents(
    repo_url: str | None = None,
    dry_run: bool = False,
    interactive: bool = False,
    selected_override: set | None = None,
) -> bool:
    """
    Publish selected agent instructions to a public GitHub repository.
    """
    # 1. Discover
    available_agents = get_available_agents()
    if not available_agents:
        console.print("\n[yellow]⚠ No agent instruction files found.[/yellow]\n")
        return False

    # 2. Scan for security
    scan_results = {
        item["path"]: scan_file(item["path"])
        for item in available_agents
    }

    # 3. Selection
    selected = selected_override if selected_override is not None else set()

    if interactive:
        config = Config()
        saved = getattr(config, "published_agents", [])
        if not selected:
            selected = set(saved) if saved else set()

        selected = interactive_agents_selection(available_agents, selected)
    else:
        if not selected:
            selected = {f"{a['agent']}:{a['filename']}" for a in available_agents}

    # Map selected names back to agent dicts
    selected_items = [
        item for item in available_agents
        if f"{item['agent']}:{item['filename']}" in selected
    ]

    if not selected_items:
        console.print("\n[yellow]⚠ No agent instructions selected[/yellow]\n")
        return False

    # 4. Security panel
    selected_paths = [item["path"] for item in selected_items]
    selected_results = {p: scan_results[p] for p in selected_paths}

    if interactive:
        skip_paths = show_security_panel(selected_results)
        if skip_paths == "cancel":
            console.print("\n[yellow]Publish cancelled[/yellow]\n")
            return False
        if skip_paths:
            selected_items = [i for i in selected_items if i["path"] not in skip_paths]
            selected = {f"{i['agent']}:{i['filename']}" for i in selected_items}

    if not selected_items:
        console.print("\n[yellow]⚠ All files skipped[/yellow]\n")
        return False

    # 5. Summary
    console.print("\n[bold green]📋 Summary[/]\n")
    summary = Table(box=box.SIMPLE)
    summary.add_column("Agent", style="green")
    summary.add_column("File", style="cyan")
    summary.add_column("Security", justify="center")
    for item in selected_items:
        path = item["path"]
        result = scan_results[path]
        icon = "[red]⚠️[/]" if not result.safe else "[green]✓[/]"
        summary.add_row(item["agent"], item["filename"], icon)
    console.print(summary)

    # 6. Repo + git push
    repo_url = _resolve_repo_url(repo_url)
    if not repo_url:
        return False

    if dry_run:
        console.print(f"\n[blue]🔍 DRY RUN: Would publish {len(selected_items)} agent instructions to {repo_url}[/blue]\n")
        return True

    if interactive and not Confirm.ask("\n[bold red]Confirm publishing?[/]", default=True):
        console.print("\n[yellow]Publish cancelled[/yellow]\n")
        return False

    return _push_agents_to_repo(selected_items, repo_url)
```

#### 4.6 Shared git push helper

```python
def _push_agents_to_repo(items: list[dict], repo_url: str) -> bool:
    """Clone repo, copy agents/, commit, push."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(tmp_path)],
                capture_output=True, timeout=60,
            )
        except Exception:
            subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, timeout=15)
            subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_path, capture_output=True, timeout=15)

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(exist_ok=True)

        for item in items:
            agent_subdir = agents_dir / item["agent"]
            agent_subdir.mkdir(exist_ok=True)
            shutil.copy2(item["path"], agent_subdir / item["filename"])

        readme_path = tmp_path / "README.md"
        if readme_path.exists():
            readme_path.write_text(_generate_readme_for_agents(items, repo_url))

        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True, timeout=30)
        subprocess.run(
            ["git", "commit", "-m", f"feat: publish {len(items)} agent instructions"],
            cwd=tmp_path, capture_output=True, check=True, timeout=30,
        )
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=tmp_path, capture_output=True, check=True, timeout=15)
        subprocess.run(["git", "push", "-u", "origin", "main", "--force"], cwd=tmp_path, capture_output=True, check=True, timeout=120)

        console.print(f"\n[green]✓ Published {len(items)} agent instructions to {repo_url}![/green]\n")
        return True
```

### Definition of Done

- [ ] `publish_agents()` funciona end-to-end
- [ ] TUI com Rich table para seleção (espelha `publish_skills`)
- [ ] Security panel aparece APÓS seleção, não antes
- [ ] Options: editar, skip, continuar, cancelar
- [ ] Resumo com ícone de segurança (⚠️ ou ✓) por arquivo
- [ ] Cross-reference notice: "💡 Quer publicar também skills? agent-sync publish --skills"

### Acceptance Criteria

```
AC-S3: publish_agents() com interactive=True mostra TUI de seleção

AC-S3: Arquivo com /Users/cali/ mostra ⚠️ no resumo

AC-S3: Security panel oferece 4 opções (c/e/s/q)

AC-S3: publish_agents() com dry_run=True não faz git push

AC-S3: Arquivos copiados para agents/<agent>/<file> no repo
```

---

## 5. Scope S4 — Config Persistence

**[TYPE]** feature

### Objective

Adicionar `published_agents` à `Config` class e persistir seleção de agent instructions.

### Implementation

**Modificar:** `src/agent_sync/config.py`

```python
@property
def published_agents(self) -> list[str]:
    """Get list of agent instruction files whitelisted for public publishing.

    Format: ["agent:filename", ...]
    e.g., ["pi.dev:AGENTS.md", "gemini-cli:GEMINI.md"]
    """
    return self._config.get("published_agents", [])

@published_agents.setter
def published_agents(self, items: list[str]) -> None:
    """Set list of agent instruction files for public publishing."""
    self._config["published_agents"] = sorted(list(set(items)))
    self.save()
```

### Definition of Done

- [ ] `config.published_agents` retorna lista de `"agent:filename"`
- [ ] `config.published_agents = [...]` persiste em config.yaml
- [ ] Na próxima execução, seleção salva aparece como default

### Acceptance Criteria

```
AC-S4: config.published_agents = ["pi.dev:AGENTS.md"] persiste em config.yaml

AC-S4: Reiniciar e ler config.published_agents retorna a lista salva

AC-S4: publish_agents() usa published_agents como default na TUI
```

---

## 6. Scope S5 — CLI Integration

**[TYPE]** feature

### Objective

Integrar `publish --agents`, `publish --skills`, `publish --all` no CLI. `publish` sem flags assume `--all`.

### Implementation

**Modificar:** `src/agent_sync/cli.py`

```python
@click.command("publish")
@click.option("--skills", is_flag=True, help="Publish skills")
@click.option("--agents", is_flag=True, help="Publish agent instructions")
@click.option("--all", "publish_all", is_flag=True, default=True, help="Publish both (default)")
@click.option("--dry-run", is_flag=True, help="Show what would be published")
@click.option("--repo", "repo_url", help="GitHub repository URL")
@click.pass_context
def publish(ctx, skills, agents, publish_all, dry_run, repo_url):
    """
    Publish skills and/or agent instructions to a public GitHub repository.

    Default: publishes BOTH skills and agent instructions (--all).
    Use --skills or --agents to publish only one type.
    """
    from .publish import publish_skills, publish_agents

    # Default: publish all if no specific flags
    do_all = publish_all and not skills and not agents
    do_skills = skills or do_all
    do_agents = agents or do_all

    success = True

    if do_skills:
        from .publish import publish_skills
        success_skills = publish_skills(
            repo_url=repo_url,
            dry_run=dry_run,
            interactive=False,
        )
        if not success_skills:
            success = False

    if do_agents:
        from .publish import publish_agents
        success_agents = publish_agents(
            repo_url=repo_url,
            dry_run=dry_run,
            interactive=False,
        )
        if not success_agents:
            success = False

    if not success:
        raise click.Abort()
```

### Definition of Done

- [ ] `agent-sync publish --agents` chama `publish_agents()`
- [ ] `agent-sync publish --skills` chama `publish_skills()`
- [ ] `agent-sync publish` (sem flags) assume `--all` e publica ambos
- [ ] `agent-sync skills publish` continua funcionando (deprecated notice)
- [ ] `--dry-run` e `--repo` funcionam em todos os modos

### Acceptance Criteria

```
AC-S5: agent-sync publish --agents --dry-run mostra preview sem push

AC-S5: agent-sync publish (sem flags) executa skills + agents sequencialmente

AC-S5: agent-sync skills publish mostra deprecation warning

AC-S5: --repo override funciona em todos os modos
```

---

## 7. Scope S6 — publish.py Refactoring

**[TYPE]** feature

### Objective

Refatorar `publish.py` para extrair código compartilhado em helpers reutilizáveis.

### Implementation

**Modificar:** `src/agent_sync/publish.py`

```python
def _resolve_repo_url(repo_url: str | None) -> str | None:
    """Resolve repo URL: param → publish.yaml → prompt."""
    publish_config = {}
    if PUBLISH_CONFIG_PATH.exists():
        try:
            publish_config = yaml.safe_load(PUBLISH_CONFIG_PATH.read_text()) or {}
        except Exception: pass

    resolved = repo_url or publish_config.get("repo_url")
    if not resolved:
        try:
            result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True, text=True, timeout=5,
            )
            username = result.stdout.strip() if result.returncode == 0 else "YOUR_USERNAME"
        except Exception:
            username = "YOUR_USERNAME"

        default_repo = f"{username}/agent-sync-public-skills"
        resolved = Prompt.ask(
            "\n[bold]Enter GitHub repository URL[/]",
            default=f"https://github.com/{default_repo}",
        )
        if not validate_github_url(resolved):
            console.print("\n[red]✗ Invalid repository URL[/red]\n")
            return None

        PUBLISH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        publish_config["repo_url"] = resolved
        PUBLISH_CONFIG_PATH.write_text(yaml.dump(publish_config))

    return resolved


def _git_clone_or_init(repo_url: str, tmp_path: Path) -> None:
    """Clone existing repo or init fresh."""
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(tmp_path)],
            capture_output=True, timeout=60,
        )
    except Exception:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, timeout=15)
        subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_path, capture_output=True, timeout=15)


def _git_push(tmp_path: Path, repo_url: str, message: str) -> None:
    """Git add, commit, push."""
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True, timeout=30)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=tmp_path, capture_output=True, check=True, timeout=30,
    )
    try:
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=tmp_path, capture_output=True, timeout=15)
    except Exception:
        pass
    subprocess.run(
        ["git", "push", "-u", "origin", "main", "--force"],
        cwd=tmp_path, capture_output=True, check=True, timeout=120,
    )


def generate_readme_for_agents(items: list, repo_url: str) -> str:
    """Generate agents/README section for the repository README."""
    repo_name = repo_url.replace("https://github.com/", "").replace(".git", "")
    sections = {}
    for item in items:
        agent = item["agent"]
        if agent not in sections:
            sections[agent] = []
        sections[agent].append(item["filename"])

    lines = ["\n## Agent Instructions\n"]
    for agent, files in sorted(sections.items()):
        lines.append(f"### {agent}")
        for f in files:
            lines.append(f"- `{f}`")
        lines.append("")
    return "\n".join(lines)
```

### Definition of Done

- [ ] `publish_skills()` usa `_resolve_repo_url()`, `_git_clone_or_init()`, `_git_push()`
- [ ] `publish_agents()` usa os mesmos helpers
- [ ] Não há duplicação de lógica de git ou repo URL

### Acceptance Criteria

```
AC-S6: publish_skills() refatorado — mesma funcionalidade, código DRY

AC-S6: publish_agents() usa helpers compartilhados

AC-S6: generate_readme_for_agents() gera seção markdown correta
```

---

## 8. Task Summary Table

| Scope | Task | Sequenced by | Blocking |
|-------|------|-------------|---------|
| S1 | Criar `agent_discovery.py` | - | S2, S3 |
| S1 | Testar discovery com dados reais | S1 | S2, S3 |
| S2 | Criar `security_scanner.py` | S1 | S3 |
| S2 | Testes unitários do scanner | S2 | S3 |
| S3 | Estrutura base `publish_agents()` | S1, S2 | S4, S5 |
| S3 | Rich table agents | S3 | S4, S5 |
| S3 | Security panel component | S3 | S4, S5 |
| S3 | Git push para `agents/` | S3 | S4, S5 |
| S3 | Cross-reference notices | S3 | - |
| S4 | `published_agents` em Config | S3 | S5 |
| S4 | Salvar seleção pós-confirm | S4 | S5 |
| S5 | CLI `publish --agents` | S3, S4 | S6 |
| S5 | CLI `publish --skills` | S5 | S6 |
| S5 | CLI `publish` default --all | S5 | S6 |
| S5 | `skills publish` deprecated | S5 | - |
| S6 | Shared helpers | S5 | - |

---

## 9. Final Summary

### Scope Names

| ID | Name | Type | Dep |
|----|------|------|-----|
| S1 | Agent Discovery Spike | spike | - |
| S2 | Security Scanner | feature | S1 |
| S3 | TUI + publish_agents() | feature | S1, S2 |
| S4 | Config Persistence | feature | S3 |
| S5 | CLI Integration | feature | S3, S4 |
| S6 | publish.py Refactoring | feature | S5 |

### Execution Routing

| Scope | Executor |
|-------|----------|
| S1 | scout / worker |
| S2 | worker |
| S3 | worker |
| S4 | worker |
| S5 | worker |
| S6 | worker |

### Rollout Sequence

```
S1 (spike) → S2 → S3 → S4 → S5 → S6
   ↓
Valida discovery
   ↓
Scanner
   ↓
TUI completa
   ↓
Persistência
   ↓
CLI final
   ↓
Refatoração
```