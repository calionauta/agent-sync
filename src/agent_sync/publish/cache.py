from __future__ import annotations


"""Cache management for external repositories."""

import datetime
import shutil
from pathlib import Path


# Default cache directory
cache_dir = Path.home() / ".cache" / "agent-sync" / "repos"


def get_cache_path(cache_dir: Path, repo_url: str) -> Path:
    """Get the cache path for a repository.
    
    Args:
        cache_dir: Base cache directory
        repo_url: GitHub repository URL
        
    Returns:
        Path to the cached repository.
    """
    # Extract owner/repo from URL
    normalized = normalize_repo_id(repo_url)
    return cache_dir / normalized.replace("/", "_")


def normalize_repo_id(url: str) -> str:
    """Normalize a GitHub URL to owner/repo format.
    
    Args:
        url: GitHub URL or shorthand
        
    Returns:
        Normalized owner/repo string
    """
    url = url.strip()
    
    # Handle git@github.com:owner/repo.git
    if url.startswith("git@"):
        url = url.replace("git@github.com:", "https://github.com/")
    
    # Remove .git suffix
    url = url.rstrip("/").replace(".git", "")
    
    # Remove protocol
    url = url.replace("https://github.com/", "")
    url = url.replace("http://github.com/", "")
    
    return url


def is_cache_valid(cache_path: Path, ttl_hours: int = 24) -> bool:
    """Check if cache is valid (exists and not expired).
    
    Args:
        cache_path: Path to cached repository
        ttl_hours: TTL in hours
        
    Returns:
        True if cache is valid and not expired.
    """
    if not cache_path.exists():
        return False
    
    # Check modification time
    mtime = cache_path.stat().st_mtime
    cache_age = datetime.datetime.now().timestamp() - mtime
    ttl_seconds = ttl_hours * 3600
    
    return cache_age < ttl_seconds


def clone_shallow(repo_url: str, cache_path: Path) -> bool:
    """Clone a repository shallowly to cache.
    
    Args:
        repo_url: GitHub repository URL
        cache_path: Where to clone
        
    Returns:
        True if successful, False otherwise.
    """
    import subprocess
    
    # Remove existing cache if present
    if cache_path.exists():
        shutil.rmtree(cache_path)
    
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--bare", repo_url, str(cache_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def find_skills_in_cache(cache_path: Path) -> list[Path]:
    """Find all skills in a cached repository.
    
    Args:
        cache_path: Path to cached repository (bare git)
        
    Returns:
        List of paths to skill directories.
    """
    import subprocess
    
    skills = []
    
    if not cache_path.exists():
        return skills
    
    # Use git ls-tree to list files without checking out
    try:
        # List all files in the repo
        result = subprocess.run(
            ["git", "--git-dir", str(cache_path), "ls-tree", "-r", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return skills
        
        files = result.stdout.strip().split("\n")
        
        # Find SKILL.md files
        for f in files:
            if f.endswith("SKILL.md"):
                # Get the directory containing SKILL.md
                skill_dir = cache_path.parent / cache_path.name / f.replace("/SKILL.md", "")
                if skill_dir.exists():
                    skills.append(skill_dir)
        
        # Also check for skills/ directory
        skills_dir = cache_path.parent / cache_path.name / "skills"
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    skills.append(item)
                    
    except Exception:
        pass
    
    return skills


def clear_cache(cache_dir: Path, repo_url: str | None = None) -> int:
    """Clear cache for a specific repo or all repos.
    
    Args:
        cache_dir: Base cache directory
        repo_url: Optional specific repo URL to clear
        
    Returns:
        Number of items cleared.
    """
    if repo_url:
        cache_path = get_cache_path(cache_dir, repo_url)
        if cache_path.exists():
            shutil.rmtree(cache_path)
            return 1
        return 0
    
    # Clear all
    count = 0
    if cache_dir.exists():
        for item in cache_dir.iterdir():
            shutil.rmtree(item)
            count += 1
    return count


def get_cache_info(cache_dir: Path, repo_url: str) -> dict | None:
    """Get cache information for a repository.
    
    Args:
        cache_dir: Base cache directory
        repo_url: GitHub repository URL
        
    Returns:
        Dict with cache info or None if not cached.
    """
    cache_path = get_cache_path(cache_dir, repo_url)
    
    if not cache_path.exists():
        return None
    
    stat = cache_path.stat()
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
    
    return {
        "path": str(cache_path),
        "size_mb": stat.st_size / (1024 * 1024),
        "last_modified": mtime.isoformat(),
        "age_hours": (datetime.datetime.now() - mtime).total_seconds() / 3600,
    }