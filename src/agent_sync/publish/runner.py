"""Publish runner - thin wrapper that delegates to specialized modules.

SoC: This module only orchestrates. Real logic is in:
  - setup.py: Publish flows (skills, agents, setup)
  - git_publish.py: Git operations
  - discovery.py: Source discovery
  - models.py: Domain models

DRY: Delegates to setup.py functions.
"""

from enum import Enum

from .setup import (
    confirm,
    run_skills_flow,
    run_agents_flow,
    run_publish_setup,
    print_repo_not_configured,
)
from .git_publish import publish_skills, publish_agents
from .models import SelectionState, SourceInfo


class ItemType(Enum):
    """Type of item being published."""
    SKILLS = "skills"
    AGENTS = "agents"


def run_publish_flow(item_type: ItemType = ItemType.SKILLS) -> bool:
    """Main unified publish flow for skills or agents."""
    if item_type == ItemType.SKILLS:
        return run_skills_flow()
    else:
        return run_agents_flow()


def run_all_publish_flow() -> bool:
    """Run all publish flow (step-by-step)."""
    return run_publish_setup()


# Legacy exports
def run_publish_flow_legacy() -> bool:
    """Legacy entry point for skills."""
    return run_publish_flow(ItemType.SKILLS)


def run_agents_publish_flow_legacy() -> bool:
    """Legacy entry point for agents."""
    return run_publish_flow(ItemType.AGENTS)


# Re-export helpers for internal use
def _confirm(prompt: str, default_yes: bool = True) -> bool:
    """Ask a confirmation question with Y as default."""
    return confirm(prompt, default_yes)


def _print_repo_not_configured() -> None:
    """Print message when repo is not configured."""
    print_repo_not_configured()