from __future__ import annotations


"""External GitHub repository skill discovery."""

import shutil
import subprocess
from pathlib import Path

from datetime import datetime

from .base import SkillSource, SourceConfig, SourceStatus
from .cache import (
    get_cache_info,
    get_cache_path,
    is_cache_valid,
    normalize_repo_id,
)


def discover_external_skills(
    source: SourceConfig,
    cache_dir: Path,
) -> tuple[list[SkillSource], SourceStatus]:
    """Discover skills from an external GitHub repository.
    
    Uses cache if valid, otherwise clones shallowly.
    
    Args:
        source: SourceConfig with repository URL
        cache_dir: Base cache directory
        
    Returns:
        Tuple of (list of SkillSource, status)
    """
    cache_path = get_cache_path(cache_dir, source.url)
    cache_valid = is_cache_valid(cache_path, source.cache_ttl_hours)
    
    if cache_valid:
        # Use cached repo
        skills = _find_skills_in_repo(cache_path, source)
        return skills, SourceStatus.ACTIVE
    
    # Clone repository
    success = _clone_repo(source.url, cache_path)
    
    if not success:
        # Try to use stale cache
        if cache_path.exists():
            skills = _find_skills_in_repo(cache_path, source)
            if skills:
                return skills, SourceStatus.SKIPPED  # Stale cache, warn user
        return [], SourceStatus.FAILED
    
    # Find skills in cloned repo
    skills = _find_skills_in_repo(cache_path, source)
    
    if skills:
        # Update last_success on successful clone
        from .config import update_source_status
        update_source_status(source.url, SourceStatus.ACTIVE)
        return skills, SourceStatus.ACTIVE
    else:
        return [], SourceStatus.SKIPPED  # No skills found


def _clone_repo(repo_url: str, cache_path: Path) -> bool:
    """Clone repository shallowly to cache path.
    
    Args:
        repo_url: GitHub repository URL
        cache_path: Where to clone
        
    Returns:
        True if successful.
    """
    # Remove existing cache
    if cache_path.exists():
        shutil.rmtree(cache_path)
    
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(cache_path)],
            capture_output=True,
            text=True,
            timeout=180,
            env={**subprocess.os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def _find_skills_in_repo(cache_path: Path, source: SourceConfig) -> list[SkillSource]:
    """Find skills in a cloned repository.
    
    Args:
        cache_path: Path to cloned repository
        source: Source configuration
        
    Returns:
        List of SkillSource objects.
    """
    skills = []
    repo_id = normalize_repo_id(source.url)
    
    if not cache_path.exists():
        return skills
    
    try:
        # List all files in HEAD
        result = subprocess.run(
            ["git", "-C", str(cache_path), "ls-files"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return skills
        
        files = result.stdout.strip().split("\n")
        
        # Find SKILL.md files
        for f in files:
            if not f:
                continue
            
            # Check for SKILL.md at root or in subdirectory
            if f.endswith("/SKILL.md"):
                # Skill is in a directory (e.g., skills/name/SKILL.md or just name/SKILL.md)
                skill_dir = f.replace("/SKILL.md", "")
                skill_name = skill_dir.split("/")[-1]  # Get last component
                
                if _is_valid_skill_name(skill_name):
                    # Store the DIRECTORY path, not the SKILL.md file
                    # This ensures all subdirectories are published
                    skill_dir_path = cache_path / skill_dir
                    skill = SkillSource(
                        name=skill_name,
                        path=skill_dir_path,  # Parent directory, not SKILL.md
                        source_type="external",
                        source_url=source.url,
                        source_id=repo_id,
                    )
                    skills.append(skill)
            elif f == "SKILL.md":
                # SKILL.md at root - skill name is repo name
                skill_name = repo_id.split("/")[-1]
                # Store the directory path (parent of SKILL.md)
                skill_dir_path = cache_path
                skill = SkillSource(
                    name=skill_name,
                    path=skill_dir_path,  # Cache root directory
                    source_type="external",
                    source_url=source.url,
                    source_id=repo_id,
                )
                skills.append(skill)
        
        # Also check for skills/ directory pattern
        # (Some repos may not track all files in git)
        skills_dir = cache_path / "skills"
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    skill_name = item.name
                    if _is_valid_skill_name(skill_name):
                        # Check if already added (deduplicate)
                        if not any(s.name == skill_name for s in skills):
                            skill = SkillSource(
                                name=skill_name,
                                path=item,  # The directory, not SKILL.md
                                source_type="external",
                                source_url=source.url,
                                source_id=repo_id,
                            )
                            skills.append(skill)
                        
    except Exception:
        pass
    
    # Final deduplication by name (in case both methods found same skill)
    seen = set()
    unique_skills = []
    for skill in skills:
        if skill.name not in seen:
            seen.add(skill.name)
            unique_skills.append(skill)
    skills = unique_skills
    
    # Sort alphabetically by name
    skills.sort(key=lambda s: s.name.lower())
    
    return skills


def _is_valid_skill_name(name: str) -> bool:
    """Check if skill name is valid.
    
    Valid: lowercase, numbers, hyphens. No leading/trailing/consecutive hyphens.
    """
    import re
    # Match: starts with letter, then letters/numbers/hyphens, ends with letter/number
    pattern = r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$'
    return bool(re.match(pattern, name))


def refresh_source(source: SourceConfig, cache_dir: Path) -> tuple[list[SkillSource], SourceStatus]:
    """Force refresh of a source (clear cache and re-clone).
    
    Args:
        source: SourceConfig to refresh
        cache_dir: Base cache directory
        
    Returns:
        Tuple of (list of SkillSource, status)
    """
    # Clear cache
    cache_path = get_cache_path(cache_dir, source.url)
    if cache_path.exists():
        shutil.rmtree(cache_path)
    
    # Rediscover
    return discover_external_skills(source, cache_dir)


def get_source_staleness(source: SourceConfig, cache_dir: Path) -> str | None:
    """Get staleness info for a source.
    
    Args:
        source: SourceConfig to check
        cache_dir: Base cache directory
        
    Returns:
        Human-readable staleness string or None if fresh.
    """
    cache_info = get_cache_info(cache_dir, source.url)
    
    if not cache_info:
        return None
    
    if is_cache_valid(Path(cache_info["path"]), source.cache_ttl_hours):
        return None
    
    return f"Cache de {cache_info['last_modified']}"