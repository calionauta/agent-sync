"""Sync management for agent-sync."""

import fnmatch
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from . import paths
from .agents import BaseAgent
from .skills import MANIFEST_FILENAME
from .validators import validate_github_url

console = Console()


# ---------------------------------------------------------------------------
# Token sanitization
# ---------------------------------------------------------------------------

# Patterns for tokens that could appear in git remote URLs or error output.
_TOKEN_PATTERNS = [
    # GitHub PATs, OAuth, App tokens (ghp_, gho_, ghu_, ghs_, ghr_)
    re.compile(r'gh[pousr]_[A-Za-z0-9_]{20,}'),
    # Generic token-like strings in URLs: https://<token>@github.com
    re.compile(r'(https?://)[^@/\s]+(@github\.com)'),
    # x-access-token: <token>@github.com
    re.compile(r'(https?://x-access-token:)[^@/\s]+(@github\.com)'),
]


def _sanitize_git_output(text: str) -> str:
    """Strip potential authentication tokens from git output.

    Git error messages can contain remote URLs with embedded tokens.
    This function redacts them before the text reaches logs, terminals,
    or exception messages.
    """
    if not text:
        return text
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub(r'\1***\2' if pattern in _TOKEN_PATTERNS[1:] else '***', text)
    return text


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class PullConflict:
    """Represents a file conflict between local and remote versions."""

    agent_name: str  # e.g., "pi.dev", "gemini-cli"
    filename: str  # e.g., "AGENTS.md", "settings.json"
    local_path: Path  # Local file path
    remote_path: Path  # Path in repo (relative to repo root)
    local_modified: Optional[datetime] = None
    remote_modified: Optional[datetime] = None
    diff_stats: dict = field(default_factory=lambda: {"added": 0, "removed": 0})  # Lines added/removed

    @property
    def display_name(self) -> str:
        """Display name for UI."""
        return f"{self.agent_name}/{self.filename}"

    @property
    def diff_summary(self) -> str:
        """Short summary of changes for display."""
        added = self.diff_stats.get("added", 0)
        removed = self.diff_stats.get("removed", 0)
        if added and removed:
            return f"{added} +l / {removed} -l"
        elif added:
            return f"{added} +l"
        elif removed:
            return f"{removed} -l"
        return ""


@dataclass
class SkillDrift:
    """Represents a skill whose local content differs from the repo version."""
    name: str
    files_changed: int
    local_path: Path
    repo_path: Path
    file_details: list[dict] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def diff_summary(self) -> str:
        return f"{self.files_changed} file(s) modified"


@dataclass
class PullSummary:
    """Summary of a pull operation."""
    conflicts: list[PullConflict] = field(default_factory=list)
    skill_drifts: list[SkillDrift] = field(default_factory=list)
    new_files: int = 0
    updated_files: int = 0
    deleted_files: int = 0

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def has_skill_drifts(self) -> bool:
        return len(self.skill_drifts) > 0

    @property
    def total_changes(self) -> int:
        return len(self.conflicts) + len(self.skill_drifts) + self.new_files + self.updated_files + self.deleted_files


def _get_app_name() -> str:
    """Get app name from package metadata (or fallback)."""
    try:
        from importlib.metadata import version
        return version("agent-sync").split(".")[0]
    except Exception:
        return "agent-sync"


class SyncManager:
    """Manages synchronization with GitHub repository."""

    # Files to NEVER sync (sensitive, local-only, or transient)
    EXCLUDE_PATTERNS = [
        # Secrets
        "*auth*.json",
        "*accounts*.json",
        "*overrides*.json*",
        "*credentials*.json",

        # Lock files
        "*.lock",
        "package-lock.json",
        "bun.lock",

        # System files
        ".DS_Store",

        # Agent session state (not configuration)
        "history/",
        "tmp/",
        "state.json",
        "projects.json",
        "installation_id",

        # Transient files
        "*.bak",
        "*.log",
        "*.log.*",

        # Database files
        "*.db",
        "*.mdb",
        "*.ldb",
    ]

    def __init__(self, config):
        self.config = config
        self.repo_dir = paths.REPO_DIR
        self.state_file = paths.STATE_FILE

        # Ensure directories exist BEFORE any operations
        try:
            self.repo_dir.mkdir(parents=True, exist_ok=True)  # Create repo dir itself
            self.repo_dir.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise RuntimeError(
                f"Cannot create directory {self.repo_dir}. "
                f"Check permissions or set XDG_DATA_HOME environment variable."
            ) from e

        # Verify directory was created
        if not self.repo_dir.exists():
            raise RuntimeError(f"Failed to create directory {self.repo_dir}")

    def _run_git(self, *args, cwd: Path | None = None, timeout: int | None = 60) -> str:
        """Run a git command and return output.

        Creates a copy of environment without GITHUB_TOKEN to avoid conflicts
        with gh CLI keyring auth.

        Args:
            timeout: Maximum seconds to wait for the command (default 60).
                     Prevents infinite hangs on auth prompts or network issues.
        """
        # Create a copy of environment without GITHUB_TOKEN
        # This prevents git from using the invalid token
        env = os.environ.copy()
        env.pop("GITHUB_TOKEN", None)
        # Never prompt for credentials - fail fast with a clear error instead
        env["GIT_TERMINAL_PROMPT"] = "0"

        cmd = ["git"] + list(args)
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.repo_dir,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"Git command timed out after {timeout}s: {' '.join(cmd)}\n"
                "This usually means git is stuck waiting for authentication.\n"
                "Try one of these solutions:\n"
                "  1. Run 'gh auth status' to check GitHub authentication\n"
                "  2. Run 'gh auth refresh' to refresh credentials\n"
                "  3. Check your git remote configuration: git remote -v\n"
                "  4. Unset GITHUB_TOKEN if set: unset GITHUB_TOKEN"
            ) from e

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd,
                _sanitize_git_output(result.stdout),
                _sanitize_git_output(result.stderr),
            )

        return result.stdout.strip()

    def _check_git_installed(self) -> bool:
        """Check if git is installed."""
        return shutil.which("git") is not None

    def _check_gh_installed(self) -> bool:
        """Check if GitHub CLI is installed."""
        return shutil.which("gh") is not None

    def init_repo(self, name: str = None, private: bool = True, agents: tuple[str, ...] = ()) -> str:
        """
        Initialize a new sync repository or link to existing one.

        Args:
            name: Repository name
            private: Whether repo should be private
            agents: List of agents to sync

        Returns:
            Repository URL
        """
        from rich.prompt import Confirm

        if not self._check_gh_installed():
            raise RuntimeError("GitHub CLI (gh) is required. Install with: brew install gh")

        if not self._check_git_installed():
            raise RuntimeError("Git is required. Install with: brew install git")

        # Ensure repo directory exists
        self.repo_dir.mkdir(parents=True, exist_ok=True)

        # If name is None, use default from gh auth
        if name is None:
            gh_user = self._get_github_user()
            name = "agent-sync-private"
            console.print(f"[dim]Using default repo: {gh_user}/agent-sync-private[/dim]\n")

        # Check if repo already exists on GitHub
        # Support both simple names and slugs
        if "/" in name:
            repo_name = name
            repo_url = f"https://github.com/{name}.git"
        else:
            repo_name = f"{self._get_github_user()}/{name}"
            repo_url = f"https://github.com/{repo_name}.git"

        result = subprocess.run(
            ["gh", "repo", "view", "--json", "name,isPrivate", "--", repo_name],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            # Repo exists - check visibility
            repo_info = json.loads(result.stdout)
            is_private = repo_info.get("isPrivate", False)

            if not is_private:
                # Public repo - warn about security
                console.print("\n[yellow]⚠️  WARNING: Repository is PUBLIC![/yellow]\n")
                console.print("Your configs may contain:")
                console.print("  • API keys")
                console.print("  • Auth tokens")
                console.print("  • MCP credentials\n")

                if not Confirm.ask(
                    "[bold red]Continue with public repository?[/bold red]\n"
                    "This is NOT recommended for config sync.",
                    default=False,
                ):
                    raise RuntimeError("User cancelled due to public repository warning")

            # Clone existing repo
            console.print(f"\n[bold]Linking to existing repository: {repo_name}[/]\n")

            if self.repo_dir.exists() and any(self.repo_dir.iterdir()):
                # Directory has content, use existing
                console.print("[dim]Using existing local directory[/dim]\n")
            else:
                # Empty directory, clone
                repo_url_to_clone = f"https://github.com/{repo_name}.git"
                if not validate_github_url(repo_url_to_clone):
                    raise ValueError(f"Invalid repository name resulted in invalid URL: {repo_url_to_clone}")

                result = subprocess.run(
                    ["git", "clone", repo_url_to_clone, str(self.repo_dir)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(
                        result.returncode, result.args,
                        _sanitize_git_output(result.stdout),
                        _sanitize_git_output(result.stderr),
                    )

            # Update config
            self.config.repo_url = repo_url
            if agents:
                self.config.agents = list(agents)
            self._save_state("linked", repo_url)

            return repo_url

        # Repo doesn't exist - create it
        visibility = "private" if private else "public"

        # Inform user about what we're creating
        if private:
            console.print(f"\n[green]🔒 Creating PRIVATE repository: {repo_name}[/green]")
            console.print("[dim]   Contains: configs, skills, agents[/dim]")
            console.print("[dim]   ⚠️  Warning: Will store API keys and credentials![/dim]\n")
        else:
            console.print(f"\n[yellow]🌐 Creating PUBLIC repository: {repo_name}[/yellow]")
            console.print("[dim]   Contains: skills, agents[/dim]\n")

        # Create repository on GitHub
        result = subprocess.run(
            ["gh", "repo", "create", f"--{visibility}", "--source", ".", "--remote", "origin", "--", name],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            # Try alternative approach
            alt_result = subprocess.run(
                ["gh", "repo", "create", f"--{visibility}", "--", name],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            if alt_result.returncode != 0:
                raise subprocess.CalledProcessError(
                    alt_result.returncode, alt_result.args,
                    _sanitize_git_output(alt_result.stdout),
                    _sanitize_git_output(alt_result.stderr),
                )

            # Initialize local git
            self._run_git("init")
            self._run_git("config", "user.email", "agent-sync@local")
            self._run_git("config", "user.name", "agent-sync")
            self._run_git("remote", "add", "origin", repo_url)

        # Create initial structure
        self._create_repo_structure(agents)

        # Initial commit
        self._run_git("add", ".")
        self._run_git("commit", "-m", "chore: initial sync structure")
        self._run_git("push", "-u", "origin", "main")

        # Update config
        self.config.repo_url = repo_url

        if agents:
            self.config.agents = list(agents)

        self._save_state("initialized", repo_url)

        return repo_url

    def _clone_to_repo(self, repo_url: str) -> None:
        """Clone repository to self.repo_dir using temp directory for safety.

        Uses temp directory to prevent data loss if clone fails.
        Reusable helper for init_repo and link_repo.

        Args:
            repo_url: GitHub repository URL to clone
        """
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_repo = Path(temp_dir) / "repo"

            result = subprocess.run(
                ["git", "clone", repo_url, str(temp_repo)],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, result.args,
                    _sanitize_git_output(result.stdout),
                    _sanitize_git_output(result.stderr),
                )

            # Only after successful clone, replace existing repo
            if self.repo_dir.exists():
                shutil.rmtree(self.repo_dir)

            shutil.move(str(temp_repo), str(self.repo_dir))

    def link_repo(self, repo_url: str) -> None:
        """Link to an existing sync repository."""
        if not validate_github_url(repo_url):
            raise ValueError(f"Invalid repository URL: {repo_url}")

        if not self._check_git_installed():
            raise RuntimeError("Git is required")

        self._clone_to_repo(repo_url)

        # Update config
        self.config.repo_url = repo_url

        self._save_state("linked", repo_url)

    def pull(
        self,
        force: bool = False,
        dry_run: bool = False,
        interactive: bool = True,
        skills_only: bool = False,
        configs_only: bool = False,
        agents_only: bool = False,
        conflict_resolver: Optional[callable] = None,
        skills_filter: Optional[list[str]] = None,
        agents_filter: Optional[list[str]] = None,
        skills_exclude: Optional[list[str]] = None,
        agents_exclude: Optional[list[str]] = None,
        prune: bool = False,
    ) -> tuple[list[str], PullSummary]:
        """
        Fetch and apply remote configuration with conflict detection.

        Args:
            force: Apply all remote changes without confirmation
            dry_run: Show what would change without applying
            interactive: Show interactive prompts for conflicts
            skills_only: Pull only skills (not configs)
            configs_only: Pull only configs (not skills)
            agents_only: Pull only custom agents (not configs or skills)
            conflict_resolver: Optional callback to resolve conflicts

        Returns:
            Tuple of (applied changes, pull summary)
        """
        # If repo doesn't exist or is not a valid git repo, clone it automatically
        is_valid_git_repo = self.repo_dir.exists() and (self.repo_dir / ".git").exists()

        if not is_valid_git_repo:
            # Use default repo if not configured
            if not self.config.repo_url:
                gh_user = self._get_github_user()
                self.config.repo_url = f"https://github.com/{gh_user}/agent-sync-private.git"
                console.print(f"\n[dim]Using default repo: {self.config.repo_url}[/dim]\n")

            console.print("\n[bold]📥 Cloning repository...[/]\n")
            self.link_repo(self.config.repo_url)

        # Fetch latest
        self._run_git("fetch", "origin")

        # Detect conflicts and skill drifts before pulling
        conflicts = self._detect_conflicts(skills_only, configs_only, agents_only)
        skill_drifts = self._detect_skill_drifts(skills_filter, skills_exclude)
        summary = PullSummary(conflicts=conflicts, skill_drifts=skill_drifts)

        # Build the skill names to keep local from interactive choice
        keep_local_skills: set[str] = set()

        # Dry run: show what would change
        if dry_run:
            self._show_pull_preview(summary)
            return ([], summary)

        # Handle skill drifts (before git pull, so we know user intent)
        if skill_drifts and not force:
            if interactive:
                apply_remote = self._handle_skill_drifts_interactive(skill_drifts)
                if not apply_remote:
                    keep_local_skills = {d.name for d in skill_drifts}
            else:
                # No interactive: keep local (current behavior)
                keep_local_skills = {d.name for d in skill_drifts}
        # Clear from summary since they've been resolved
        summary.skill_drifts = []

        # Handle conflicts
        if conflicts and interactive and not force:
            if conflict_resolver:
                conflict_resolver(conflicts)
            else:
                self._handle_conflicts_interactive(conflicts)
            # Mark conflicts as resolved (local version kept)
            summary.conflicts = []  # Cleared after resolution

        # Check for local changes in repo (unstaged)
        # Ignore manifest file which is auto-generated
        status = self._run_git("status", "--porcelain")
        # Filter out manifest file (it's auto-generated, not user content)
        relevant_changes = [line for line in status.split('\n')
                         if line and '.agent-sync-manifest.json' not in line]
        if relevant_changes and not force:
            raise RuntimeError(
                "You have local changes. Commit them first or use --force"
            )

        # Pull changes
        self._run_git("pull", "origin", "main")

        changes = []

        # Apply configs (or skip based on flags)
        if not skills_only and not agents_only:
            changes.extend(self._apply_synced_configs(agents_filter=agents_filter, agents_exclude=agents_exclude))
        else:
            console.print("[dim]Skipping configs (skills/agents-only mode)[/dim]")

        # Apply global gitignore
        if not skills_only and not agents_only:
            changes.extend(self._apply_gitignore_global(force=force, dry_run=dry_run))

        # Apply skills (or skip based on flags)
        if not configs_only and not agents_only:
            skill_changes = self._apply_synced_skills(
                skills_filter=skills_filter,
                skills_exclude=skills_exclude,
                force=force,
                interactive=interactive,
                keep_local_skills=keep_local_skills,
            )
            changes.extend(skill_changes)
        else:
            console.print("[dim]Skipping skills (configs/agents-only mode)[/dim]")

        # Apply custom agents (or skip based on flags)
        if not skills_only and not configs_only:
            agent_changes = self._apply_synced_agents()
            changes.extend(agent_changes)
        else:
            console.print("[dim]Skipping agents (skills/configs-only mode)[/dim]")

        # Mirror-pull: remove local skills that are in hub but not in privado.
        # This is the inverse of mirror-push. Default off (safety) — user
        # must opt in with --prune to actually delete local skills.
        if prune and not configs_only and not agents_only:
            local_pruned = self._prune_local_orphan_skills()
            changes.extend(local_pruned)
            if local_pruned:
                console.print(
                    f"[green]✓ Pruned {len(local_pruned)} orphan skill(s) from local hub[/green]"
                )

        self._save_state("pulled", self.config.repo_url)

        return (changes, summary)

    def _prune_local_orphan_skills(self) -> list[dict]:
        """Remove skills from ~/.agents/skills/ that are not in privado.

        Inverse of `_prune_orphan_skills` (which cleans privado). Called by
        `pull(prune=True)` after the local clone of the private repo has
        been updated and synced skills applied. Ensures the local hub is a
        mirror of privado.

        Returns:
            List of change dicts (one per removed skill) with status='D'.
        """
        import shutil

        local_hub = paths.HUB_DIR
        if not local_hub.exists():
            return []

        # Skills in the local clone of privado (already pulled)
        synced_skills_dir = self.repo_dir / "skills"
        if not synced_skills_dir.exists():
            return []

        privado_skill_names = {
            d.name for d in synced_skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }

        # Skills in the local hub
        local_skill_names = {
            d.name for d in local_hub.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }

        orphan_locals = sorted(local_skill_names - privado_skill_names)
        if not orphan_locals:
            return []

        pruned: list[dict] = []
        for orphan in orphan_locals:
            path = local_hub / orphan
            try:
                shutil.rmtree(path)
            except Exception as e:
                console.print(
                    f"[yellow]⚠ Could not remove local skill {orphan}: {e}[/yellow]"
                )
                continue
            pruned.append({
                "path": f"~/.agents/skills/{orphan}/",
                "status": "D",
                "label": "deleted (prune)",
                "directory_count": None,
            })
        return pruned

    def _detect_conflicts(
        self,
        skills_only: bool = False,
        configs_only: bool = False,
        agents_only: bool = False,
    ) -> list[PullConflict]:
        """Detect files that have been modified both locally and remotely.

        A conflict occurs when:
        1. The file exists locally
        2. The file has been modified locally (unstaged changes in git)
        3. The remote version is different from the local version

        Args:
            skills_only: Only check skills
            configs_only: Only check configs
            agents_only: Only check agents

        Returns:
            List of conflicts detected
        """
        from .agents import get_all_agents

        conflicts = []

        # Check unstaged changes in the repo
        status_output = self._run_git("status", "--porcelain")
        unstaged_files = set()

        for line in status_output.strip().split("\n"):
            if line and line[1] == " " and not line.startswith("?"):  # Unstaged changes (not untracked)
                # Format: XY filename, XY is status (M = modified, D = deleted, etc.)
                parts = line.split(" ", 1)
                if len(parts) >= 2:
                    unstaged_files.add(parts[1])

        # Get list of files in HEAD (what's in the repo)
        try:
            head_files = self._run_git("ls-tree", "-r", "--name-only", "HEAD").strip().split("\n")
        except subprocess.CalledProcessError:
            head_files = []  # Empty repo

        # Check configs
        if not skills_only and not agents_only:
            for agent in get_all_agents():
                # Skip if agent sync is disabled
                if not self.config.is_agent_enabled(agent.name):
                    continue

                synced_config_dir = self.repo_dir / "configs" / agent.name
                if not synced_config_dir.exists():
                    continue

                for config_file in synced_config_dir.glob("*"):
                    if not config_file.is_file():
                        continue

                    relative_path = str(config_file.relative_to(self.repo_dir))

                    # Check if this file is in unstaged changes
                    if relative_path in unstaged_files:
                        # Get diff stats
                        diff_stats = self._get_file_diff_stats(relative_path)

                        local_path = agent.config_path.parent / config_file.name

                        conflict = PullConflict(
                            agent_name=agent.name,
                            filename=config_file.name,
                            local_path=local_path,
                            remote_path=Path(relative_path),
                            diff_stats=diff_stats,
                        )
                        conflicts.append(conflict)

        # Check skills
        if not configs_only and not agents_only:
            synced_skills_dir = self.repo_dir / "skills"
            if synced_skills_dir.exists():
                for skill_item in synced_skills_dir.glob("*"):
                    if skill_item.name.startswith(".") or not skill_item.is_dir():
                        continue

                    for skill_file in skill_item.rglob("*"):
                        if skill_file.is_file() and skill_file.name != MANIFEST_FILENAME:
                            relative_path = str(skill_file.relative_to(self.repo_dir))

                            if relative_path in unstaged_files:
                                diff_stats = self._get_file_diff_stats(relative_path)

                                conflict = PullConflict(
                                    agent_name="skills",
                                    filename=f"{skill_item.name}/{skill_file.name}",
                                    local_path=skill_file,
                                    remote_path=Path(relative_path),
                                    diff_stats=diff_stats,
                                )
                                conflicts.append(conflict)

        # Check global gitignore
        if not skills_only and not agents_only:
            gitignore_repo = self.repo_dir / "configs" / "gitignore_global"
            if gitignore_repo.exists():
                relative_path = "configs/gitignore_global"
                local_gitignore = self._get_global_gitignore_path()

                if local_gitignore and local_gitignore.exists():
                    # Check if local version differs from repo version
                    try:
                        local_content = local_gitignore.read_text(encoding="utf-8")
                        remote_content = gitignore_repo.read_text(encoding="utf-8")
                        if local_content != remote_content:
                            diff_stats = self._get_file_diff_stats(relative_path)
                            conflict = PullConflict(
                                agent_name="git",
                                filename="gitignore_global",
                                local_path=local_gitignore,
                                remote_path=Path(relative_path),
                                diff_stats=diff_stats,
                            )
                            conflicts.append(conflict)
                    except (OSError, UnicodeDecodeError):
                        pass

        return conflicts

    def _get_file_diff_stats(self, file_path: str) -> dict:
        """Get diff statistics (added/removed lines) for a file."""
        try:
            result = self._run_git("diff", "--stat", "--", file_path)
            # Parse output like: " 1 file changed, 2 insertions(+), 3 deletions(-)"
            stats = {"added": 0, "removed": 0}
            if "insertion" in result:
                import re
                match = re.search(r"(\d+) insertion", result)
                if match:
                    stats["added"] = int(match.group(1))
            if "deletion" in result:
                import re
                match = re.search(r"(\d+) deletion", result)
                if match:
                    stats["removed"] = int(match.group(1))
            return stats
        except subprocess.CalledProcessError:
            return {"added": 0, "removed": 0}

    # ------------------------------------------------------------------ #
    # Skill drift detection
    # ------------------------------------------------------------------ #

    def _compare_skill_dirs(self, local_dir: Path, repo_dir: Path) -> dict | None:
        """Compare a local skill directory against the repo version recursively.

        Returns a dict with 'files_changed' count and 'file_details' list,
        or None if the directories are identical.
        """
        # Collect all relative paths from both sides
        local_files: dict[str, Path] = {}
        repo_files: dict[str, Path] = {}

        if local_dir.is_dir():
            for p in local_dir.rglob("*"):
                if p.is_file() and not p.name.startswith("."):
                    local_files[str(p.relative_to(local_dir))] = p

        if repo_dir.is_dir():
            for p in repo_dir.rglob("*"):
                if p.is_file() and not p.name.startswith("."):
                    repo_files[str(p.relative_to(repo_dir))] = p

        all_paths = set(local_files) | set(repo_files)
        file_details = []

        for rel_path in sorted(all_paths):
            local_p = local_files.get(rel_path)
            repo_p = repo_files.get(rel_path)

            if local_p and repo_p:
                # Both sides: compare byte content
                if self._same_content(local_p, repo_p):
                    continue
                # Count added/removed lines via text diff
                local_lines = local_p.read_bytes().count(b"\n")
                repo_lines = repo_p.read_bytes().count(b"\n")
                added = max(0, repo_lines - local_lines)
                removed = max(0, local_lines - repo_lines)
                file_details.append({
                    "path": rel_path,
                    "local": local_p,
                    "repo": repo_p,
                    "added": added,
                    "removed": removed,
                })
            elif local_p and not repo_p:
                file_details.append({
                    "path": rel_path,
                    "local": local_p,
                    "repo": None,
                    "added": 0,
                    "removed": local_p.read_bytes().count(b"\n") + 1,
                })
            elif repo_p and not local_p:
                file_details.append({
                    "path": rel_path,
                    "local": None,
                    "repo": repo_p,
                    "added": repo_p.read_bytes().count(b"\n") + 1,
                    "removed": 0,
                })

        if not file_details:
            return None

        return {
            "files_changed": len(file_details),
            "file_details": file_details,
        }

    def _detect_skill_drifts(
        self,
        skills_filter: Optional[list[str]] = None,
        skills_exclude: Optional[list[str]] = None,
    ) -> list[SkillDrift]:
        """Detect skills whose local content differs from the repo version.

        Only checks skills that exist in BOTH locations - orphan skills
        (exist in only one place) are left untouched.
        """
        synced_skills_dir = self.repo_dir / "skills"
        global_skills_dir = paths.HUB_DIR

        if not synced_skills_dir.exists() or not global_skills_dir.exists():
            return []

        drifts = []
        for skill_item in synced_skills_dir.glob("*"):
            if skill_item.name.startswith("."):
                continue

            # Apply filter/exclude
            if skills_filter and skill_item.name not in skills_filter:
                continue
            if skills_exclude and skill_item.name in skills_exclude:
                continue

            local_skill = global_skills_dir / skill_item.name
            if not local_skill.exists():
                continue  # orphan: only in repo, skip

            diff = self._compare_skill_dirs(local_skill, skill_item)
            if diff is not None:
                drifts.append(SkillDrift(
                    name=skill_item.name,
                    files_changed=diff["files_changed"],
                    file_details=diff["file_details"],
                    local_path=local_skill,
                    repo_path=skill_item,
                ))

        return drifts

    def _show_skill_diff(self, drifts: list[SkillDrift]) -> None:
        """Show diff for skill drifts using pager."""
        import os
        import subprocess
        import tempfile

        from rich.console import Console
        console = Console()

        if not drifts:
            return

        diff_segments = []
        for drift in drifts:
            for fd in drift.file_details:
                label = f"{drift.name}/{fd['path']}"
                # Get repo version via git show
                repo_rel = f"skills/{drift.name}/{fd['path']}"
                try:
                    remote_content = self._run_git("show", f"origin/main:{repo_rel}")
                except subprocess.CalledProcessError:
                    remote_content = ""

                # Read local version, with binary safety
                try:
                    local_content = fd["local"].read_text() if fd["local"] else ""
                except (UnicodeDecodeError, Exception):
                    local_content = ""

                # Generate unified diff (unified_diff already outputs ---/+++ headers)
                import difflib
                diff_lines = list(difflib.unified_diff(
                    local_content.splitlines(keepends=True),
                    remote_content.splitlines(keepends=True),
                    fromfile=f"a/{label}",
                    tofile=f"b/{label}",
                ))
                if diff_lines:
                    diff_segments.extend(diff_lines)
                    diff_segments.append("\n")

        full_diff = "".join(diff_segments)
        if not full_diff.strip():
            console.print("[dim]Files differ but could not generate diff.[/dim]")
            return

        with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as f:
            f.write(full_diff)
            diff_path = f.name

        try:
            pager = os.environ.get('PAGER', 'less')
            subprocess.run(
                [pager, diff_path],
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError:
            # Pager not available, fall back to printing inline
            console.print("[yellow]Pager not found, showing diff inline:[/yellow]\n")
            console.print(full_diff)
        finally:
            os.unlink(diff_path)

    def _handle_skill_drifts_interactive(self, drifts: list[SkillDrift]) -> bool:
        """Handle skill drifts interactively with user prompts.

        Returns True if user chose to apply remote versions, False to keep local.
        """
        from rich.console import Console
        from rich.prompt import Prompt

        console = Console()

        if not drifts:
            return False

        console.print("\n[bold yellow]⚠️  Skill Differences Detected[/bold yellow]\n")
        console.print("[dim]Some skills have local changes that differ from the repository.[/dim]\n")

        for i, drift in enumerate(drifts, 1):
            console.print(f"{i}. {drift.name} ({drift.diff_summary})")

        console.print()
        console.print("[Enter] Keep local version (default)")
        console.print("[a] Apply all remote versions (overwrite local)")
        console.print("[v] View diff")
        console.print("[q] Abort pull")
        console.print()

        while True:
            choice = Prompt.ask(
                "[cyan]Choose action[/cyan]",
                choices=["a", "v", "q", ""],
                default="",
            )

            if choice == "a":
                console.print("[green]✓ Will apply remote skill versions[/green]")
                return True
            elif choice == "v":
                self._show_skill_diff(drifts)
            elif choice == "q":
                raise RuntimeError("Pull aborted by user")
            elif choice == "":
                console.print("[dim]Keeping local skill versions.[/dim]")
                return False

    def _show_pull_preview(self, summary: PullSummary) -> None:
        """Show a preview of what would be pulled."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console()

        console.print("\n[bold cyan]Pull Preview[/bold cyan]\n")

        if summary.has_conflicts:
            console.print(f"[yellow]⚠️  {len(summary.conflicts)} conflict(s):[/yellow]")
            for conflict in summary.conflicts:
                console.print(f"  • {conflict.display_name} ({conflict.diff_summary})")
            console.print()

        if summary.has_skill_drifts:
            console.print(f"[yellow]⚠️  {len(summary.skill_drifts)} skill(s) with differences:[/yellow]")
            for drift in summary.skill_drifts:
                console.print(f"  • {drift.name} ({drift.diff_summary})")
            console.print()

        # Local-orphan prune candidates (skills in ~/.agents/skills/ but not in privado).
        # Shown always (independent of --prune) so the user sees the cleanup
        # opportunity even on default pull.
        local_orphans = self._detect_local_orphan_skills()
        if local_orphans:
            console.print(
                f"[yellow]⚠️  {len(local_orphans)} local skill(s) NOT in private repo (use --prune to remove):[/yellow]"
            )
            for name in local_orphans:
                console.print(f"  - {name}")
            console.print()

        # Count non-conflict and non-drift changes
        other = summary.new_files + summary.updated_files + summary.deleted_files
        if other > 0:
            console.print(f"[green]+ {other} file(s) to update (auto-apply)[/green]")

        if not summary.has_conflicts and not summary.has_skill_drifts and other == 0 and not local_orphans:
            console.print("[dim]No changes to pull.[/dim]")

        console.print("\n[dim]Run without --dry-run to apply changes. Add --prune to remove local orphans.[/dim]")

    def _detect_local_orphan_skills(self) -> list[str]:
        """Return the list of skill names in local hub that are missing from privado.

        Pure read-only detection — does not touch the filesystem. Used by the
        pull preview and by tests. The actual deletion lives in
        `_prune_local_orphan_skills`.
        """
        local_hub = paths.HUB_DIR
        synced_skills_dir = self.repo_dir / "skills"
        if not local_hub.exists() or not synced_skills_dir.exists():
            return []

        local_skill_names = {
            d.name for d in local_hub.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }
        privado_skill_names = {
            d.name for d in synced_skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }
        return sorted(local_skill_names - privado_skill_names)

    def _handle_conflicts_interactive(self, conflicts: list[PullConflict]) -> None:
        """Handle conflicts interactively with user prompts."""
        from rich.console import Console
        from rich.prompt import Prompt

        console = Console()

        console.print("\n[bold yellow]⚠️  Conflicts Detected[/bold yellow]\n")
        console.print("[dim]Your local changes differ from remote.[/dim]\n")

        for i, conflict in enumerate(conflicts, 1):
            console.print(f"{i}. {conflict.display_name} ({conflict.diff_summary})")

        console.print()
        console.print("[Enter] Keep local version (default)")
        console.print("[a] Apply all conflicts (use remote version)")
        console.print("[v] View diff")
        console.print("[q] Abort")
        console.print()

        while True:
            choice = Prompt.ask(
                "[cyan]Choose action[/cyan]",
                choices=["a", "v", "q", ""],
                default="",
            )

            if choice == "a":
                # Apply all remote - discard local changes in repo
                # git pull will merge remote over our cleaned state
                self._run_git("checkout", "HEAD", "--", ".")
                console.print("[green]✓ Applied all remote versions[/green]")
                return
            elif choice == "v":
                self._show_conflict_diff(conflicts[0] if conflicts else None)
            elif choice == "q":
                raise RuntimeError("Pull aborted by user")
            elif choice == "":
                # Keep local - just return, local changes in repo will be preserved
                console.print("[dim]Keeping local versions.[/dim]")
                return

    def _show_conflict_diff(self, conflict: PullConflict | None) -> None:
        """Show diff for a conflict using pager."""
        import os
        import subprocess
        import tempfile

        if not conflict:
            return

        from rich.console import Console
        console = Console()

        # Get remote version to temp file
        try:
            remote_content = self._run_git("show", f"origin/main:{conflict.remote_path}")
        except subprocess.CalledProcessError:
            remote_content = ""

        # Read local version
        try:
            local_content = conflict.local_path.read_text()
        except (FileNotFoundError, PermissionError):
            local_content = ""

        # Create temp files for diff
        with tempfile.NamedTemporaryFile(mode='w', suffix='.local', delete=False) as local_file:
            local_file.write(local_content)
            local_temp = local_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.remote', delete=False) as remote_file:
            remote_file.write(remote_content)
            remote_temp = remote_file.name

        try:
            # Show diff using pager
            pager = os.environ.get('PAGER', 'less')
            subprocess.run(
                [pager, '-d', '-c',
                 f'--- Local: {conflict.display_name}\n+++ Remote: {conflict.display_name}',
                 local_temp, remote_temp],
                stdin=subprocess.DEVNULL
            )
        finally:
            os.unlink(local_temp)
            os.unlink(remote_temp)

    def _push_stage_and_get_changes(
        self,
        message: str = "chore: sync config updates",
        skills_only: bool = False,
        configs_only: bool = False,
        agents_only: bool = False,
        skills_filter: Optional[list[str]] = None,
        agents_filter: Optional[list[str]] = None,
        skills_exclude: Optional[list[str]] = None,
        agents_exclude: Optional[list[str]] = None,
        prune: bool = False,
    ) -> tuple[list[dict], list[str]]:
        """Stage files and return (changed_files, orphans).

        Returns:
            (changed_files, orphans) where:
            - changed_files: list of dicts with 'path', 'status', 'label',
              'directory_count' for everything to be committed.
            - orphans: list of skill names that exist in HEAD but are
              missing from the local hub. Always detected; only pruned
              if `prune=True`.
        """
        from .agents import get_all_agents

        if not self.repo_dir.exists():
            raise RuntimeError("Not linked to a repository. Run 'agent-sync init' or 'link' first")

        # Show progress spinner based on what's being synced
        # Count only available agents that are enabled (not all registry entries)
        agents_count = len([a for a in get_all_agents()
                           if self.config.is_agent_enabled(a.name) and a.is_available()])

        global_skills_dir = paths.HUB_DIR
        skills_count = len([d for d in global_skills_dir.iterdir()
                           if d.is_dir() and (d / "SKILL.md").exists()]) if global_skills_dir.exists() else 0

        if skills_only and not configs_only:
            console.print(f"  [dim]📦 Syncing {skills_count} skills...[/dim]")
            self._stage_skills()
        elif configs_only and not skills_only:
            console.print(f"  [dim]⚙️  Syncing {agents_count} agent configurations...[/dim]")
            self._stage_all_agent_files()
            self._stage_agents()
        else:
            console.print(f"  [dim]⚙️  Syncing {agents_count} agents...[/dim]")
            self._stage_all_agent_files()
            console.print(f"  [dim]📦 Syncing skills...[/dim]")
            self._stage_skills()
            console.print(f"  [dim]🤖 Syncing custom agent definitions...[/dim]")
            self._stage_agents()

        # Parse BOTH staged and unstaged changes
        status = self._run_git("status", "--porcelain")

        # Always parse working tree changes (unstaged)
        changed_files = []

        # Stage global gitignore
        if not skills_only:
            gitignore_file = self._stage_gitignore_global()
            if gitignore_file:
                changed_files.append({
                    'path': gitignore_file,
                    'status': 'M',
                    'label': 'global gitignore',
                    'directory_count': 0,
                })
        for line in status.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            # Parse porcelain format: XY PATH or R100 OLD\tNEW (tab-separated)
            if '\t' in stripped:
                status_code = stripped[:1]
                path = stripped.split('\t')[-1]
            else:
                parts = stripped.split()
                status_code = parts[0]
                path = parts[-1]

            # Skip manifest file
            if path == '.agent-sync-manifest.json':
                continue

            # Skip if already in list
            if any(c['path'] == path for c in changed_files):
                continue

            # Classify the status for a human-readable label
            if status_code == '??':
                label = 'added'
            elif 'D' in status_code:
                label = 'deleted'
            elif 'A' in status_code:
                label = 'added'
            else:
                label = 'modified'

            # Count files if git reported a whole directory (trailing slash)
            directory_count = None
            if path.endswith('/'):
                dir_path = self.repo_dir / path.rstrip('/')
                if dir_path.exists():
                    directory_count = sum(1 for _ in dir_path.rglob('*') if _.is_file())
                path = path.rstrip('/')

            changed_files.append({
                'path': path,
                'status': status_code,
                'label': label,
                'directory_count': directory_count,
            })

        # Detect orphan skills (in HEAD but missing from local hub) so the
        # caller can warn the user. We ALWAYS detect (cheap read-only git
        # query); we only actually prune if the user explicitly asked.
        orphans = (
            self._detect_orphan_skills()
            if not configs_only and not agents_only
            else []
        )

        if prune and orphans and not configs_only and not agents_only:
            changed_files.extend(self._prune_orphan_skills(orphans))

        return changed_files, orphans

    def _detect_orphan_skills(self) -> list[str]:
        """Read-only: return skill names in HEAD but missing from local hub.

        Cheaper than `_prune_orphan_skills` because it does not touch the
        git index. Used to surface a warning to the user on default `push`
        and by `agent-sync skills prune --dry-run`.
        """
        local_hub = paths.HUB_DIR
        if not local_hub.exists():
            return []

        local_skill_names = {
            d.name for d in local_hub.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }

        try:
            # `-d` restricts to directory entries only — a file like
            # `skills/RETIRED.md` (manifest) would otherwise be treated as
            # a phantom orphan.
            head_ls = self._run_git("ls-tree", "-d", "--name-only", "HEAD", "skills/")
        except subprocess.CalledProcessError:
            return []  # Empty repo or no skills/ yet

        head_skill_names: set[str] = set()
        for name in head_ls.split("\n"):
            if not name:
                continue
            bare = name[len("skills/"):] if name.startswith("skills/") else name
            if bare and not bare.startswith("."):
                head_skill_names.add(bare)

        return sorted(head_skill_names - local_skill_names)

    def _prune_orphan_skills(self, orphans: list[str] | None = None) -> list[dict]:
        """Stage `git rm --cached` for each orphan skill and return change dicts.

        For each orphan skill, `git rm --cached` it (stages the deletion in
        the next commit) and returns a synthetic change entry so the caller
        can show it in the +/~/− summary.

        Args:
            orphans: Pre-detected orphan skill names. If None, calls
                     `_detect_orphan_skills()` to compute them (skips a
                     redundant git query when the caller already detected).

        Returns:
            List of change dicts (one per pruned skill) with status='D' and
            label='deleted'.
        """
        if orphans is None:
            orphans = self._detect_orphan_skills()
        if not orphans:
            return []

        pruned: list[dict] = []
        for orphan in orphans:
            path = f"skills/{orphan}"
            try:
                self._run_git("rm", "-r", "--cached", path)
                # Also nuke from disk so a subsequent pull doesn't resurrect them
                file_path = self.repo_dir / path
                if isinstance(file_path, Path) and file_path.exists():
                    if file_path.is_dir():
                        shutil.rmtree(file_path, ignore_errors=True)
                    else:
                        file_path.unlink(missing_ok=True)
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[yellow]⚠ Could not prune {path}: {e.stderr.strip()}[/yellow]"
                )
                continue
            pruned.append({
                "path": path + "/",
                "status": "D",
                "label": "deleted",
                "directory_count": None,
            })
        return pruned
    def sync(self, force: bool = False, skills: bool = True, configs: bool = True, agents: bool = False) -> bool:
        """
        Run full sync cycle (pull + push).

        Args:
            force: Force pull even with local changes
            skills: Include skills in sync
            configs: Include configs in sync
            agents: Include agent configs in sync

        Returns:
            True if successful, False otherwise
        """
        try:
            # Pull first
            self.pull(force=force, skills_only=not skills, configs_only=not configs and not agents, agents_only=agents)
            # Then push
            self.push(skills_only=not skills, configs_only=not configs, agents_only=agents)
            return True
        except Exception:
            return False

    def push(self, message: str = "chore: sync config updates", skills_only: bool = False, configs_only: bool = False, agents_only: bool = False, prune: bool = False) -> tuple[list[dict], list[str]]:
        """Commit and push local changes to the private repo.

        By default (`prune=False`), the private repo is additive: skills
        missing from the local hub stay in the repo. Set `prune=True` to
        remove them in the same commit (records a `D` entry; no `--force`).

        Returns:
            (changed_files, orphans):
            - changed_files: list of change dicts that were committed+pushd.
            - orphans: list of orphan skill names that were DETECTED but
              NOT pruned (because `prune=False`). Empty if prune ran.
        """
        changed_files, orphans = self._push_stage_and_get_changes(
            message, skills_only, configs_only, agents_only, prune=prune
        )
        if not changed_files:
            return []

        self._run_git("add", ".")
        self._run_git("commit", "-m", message)

        try:
            self._run_git("push", "origin", "main")
        except subprocess.CalledProcessError as e:
            if "Authentication failed" in e.stderr or "Invalid username or token" in e.stderr:
                raise RuntimeError(
                    "GitHub authentication failed. Try one of these solutions:\n"
                    "  1. Unset GITHUB_TOKEN: run 'unset GITHUB_TOKEN' and try again\n"
                    "  2. Refresh gh CLI auth: run 'gh auth refresh'\n"
                    "  3. Check auth status: run 'gh auth status'\n"
                    f"\nOriginal error: {e.stderr.strip()}"
                ) from e
            raise

        self._save_state("pushed", self.config.repo_url)
        return changed_files, orphans

    def get_status(self) -> dict:
        """
        Get sync status for all agents.

        Returns:
            Dictionary with status information per agent
        """
        from .agents import get_agents

        status = {}

        for agent in get_agents():
            # Check if agent sync is enabled in config
            enabled = self.config.is_agent_enabled(agent.name)
            installed = agent.is_available()

            # Determine status based on enabled + installed
            if not enabled:
                status[agent.name] = {
                    "status": "disabled",
                    "last_sync": "-",
                    "changes": None,
                    "installed": installed,
                }
                continue

            # Agent is enabled - check if installed
            if installed:
                agent_status = {
                    "status": "active",  # Enabled + Installed
                    "last_sync": "-",
                    "changes": None,
                    "installed": True,
                }

                # Check for uncommitted changes
                if self.repo_dir.exists():
                    try:
                        changes = self._run_git(
                            "diff", "--name-only",
                            cwd=agent.config_path.parent if agent.config_path.exists() else None
                        )
                        if changes:
                            agent_status["changes"] = f"{len(changes.split())} files"
                    except Exception:
                        pass
            else:
                agent_status = {
                    "status": "not_installed",  # Enabled but not installed
                    "last_sync": "-",
                    "changes": None,
                    "installed": False,
                }

            # Get last sync time from state
            state = self._load_state()
            if state and state.get("last_sync"):
                agent_status["last_sync"] = state["last_sync"]

            status[agent.name] = agent_status

        return status

    def _create_repo_structure(self, agents: tuple[str, ...] = ()) -> None:
        """Create initial repository structure."""
        # Create directories
        (self.repo_dir / "configs").mkdir(parents=True, exist_ok=True)
        (self.repo_dir / "skills").mkdir(parents=True, exist_ok=True)
        (self.repo_dir / "prompts").mkdir(parents=True, exist_ok=True)
        (self.repo_dir / "agents").mkdir(parents=True, exist_ok=True)

        # Create .gitignore
        gitignore = """# Secrets - NEVER sync these
.env
*.secret
*auth*.json
*credentials*.json
overrides.yaml

# OS files
.DS_Store
Thumbs.db

# Editor files
*.swp
*.swo
*~

# Lock files
*.lock
package-lock.json
bun.lock

# Agent session state (not configuration)
*/history/
*/tmp/
*state.json
*projects.json
*installation_id

# Transient files
*.bak
*.log
*.log.*

# Database files
*.db
*.mdb
*.ldb

# Pi.dev git clones (cache, not configuration)
configs/pi.dev/git/
"""
        (self.repo_dir / ".gitignore").write_text(gitignore)

        # Create README
        readme = """# Agent Sync Repository

This repository syncs configuration and skills across multiple AI agents.

## Managed by agent-sync

CLI tool: https://github.com/yourusername/agent-sync

## Structure

- `configs/` - Agent configurations
- `skills/` - Shared skills (source of truth: ~/.agents/skills/)
- `prompts/` - Shared prompts (optional)
- `agents/` - Custom agents (.claude/agents/, .opencode/agents/)

## Usage

```bash
# First machine
agent-sync setup

# Additional machines
agent-sync link <repo-url>

# Sync
agent-sync pull
agent-sync push
```

## Skills

All skills are centralized in `~/.agents/skills/` and synced via `skills/`.
"""
        (self.repo_dir / "README.md").write_text(readme)

        # Create agent-specific directories
        from .agents import get_all_agents

        target_agents = agents if agents else [a.name for a in get_all_agents()]

        for agent_name in target_agents:
            (self.repo_dir / "configs" / agent_name).mkdir(parents=True, exist_ok=True)

        # Create skills directory (always)
        (self.repo_dir / "skills").mkdir(parents=True, exist_ok=True)

    def _stage_agent_configs(
        self,
        agents_filter: Optional[list[str]] = None,
        agents_exclude: Optional[list[str]] = None,
    ) -> None:
        """Stage agent configurations for commit."""
        import subprocess
        from .agents import get_all_agents

        def _is_submodule(path: Path) -> bool:
            """Check if a path is a git submodule (has .git entry but no .git dir)."""
            try:
                result = subprocess.run(
                    ["git", "ls-files", "--stage", str(path)],
                    capture_output=True, text=True, cwd=path.parent if path.is_dir() else path, timeout=5
                )
                # If git ls-files shows it as a submodule (mode 160000)
                for line in result.stdout.splitlines():
                    if path.name in line and line.startswith("160000"):
                        return True
            except Exception:
                pass
            return False

        for agent in get_all_agents():
            # Skip if agent sync is disabled
            if not self.config.is_agent_enabled(agent.name):
                continue

            # Apply filter/exclude logic
            if agents_filter and agent.name not in agents_filter:
                continue
            if agents_exclude and agent.name in agents_exclude:
                continue

            # Skip agents not available locally
            if not agent.is_available():
                continue

            # Skip global-skills (it's a special skills-management agent, not a config agent)
            if agent.name == "global-skills":
                continue

            # Skip agents whose config dir IS the agent-sync repo or is a parent of it
            # (this prevents circular copying like ~/.config/opencode/ == configs/opencode/)
            try:
                agent_dir_abs = agent.config_path.parent.resolve()
                repo_dir_abs = self.repo_dir.resolve()
                if agent_dir_abs == repo_dir_abs or agent_dir_abs.is_relative_to(repo_dir_abs):
                    continue
            except (ValueError, OSError):
                pass

            # Skip submodules (git handles them separately)
            repo_agent_dir = self.repo_dir / "configs" / agent.name
            if repo_agent_dir.exists() and _is_submodule(repo_agent_dir):
                continue

            # Get sync options for this agent
            sync_options = self.config.get_sync_options(agent.name)
            sync_configs = sync_options.get("configs", True)

            # Copy configs to repo
            if sync_configs and agent.config_path.parent.exists():
                agent_config_dir = self.repo_dir / "configs" / agent.name
                agent_config_dir.mkdir(parents=True, exist_ok=True)

                # Get config file patterns for this agent
                patterns = agent.data.get("config_patterns", [agent.config_filename])

                # 1. Remove config files from repo that no longer exist locally
                if agent_config_dir.exists():
                    for pattern in patterns:
                        for repo_config in agent_config_dir.glob(pattern):
                            if repo_config.is_file():
                                # Check if this file still exists locally
                                local_file = agent.config_path.parent / repo_config.name
                                if not local_file.exists():
                                    repo_config.unlink()

                # 2. Copy current config files to repo
                for pattern in patterns:
                    for config_file in agent.config_path.parent.glob(pattern):
                        if config_file.is_file():
                            # Skip excluded files
                            if self._should_exclude(config_file.name):
                                continue

                            # Copy config file as-is
                            dest = agent_config_dir / config_file.name
                            shutil.copy2(config_file, dest)

            # Pi.dev extra paths - copy each path category to its repo subdirectory
            if agent.name == "pi.dev":
                self._stage_pi_extra_paths(agent)

            # Generic extra_paths handling for ALL agents (except pi.dev - handled above)
            # This enables backing up directories like ~/.roo/rules/ declared in agent_registry.yaml
            extra_paths = agent.data.get("extra_paths", {})
            if extra_paths and agent.name != "pi.dev":
                for category, source_paths in extra_paths.items():
                    for source_path_str in source_paths:
                        source_path = Path(source_path_str).expanduser()
                        if source_path.exists():
                            repo_category_dir = self.repo_dir / "configs" / agent.name / category
                            repo_category_dir.mkdir(parents=True, exist_ok=True)
                            for item in source_path.iterdir():
                                if self._should_exclude(item.name):
                                    continue
                                dest = repo_category_dir / item.name
                                if item.is_dir():
                                    shutil.copytree(item, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
                                else:
                                    shutil.copy2(item, dest)

    def _stage_pi_extra_paths(self, agent) -> None:
        """Backup pi.dev extra paths to the repo directory.

        Handles directory copies (extensions, bin, global_*) and single-file
        copies (lsp-settings.json, models.json, pyrightconfig.json).
        Git worktrees are skipped (200MB+ of cache data).
        """
        pi_dir = self.repo_dir / "configs" / agent.name
        category_map = {
            "extensions": "extensions",
            "bin": "bin",
            "global_extensions": "global_extensions",
            "global_prompts": "global_prompts",
            "global_skills_local": "global_skills",
            "global_themes": "global_themes",
        }
        single_file_map = {
            "lsp_paths": ("lsp-settings.json", "lsp"),
            "models_paths": ("models.json", "models"),
            "pyrightconfig_paths": ("pyrightconfig.json", "pyrightconfig"),
        }

        # Copy directory-based paths
        for attr_name, subdir in category_map.items():
            paths = getattr(agent, f"{attr_name}_paths", None)
            if not paths:
                continue
            for src_path in paths:
                if src_path.exists():
                    dest = pi_dir / subdir
                    dest.mkdir(parents=True, exist_ok=True)
                    for item in src_path.iterdir():
                        item_dest = dest / item.name
                        if item.is_dir():
                            shutil.copytree(item, item_dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
                        else:
                            shutil.copy2(item, item_dest)

        # Copy single-file paths
        for attr_name, (filename, subdir) in single_file_map.items():
            paths = getattr(agent, attr_name, None)
            if not paths:
                continue
            for src_path in paths:
                if src_path.exists() and src_path.is_file():
                    dest_file = pi_dir / subdir / filename
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dest_file)

        # Git worktrees - skip (cache, not config)
        if hasattr(agent, 'git_paths'):
            for git_path in agent.git_paths:
                if git_path.exists():
                    total_mb = sum(f.stat().st_size for f in git_path.rglob('*') if f.is_file()) // 1024 // 1024
                    console.print(f"  [dim]Skipping git clones backup ({total_mb}MB) - these are cache, not config[/dim]")

        # Packages (special: copies each package by name)
        if hasattr(agent, 'packages_paths'):
            for package_path in agent.packages_paths:
                if package_path.exists():
                    pkg_dest = pi_dir / "packages" / package_path.name
                    pkg_dest.mkdir(parents=True, exist_ok=True)
                    if pkg_dest.exists():
                        shutil.rmtree(pkg_dest)
                    shutil.copytree(package_path, pkg_dest, ignore=shutil.ignore_patterns('.git'))

    def _restore_pi_extra_paths(self, agent, synced_config_dir: Path, changes: list[str]) -> None:
        """Restore pi.dev extra paths from repo to their original locations.

        Handles directory copies (extensions, prompts, themes, bin, global_*),
        single-file copies (lsp-settings.json, models.json, pyrightconfig.json),
        git worktrees (skip), and packages.
        """
        dir_categories = {
            "extensions": "extensions_paths",
            "prompts": "prompts_paths",
            "themes": "themes_paths",
            "bin": "bin_paths",
            "global_extensions": "global_extensions_paths",
            "global_prompts": "global_prompts_paths",
            "global_skills": "global_skills_local_paths",
            "global_themes": "global_themes_paths",
        }
        single_files = {
            "lsp-settings.json": "lsp_paths",
            "models.json": "models_paths",
            "pyrightconfig.json": "pyrightconfig_paths",
        }

        # Directory copies
        for subdir, attr_name in dir_categories.items():
            synced_dir = synced_config_dir / subdir
            if not synced_dir.exists():
                continue
            paths = getattr(agent, attr_name, None)
            if not paths:
                continue
            for dst_path in paths:
                dst_path.mkdir(parents=True, exist_ok=True)
                for item in synced_dir.iterdir():
                    dest = dst_path / item.name
                    if not dest.exists() or (item.is_file() and self._same_content(dest, item)):
                        if item.is_dir():
                            shutil.copytree(item, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
                        else:
                            shutil.copy2(item, dest)
                        changes.append(f"{agent.name}/{subdir}: {item.name}")

        # Single-file copies
        for filename, attr_name in single_files.items():
            synced_file = synced_config_dir / filename
            if not synced_file.exists():
                continue
            paths = getattr(agent, attr_name, None)
            if not paths:
                continue
            for dst_path in paths:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                dest = dst_path
                if not dest.exists() or self._same_content(dest, synced_file):
                    shutil.copy2(synced_file, dest)
                    changes.append(f"{agent.name}: {filename}")

        # Git worktrees - skip (cache, not config)
        synced_git_dir = synced_config_dir / "git"
        if synced_git_dir.exists():
            total_mb = sum(f.stat().st_size for f in synced_git_dir.rglob('*') if f.is_file()) // 1024 // 1024
            console.print(f"  [dim]Skipping git clones restore ({total_mb}MB) - these are cache, not config[/dim]")

        # Packages - special: copies each package by name with rmtree
        synced_packages_dir = synced_config_dir / "packages"
        if synced_packages_dir.exists():
            for package_path in agent.packages_paths:
                package_path.parent.mkdir(parents=True, exist_ok=True)
                for package_item in synced_packages_dir.iterdir():
                    dest = package_path.parent / package_item.name
                    if package_item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(package_item, dest, ignore=shutil.ignore_patterns('.git'))
                        changes.append(f"{agent.name}/package: {package_item.name}")

    def _stage_agents(self) -> None:
        """
        Stage agent files (.md definitions) to the repo.
        """
        console.print(f"  [dim]  └─ Cleaning up unavailable agents...[/dim]")
        """
        Stage custom agents for commit.

        Structure in repo:
        - agents/<agent-name>/project/ - Project-level agents (.claude/agents/, .opencode/agents/)
        - agents/<agent-name>/global/ - Global agents (~/.claude/agents/, ~/.config/opencode/agents/)
        """
        from .agents import get_all_agents

        repo_agents_dir = self.repo_dir / "agents"

        # Ensure repo agents directory exists
        repo_agents_dir.mkdir(parents=True, exist_ok=True)

        # Remove agents directories that are no longer available locally
        # (e.g., claude-code was uninstalled)
        for agent_repo_subdir in list(repo_agents_dir.iterdir()):
            agent_name = agent_repo_subdir.name
            # Find the agent
            agent = next((a for a in get_all_agents() if a.name == agent_name), None)
            if not agent:
                # Unknown agent in repo - remove it
                if agent_repo_subdir.is_dir():
                    shutil.rmtree(agent_repo_subdir)
                    console.print(f"  [dim]Removed unknown agent: {agent_name}[/dim]")
                continue
            # Check sync_mode - if 'all', don't remove here (let main loop handle cleanup)
            sync_mode = self.config.get_sync_mode(agent_name)
            if sync_mode == "all":
                continue

            # If agent is available, keep (will be updated above)
            if agent.is_available():
                continue
            # If agent has local agents dirs, keep (might have custom agents)
            has_local = (agent.agents_path and agent.agents_path.exists()) or \
                        (agent.agents_path_global and agent.agents_path_global.exists())
            if has_local:
                continue
            # Agent not available and no local agents dirs - remove
            if agent_repo_subdir.is_dir():
                shutil.rmtree(agent_repo_subdir)
                console.print(f"  [dim]Removed unavailable agent: {agent_name}[/dim]")

        for agent in get_all_agents():
            # Skip if agent sync is disabled
            if not self.config.is_agent_enabled(agent.name):
                continue

            # Skip if agent doesn't support custom agents
            if not agent.supports_custom_agents():
                continue

            # Define agent_repo_dir early (used for cleanup)
            agent_repo_dir = repo_agents_dir / agent.name

            # Check sync mode and availability
            sync_mode = self.config.get_sync_mode(agent.name)
            is_available = agent.is_available()

            # Auto-clean: if agent not installed and sync_mode='installed', clean repo
            if sync_mode == "installed" and not is_available:
                if agent_repo_dir.exists():
                    console.print(f"  [dim]  └─ Cleaning up {agent.name} (not installed)...[/dim]")
                    shutil.rmtree(agent_repo_dir)
                continue

            # Auto-clean: if sync_mode='all' but no local files, clean repo
            has_project = agent.agents_path and agent.agents_path.exists() and any(agent.agents_path.rglob("*.md"))
            has_global = agent.agents_path_global and agent.agents_path_global.exists() and any(agent.agents_path_global.rglob("*.md"))

            if sync_mode == "always" and not has_project and not has_global:
                # Clean repo directory for this agent
                if agent_repo_dir.exists():
                    console.print(f"  [dim]  └─ Cleaning up {agent.name} (no local agents)...[/dim]")
                    shutil.rmtree(agent_repo_dir)
                continue


            # 1. Stage project-level agents (.claude/agents/, .opencode/agents/)
            if has_project:
                project_agent_count = len(list(agent.agents_path.rglob("*.md")))
                console.print(f"  [dim]  └─ Syncing {project_agent_count} project agents for {agent.name}...[/dim]")

                project_agents_dir = agent_repo_dir / "project"
                project_agents_dir.mkdir(parents=True, exist_ok=True)

                # Remove agents from repo that no longer exist locally
                if project_agents_dir.exists():
                    for repo_agent_file in project_agents_dir.rglob("*.md"):
                        local_file = agent.agents_path / repo_agent_file.relative_to(project_agents_dir)
                        if not local_file.exists():
                            repo_agent_file.unlink()
                    # Clean up empty directories
                    for dirpath in sorted(project_agents_dir.rglob("*"), reverse=True):
                        if dirpath.is_dir() and not any(dirpath.iterdir()):
                            dirpath.rmdir()

                # Copy current project agents to repo
                for agent_file in agent.agents_path.rglob("*.md"):
                    if agent_file.is_file():
                        # Skip excluded files
                        if self._should_exclude(agent_file.name):
                            continue

                        # Create relative path structure
                        rel_path = agent_file.relative_to(agent.agents_path)
                        dest = project_agents_dir / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(agent_file, dest)

            # 2. Stage global agents (~/.claude/agents/, ~/.config/opencode/agents/)
            if has_global:
                global_agent_count = len(list(agent.agents_path_global.rglob("*.md")))
                console.print(f"  [dim]  └─ Syncing {global_agent_count} global agents for {agent.name}...[/dim]")
                global_agents_dir = agent_repo_dir / "global"
                global_agents_dir.mkdir(parents=True, exist_ok=True)

                # Remove agents from repo that no longer exist locally
                if global_agents_dir.exists():
                    for repo_agent_file in global_agents_dir.rglob("*.md"):
                        local_file = agent.agents_path_global / repo_agent_file.relative_to(global_agents_dir)
                        if not local_file.exists():
                            repo_agent_file.unlink()
                    # Clean up empty directories
                    for dirpath in sorted(global_agents_dir.rglob("*"), reverse=True):
                        if dirpath.is_dir() and not any(dirpath.iterdir()):
                            dirpath.rmdir()

                # Copy current global agents to repo
                for agent_file in agent.agents_path_global.rglob("*.md"):
                    if agent_file.is_file():
                        # Skip excluded files
                        if self._should_exclude(agent_file.name):
                            continue

                        # Create relative path structure
                        rel_path = agent_file.relative_to(agent.agents_path_global)
                        dest = global_agents_dir / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(agent_file, dest)
                continue

            agent_repo_dir = repo_agents_dir / agent.name

            # 1. Stage project-level agents (.claude/agents/, .opencode/agents/)
            if agent.agents_path and agent.agents_path.exists():
                project_agent_count = len(list(agent.agents_path.rglob("*.md")))
                if project_agent_count > 0:
                    console.print(f"  [dim]  └─ Syncing {project_agent_count} project agents for {agent.name}...[/dim]")

                project_agents_dir = agent_repo_dir / "project"
                project_agents_dir.mkdir(parents=True, exist_ok=True)
                project_agent_count = len(list(agent.agents_path.rglob("*.md")))
                if project_agent_count > 0:
                    console.print(f"  [dim]  └─ Syncing {project_agent_count} project agents for {agent.name}...[/dim]")
                project_agents_dir = agent_repo_dir / "project"
                project_agents_dir.mkdir(parents=True, exist_ok=True)

                # Remove agents from repo that no longer exist locally
                if project_agents_dir.exists():
                    for repo_agent_file in project_agents_dir.rglob("*.md"):
                        local_file = agent.agents_path / repo_agent_file.relative_to(project_agents_dir)
                        if not local_file.exists():
                            repo_agent_file.unlink()
                    # Clean up empty directories
                    for dirpath in sorted(project_agents_dir.rglob("*"), reverse=True):
                        if dirpath.is_dir() and not any(dirpath.iterdir()):
                            dirpath.rmdir()

                # Copy current project agents to repo
                for agent_file in agent.agents_path.rglob("*.md"):
                    if agent_file.is_file():
                        # Skip excluded files
                        if self._should_exclude(agent_file.name):
                            continue

                        # Create relative path structure
                        rel_path = agent_file.relative_to(agent.agents_path)
                        dest = project_agents_dir / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(agent_file, dest)

            # 2. Stage global agents (~/.claude/agents/, ~/.config/opencode/agents/)
            if agent.agents_path_global and agent.agents_path_global.exists():
                global_agent_count = len(list(agent.agents_path_global.rglob("*.md")))
                if global_agent_count > 0:
                    console.print(f"  [dim]  └─ Syncing {global_agent_count} global agents for {agent.name}...[/dim]")
                global_agents_dir = agent_repo_dir / "global"
                global_agents_dir.mkdir(parents=True, exist_ok=True)

                # Remove agents from repo that no longer exist locally
                if global_agents_dir.exists():
                    for repo_agent_file in global_agents_dir.rglob("*.md"):
                        local_file = agent.agents_path_global / repo_agent_file.relative_to(global_agents_dir)
                        if not local_file.exists():
                            repo_agent_file.unlink()
                    # Clean up empty directories
                    for dirpath in sorted(global_agents_dir.rglob("*"), reverse=True):
                        if dirpath.is_dir() and not any(dirpath.iterdir()):
                            dirpath.rmdir()

                # Copy current global agents to repo
                for agent_file in agent.agents_path_global.rglob("*.md"):
                    if agent_file.is_file():
                        # Skip excluded files
                        if self._should_exclude(agent_file.name):
                            continue

                        # Create relative path structure
                        rel_path = agent_file.relative_to(agent.agents_path_global)
                        dest = global_agents_dir / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(agent_file, dest)

    def _stage_skills(self) -> None:
        """
        Stage skills for commit, including extension skills.

        Structure in repo:
        - skills/_global/ or skills/<skill-name>/ - Global skills from ~/.agents/skills/
        - skills/<agent>-<extension>/ - Extension skills
        """
        from .skills import SkillsManager

        global_skills_dir = paths.HUB_DIR
        repo_skills_dir = self.repo_dir / "skills"

        # Ensure repo skills directory exists
        repo_skills_dir.mkdir(parents=True, exist_ok=True)

        # Scan for extension skills
        skills_manager = SkillsManager()
        skills_manager.scan_all_agents()

        # 1. Remove skills from repo that no longer exist locally
        if repo_skills_dir.exists():
            for repo_skill in repo_skills_dir.iterdir():
                if repo_skill.name.startswith("."):
                    continue

                # Check if it's a global skill
                is_global = (global_skills_dir / repo_skill.name).exists()

                # Check if it's an extension skill
                is_extension = repo_skill.name in skills_manager.extension_skills

                if not is_global and not is_extension:
                    if repo_skill.is_dir():
                        shutil.rmtree(repo_skill)
                    else:
                        repo_skill.unlink()

        # 2. Copy global skills to repo
        if global_skills_dir.exists():
            for skill_item in global_skills_dir.iterdir():
                if skill_item.name.startswith("."):
                    continue

                dest = repo_skills_dir / skill_item.name

                if skill_item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(skill_item, dest)
                else:
                    shutil.copy2(skill_item, dest)

        # 3. Copy extension skills to repo
        for ext_name, ext_info in skills_manager.extension_skills.items():
            source_dir = Path(ext_info["skills_dir"])
            dest_dir = repo_skills_dir / ext_name

            if not source_dir.exists():
                continue

            # Remove existing dest if present
            if dest_dir.exists():
                shutil.rmtree(dest_dir)

            # Copy extension skills
            dest_dir.mkdir(parents=True, exist_ok=True)

            for skill_item in source_dir.iterdir():
                if skill_item.name.startswith(".") or skill_item.is_symlink():
                    continue

                if skill_item.is_dir():
                    shutil.copytree(skill_item, dest_dir / skill_item.name)
                else:
                    shutil.copy2(skill_item, dest_dir / skill_item.name)

        # 4. Stage symlinks for backup
        self._stage_symlinks_for_backup()

        # 5. Create and save manifest
        manifest = self._create_manifest()
        self._save_manifest(manifest)

    @staticmethod
    def _same_content(path1: Path, path2: Path) -> bool:
        """Compare two files by byte content. Safe for both text and binary files."""
        try:
            return path1.read_bytes() == path2.read_bytes()
        except Exception:
            return False

    def _should_exclude(self, filename: str, exclude_patterns: list[str] | None = None) -> bool:
        """Check if a file should be excluded from sync.

        Args:
            filename: Name or relative path of the file
            exclude_patterns: Optional list of glob patterns to exclude
        """
        import fnmatch

        # Get just the filename for pattern matching
        just_name = Path(filename).name

        # Check custom exclude patterns first
        if exclude_patterns:
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(filename, pattern):
                    return True
                if fnmatch.fnmatch(just_name, pattern):
                    return True

        # Check default exclude patterns
        for pattern in self.EXCLUDE_PATTERNS:
            # Handle directory patterns (e.g., "history/")
            if pattern.endswith('/'):
                dir_name = pattern.rstrip('/')
                # Check if filename starts with dir_name/ or contains /dir_name/
                if filename.startswith(f"{dir_name}/") or f"/{dir_name}/" in filename or filename.endswith(f"/{dir_name}") or just_name == dir_name:
                    return True
            # Handle file patterns
            elif fnmatch.fnmatch(filename, pattern):
                return True
            elif fnmatch.fnmatch(just_name, pattern):
                return True

        return False
        """Check if a file should be excluded from sync.

        Args:
            filename: Name or relative path of the file
            exclude_patterns: Optional list of glob patterns to exclude
        """
        import fnmatch

        # Check custom exclude patterns first
        if exclude_patterns:
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(filename, pattern):
                    return True
                # Also check just the filename against pattern
                if fnmatch.fnmatch(Path(filename).name, pattern):
                    return True

        # Check default exclude patterns
        for pattern in self.EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(filename, pattern):
                return True

        return False

    def _copy_directory(
        self,
        src: Path,
        dest: Path,
        exclude: list[str] | None = None,
        preserve_symlinks: bool = True,
    ) -> int:
        """
        Copy entire directory preserving symlinks.

        Delegates symlink and file copies to _copy_item.

        Args:
            src: Source directory
            dest: Destination directory
            exclude: List of glob patterns to exclude
            preserve_symlinks: If True, copy symlinks as symlinks (default: True)

        Returns:
            Number of files copied
        """
        if not src.exists():
            return 0

        dest.mkdir(parents=True, exist_ok=True)
        copied = 0

        for item in src.rglob("*"):
            rel_path = item.relative_to(src)
            if self._should_exclude(str(rel_path), exclude):
                continue
            if item.is_dir():
                (dest / rel_path).mkdir(parents=True, exist_ok=True)
            else:
                copied += self._copy_item(item, src, dest, exclude, preserve_symlinks)

        return copied

    def _copy_item(self, item: Path, src: Path, dest: Path, exclude: list[str] | None = None, preserve_symlinks: bool = True) -> int:
        """Copy a single item (symlink, file, or directory) preserving relative path."""
        rel_path = item.relative_to(src)
        dest_item = dest / rel_path

        if self._should_exclude(str(rel_path), exclude):
            return 0

        if item.is_symlink() and preserve_symlinks:
            if dest_item.exists() or dest_item.is_symlink():
                dest_item.unlink()
            dest_item.parent.mkdir(parents=True, exist_ok=True)
            dest_item.symlink_to(item.readlink())
            return 1

        if item.is_file():
            dest_item.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_item)
            return 1

        if item.is_dir():
            return self._copy_directory(item, dest_item, exclude, preserve_symlinks)

        return 0

    def _copy_path_pattern(
        self,
        src: Path,
        dest: Path,
        pattern: str,
        exclude: list[str] | None = None,
        preserve_symlinks: bool = True,
    ) -> int:
        """
        Copy files matching a glob pattern.

        Args:
            src: Source directory (agent config dir)
            dest: Destination directory (repo configs/agent/)
            pattern: Glob pattern (e.g., "plugins/", "**/*.js", "commands/*")
            exclude: List of patterns to exclude
            preserve_symlinks: If True, preserve symlinks

        Returns:
            Number of files copied
        """
        if not src.exists():
            return 0

        copied = 0

        if pattern.endswith("/"):
            # Directory pattern - copy entire directory
            dir_path = src / pattern.rstrip("/")
            if dir_path.exists():
                dest_dir = dest / pattern.rstrip("/")
                copied += self._copy_directory(dir_path, dest_dir, exclude, preserve_symlinks)
        elif "**" in pattern:
            # Recursive glob pattern
            for item in src.rglob("*"):
                rel_path_str = str(item.relative_to(src))
                file_pattern = pattern.replace("**/", "*").replace("**", "*")
                if fnmatch.fnmatch(rel_path_str, pattern) or fnmatch.fnmatch(item.name, file_pattern):
                    copied += self._copy_item(item, src, dest, exclude, preserve_symlinks)
        else:
            # Simple path or single wildcard
            for item in src.glob(pattern):
                copied += self._copy_item(item, src, dest, exclude, preserve_symlinks)

        return copied

    def _stage_all_agent_files(
        self,
        agents_filter: Optional[list[str]] = None,
        agents_exclude: Optional[list[str]] = None,
    ) -> None:
        """Stage all agent files for backup.

        Calls _stage_agent_configs() ONCE (it handles all agents internally)
        then iterates over enabled agents for additional file sync.
        """
        from .agents import get_all_agents

        # Stage configs once for ALL agents (avoids O(n2) redundant copies)
        self._stage_agent_configs(agents_filter=agents_filter, agents_exclude=agents_exclude)

        for agent in get_all_agents():
            if self.config.is_agent_enabled(agent.name):
                self._stage_agent_files(agent)

    def _stage_agent_files(self, agent: BaseAgent) -> None:
        """
        Stage agent files for backup based on sync configuration.

        Supports three modes:
        1. configs only (default) - Only config files
        2. all_files: true - Entire agent directory
        3. paths: [...] - Specific paths/patterns

        Args:
            agent: Agent object with config directory
        """

        # Skip if agent sync is disabled
        if not self.config.is_agent_enabled(agent.name):
            return

        if not agent.is_available() and agent.name != "global-skills":
            return

        # Get sync configuration
        sync_options = self.config.get_sync_options(agent.name)
        sync_options.get("configs", True)
        all_files = sync_options.get("all_files", False)
        paths = sync_options.get("paths")
        exclude = sync_options.get("exclude", [])

        agent_config_dir = Path(agent.config_dir).expanduser()
        repo_agent_dir = self.repo_dir / "configs" / agent.name

        if not agent_config_dir.exists():
            return

        # Configs are already staged by _stage_all_agent_files() via _stage_agent_configs()
        # which handles ALL agents in a single pass. Do NOT call it again here.

        # Copy all files (entire directory)
        if all_files:
            console.print(f"  [dim]Backing up all files: {agent.name}[/dim]")
            self._copy_directory(
                src=agent_config_dir,
                dest=repo_agent_dir,
                exclude=exclude,
                preserve_symlinks=True,
            )
            return

        # Copy specific paths
        if paths:
            console.print(f"  [dim]Backing up paths: {agent.name} - {len(paths)} patterns[/dim]")
            for path_pattern in paths:
                self._copy_path_pattern(
                    src=agent_config_dir,
                    dest=repo_agent_dir,
                    pattern=path_pattern,
                    exclude=exclude,
                    preserve_symlinks=True,
                )

    def _apply_synced_configs(
        self,
        agents_filter: Optional[list[str]] = None,
        agents_exclude: Optional[list[str]] = None,
    ) -> list[str]:
        """Apply synced configurations to local agent directories.

        Args:
            agents_filter: Only apply configs for these agents (None = all)
            agents_exclude: Skip configs for these agents
        """
        from .agents import get_all_agents

        changes = []

        for agent in get_all_agents():
            # Skip if agent sync is disabled
            if not self.config.is_agent_enabled(agent.name):
                continue

            synced_config_dir = self.repo_dir / "configs" / agent.name

            # Get sync options for this agent
            sync_options = self.config.get_sync_options(agent.name)
            sync_configs = sync_options.get("configs", True)

            # Apply configs
            if sync_configs and synced_config_dir.exists() and agent.config_path.parent.exists():
                for config_file in synced_config_dir.glob("*"):
                    if config_file.is_file():
                        dest = agent.config_path.parent / config_file.name
                        if not dest.exists() or self._same_content(dest, config_file):
                            shutil.copy2(config_file, dest)
                            changes.append(f"{agent.name}: {config_file.name}")

            # Restore pi.dev extra paths from repo to original locations
            if agent.name == "pi.dev":
                self._restore_pi_extra_paths(agent, synced_config_dir, changes)

            extra_paths = agent.data.get("extra_paths", {})
            if extra_paths and agent.name != "pi.dev":
                for category, source_paths in extra_paths.items():
                    synced_category_dir = synced_config_dir / category
                    if synced_category_dir.exists():
                        for source_path_str in source_paths:
                            source_path = Path(source_path_str).expanduser()
                            source_path.mkdir(parents=True, exist_ok=True)
                            for item in synced_category_dir.iterdir():
                                dest = source_path / item.name
                                if dest.exists() and item.is_file() and self._same_content(dest, item):
                                    continue
                                if item.is_dir():
                                    if dest.exists():
                                        shutil.rmtree(dest)
                                    shutil.copytree(item, dest, ignore=shutil.ignore_patterns('.git'))
                                else:
                                    shutil.copy2(item, dest)
                                changes.append(f"{agent.name}/{category}: {item.name}")

        return changes

    def _apply_synced_agents(self) -> list[str]:
        """
        Apply synced custom agents to local directories.

        Restores:
        1. Project-level agents (.claude/agents/, .opencode/agents/)
        2. Global agents (~/.claude/agents/, ~/.config/opencode/agents/)
        """
        from .agents import get_all_agents

        changes = []

        for agent in get_all_agents():
            # Skip if agent sync is disabled
            if not self.config.is_agent_enabled(agent.name):
                continue

            # Skip if agent doesn't support custom agents
            if not agent.supports_custom_agents():
                continue

            # Skip if sync_mode='installed' and agent is not installed
            sync_mode = self.config.get_sync_mode(agent.name)
            is_available = agent.is_available()
            if sync_mode == "installed" and not is_available:
                continue

            repo_agents_dir = self.repo_dir / "agents" / agent.name

            # 1. Apply project-level agents
            if not self.config.is_agent_enabled(agent.name):
                continue

            # Skip if agent doesn't support custom agents
            if not agent.supports_custom_agents():
                continue

            repo_agents_dir = self.repo_dir / "agents" / agent.name

            # 1. Apply project-level agents
            project_agents_src = repo_agents_dir / "project"
            if project_agents_src.exists() and agent.agents_path:
                agent.agents_path.mkdir(parents=True, exist_ok=True)

                for agent_file in project_agents_src.rglob("*.md"):
                    if agent_file.is_file():
                        rel_path = agent_file.relative_to(project_agents_src)
                        dest = agent.agents_path / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)

                        if not dest.exists() or self._same_content(dest, agent_file):
                            shutil.copy2(agent_file, dest)
                            changes.append(f"{agent.name}/project: {rel_path}")

            # 2. Apply global agents
            global_agents_src = repo_agents_dir / "global"
            if global_agents_src.exists() and agent.agents_path_global:
                agent.agents_path_global.mkdir(parents=True, exist_ok=True)

                for agent_file in global_agents_src.rglob("*.md"):
                    if agent_file.is_file():
                        rel_path = agent_file.relative_to(global_agents_src)
                        dest = agent.agents_path_global / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)

                        if not dest.exists() or self._same_content(dest, agent_file):
                            shutil.copy2(agent_file, dest)
                            changes.append(f"{agent.name}/global: {rel_path}")

        return changes

    def _apply_synced_skills(
        self,
        skills_filter: Optional[list[str]] = None,
        skills_exclude: Optional[list[str]] = None,
        force: bool = False,
        interactive: bool = True,
        keep_local_skills: Optional[set[str]] = None,
    ) -> list[str]:
        """
        Apply synced skills to local directories.

        Uses manifest to:
        1. Restore extension skills to their original locations
        2. Restore symlinks
        3. Restore global skills to ~/.agents/skills/

        Args:
            skills_filter: Only apply these specific skills (None = all)
            skills_exclude: Exclude these skills from being applied
            force: Apply all remote versions without confirmation
            interactive: Show interactive prompts for skill drifts
            keep_local_skills: Pre-resolved set of skill names to keep local
                              (when called from pull(), avoids double detection)
        """
        changes = []
        synced_skills_dir = self.repo_dir / "skills"
        global_skills_dir = paths.HUB_DIR

        # Load manifest to get extension info
        manifest = self._load_manifest()

        # 1. Restore extension skills first (if manifest exists)
        if manifest and manifest.get("extensions"):
            console.print("[bold]📦 Restoring extension skills...[/]\n")
            self._restore_extension_skills(manifest)
            console.print()

        # 2. Restore symlinks (if manifest exists)
        if manifest:
            console.print("[bold]🔗 Restoring symlinks...[/]\n")
            symlinks_restored = self._restore_symlinks_from_backup()
            if symlinks_restored > 0:
                console.print(f"  [green]✓ Restored {symlinks_restored} symlinks[/green]\n")
            else:
                console.print("  [dim]No symlinks to restore[/dim]\n")

        # 3. Restore global skills (skip extension skills from manifest)
        if synced_skills_dir.exists():
            global_skills_dir.mkdir(parents=True, exist_ok=True)

            # Get extension skill names from manifest to skip them
            extension_skill_names = set()
            if manifest:
                for ext_name in manifest.get("extensions", {}).keys():
                    extension_skill_names.add(ext_name)

            # Detect skill drifts only if not pre-resolved by caller
            if keep_local_skills is None:
                skill_drifts = self._detect_skill_drifts(skills_filter, skills_exclude)
                resolved_keep: set[str] = set()

                if skill_drifts:
                    if force:
                        pass
                    elif interactive:
                        apply_remote = self._handle_skill_drifts_interactive(skill_drifts)
                        if not apply_remote:
                            resolved_keep = {d.name for d in skill_drifts}
                    else:
                        resolved_keep = {d.name for d in skill_drifts}
            else:
                resolved_keep = keep_local_skills

            for skill_item in synced_skills_dir.glob("*"):
                if skill_item.name.startswith("."):
                    continue

                # Skip extension skills (they were restored above)
                if skill_item.name in extension_skill_names:
                    continue

                # Apply filter/exclude logic
                if skills_filter and skill_item.name not in skills_filter:
                    continue
                if skills_exclude and skill_item.name in skills_exclude:
                    continue

                dest = global_skills_dir / skill_item.name

                # Skip skills where user chose to keep local version
                if skill_item.name in resolved_keep:
                    continue

                # Skip identical files to avoid unnecessary I/O
                if dest.exists() and skill_item.is_file() and self._same_content(dest, skill_item):
                    continue

                # Copy: overwrites existing (for drifts/force) or creates new
                if skill_item.is_dir():
                    shutil.copytree(skill_item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(skill_item, dest)
                changes.append(f"global-skills: {skill_item.name}")

        return changes

    def _create_manifest(self) -> dict:
        """
        Create manifest for extension skills and symlinks.

        Returns:
            Manifest dict with extensions and global_skills info
        """
        from .skills import SkillsManager

        skills_manager = SkillsManager()

        # Scan for extension skills
        skills_manager.scan_all_agents()

        manifest = {
            "version": 1,
            "created_at": datetime.now().isoformat(),
            "extensions": {},
            "global_skills": [],
        }

        # Add extension info to manifest
        for ext_name, ext_info in skills_manager.extension_skills.items():
            manifest["extensions"][ext_name] = {
                "agent": ext_info["agent"],
                "extension_dir": ext_info["extension"],
                "skills_dir": ext_info["skills_dir"],
            }

            # Add symlink info if exists
            if ext_info.get("symlink"):
                manifest["extensions"][ext_name]["symlink"] = ext_info["symlink"]

        # List global skills
        global_skills_dir = paths.HUB_DIR
        if global_skills_dir.exists():
            for skill_item in global_skills_dir.iterdir():
                if skill_item.name.startswith("."):
                    continue
                manifest["global_skills"].append(skill_item.name)

        return manifest

    def _save_manifest(self, manifest: dict) -> None:
        """Save manifest to repo directory."""
        manifest_path = self.repo_dir / MANIFEST_FILENAME

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    def _load_manifest(self) -> dict | None:
        """Load manifest from repo directory."""
        manifest_path = self.repo_dir / MANIFEST_FILENAME

        if manifest_path.exists():
            with open(manifest_path) as f:
                return json.load(f)

        return None

    def _stage_symlinks_for_backup(self) -> None:
        """
        Stage symlinks from agent skill directories for backup.

        Extension symlinks are preserved in configs/<agent>/skills/
        """
        from .agents import get_all_agents
        from .skills import SkillsManager

        skills_manager = SkillsManager()

        for agent in get_all_agents():
            if not agent.skills_path.exists():
                continue

            # Create backup directory for symlinks
            backup_dir = self.repo_dir / "configs" / agent.name / "skills"
            backup_dir.mkdir(parents=True, exist_ok=True)

            for item in agent.skills_path.iterdir():
                if item.is_symlink():
                    # Check if this is an extension symlink
                    if skills_manager._is_extension_symlink(item, agent):
                        # Backup the symlink itself
                        symlink_backup = backup_dir / item.name

                        # Remove existing backup if present
                        if symlink_backup.exists() or symlink_backup.is_symlink():
                            symlink_backup.unlink()

                        # Recreate symlink with same target
                        symlink_backup.symlink_to(item.readlink())

    def _restore_symlinks_from_backup(self) -> int:
        """
        Restore symlinks from backup to agent skill directories.

        Returns:
            Number of symlinks restored
        """
        from .agents import get_all_agents

        restored = 0

        for agent in get_all_agents():
            backup_dir = self.repo_dir / "configs" / agent.name / "skills"

            if not backup_dir.exists():
                continue

            # Ensure agent skills directory exists
            agent.skills_path.mkdir(parents=True, exist_ok=True)

            for item in backup_dir.iterdir():
                if item.is_symlink():
                    # Restore symlink to agent skills directory
                    symlink_path = agent.skills_path / item.name

                    # Remove existing if present
                    if symlink_path.exists() or symlink_path.is_symlink():
                        symlink_path.unlink()

                    # Recreate symlink with same target
                    symlink_path.symlink_to(item.readlink())
                    restored += 1

        return restored

    def _restore_extension_skills(self, manifest: dict) -> int:
        """
        Restore extension skills from repo to their original locations.

        Args:
            manifest: Loaded manifest dict

        Returns:
            Number of extensions restored
        """
        restored = 0

        for ext_name, ext_info in manifest.get("extensions", {}).items():
            agent_name = ext_info.get("agent")
            extension_dir = ext_info.get("extension_dir")

            # Get agent config
            from .agents import get_agent
            agent = get_agent(agent_name)

            if not agent:
                console.print(f"[yellow]Warning: Agent {agent_name} not found, skipping extension {ext_name}[/yellow]")
                continue

            # Source in repo
            source_dir = self.repo_dir / "skills" / ext_name

            if not source_dir.exists():
                console.print(f"[yellow]Warning: Extension skills not found in repo: {ext_name}[/yellow]")
                continue

            # Destination: ~/.config/opencode/superpowers/skills/
            config_dir = Path(agent.config_dir).expanduser()
            dest_dir = config_dir / extension_dir / "skills"

            # Create destination and copy skills
            dest_dir.mkdir(parents=True, exist_ok=True)

            for skill_item in source_dir.iterdir():
                if skill_item.name.startswith("."):
                    continue

                dest_skill = dest_dir / skill_item.name

                if skill_item.is_dir():
                    shutil.copytree(skill_item, dest_skill, dirs_exist_ok=True)
                else:
                    shutil.copy2(skill_item, dest_skill)

            restored += 1
            console.print(f"  [green]✓ Restored extension: {agent_name}-{extension_dir}[/green]")

        return restored

    # -----------------------------------------------------------------------
    # Global gitignore sync
    # -----------------------------------------------------------------------

    CRITICAL_GITIGNORE_PATTERNS = frozenset({
        "*.pem", "*.key", "*.secret", "*.token",
        ".env", ".env.*", "*.env.*",
        "secrets/", "credentials/", "tokens/", "api_keys/",
        "mcp-secrets",
    })

    def _get_global_gitignore_path(self) -> Optional[Path]:
        """Return the user's global gitignore path, or None if not configured."""
        try:
            result = subprocess.run(
                ["git", "config", "--global", "core.excludesFile"],
                capture_output=True, text=True, check=False, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                path_str = os.path.expanduser(result.stdout.strip())
                path = Path(path_str)
                if path.exists():
                    return path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        # Fallback: common default locations
        for candidate in [
            Path.home() / ".gitignore_global",
            Path.home() / ".config" / "git" / "ignore",
            Path.home() / ".gitignore",
        ]:
            if candidate.exists():
                return candidate
        return None

    def _stage_gitignore_global(self) -> Optional[str]:
        """Backup the user's global gitignore to the repo.

        Returns the repo-relative filename if staged, None otherwise.
        """
        global_path = self._get_global_gitignore_path()
        if global_path is None:
            return None

        try:
            dest = self.repo_dir / "configs" / "gitignore_global"
            dest.parent.mkdir(parents=True, exist_ok=True)

            src_content = global_path.read_text(encoding="utf-8")
            if dest.exists() and dest.read_text(encoding="utf-8") == src_content:
                return None  # Already up-to-date

            dest.write_text(src_content, encoding="utf-8")
            return "configs/gitignore_global"
        except (OSError, PermissionError):
            return None

    def _apply_gitignore_global(self, force: bool = False, dry_run: bool = False) -> list[str]:
        """Apply the global gitignore from the synced repo.

        Shows diff and asks user for replace/keep/merge.
        Returns list of change descriptions.
        """
        changes = []
        repo_file = self.repo_dir / "configs" / "gitignore_global"
        if not repo_file.exists():
            return changes

        remote_content = repo_file.read_text(encoding="utf-8")
        remote_patterns = {l.strip() for l in remote_content.splitlines()
                           if l.strip() and not l.strip().startswith("#")}

        local_path = self._get_global_gitignore_path()

        # --- Local file doesn't exist: offer to create ---
        if local_path is None:
            if force:
                dest = Path.home() / ".gitignore_global"
                if not dry_run:
                    dest.write_text(remote_content, encoding="utf-8")
                    self._run_git("config", "--global", "core.excludesFile", str(dest))
                changes.append(f"gitignore_global: created {dest}")  # Reports even in dry-run
                return changes

            try:
                from rich.prompt import Confirm
                console.print("\n[yellow]📄 .gitignore_global not found on this machine.[/yellow]")
                console.print("[dim]Remote repo contains:")
                for line in remote_content.splitlines()[:15]:
                    console.print(f"  {line}")
                if len(remote_content.splitlines()) > 15:
                    console.print(f"  ... and {len(remote_content.splitlines()) - 15} more lines")
                console.print("[/dim]")

                if Confirm.ask("Create ~/.gitignore_global from remote version?", default=True):
                    if not dry_run:
                        dest = Path.home() / ".gitignore_global"
                        dest.write_text(remote_content, encoding="utf-8")
                        self._run_git("config", "--global", "core.excludesFile", str(dest))
                    changes.append("gitignore_global: created from remote")
            except (EOFError, KeyboardInterrupt):
                pass

        # --- Local file exists: diff and prompt ---
        else:
            local_content = local_path.read_text(encoding="utf-8")
            if local_content == remote_content:
                return changes  # Identical

            local_patterns = {l.strip() for l in local_content.splitlines()
                               if l.strip() and not l.strip().startswith("#")}

            added = remote_patterns - local_patterns
            removed = local_patterns - remote_patterns

            if not added and not removed:
                return changes  # Only comment differences

            # --- Force mode: merge (add missing, keep local) ---
            if force:
                if not dry_run:
                    merged_lines = local_content.rstrip() + "\n"
                    for pattern in sorted(added):
                        merged_lines += f"{pattern}\n"
                    local_path.write_text(merged_lines, encoding="utf-8")
                changes.append(f"gitignore_global: merged {len(added)} new patterns")
                return changes

            # --- Interactive prompt ---
            try:
                from rich.prompt import Confirm, Prompt
                console.print("\n[yellow]📄 .gitignore_global - differences found:[/yellow]")
                if added:
                    console.print("  [green]+ New patterns (in remote):[/green]")
                    for p in sorted(added):
                        console.print(f"    + {p}")
                if removed:
                    console.print("  [red]- Patterns only on this machine:[/red]")
                    for p in sorted(removed):
                        console.print(f"    - {p}")

                # Security warning
                missing_critical = self.CRITICAL_GITIGNORE_PATTERNS - local_patterns
                if missing_critical:
                    console.print(
                        f"\n  [bold red]⚠  Your local gitignore is missing critical security patterns:[/bold red]"
                    )
                    for p in sorted(missing_critical):
                        console.print(f"    ⚠  {p}")
                    console.print(
                        "  [dim]These patterns prevent agents from seeing sensitive files.[/dim]"
                    )

                console.print("\nOptions:")
                console.print("  [green][1][/green] Replace with remote version")
                console.print("  [yellow][2][/yellow] Keep local version")
                console.print("  [cyan][3][/cyan] Merge (add missing patterns to local)")

                choice = Prompt.ask("Choice", choices=["1", "2", "3"], default="2")

                if choice == "1":
                    if not dry_run:
                        local_path.write_text(remote_content, encoding="utf-8")
                    changes.append("gitignore_global: replaced with remote version")
                elif choice == "3":
                    if not dry_run:
                        merged_lines = local_content.rstrip() + "\n"
                        for pattern in sorted(added):
                            merged_lines += f"{pattern}\n"
                        local_path.write_text(merged_lines, encoding="utf-8")
                    changes.append(f"gitignore_global: merged {len(added)} new patterns")
                else:
                    changes.append("gitignore_global: kept local version")

            except (EOFError, KeyboardInterrupt):
                changes.append("gitignore_global: skipped")

        return changes

    def _get_github_user(self) -> str:
        """Get current GitHub username."""
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, result.args,
                _sanitize_git_output(result.stdout),
                _sanitize_git_output(result.stderr),
            )
        return result.stdout.strip()

    def _save_state(self, action: str, repo_url: str | None = None) -> None:
        """Save sync state."""
        state = {
            "last_sync": datetime.now().isoformat(),
            "last_action": action,
            "repo_url": repo_url or self.config.repo_url,
        }

        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self) -> dict | None:
        """Load sync state."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return None
