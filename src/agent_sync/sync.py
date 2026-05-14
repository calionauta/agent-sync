"""Sync management for agent-sync."""

import fnmatch
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from platformdirs import user_data_dir
from rich.console import Console

from .agents import BaseAgent
from .skills import MANIFEST_FILENAME
from .validators import validate_github_url

console = Console()


class SyncManager:
    """Manages synchronization with GitHub repository."""

    # Cross-platform data directory
    # Linux: ~/.local/share/agent-sync
    # macOS: ~/Library/Application Support/agent-sync
    # Windows: ~\AppData\Roaming\agent-sync
    DATA_DIR = Path(user_data_dir("agent-sync", "renatocaliari"))
    DEFAULT_REPO_DIR = DATA_DIR / "repo"
    STATE_FILE = DATA_DIR / "sync-state.json"
    MANIFEST_FILE = DATA_DIR / "repo" / ".agent-sync-manifest.json"

    # Files to NEVER sync (sensitive or local-only)
    EXCLUDE_PATTERNS = [
        "*auth*.json",
        "*accounts*.json",
        "*overrides*.json*",
        "*.lock",
        ".DS_Store",
        "package-lock.json",
        "bun.lock",
    ]

    def __init__(self, config):
        self.config = config
        self.repo_dir = self.DEFAULT_REPO_DIR
        self.state_file = self.STATE_FILE

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
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

        return result.stdout.strip()

    def _check_git_installed(self) -> bool:
        """Check if git is installed."""
        return shutil.which("git") is not None

    def _check_gh_installed(self) -> bool:
        """Check if GitHub CLI is installed."""
        return shutil.which("gh") is not None

    def init_repo(self, name: str, private: bool = True, agents: tuple[str, ...] = ()) -> str:
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

                subprocess.run(
                    ["git", "clone", repo_url_to_clone, str(self.repo_dir)],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )

            # Update config
            self.config.repo_url = repo_url
            if agents:
                self.config.agents = list(agents)
            self._save_state("linked", repo_url)

            return repo_url

        # Repo doesn't exist - create it
        visibility = "private" if private else "public"

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
            subprocess.run(
                ["gh", "repo", "create", f"--{visibility}", "--", name],
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )

            # Initialize local git
            self._run_git("init")
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

    def link_repo(self, repo_url: str) -> None:
        """
        Link to an existing sync repository.

        Args:
            repo_url: GitHub repository URL
        """
        if not validate_github_url(repo_url):
            raise ValueError(f"Invalid repository URL: {repo_url}")

        if not self._check_git_installed():
            raise RuntimeError("Git is required")

        # Clone repository
        if self.repo_dir.exists():
            shutil.rmtree(self.repo_dir)

        subprocess.run(
            ["git", "clone", repo_url, str(self.repo_dir)],
            check=True,
            timeout=120,
        )

        # Update config
        self.config.repo_url = repo_url

        self._save_state("linked", repo_url)

    def pull(self, force: bool = False, skills_only: bool = False, configs_only: bool = False, agents_only: bool = False) -> list[str]:
        """
        Fetch and apply remote configuration.

        Args:
            force: Force pull even with local changes
            skills_only: Pull only skills (not configs)
            configs_only: Pull only configs (not skills)
            agents_only: Pull only custom agents (not configs or skills)

        Returns:
            List of applied changes
        """
        # If repo doesn't exist or is not a valid git repo, clone it automatically
        is_valid_git_repo = self.repo_dir.exists() and (self.repo_dir / ".git").exists()

        if not is_valid_git_repo:
            if not self.config.repo_url:
                raise RuntimeError("Not linked to a repository. Run 'agent-sync link <url>' or 'agent-sync config repo <url>' first")

            console.print("\n[bold]📥 Cloning repository...[/]\n")
            self.link_repo(self.config.repo_url)

        # Check for local changes
        if not force:
            status = self._run_git("status", "--porcelain")
            if status:
                raise RuntimeError(
                    "You have local changes. Commit them first or use --force"
                )

        # Fetch and pull
        self._run_git("fetch", "origin")
        self._run_git("pull", "origin", "main")

        changes = []

        # Apply configs (or skip based on flags)
        if not skills_only and not agents_only:
            changes.extend(self._apply_synced_configs())
        else:
            console.print("[dim]Skipping configs (skills/agents-only mode)[/dim]")

        # Apply skills (or skip based on flags)
        if not configs_only and not agents_only:
            skill_changes = self._apply_synced_skills()
            changes.extend(skill_changes)
        else:
            console.print("[dim]Skipping skills (configs/agents-only mode)[/dim]")

        # Apply custom agents (or skip based on flags)
        if not skills_only and not configs_only:
            agent_changes = self._apply_synced_agents()
            changes.extend(agent_changes)
        else:
            console.print("[dim]Skipping agents (skills/configs-only mode)[/dim]")

        self._save_state("pulled", self.config.repo_url)

        return changes

    def push(self, message: str = "chore: sync config updates", skills_only: bool = False, configs_only: bool = False, agents_only: bool = False) -> list[str]:
        """
        Commit and push local changes.

        Args:
            message: Commit message
            skills_only: Push only skills (not configs)
            configs_only: Push only configs (not skills)
            agents_only: Push only custom agents (not configs or skills)

        Returns:
            List of pushed files
        """
        if not self.repo_dir.exists():
            raise RuntimeError("Not linked to a repository. Run 'agent-sync init' or 'link' first")

        # Stage files based on flags
        if skills_only:
            # Stage only skills
            self._stage_skills()
        elif configs_only:
            # Stage only configs (with new path support)
            self._stage_all_agent_files()
        elif agents_only:
            # Stage only custom agents
            self._stage_agents()
        else:
            # Stage everything (default)
            self._stage_all_agent_files()
            self._stage_skills()
            self._stage_agents()

        # Check for changes
        status = self._run_git("status", "--porcelain")
        if not status:
            return []

        # Get list of changed files
        changed_files = []
        for line in status.split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    changed_files.append(parts[-1])

        # Commit and push
        self._run_git("add", ".")
        self._run_git("commit", "-m", message)

        try:
            self._run_git("push", "origin", "main")
        except subprocess.CalledProcessError as e:
            # Check if it's an auth error
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

        return changed_files

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

    def _stage_agent_configs(self) -> None:
        """Stage agent configurations for commit."""
        from .agents import get_all_agents

        for agent in get_all_agents():
            # Skip if agent sync is disabled
            if not self.config.is_agent_enabled(agent.name):
                continue

            if not agent.is_available() and agent.name != "global-skills":
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
        Stage custom agents for commit.

        Structure in repo:
        - agents/<agent-name>/project/ - Project-level agents (.claude/agents/, .opencode/agents/)
        - agents/<agent-name>/global/ - Global agents (~/.claude/agents/, ~/.config/opencode/agents/)
        """
        from .agents import get_all_agents

        repo_agents_dir = self.repo_dir / "agents"

        # Ensure repo agents directory exists
        repo_agents_dir.mkdir(parents=True, exist_ok=True)

        for agent in get_all_agents():
            # Skip if agent sync is disabled
            if not self.config.is_agent_enabled(agent.name):
                continue

            # Skip if agent doesn't support custom agents
            if not agent.supports_custom_agents():
                continue

            # Check if agent is available OR if agents directory exists
            is_available = agent.is_available()
            has_agents_dir = (agent.agents_path and agent.agents_path.exists()) or \
                            (agent.agents_path_global and agent.agents_path_global.exists())

            if not is_available and not has_agents_dir and agent.name != "global-skills":
                continue

            agent_repo_dir = repo_agents_dir / agent.name

            # 1. Stage project-level agents (.claude/agents/, .opencode/agents/)
            if agent.agents_path and agent.agents_path.exists():
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

        global_skills_dir = Path.home() / ".agents" / "skills"
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

    def _stage_all_agent_files(self) -> None:
        """Stage all agent files for backup.

        Calls _stage_agent_configs() ONCE (it handles all agents internally)
        then iterates over enabled agents for additional file sync.
        """
        from .agents import get_all_agents

        # Stage configs once for ALL agents (avoids O(n2) redundant copies)
        self._stage_agent_configs()

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

    def _apply_synced_configs(self) -> list[str]:
        """Apply synced configurations to local agent directories."""
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

    def _apply_synced_skills(self) -> list[str]:
        """
        Apply synced skills to local directories.

        Uses manifest to:
        1. Restore extension skills to their original locations
        2. Restore symlinks
        3. Restore global skills to ~/.agents/skills/
        """
        changes = []
        synced_skills_dir = self.repo_dir / "skills"
        global_skills_dir = Path.home() / ".agents" / "skills"

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

            for skill_item in synced_skills_dir.glob("*"):
                if skill_item.name.startswith("."):
                    continue

                # Skip extension skills (they were restored above)
                if skill_item.name in extension_skill_names:
                    continue

                dest = global_skills_dir / skill_item.name
                if not dest.exists() or (skill_item.is_file() and self._same_content(dest, skill_item)):
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
        global_skills_dir = Path.home() / ".agents" / "skills"
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

    def _get_github_user(self) -> str:
        """Get current GitHub username."""
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
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
