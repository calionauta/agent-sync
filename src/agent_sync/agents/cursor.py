"""Cursor agent handler - Native support for ~/.agents/skills/."""

from typing import Dict, Any

from .base import BaseAgent


class CursorAgent(BaseAgent):
    """
    Cursor IDE integration with native skills support.
    
    Cursor uses:
    - ~/.cursor/skills/{name}/SKILL.md (global)
    - .cursor/skills/{name}/SKILL.md (project)
    
    Native: Cursor can read from ~/.agents/skills/ natively.
    """

    def __init__(self, name: str, data: Dict[str, Any]):
        super().__init__(name, data)
        self.migrate_from = data.get("migrate_from", [])


