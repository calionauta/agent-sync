from __future__ import annotations


"""Git operations for publish feature.

SoC: Git operations separated from discovery and UI logic.
DRY: Single _do_git_publish() used by both skills and agents.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console

from .base import SourceWithSkills


console = Console()


# =============================================================================
# GENERIC GIT PUBLISH
# =============================================================================

def do_git_publish(
    items: list[tuple[Path, str]],
    subdir: str,
    readme_generator: Callable[[Path, list, str], None],
    count: int,
    item_name: str,
    repo: str,
) -> bool:
    """Generic git publish operation.
    
    DRY: Single implementation used by both skills and agents.
    
    Args:
        items: List of (source_path, dest_name) tuples
        subdir: Subdirectory name (e.g., "skills", "agents")
        readme_generator: Function to generate README
        count: Number of items
        item_name: Name for messages (e.g., "skills", "agents")
        repo: Target repository URL
    
    Returns:
        True if published successfully
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="agent-sync-publish-"))
    
    try:
        # Create subdirectory
        items_dir = tmp_dir / subdir
        items_dir.mkdir(parents=True)
        
        # Copy items (handles both files and directories)
        for src_path, dest_name in items:
            dest = items_dir / dest_name
            if src_path.is_dir():
                shutil.copytree(src_path, dest, dirs_exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest)
        
        # Generate README
        readme_generator(items_dir, items, repo)
        
        # Git operations
        git_commit_and_push(tmp_dir, repo, count)
        
        console.print(f"\n[green]✓ Published {count} {item_name}![/]")
        return True
        
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]✗ Git error: {e.stderr or str(e)}[/]")
        return False
    except Exception as e:
        console.print(f"\n[red]✗ Error publishing: {e}[/]")
        return False
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def git_commit_and_push(tmp_dir: Path, repo_url: str, count: int) -> None:
    """Git add, commit, and push to repo.
    
    Args:
        tmp_dir: Temporary directory with content to publish
        repo_url: Target repository URL
        count: Number of items for commit message
    """
    # Initialize git
    subprocess.run(["git", "init"], cwd=tmp_dir, check=True, capture_output=True, timeout=10)
    subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_dir, check=True, capture_output=True, timeout=10)
    
    # Add and commit
    subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True, capture_output=True, timeout=30)
    commit_result = subprocess.run(
        ["git", "commit", "-m", f"feat: publish {count} items"],
        cwd=tmp_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if commit_result.returncode != 0:
        raise subprocess.CalledProcessError(
            commit_result.returncode, "git commit",
            commit_result.stdout, commit_result.stderr
        )
    
    # Push
    subprocess.run(
        ["git", "remote", "add", "origin", repo_url],
        cwd=tmp_dir,
        check=True,
        capture_output=True,
        timeout=10,
    )
    push_result = subprocess.run(
        ["git", "push", "-u", "origin", "main", "--force"],
        cwd=tmp_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if push_result.returncode != 0:
        raise subprocess.CalledProcessError(
            push_result.returncode, "git push",
            push_result.stdout, push_result.stderr
        )


# =============================================================================
# SKILLS PUBLISH
# =============================================================================

def publish_skills(
    selected: dict[str, list[str]],
    sources: list[SourceWithSkills],
    published_repo: str,
) -> bool:
    """Publish selected skills to the target repository.
    
    Args:
        selected: Dict of source_id -> [skill_names]
        sources: List of SourceWithSkills for lookup
        published_repo: Target repository URL
    
    Returns:
        True if published successfully
    """
    # Build source lookup
    source_map = {src.source_id: src for src in sources}
    
    # Collect skills to publish
    skills_to_publish: list[tuple[Path, str]] = []
    
    for source_id, skill_names in selected.items():
        src = source_map.get(source_id)
        if not src:
            continue
        
        for skill_name in skill_names:
            for skill in src.skills:
                if skill.name == skill_name:
                    skills_to_publish.append((skill.path, f"{source_id}/{skill_name}"))
                    break
    
    if not skills_to_publish:
        console.print("[yellow]⚠ No skills selected to publish[/]")
        return False
    
    return do_git_publish(
        items=skills_to_publish,
        subdir="skills",
        readme_generator=generate_skills_readme,
        count=len(skills_to_publish),
        item_name="skills",
        repo=published_repo,
    )


# =============================================================================
# AGENTS PUBLISH
# =============================================================================

def publish_agents(
    selected: dict[str, list[str]],
    published_repo: str,
) -> bool:
    """Publish selected agents to the target repository.
    
    Args:
        selected: Dict with "agents" key -> [agent_names]
        published_repo: Target repository URL
    
    Returns:
        True if published successfully
    """
    from .agents_source import discover_local_agents
    
    agents_to_publish = selected.get("agents", [])
    
    if not agents_to_publish:
        console.print("[yellow]⚠ No agents selected to publish[/]")
        return False
    
    # Find agent paths
    all_agents = {a.name: a for a in discover_local_agents()}
    items: list[tuple[Path, str]] = []
    
    for agent_name in agents_to_publish:
        agent = all_agents.get(agent_name)
        if agent:
            items.append((Path(agent.path), f"agents/{agent_name}.md"))
    
    if not items:
        return False
    
    return do_git_publish(
        items=items,
        subdir="agents",
        readme_generator=generate_agents_readme,
        count=len(items),
        item_name="agents",
        repo=published_repo,
    )


# =============================================================================
# README GENERATORS
# =============================================================================

def generate_skills_readme(skills_dir: Path, selected: list, repo_url: str) -> None:
    """Generate README.md for skills directory.
    
    Args:
        skills_dir: Directory containing published skills
        selected: List of (path, name) tuples that were published
        repo_url: Repository URL for install instructions
    """
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    
    lines = [
        "# Skills\n",
        f"Published from [{repo_name}]({repo_url})\n",
        "\n## Available Skills\n",
    ]
    
    # Group by source
    by_source: dict[str, list[str]] = {}
    for _, name in selected:
        if "/" in name:
            source, skill = name.split("/", 1)
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(skill)
        else:
            if "local" not in by_source:
                by_source["local"] = []
            by_source["local"].append(name)
    
    # Generate list
    for source, skills in sorted(by_source.items()):
        lines.append(f"\n### {source.upper()}\n")
        for skill in sorted(skills):
            lines.append(f"- {skill}\n")
    
    lines.append(f"\n## Install All\n\n```bash\nagent-sync publish --add-source {repo_url}\n```\n")
    
    readme_path = skills_dir / "README.md"
    readme_path.write_text("".join(lines))


def generate_agents_readme(agents_dir: Path, selected: list, repo_url: str) -> None:
    """Generate README.md for agents directory.
    
    Args:
        agents_dir: Directory containing published agents
        selected: List of (path, name) tuples that were published
        repo_url: Repository URL
    """
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    
    lines = [
        "# Agents\n",
        f"Published from [{repo_name}]({repo_url})\n",
        "\n## Available Agents\n",
    ]
    
    agent_names = []
    for _, name in selected:
        if "/" in name:
            agent_name = name.split("/")[-1].replace(".md", "")
            agent_names.append(agent_name)
    
    for name in sorted(agent_names):
        lines.append(f"- {name}\n")
    
    readme_path = agents_dir / "README.md"
    readme_path.write_text("".join(lines))