"""Publish module for agent-sync skills publishing.

This module handles publishing skills from multiple sources to a central
public repository for sharing with the community.
"""

from __future__ import annotations

from ..security_scanner import ScanResult
from ..validators import validate_github_url
from .agents_source import (
    AgentSource,
    AgentSourceStatus,
    discover_local_agents,
    get_local_agent_status,
    publish_agents,
)
from .base import (
    PublishConfig,
    SkillSource,
    SourceConfig,
    SourceStatus,
)
from .cache import (
    cache_dir,
    clear_cache,
    get_cache_info,
    get_cache_path,
    is_cache_valid,
    normalize_repo_id,
)
from .config import (
    CONFIG_PATH,
    add_source,
    get_published_repo,
    get_selected_skills,
    list_sources,
    load_config,
    remove_source,
    save_config,
    save_selected_skills,
    set_published_repo,
    update_source_status,
)
from .discovery import (
    build_initial_selection,
    discover_agents_sources,
    discover_all_sources,
    discover_skills_sources,
    load_saved_selection,
    skills_to_source_infos,
)
from .external_source import (
    discover_external_skills,
    get_source_staleness,
    refresh_source,
)
from .git_publish import (
    do_git_publish,
    generate_agents_readme,
    generate_skills_readme,
    git_commit_and_push,
    publish_skills,
)
from .local_source import (
    SKILLS_DIR,
    discover_local_skills,
    get_local_source_status,
)
from .models import (
    PublishState,
    SelectionState,
    SourceInfo,
    SourcePickerItem,
    build_picker_items,
    handle_number_input_for_state,
    parse_number_input,
)
from .runner import (
    run_publish_setup,
)
from .tui import (
    MultiSelectTUI,
    create_agents_tui,
    create_skills_tui,
)


def has_significant_issues(result: ScanResult) -> bool:
    """Check if result has issues that warrant user attention."""
    if not result.safe:
        return True
    return any(
        issue.get("context") not in ("variable", "deprecated")
        and issue.get("severity") in ("critical", "high")
        for issue in result.issues
    )


__all__ = [
    # Base types
    "PublishConfig",
    "SkillSource",
    "SourceConfig",
    "SourceStatus",
    # Cache
    "cache_dir",
    "clear_cache",
    "get_cache_info",
    "get_cache_path",
    "is_cache_valid",
    "normalize_repo_id",
    # Config
    "CONFIG_PATH",
    "add_source",
    "get_published_repo",
    "get_selected_skills",
    "list_sources",
    "load_config",
    "remove_source",
    "save_config",
    "save_selected_skills",
    "set_published_repo",
    "update_source_status",
    # Models
    "PublishState",
    "SelectionState",
    "SourceInfo",
    "SourcePickerItem",
    "build_picker_items",
    "parse_number_input",
    "handle_number_input_for_state",
    # Sources
    "discover_external_skills",
    "discover_local_skills",
    "get_local_source_status",
    "get_source_staleness",
    "refresh_source",
    "SKILLS_DIR",
    # Publish flows
    "run_publish_setup",
    # TUI
    "MultiSelectTUI",
    "create_skills_tui",
    "create_agents_tui",
    # Agents
    "AgentSource",
    "AgentSourceStatus",
    "discover_local_agents",
    "get_local_agent_status",
    "publish_agents",
    # Security
    "has_significant_issues",
    # Validators
    "validate_github_url",
    # Discovery
    "build_initial_selection",
    "discover_agents_sources",
    "discover_all_sources",
    "discover_skills_sources",
    "load_saved_selection",
    "skills_to_source_infos",
    # Git primitives
    "do_git_publish",
    "publish_skills",
    "git_commit_and_push",
    "generate_skills_readme",
    "generate_agents_readme",
]
