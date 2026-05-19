"""Source discovery for publish feature.

DRY: Unified discovery of skills and agents from multiple sources.
SoC: Discovery logic separated from UI and git operations.
"""

from typing import Optional

from rich.console import Console

from .base import SourceWithSkills, SourceStatus
from .config import load_config, PublishStateManager
from .local_source import discover_local_skills
from .external_source import discover_external_skills, get_source_staleness
from .agents_source import discover_local_agents
from .models import SourceInfo, SelectionState


console = Console()


# =============================================================================
# SKILLS DISCOVERY
# =============================================================================

def discover_skills_sources(config) -> list[SourceWithSkills]:
    """Discover all skills sources (local + external).
    
    Args:
        config: PublishConfig loaded from config file
    
    Returns:
        List of SourceWithSkills with discovered skills
    """
    results: list[SourceWithSkills] = []
    
    # Local skills
    local_skills = discover_local_skills()
    results.append(SourceWithSkills(
        source_id="local",
        source_url="local",
        status=SourceStatus.ACTIVE if local_skills else SourceStatus.UNKNOWN,
        skills=local_skills,
        is_local=True,
    ))
    
    # External sources
    for source in config.skill_sources:
        skills, status = discover_external_skills(source, config.cache_dir)
        staleness = get_source_staleness(source, config.cache_dir)
        
        results.append(SourceWithSkills(
            source_id=source.repo_id,
            source_url=source.url,
            status=status,
            skills=skills,
            is_local=False,
            staleness=staleness,
        ))
    
    return results


def skills_to_source_infos(sources: list[SourceWithSkills]) -> list[SourceInfo]:
    """Convert SourceWithSkills to SourceInfo for TUI.
    
    Args:
        sources: List of SourceWithSkills from discovery
    
    Returns:
        List of SourceInfo for UI display
    """
    source_infos: list[SourceInfo] = []
    
    for src in sources:
        # Truncate URL for display
        if src.source_url == "local":
            subtitle = "~/.agents/skills/"
        else:
            subtitle = _truncate_url(src.source_url)
        
        source_infos.append(SourceInfo(
            source_id=src.source_id,
            label=src.label,  # Use the property from SourceWithSkills
            subtitle=subtitle,
            items=[s.name for s in src.skills],
            status=src.status.value,
            extra=src.staleness or "",
        ))
    
    return source_infos


def build_initial_selection(
    config,
    sources: list[SourceWithSkills],
) -> dict[str, set[str]]:
    """Build initial selection from saved config.
    
    Args:
        config: PublishConfig with saved selections
        sources: List of discovered SourceWithSkills
    
    Returns:
        Dict of source_id -> set of selected item names
    """
    selection: dict[str, set[str]] = {}
    
    for src in sources:
        saved = config.get_skills_for_source(src.source_id)
        selection[src.source_id] = set(saved) if saved else set()
    
    return selection


# =============================================================================
# AGENTS DISCOVERY
# =============================================================================

def discover_agents_sources() -> list[SourceInfo]:
    """Discover all local agents.
    
    Returns:
        List of SourceInfo with discovered agents
    """
    agents = discover_local_agents()
    
    if not agents:
        return []
    
    return [
        SourceInfo(
            source_id="agents",
            label="AGENTS",
            subtitle="~/.pi/agent/",
            items=[a.name for a in agents],
            status="active",
            extra="",
        )
    ]


# =============================================================================
# COMBINED DISCOVERY
# =============================================================================

def discover_all_sources() -> tuple[list[SourceInfo], list[SourceWithSkills], list[SourceInfo]]:
    """Discover all sources (skills + agents) and restore saved selection.
    
    Returns:
        Tuple of (skills_sources, skills_source_infos, agents_source_infos)
    """
    config = load_config()
    
    # Discover skills
    skills_sources = discover_skills_sources(config)
    skills_source_infos = skills_to_source_infos(skills_sources)
    
    # Discover agents
    agents_source_infos = discover_agents_sources()
    
    return skills_sources, skills_source_infos, agents_source_infos


def load_saved_selection(
    source_infos: list[SourceInfo],
) -> dict[str, set[str]]:
    """Load saved selection from config and restore to sources.
    
    Args:
        source_infos: List of SourceInfo to populate selection
    
    Returns:
        Dict of source_id -> set of selected items
    """
    saved_state = PublishStateManager.load()
    
    selection: dict[str, set[str]] = {}
    for src in source_infos:
        selection[src.source_id] = set()
    
    # Restore from saved state
    for src_id, names in saved_state.skills.items():
        if src_id in selection:
            selection[src_id].update(names)
    for src_id, names in saved_state.agents.items():
        if src_id in selection:
            selection[src_id].update(names)
    
    return selection


# =============================================================================
# HELPERS
# =============================================================================

def _truncate_url(url: str, max_len: int = 40) -> str:
    """Truncate URL for display."""
    if not url or url == "local":
        return url
    if len(url) <= max_len:
        return url
    parts = url.split("/")
    if len(parts) >= 3:
        return f"{parts[0]}//.../{parts[-1]}"
    return url[:max_len-1] + "…"


def get_source_label(source_id: str, is_local: bool = False) -> str:
    """Get display label for a source."""
    if source_id == "local":
        return "LOCAL"
    if source_id == "agents":
        return "AGENTS"
    # External: extract owner from "owner/repo"
    parts = source_id.split("/")
    if len(parts) >= 2:
        return parts[1].upper()[:6]  # Just the repo name, truncated
    return source_id.upper()[:6]