"""Windsurf agent handler - Copy method for skills sync."""

from pathlib import Path
from typing import List, Dict, Any

from .base import BaseAgent


class WindsurfAgent(BaseAgent):
    """
    Windsurf IDE integration with copy-based skills sync.
    
    Windsurf uses:
    - ~/.codeium/windsurf/skills/{name}/SKILL.md (global)
    - .windsurf/skills/{name}/SKILL.md (project)
    
    Method: Copy FROM project/global directories TO ~/.agents/skills/
    """

    def __init__(self, name: str, data: Dict[str, Any]):
        super().__init__(name, data)
        self.copy_from = data.get("copy_from", [])  # List of source paths
        self.copy_to = self._expand_path(data.get("copy_to", "~/.agents/skills/"))


