"""Cline agent handler - Copy method for skills sync."""

from typing import Dict, Any

from .base import BaseAgent


class ClineAgent(BaseAgent):
    """
    Cline integration with copy-based skills sync.
    
    Cline uses:
    - ~/.cline/skills/{name}/SKILL.md (global)
    - .cline/skills/{name}/SKILL.md (project)
    - .clinerules/skills/{name}/SKILL.md (project alternative)
    - .claude/skills/{name}/SKILL.md (project legacy)
    
    Method: Copy FROM project/global directories TO ~/.agents/skills/
    """

    def __init__(self, name: str, data: Dict[str, Any]):
        super().__init__(name, data)
        self.copy_from = data.get("copy_from", [])
        self.copy_to = self._expand_path(data.get("copy_to", "~/.agents/skills/"))


