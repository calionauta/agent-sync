"""Loader for agent registry YAML."""

import yaml
from pathlib import Path
from typing import Dict, Any


def get_registry_path() -> Path:
    """Get path to agent_registry.yaml."""
    return Path(__file__).parent.parent / "agent_registry.yaml"


def load_registry() -> Dict[str, Any]:
    """Load agent registry from YAML."""
    path = get_registry_path()
    if not path.exists():
        raise FileNotFoundError(f"Agent registry not found at {path}")
    
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    
    validate_registry(data)
    return data


def validate_registry(data: Dict[str, Any]) -> None:
    """Validate agent registry schema."""
    required_fields = ["method", "skills_dir_name", "check"]
    
    for agent_name, agent_data in data.items():
        # Global skills is a special case
        if agent_name == "global-skills":
            continue
            
        for field in required_fields:
            if field not in agent_data:
                raise ValueError(f"Agent '{agent_name}' is missing required field: {field}")
        
        # Method-specific validation
        method = agent_data.get("method")
        if method not in ["native", "config", "copy"]:
            raise ValueError(f"Agent '{agent_name}' has invalid method: {method}")
            
        if method == "config" and "config_update" not in agent_data:
            # Note: config method can be used without auto-update, but usually it's why it's chosen
            pass


