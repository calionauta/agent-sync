"""Agent-specific configurations and handlers (YAML-driven)."""

from typing import Optional, List, Dict, Any
from .base import BaseAgent, GLOBAL_SKILLS_DIR
from .registry_loader import load_registry

# Import specialized agent handlers
from .roocode import RooCodeAgent
from .cline import ClineAgent
from .cursor import CursorAgent
from .windsurf import WindsurfAgent

# Internal entries that are not real agents
INTERNAL_ENTRIES = {"global-skills"}

# Map of agent names to their specialized handler classes
AGENT_HANDLERS: Dict[str, type] = {
    "roocode": RooCodeAgent,
    "cline": ClineAgent,
    "cursor": CursorAgent,
    "windsurf": WindsurfAgent,
}


def _create_agent(name: str, data: Dict[str, Any]) -> BaseAgent:
    """
    Create agent instance, using specialized handler if available.

    Args:
        name: Agent name from registry
        data: Agent data from registry

    Returns:
        Agent instance (specialized or base)
    """
    handler_class = AGENT_HANDLERS.get(name)
    if handler_class:
        return handler_class(name, data)
    return BaseAgent(name, data)


def get_all_agents() -> List[BaseAgent]:
    """Get all available agent integrations from YAML registry (including internal)."""
    registry = load_registry()
    agents = []
    for name, data in registry.items():
        agents.append(_create_agent(name, data))
    return agents


def get_agents() -> List[BaseAgent]:
    """Get all real agent integrations (excludes internal entries like global-skills)."""
    registry = load_registry()
    agents = []
    for name, data in registry.items():
        if name not in INTERNAL_ENTRIES:
            agents.append(_create_agent(name, data))
    return agents


def get_agent(name: str) -> Optional[BaseAgent]:
    """Get a specific agent by name."""
    registry = load_registry()
    if name in registry:
        return _create_agent(name, registry[name])
    return None


