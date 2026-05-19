from __future__ import annotations


"""Config file management for publish feature."""


import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

import yaml

from .base import PublishConfig, SourceConfig, SourceStatus


CONFIG_PATH = Path.home() / ".config" / "agent-sync" / "publish.yaml"


def load_config() -> PublishConfig:
    """Load publish configuration from YAML file.
    
    Returns:
        PublishConfig with defaults if file doesn't exist.
    """
    if not CONFIG_PATH.exists():
        return PublishConfig(published_repo="")
    
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text())
        if not data:
            return PublishConfig(published_repo="")
        return PublishConfig.from_dict(data)
    except (yaml.YAMLError, KeyError, ValueError) as e:
        # If config is corrupted, backup and return default
        backup_path = CONFIG_PATH.with_suffix(".yaml.bak")
        shutil.copy2(CONFIG_PATH, backup_path)
        return PublishConfig(published_repo="")


def save_config(config: PublishConfig) -> None:
    """Save publish configuration to YAML file atomically.
    
    Writes to temp file first, then renames for atomic update.
    
    Args:
        config: PublishConfig to save
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temp file first
    fd, tmp_path = tempfile.mkstemp(suffix=".yaml", prefix="publish-")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)
        
        # Atomic rename
        shutil.move(tmp_path, CONFIG_PATH)
    except Exception:
        # Clean up temp file on error
        Path(tmp_path).unlink(missing_ok=True)
        raise


def add_source(url: str) -> None:
    """Add a new external source to config.
    
    Args:
        url: GitHub repository URL
    """
    config = load_config()
    source = config.add_source(url)
    save_config(config)


def remove_source(url: str) -> bool:
    """Remove an external source from config.
    
    Args:
        url: GitHub repository URL
        
    Returns:
        True if source was removed, False if not found.
    """
    config = load_config()
    removed = config.remove_source(url)
    if removed:
        save_config(config)
    return removed


def list_sources() -> list[SourceConfig]:
    """List all configured external sources.
    
    Returns:
        List of SourceConfig objects.
    """
    config = load_config()
    return config.skill_sources


def update_source_status(url: str, status: SourceStatus, last_success: str | None = None) -> None:
    """Update status for a source.
    
    Args:
        url: GitHub repository URL
        status: New status
        last_success: ISO date string of last successful discovery (auto-set to now if None)
    """
    config = load_config()
    for source in config.skill_sources:
        if source.url == url:
            source.status = status
            # Auto-set last_success to current time if not provided
            if last_success is None:
                source.last_success = datetime.now().isoformat()
            else:
                source.last_success = last_success
            break
    save_config(config)


def get_selected_skills() -> dict[str, list[str]]:
    """Get saved selected skills.
    
    Returns:
        Dict mapping source_id to list of skill names.
    """
    config = load_config()
    return config.selected_skills


def save_selected_skills(selected: dict[str, list[str]]) -> None:
    """Save selected skills configuration.
    
    Args:
        selected: Dict mapping source_id to list of skill names
    """
    config = load_config()
    config.selected_skills = selected
    save_config(config)


def get_published_repo() -> str:
    """Get the target repo for publishing.
    
    Returns:
        GitHub URL of published repo.
    """
    config = load_config()
    return config.published_repo


def set_published_repo(url: str) -> None:
    """Set the target repo for publishing.
    
    Args:
        url: GitHub repository URL
    """
    config = load_config()
    config.published_repo = url
    save_config(config)


# =============================================================================
# Publish State Manager (session state, saved after successful publish)
# =============================================================================

@dataclass
class PublishState:
    """State of a publish session.
    
    Tracks what was selected in the last publish operation.
    """
    timestamp: Optional[str] = None
    skills: dict[str, list[str]] = field(default_factory=dict)
    agents: dict[str, list[str]] = field(default_factory=dict)
    
    def get_skills_count(self) -> int:
        """Total skills selected."""
        return sum(len(v) for v in self.skills.values())
    
    def get_agents_count(self) -> int:
        """Total agents selected."""
        return sum(len(v) for v in self.agents.values())
    
    def get_total_count(self) -> int:
        """Total items selected."""
        return self.get_skills_count() + self.get_agents_count()
    
    def is_empty(self) -> bool:
        """Check if nothing is selected."""
        return self.get_total_count() == 0
    
    def get_all_source_ids(self) -> set[str]:
        """Get all source IDs with selections."""
        result = set(self.skills.keys())
        result.update(self.agents.keys())
        return result
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "timestamp": self.timestamp,
            "skills": self.skills,
            "agents": self.agents,
        }
    
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "PublishState":
        """Create from dict."""
        if not data:
            return cls()
        return cls(
            timestamp=data.get("timestamp"),
            skills=data.get("skills", {}),
            agents=data.get("agents", {}),
        )


class PublishStateManager:
    """Manages publish state in config.toml.
    
    State is loaded on startup and saved ONLY after successful publish.
    """
    
    @staticmethod
    def load() -> PublishState:
        """Load publish state from config.
        
        Returns:
            PublishState with selections from last successful publish,
            or empty PublishState if none exists.
        """
        config = load_config()
        return PublishState.from_dict(config.selected_skills.get("_last_publish"))
    
    @staticmethod
    def save(skills: dict[str, list[str]], agents: dict[str, list[str]]) -> None:
        """Save publish state to config.
        
        Called ONLY after successful publish operation.
        
        Args:
            skills: Dict of source_id → selected skill names
            agents: Dict of source_id → selected agent names
        """
        config = load_config()
        
        state = PublishState(
            timestamp=datetime.now().isoformat(),
            skills=skills,
            agents=agents,
        )
        
        # Store under _last_publish key (reserved, not a real source)
        config.selected_skills["_last_publish"] = state.to_dict()
        save_config(config)
    
    @staticmethod
    def clear() -> None:
        """Clear publish state from config."""
        config = load_config()
        config.selected_skills.pop("_last_publish", None)
        save_config(config)
    
    @staticmethod
    def get_source_state(state: PublishState, source_id: str) -> set[str]:
        """Get selected items for a specific source.
        
        Args:
            state: The publish state
            source_id: e.g., "local", "renatocaliari/pi-product-workflow", "agents"
        
        Returns:
            Set of selected item names, empty set if none.
        """
        result = set()
        if source_id in state.skills:
            result.update(state.skills[source_id])
        if source_id in state.agents:
            result.update(state.agents[source_id])
        return result