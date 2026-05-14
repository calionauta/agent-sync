"""RooCode agent handler - Native support for ~/.agents/skills/."""

from typing import Dict, Any

from .base import BaseAgent


class RooCodeAgent(BaseAgent):
    """
    RooCode integration with native skills support.
    
    RooCode natively reads from:
    - ~/.roo/skills/ (higher priority)
    - ~/.agents/skills/ (lower priority - cross-agent)
    - .roo/skills/ (project, higher priority)
    - .agents/skills/ (project, lower priority)
    
    Also supports mode-specific skills:
    - ~/.roo/skills-code/ (Code mode only)
    - ~/.roo/skills-architect/ (Architect mode only)
    """

    def __init__(self, name: str, data: Dict[str, Any]):
        super().__init__(name, data)
        self.mode_specific = data.get("mode_specific", False)


