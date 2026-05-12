"""Base class for agent integrations based on YAML registry."""

import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List


# Global skills directory (shared across all agents)
GLOBAL_SKILLS_DIR = Path.home() / ".agents" / "skills"


class BaseAgent:
    """Agent integration driven by YAML registry data."""

    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data
        self.enabled: bool = True

        # Load registry data
        self.method = data.get("method", "copy")
        self.skills_dir_name = data.get("skills_dir_name", "skills")
        self.config_dir = self._expand_path(data.get("config_dir", "~/.config"))
        self.config_filename = data.get("config_filename", "config.json")
        
        # Custom agents support (optional)
        self.agents_dir_name = data.get("agents_dir_name")
        self.agents_dir_global = self._expand_path(data.get("agents_dir_global", "")) if data.get("agents_dir_global") else None
        
    def _expand_path(self, path_str: str) -> Path:
        """Expand ~ in path strings."""
        if not path_str:
            return Path("")
        return Path(path_str).expanduser()

    @property
    def config_path(self) -> Path:
        """Path to agent configuration file."""
        if not self.data.get("config_filename"):
            return Path("")
        return self.config_dir / self.config_filename

    @property
    def skills_path(self) -> Path:
        """Path to agent-specific skills directory."""
        return self.config_dir / self.skills_dir_name

    @property
    def agents_path(self) -> Optional[Path]:
        """Path to agent-specific custom agents directory (project-level)."""
        if not self.agents_dir_name:
            return None
        return self.config_dir / self.agents_dir_name

    @property
    def agents_path_global(self) -> Optional[Path]:
        """Path to global custom agents directory (~/.claude/agents/, etc.)."""
        return self.agents_dir_global

    @property
    def global_skills_path(self) -> Path:
        """Path to global ~/.agents/skills directory."""
        return GLOBAL_SKILLS_DIR

    def is_available(self) -> bool:
        """Check if this agent is installed/configured based on check in YAML."""
        check = self.data.get("check", {})
        
        if check.get("always"):
            return True
            
        if "binary" in check:
            return shutil.which(check["binary"]) is not None
            
        if "path" in check:
            return self._expand_path(check["path"]).exists()
            
        return False

    def get_config(self) -> Optional[dict]:
        """Load agent configuration."""
        if self.config_path.exists() and self.config_path.is_file():
            with open(self.config_path) as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return None
        return None

    def save_config(self, config: dict) -> None:
        """Save agent configuration."""
        if not self.config_path:
            return
            
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def enable(self) -> None:
        """Enable sync for this agent."""
        self.enabled = True

    def disable(self) -> None:
        """Disable sync for this agent."""
        self.enabled = False

    def is_enabled(self) -> bool:
        """Check if sync is enabled for this agent."""
        return self.enabled

    def supports_native(self) -> bool:
        """Check if this agent natively supports ~/.agents/skills/."""
        return self.method == "native"

    def supports_config(self) -> bool:
        """Check if this agent supports config-based skills paths."""
        return self.method == "config"

    def supports_copy(self) -> bool:
        """Check if this agent uses copy method."""
        return self.method == "copy"

    def supports_custom_agents(self) -> bool:
        """Check if this agent supports custom agents (.claude/agents/, .opencode/agents/, etc.)."""
        return self.agents_dir_name is not None

    def get_all_skills_paths(self) -> List[Path]:
        """Get all skills paths for this agent."""
        paths = [self.skills_path]
        
        # Some agents use global skills natively
        if self.supports_native():
            paths.append(self.global_skills_path)
            
        # Add extra paths if defined in registry
        extra = self.data.get("extra_paths", {})
        # skills is implied by skills_dir_name, but we could have more
        
        # Filter to only existing paths
        return [p for p in paths if p.exists()]

    # Pi-specific properties (handled dynamically)
    @property
    def extensions_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("extensions", [])
        return [self._expand_path(p) for p in paths]

    @property
    def prompts_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("prompts", [])
        return [self._expand_path(p) for p in paths]

    @property
    def themes_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("themes", [])
        return [self._expand_path(p) for p in paths]

    @property
    def bin_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("bin", [])
        return [self._expand_path(p) for p in paths]

    @property
    def git_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("git", [])
        return [self._expand_path(p) for p in paths]

    @property
    def lsp_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("lsp", [])
        return [self._expand_path(p) for p in paths]

    @property
    def models_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("models", [])
        return [self._expand_path(p) for p in paths]

    @property
    def global_extensions_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("global_extensions", [])
        return [self._expand_path(p) for p in paths]

    @property
    def global_prompts_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("global_prompts", [])
        return [self._expand_path(p) for p in paths]

    @property
    def global_skills_local_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("global_skills_local", [])
        return [self._expand_path(p) for p in paths]

    @property
    def global_themes_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("global_themes", [])
        return [self._expand_path(p) for p in paths]

    @property
    def pyrightconfig_paths(self) -> List[Path]:
        paths = self.data.get("extra_paths", {}).get("pyrightconfig", [])
        return [self._expand_path(p) for p in paths]

    @property
    def packages_paths(self) -> List[Path]:
        """Detect local packages from agent configuration.
        
        For pi.dev, reads settings.json and resolves relative paths
        like '../product-workflow' to absolute paths.
        """
        packages = []
        config = self.get_config()
        
        if not config or "packages" not in config:
            return packages
        
        for package in config["packages"]:
            # Handle string format: "../product-workflow" or "git:github.com/..."
            if isinstance(package, str):
                # Skip git/npm packages - only sync local paths
                if package.startswith("git:") or package.startswith("npm:"):
                    continue
                
                # Resolve relative paths
                if package.startswith("./") or package.startswith("../"):
                    # Resolve relative to config directory
                    resolved = (self.config_path.parent / package).resolve()
                    if resolved.exists():
                        packages.append(resolved)
            
            # Handle object format: {"source": "../product-workflow"}
            elif isinstance(package, dict):
                source = package.get("source", "")
                if isinstance(source, str) and (source.startswith("./") or source.startswith("../")):
                    resolved = (self.config_path.parent / source).resolve()
                    if resolved.exists():
                        packages.append(resolved)
        
        return packages

    def __repr__(self) -> str:
        return f"BaseAgent(name={self.name}, method={self.method}, enabled={self.enabled})"
