from __future__ import annotations


"""Local skills source discovery."""

from pathlib import Path

from .base import SkillSource, SourceStatus


# Standard local skills directory
SKILLS_DIR = Path.home() / ".agents" / "skills"


def discover_local_skills() -> list[SkillSource]:
    """Discover skills from ~/.agents/skills/.
    
    Returns:
        List of SkillSource objects for local skills, sorted alphabetically.
    """
    skills = []
    
    if not SKILLS_DIR.exists():
        return skills
    
    # Collect all skill paths first
    skill_paths = []
    for item in SKILLS_DIR.iterdir():
        if item.name.startswith("."):
            continue
        
        # Skill can be a directory (with SKILL.md) or a .md file
        if item.is_dir() and (item / "SKILL.md").exists():
            skill_paths.append(item)
        elif item.is_file() and item.suffix == ".md":
            # Root .md files are ignored in ~/.agents/skills/ per pi spec
            pass
    
    # Sort alphabetically by name
    skill_paths.sort(key=lambda p: p.name.lower())
    
    # Create skill sources from sorted paths
    for path in skill_paths:
        skill = _create_skill_source(path)
        if skill:
            skills.append(skill)
    
    return skills


def _create_skill_source(path: Path) -> SkillSource | None:
    """Create a SkillSource from a path.
    
    Args:
        path: Path to skill directory
        
    Returns:
        SkillSource or None if invalid.
    """
    try:
        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            return None
        
        name = path.name
        
        # Validate name format (lowercase, hyphens only)
        if not _is_valid_skill_name(name):
            return None
        
        return SkillSource(
            name=name,
            path=path,
            source_type="local",
            source_url="local",
            source_id="local",
        )
    except Exception:
        return None


def _is_valid_skill_name(name: str) -> bool:
    """Check if skill name is valid.
    
    Valid: lowercase, numbers, hyphens. No leading/trailing/consecutive hyphens.
    """
    import re
    # Match: starts with letter, then letters/numbers/hyphens, ends with letter/number
    pattern = r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$'
    return bool(re.match(pattern, name))


def get_local_source_status() -> SourceStatus:
    """Get the status of local skills source.
    
    Returns:
        SourceStatus. Always ACTIVE if directory exists.
    """
    if SKILLS_DIR.exists():
        return SourceStatus.ACTIVE
    return SourceStatus.UNKNOWN