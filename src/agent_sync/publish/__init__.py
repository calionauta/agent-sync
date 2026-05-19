from __future__ import annotations


"""Publish module for agent-sync skills publishing.

This module handles publishing skills from multiple sources to a central
public repository for sharing with the community.
"""

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
from .external_source import (
    discover_external_skills,
    get_source_staleness,
    refresh_source,
)
from .local_source import (
    discover_local_skills,
    get_local_source_status,
    SKILLS_DIR,
)
from .git_publish import (
    publish_skills,
    publish_agents,
    do_git_publish,
    git_commit_and_push,
    generate_skills_readme,
    generate_agents_readme,
)
from .discovery import (
    discover_skills_sources,
    discover_agents_sources,
    discover_all_sources,
    skills_to_source_infos,
    build_initial_selection,
    load_saved_selection,
)
from .models import (
    PublishState,
    SelectionState,
    SourceInfo,
    SourcePickerItem,
    build_picker_items,
    parse_number_input,
    handle_number_input_for_state,
)
from .runner import (
    run_publish_setup,
)
from .tui import (
    MultiSelectTUI,
    create_skills_tui,
    create_agents_tui,
)
from .agents_source import (
    AgentSource,
    AgentSourceStatus,
    discover_local_agents,
    get_local_agent_status,
    publish_agents,
)
from ..validators import validate_github_url


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
]