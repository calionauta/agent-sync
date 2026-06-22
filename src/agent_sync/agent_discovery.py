"""
Agent instruction file discovery.

Scans agent_registry.yaml to find instruction files (.md) in agent
config directories based on config_patterns.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AgentInstructionFile:
    """Represents a discovered agent instruction file."""
    agent_name: str  # e.g., "pi.dev", "gemini-cli"
    filename: str  # e.g., "AGENTS.md", "GEMINI.md"
    full_path: Path  # e.g., Path.home() / ".pi/agent/AGENTS.md"
    exists: bool  # False if file doesn't exist on disk


def load_registry() -> dict:
    """Load agent_registry.yaml from the same directory as this module."""
    registry_path = Path(__file__).parent / "agent_registry.yaml"
    with open(registry_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def discover_agent_instructions(
    include_agents: list[str] | None = None,
    exclude_agents: list[str] | None = None,
) -> list[AgentInstructionFile]:
    """
    Scan config_patterns from registry and find .md instruction files.

    Finds two types of agent files:
    1. Agent instruction files in config_dir root (AGENTS.md, GEMINI.md, etc.)
    2. Custom agent definitions in agents/ subdirectories (agent.agents_path)

    Args:
        include_agents: Optional list of agent names to include. If None, include all.
        exclude_agents: Optional list of agent names to exclude (applied after include).

    Returns:
        List of AgentInstructionFile for all matching .md files across all agents.
        Only returns files that actually exist on disk.
    """
    registry = load_registry()

    # Agents to scan (exclude global-skills — no config_dir)
    agents_to_scan = [k for k in registry.keys() if k != "global-skills"]

    # Apply include filter
    if include_agents is not None:
        agents_to_scan = [a for a in agents_to_scan if a in include_agents]

    # Apply exclude filter
    if exclude_agents is not None:
        agents_to_scan = [a for a in agents_to_scan if a not in exclude_agents]

    results: list[AgentInstructionFile] = []

    for agent_name in agents_to_scan:
        agent_data = registry[agent_name]
        config_dir_raw = agent_data.get("config_dir", "")
        config_patterns: list[str] = agent_data.get("config_patterns", [])
        config_filename = agent_data.get("config_filename", "")

        if not config_dir_raw:
            # Agent has no config directory, skip
            continue

        # Resolve ~ in config_dir
        config_dir = Path(config_dir_raw).expanduser()

        if not config_dir.exists():
            # Config directory doesn't exist, skip
            continue

        # === Type 1: Agent instruction files in config_dir root (AGENTS.md, GEMINI.md, etc.) ===
        # Build patterns list (config_patterns + config_filename if it ends with .md)
        all_patterns = list(config_patterns)
        if config_filename and config_filename.endswith(".md"):
            all_patterns.append(config_filename)

        for pattern in all_patterns:
            # Only care about .md files for publish --agents
            if not pattern.endswith(".md"):
                continue

            try:
                for match in config_dir.glob(pattern):
                    if match.is_file() and not match.name.startswith("."):
                        results.append(AgentInstructionFile(
                            agent_name=agent_name,
                            filename=match.name,
                            full_path=match,
                            exists=True,
                        ))
            except OSError:
                # Permission denied or other OS error, skip this pattern
                continue

        # === Type 2: Custom agent definitions in agents/ subdirectories ===
        # These are .md files in agents_path or agents_path_global subdirs
        # (e.g., ~/.claude/agents/test-reviewer.md, ~/.config/opencode/agents/*.md)
        agents_dirs = []
        agents_dir_name = agent_data.get("agents_dir_name")
        agents_dir_global_raw = agent_data.get("agents_dir_global", "")
        if agents_dir_name and (config_dir / agents_dir_name).exists():
            agents_dirs.append(config_dir / agents_dir_name)
        if agents_dir_global_raw:
            agents_dir_global = Path(agents_dir_global_raw).expanduser()
            if agents_dir_global.exists() and agents_dir_global not in agents_dirs:
                agents_dirs.append(agents_dir_global)

        for agents_dir in agents_dirs:
            try:
                for md_file in agents_dir.rglob("*.md"):
                    if md_file.is_file() and not md_file.name.startswith("."):
                        # Use relative path from agents_dir as the "filename"
                        rel_path = md_file.relative_to(agents_dir)
                        # Include agent name in the agent_name for disambiguation
                        # e.g., "claude-code/agents/test-reviewer.md"
                        display_name = f"{agent_name}/{rel_path}"
                        results.append(AgentInstructionFile(
                            agent_name=display_name,
                            filename=str(rel_path),
                            full_path=md_file,
                            exists=True,
                        ))
            except OSError:
                continue

    # Deduplicate by (agent_name, filename) — keep first occurrence
    seen: set[tuple] = set()
    unique: list[AgentInstructionFile] = []
    for item in results:
        key = (item.agent_name, item.filename)
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return sorted(unique, key=lambda x: (x.agent_name, x.filename))


def get_available_agents() -> list[dict]:
    """
    Scan for available agent instruction files.
    Returns list of dicts compatible with TUI selection pattern.

    Used by publish.py to get data in the format:
        {
            "name": "pi.dev/AGENTS.md",
            "agent": "pi.dev",
            "filename": "AGENTS.md",
            "path": Path.home() / ".pi/agent/AGENTS.md"
        }
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
