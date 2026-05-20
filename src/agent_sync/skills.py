"""Skills management for agent-sync.

Centralizes skills from all agents to ~/.agents/skills/ (source of truth).
Automatically configures agents to use global skills.

Supports extension subdirectories (e.g., ~/.config/opencode/superpowers/skills/).
"""

import hashlib
import shutil
from pathlib import Path

from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from ._tui import print_footer
from .agents import BaseAgent, get_all_agents

console = Console()

GLOBAL_SKILLS_DIR = Path.home() / ".agents" / "skills"

MANIFEST_FILENAME = ".agent-sync-manifest.json"


class SkillsManager:
    """Manages skills centralization and distribution."""

    def __init__(self, global_skills_dir: Path | None = None):
        self.global_skills_dir = global_skills_dir or GLOBAL_SKILLS_DIR
        self.conflicts: list[dict] = []
        self.resolved_conflicts: dict[str, str] = {}
        self.extension_skills: dict[str, dict] = {}  # agent-extension -> info

    def _is_extension_symlink(self, symlink: Path, agent: BaseAgent) -> bool:
        """
        Check if symlink points to internal extension directory.

        Examples:
            superpowers: ~/.config/opencode/skills/superpowers → ../superpowers/skills/
            → Target resolves to ~/.config/opencode/superpowers/skills/
            → This is INSIDE agent config dir → PRESERVE

            User symlink: ~/.config/opencode/skills/my-skill → ~/.agents/skills/my-skill/
            → Target resolves to ~/.agents/skills/my-skill/
            → This is OUTSIDE agent config dir → REMOVE

        Args:
            symlink: Path to symlink
            agent: Agent object with config_dir

        Returns:
            True if symlink points to internal extension directory
        """
        try:
            # Resolve symlink target (follow the symlink)
            target = symlink.resolve()

            # Get agent's config directory (resolved to absolute path)
            config_dir = Path(agent.config_dir).expanduser().resolve()

            # Check if target is within agent's config directory
            # This will raise ValueError if target is not relative to config_dir
            target.relative_to(config_dir)
            return True  # Inside config dir = extension symlink, preserve
        except (ValueError, FileNotFoundError):
            return False  # Outside config dir = user symlink, remove

    def _scan_extension_subdirs(self, agent: BaseAgent) -> dict[str, dict]:
        """
        Scan for extension subdirectories with their own skills/.

        Example structure:
            ~/.config/opencode/superpowers/skills/
            ~/.config/opencode/my-extension/skills/

        Args:
            agent: Agent object to scan

        Returns:
            dict mapping "agent-extension" name to info dict with:
                - agent: agent name
                - extension: extension name
                - skills_dir: path to skills directory
                - symlink_path: path to symlink (if exists)
                - symlink_target: symlink target (if exists)
        """
        extension_skills = {}
        config_dir = Path(agent.config_dir).expanduser()

        if not config_dir.exists():
            return extension_skills

        for subdir in config_dir.iterdir():
            # Skip hidden dirs and main skills dir
            if subdir.name.startswith(".") or subdir.name == "skills":
                continue

            if not subdir.is_dir():
                continue

            # Check if subdir has its own skills/
            skills_dir = subdir / "skills"
            if not skills_dir.exists() or not skills_dir.is_dir():
                continue

            # Found extension skills!
            ext_name = f"{agent.name}-{subdir.name}"

            # Check if there's a symlink pointing to this skills dir
            symlink_path = agent.skills_path / subdir.name
            symlink_info = None

            if symlink_path.is_symlink():
                try:
                    symlink_target = symlink_path.readlink()
                    symlink_info = {
                        "from": str(symlink_path),
                        "to": str(symlink_target),
                    }
                except (OSError, ValueError):
                    pass

            extension_skills[ext_name] = {
                "agent": agent.name,
                "extension": subdir.name,
                "skills_dir": str(skills_dir),
                "symlink": symlink_info,
            }

        return extension_skills

    def _is_valid_skill(self, path: Path) -> bool:
        """Check if a directory is a valid skill (has SKILL.md or common skill files)."""
        if not path.is_dir():
            return False

        # Check for SKILL.md
        if (path / "SKILL.md").exists():
            return True

        # Check for common skill files
        if any(path.glob("*.md")) or any(path.glob("*.py")) or any(path.glob("*.sh")):
            return True

        return False

    @staticmethod
    def _compute_dir_hash(path: Path) -> str:
        """Compute recursive MD5 hash of a skill directory.

        Hashes all files in the directory (sorted by path for consistency).
        Returns empty string for empty directories.
        """
        if not path.is_dir():
            return ""

        hash_md5 = hashlib.md5(usedforsecurity=False)
        for file_path in sorted(path.rglob("*")):
            if file_path.is_file() and not file_path.name.startswith("."):
                rel = str(file_path.relative_to(path))
                hash_md5.update(rel.encode())
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hash_md5.update(chunk)

        return hash_md5.hexdigest()

    @staticmethod
    def _find_orphans(
        hub_skills: set[str],
        skills_found: dict,
    ) -> dict:
        """Find orphan skills (exist in agents but NOT in hub).

        Returns:
            dict of {skill_name: {
                "agents": [(agent_name, path), ...],
                "hash": str or None,
                "content_differs": bool
            }}
        """
        orphans: dict = {}

        for agent_name, skill_data in skills_found.items():
            if isinstance(skill_data, dict) and skill_data.get("is_extension"):
                continue
            skill_paths = skill_data if isinstance(skill_data, list) else skill_data.get("paths", [])

            for skill_path in skill_paths:
                skill_name = skill_path.name
                if skill_name not in hub_skills:
                    if skill_name not in orphans:
                        orphans[skill_name] = {"agents": [], "hash": None, "content_differs": False}
                    orphans[skill_name]["agents"].append((agent_name, skill_path))

        # Check content divergence
        for skill_name, info in orphans.items():
            if len(info["agents"]) > 1:
                hashes = set()
                for _, path in info["agents"]:
                    hashes.add(SkillsManager._compute_dir_hash(path))
                info["content_differs"] = len(hashes) > 1
                info["hash"] = hashes.pop() if len(hashes) == 1 else None

        return orphans


    def scan_all_agents(self) -> dict[str, list[Path]]:
        """Scan all agents for existing skills.

        Only directories containing SKILL.md are considered valid skills.
        Files directly in the skills directory are ignored.
        Symlinks created by users are detected for removal.
        Extension subdirectories (e.g., ~/.config/opencode/superpowers/skills/) are scanned separately.

        Returns:
            dict mapping agent name to list of skill paths
        """
        skills_found = {}
        self.extension_skills = {}  # Reset extension skills

        for agent in get_all_agents():
            if agent.name == "global-skills":
                continue

            agent_skills = []

            # Scan agent's skills directory
            if agent.skills_path.exists():
                for item in agent.skills_path.iterdir():
                    # Skip hidden files (.DS_Store, .git, etc.)
                    if item.name.startswith("."):
                        continue

                    # Detect symlinks - check if they're extension symlinks or user symlinks
                    if item.is_symlink():
                        # Check if this is an extension symlink (points inside agent config)
                        if self._is_extension_symlink(item, agent):
                            # This is an extension symlink, we'll handle it via extension scanning
                            # Don't add to agent_skills, but note it for manifest
                            pass
                        # User symlinks will be removed during centralize
                        continue

                    # Only sync directories (not files)
                    if item.is_dir():
                        # Check if it's a valid skill (has SKILL.md)
                        if self._is_valid_skill(item):
                            agent_skills.append(item)
                    # Ignore files directly in skills directory

            if agent_skills:
                skills_found[agent.name] = agent_skills

            # Scan extension subdirectories (e.g., ~/.config/opencode/superpowers/skills/)
            extension_skills = self._scan_extension_subdirs(agent)
            for ext_name, ext_info in extension_skills.items():
                self.extension_skills[ext_name] = ext_info

                # Also add extension skills to skills_found
                skills_dir = Path(ext_info["skills_dir"])
                ext_skill_paths = []

                for skill_item in skills_dir.iterdir():
                    if skill_item.name.startswith(".") or skill_item.is_symlink():
                        continue
                    if skill_item.is_dir() and self._is_valid_skill(skill_item):
                        ext_skill_paths.append(skill_item)

                if ext_skill_paths:
                    # Mark extension skills with special key to skip during centralize
                    # They should only be backed up via symlinks, not centralized
                    skills_found[ext_name] = {
                        "paths": ext_skill_paths,
                        "is_extension": True,  # Flag to skip centralization
                    }

        return skills_found

    def find_conflicts(self, skills: dict[str, list[Path] | dict]) -> list[dict]:
        """Find skills with same name across different agents.

        Args:
            skills: Dict mapping agent/extension name to either:
                - list[Path]: Regular skills
                - dict: Extension skills with {"paths": [...], "is_extension": True}

        Returns:
            list of conflict dicts with 'name', 'agents', 'paths'
        """
        name_to_agents: dict[str, list[tuple[str, Path]]] = {}

        for agent_name, skill_data in skills.items():
            # Handle both old format (list) and new format (dict with "paths")
            if isinstance(skill_data, dict):
                skill_paths = skill_data.get("paths", [])
            else:
                skill_paths = skill_data

            for skill_path in skill_paths:
                skill_name = skill_path.stem if skill_path.is_file() else skill_path.name

                if skill_name not in name_to_agents:
                    name_to_agents[skill_name] = []

                name_to_agents[skill_name].append((agent_name, skill_path))

        conflicts = []
        for skill_name, agent_paths in name_to_agents.items():
            if len(agent_paths) > 1:
                conflicts.append(
                    {
                        "name": skill_name,
                        "agents": [ap[0] for ap in agent_paths],
                        "paths": [ap[1] for ap in agent_paths],
                    }
                )

        self.conflicts = conflicts
        return conflicts

    def _sync_from_repo(self) -> int:
        """Sync skills from git repo to global skills directory.

        Returns:
            Number of skills synced from repo
        """
        from .sync import SyncManager

        repo_skills_dir = SyncManager.DEFAULT_REPO_DIR / "skills"

        if not repo_skills_dir.exists():
            return 0

        synced = 0
        for skill_dir in repo_skills_dir.iterdir():
            if skill_dir.name.startswith("."):
                continue

            dest = self.global_skills_dir / skill_dir.name
            if not dest.exists():
                if skill_dir.is_dir():
                    shutil.copytree(skill_dir, dest)
                    synced += 1

        return synced

    @staticmethod
    def _pick_best_source(info: dict) -> tuple[str | None, Path | None]:
        """Pick the best source for an orphan skill.

        If content differs across agents, pick the newest by mtime.
        Otherwise pick the first agent's copy.

        Returns: (agent_name, path) or (None, None) if no valid source
        """
        agents = info.get("agents", [])
        if not agents:
            return None, None

        # If only one agent, use it
        if len(agents) == 1:
            return agents[0]

        # If content is same, use first
        if not info.get("content_differs"):
            return agents[0]

        # Pick newest by mtime
        best_agent, best_path = None, None
        best_mtime = 0

        for agent_name, path in agents:
            try:
                if path.is_dir():
                    # Use newest file in the directory
                    files = list(path.rglob("*"))
                    if files:
                        mtime = max(f.stat().st_mtime for f in files if f.is_file())
                elif path.is_file():
                    mtime = path.stat().st_mtime
                else:
                    continue

                if mtime > best_mtime:
                    best_mtime = mtime
                    best_agent, best_path = agent_name, path
            except OSError:
                continue

        return best_agent, best_path

    def centralize(
        self,
        dry_run: bool = False,
        move: bool = True,
    ) -> dict:
        """Centralize all skills into ~/.agents/skills/.

        Pipeline (no interaction needed):
          Phase 1: Scan agents
          Phase 2: Sync from repo → hub (authoritative)
          Phase 3: Find orphans → in agents but not in hub
          Phase 4: Auto-import orphans → hub (pick newest if diverge)
          Phase 5: Configure all agents to use hub
          Phase 6: Clean up user symlinks

        Args:
            dry_run: Preview without modifying anything
            move: Move (delete from agents) vs copy (keep originals)

        Returns:
            dict with stats: moved, copied, skipped, errors, orphans_found,
                           orphans_imported, diverge_warnings
        """
        stats = {
            "moved": 0,
            "copied": 0,
            "skipped": 0,
            "errors": 0,
            "symlinks_removed": 0,
            "orphans_found": 0,
            "orphans_imported": 0,
            "diverge_warnings": 0,
        }

        if not dry_run:
            self.global_skills_dir.mkdir(parents=True, exist_ok=True)

        # ─────────────────────────────────────────────────────────────────────
        # Phase 1: Scan agents
        # ─────────────────────────────────────────────────────────────────────
        console.print("\n[bold]📚 Scanning agents for skills...[/]\n")
        skills_found = self.scan_all_agents()

        if not skills_found:
            console.print("[yellow]No skills found in agent directories.[/yellow]\n")
        else:
            for agent_name, skill_data in sorted(skills_found.items()):
                if isinstance(skill_data, dict):
                    paths = skill_data.get("paths", [])
                    is_ext = skill_data.get("is_extension", False)
                else:
                    paths = skill_data
                    is_ext = False
                suffix = " [dim](extension)[/dim]" if is_ext else ""
                console.print(f"  • {agent_name}: [green]{len(paths)}[/green] skills{suffix}")
        console.print()

        # ─────────────────────────────────────────────────────────────────────
        # Phase 1b: Show hub status
        # ─────────────────────────────────────────────────────────────────────
        hub_skills = set()
        if self.global_skills_dir.exists():
            hub_skills = {
                item.name for item in self.global_skills_dir.iterdir()
                if not item.name.startswith(".")
            }

        console.print("[bold]📦 Skills Hub Status (~/.agents/skills/):[/]\n")
        if hub_skills:
            console.print(f"  [green]✓ {len(hub_skills)} skills centralized[/green]")
            console.print("  [dim]Skills:[/dim]")
            for skill_name in sorted(hub_skills):
                console.print(f"    • {skill_name}")
        else:
            console.print("  [yellow]⚠ No skills in hub[/yellow]")
            console.print("  [dim]Skills will be imported from agents[/dim]")
        console.print()

        # ─────────────────────────────────────────────────────────────────────
        # Phase 2: Sync from repo → hub (authoritative source)
        # ─────────────────────────────────────────────────────────────────────
        console.print("[bold]📥 Syncing skills from repo to ~/.agents/skills/...[/]\n")
        repo_synced = self._sync_from_repo()
        if repo_synced > 0:
            console.print(f"  [green]✓ Synced {repo_synced} skills from repo[/green]\n")
        else:
            console.print("  [dim]Nothing to sync from repo[/dim]\n")

        # ─────────────────────────────────────────────────────────────────────
        # Phase 3: Find orphans
        # ─────────────────────────────────────────────────────────────────────
        orphans = self._find_orphans(hub_skills, skills_found)
        stats["orphans_found"] = len(orphans)

        if not orphans:
            console.print("[green]✓ All skills are centralized.[/green]\n")
        else:
            console.print(f"[bold]Found [cyan]{len(orphans)}[/] orphan skill(s)[/]:\n")
            for name, info in sorted(orphans.items()):
                agents_str = ", ".join(a for a, _ in info["agents"])
                diverge = " [yellow]⚠ diverge[/yellow]" if info.get("content_differs") else ""
                console.print(f"  • {name} [dim]({agents_str})[/dim]{diverge}")
            console.print()

        # ─────────────────────────────────────────────────────────────────────
        # Phase 4: Auto-import orphans to hub
        # ─────────────────────────────────────────────────────────────────────
        if orphans:
            action = "Moving" if move else "Copying"
            console.print(f"[bold]{action} orphan skills to hub...[/]\n")

            for skill_name in sorted(orphans.keys()):
                info = orphans[skill_name]
                dest_path = self.global_skills_dir / skill_name

                # Skip if already in hub (repo version is authoritative)
                if dest_path.exists():
                    stats["skipped"] += 1
                    continue

                # Pick best source (newest by mtime if diverge)
                source_agent, source_path = self._pick_best_source(info)
                if source_agent is None:
                    stats["errors"] += 1
                    console.print(f"  [red]✗[/] {skill_name} - no valid source found")
                    continue

                if info.get("content_differs"):
                    console.print(f"  [yellow]⚠[/] {skill_name} [dim](content differs — used {source_agent})[/]")
                    stats["diverge_warnings"] += 1

                try:
                    if not dry_run:
                        if source_path.is_dir():
                            if move:
                                shutil.move(str(source_path), str(dest_path))
                            else:
                                shutil.copytree(source_path, dest_path)
                        else:
                            if move:
                                shutil.move(str(source_path), str(dest_path))
                            else:
                                shutil.copy2(source_path, dest_path)

                        # Clean up empty source dir
                        if move and source_path.is_dir():
                            try:
                                source_path.parent.rmdir()
                            except OSError:
                                pass

                    if move:
                        stats["moved"] += 1
                        console.print(f"  [green]✓[/] {skill_name} [dim](moved from {source_agent})[/]")
                    else:
                        stats["copied"] += 1
                        console.print(f"  [green]✓[/] {skill_name} [dim](copied from {source_agent})[/]")
                    stats["orphans_imported"] += 1

                except Exception as e:
                    stats["errors"] += 1
                    console.print(f"  [red]✗[/] {skill_name} - {e}")

            console.print()

        # ─────────────────────────────────────────────────────────────────────
        # Phase 5: Configure all agents to use hub
        # ─────────────────────────────────────────────────────────────────────
        console.print("[bold]⚙️  Configuring agents to use ~/.agents/skills/...[/]\n")
        self.configure_agents()

        # ─────────────────────────────────────────────────────────────────────
        # Phase 6: Clean up user symlinks
        # ─────────────────────────────────────────────────────────────────────
        console.print("[bold]🧹 Cleaning up user symlinks...[/]\n")
        stats["symlinks_removed"] = self._cleanup_user_symlinks()
        if stats["symlinks_removed"] > 0:
            console.print(f"  [yellow]Removed {stats['symlinks_removed']} symlinks[/yellow]\n")
        else:
            console.print("  [dim]No user symlinks to clean[/dim]\n")

        # ─────────────────────────────────────────────────────────────────────
        # Summary
        # ─────────────────────────────────────────────────────────────────────
        console.print("[bold]📊 Summary:[/]\n")
        if move:
            console.print(f"  [green]✓ Moved {stats['moved']} skills[/green] to hub")
        else:
            console.print(f"  [green]✓ Copied {stats['copied']} skills[/green] to hub")
        if stats["orphans_imported"] > 0:
            console.print(f"  [cyan]📦 Imported {stats['orphans_imported']} orphan(s)[/cyan]")
        if stats["skipped"] > 0:
            console.print(f"  [dim]  {stats['skipped']} already in hub[/dim]")
        if stats["diverge_warnings"] > 0:
            console.print(f"  [yellow]⚠ {stats['diverge_warnings']} had content conflicts[/yellow]")
        if stats["errors"] > 0:
            console.print(f"  [red]✗ {stats['errors']} errors[/red]")
        console.print()

        return stats


    def _cleanup_user_symlinks(self, preserve_extension_symlinks: bool = True) -> int:
        """
        Remove user-created symlinks from agent skill directories.

        Extension symlinks (pointing to internal subdirectories) are preserved.
        User symlinks (pointing to ~/.agents/skills/) are removed.

        Args:
            preserve_extension_symlinks: If True, keep symlinks pointing to internal
                                         extension directories (default: True)

        Returns:
            Number of symlinks removed
        """
        symlinks_removed = 0
        symlinks_preserved = []

        for agent in get_all_agents():
            if agent.name == "global-skills":
                continue

            if not agent.skills_path.exists():
                continue

            for item in agent.skills_path.iterdir():
                if item.is_symlink():
                    # Check if this is an extension symlink
                    if preserve_extension_symlinks and self._is_extension_symlink(item, agent):
                        try:
                            target = item.readlink()
                            resolved_target = (item.parent / target).resolve()
                            # Get agent config dir for display
                            config_dir = Path(agent.config_dir).expanduser().resolve()
                            is_inside = str(resolved_target).startswith(str(config_dir))
                            
                            if is_inside:
                                # This is an extension symlink - preserve and show details
                                ext_name = item.name
                                ext_path = resolved_target
                                symlinks_preserved.append({
                                    "agent": agent.name,
                                    "symlink": str(item),
                                    "target": str(ext_path),
                                    "extension": ext_name,
                                })
                                console.print(
                                    f"  [dim]🔗 Preserving extension symlink: {agent.name}/{item.name}[/dim]"
                                )
                                console.print(
                                    f"     [dim]└─ {item} → {ext_path}[/dim]"
                                )
                            else:
                                # Points outside config dir - remove
                                item.unlink()
                                symlinks_removed += 1
                                console.print(
                                    f"  [yellow]Removed external symlink: {agent.name}/{item.name}[/yellow]"
                                )
                        except (OSError, ValueError):
                            symlinks_preserved.append({
                                "agent": agent.name,
                                "symlink": str(item),
                                "target": "(unresolved)",
                                "extension": item.name,
                            })
                        continue

                    # User symlink - remove
                    try:
                        target = item.readlink()
                        item.unlink()
                        symlinks_removed += 1
                        console.print(
                            f"  [yellow]Removed user symlink: {agent.name}/{item.name}[/yellow]"
                        )
                        console.print(f"     [dim]└─ pointed to {target}[/dim]")
                    except Exception as e:
                        console.print(
                            f"  [red]Failed to remove symlink {agent.name}/{item.name}: {e}[/red]"
                        )

        if symlinks_preserved:
            console.print()
            console.print(f"  [green]✓ Preserved {len(symlinks_preserved)} extension symlink(s):[/green]")
            for info in symlinks_preserved:
                console.print(
                    f"    [dim]• {info['agent']}/{info['extension']}:[/dim]"
                )
                console.print(
                    f"      [dim]  {info['symlink']}[/dim]"
                )
                console.print(
                    f"      [dim]  → {info['target']}[/dim]"
                )

        return symlinks_removed

    def configure_agents(self) -> dict[str, dict]:
        """Configure all agents to use global skills."""
        results = {}

        console.print("\n[bold]Configuring agents to use global skills...[/]\n")

        for agent in get_all_agents():
            if agent.name == "global-skills":
                continue

            result = self._configure_agent(agent)
            results[agent.name] = result

            status_icon = "✓" if result["success"] else "⚠"
            status_color = "green" if result["success"] else "yellow"
            console.print(
                f"  [{status_color}]{status_icon}[/{status_color}] {agent.name}: {result['message']} [dim]({result['method']})[/dim]"
            )

        console.print()
        return results

    def _configure_agent(self, agent: BaseAgent) -> dict:
        """Configure a single agent to use global skills.

        New order (per plan):
        1. User override (from config.yaml)
        2. YAML Registry default (agent.method)
        3. Implementation (native | config | copy)
        """
        from .config import Config
        user_config = Config()

        # Determine method (priority: user override -> registry default)
        agent_conf = user_config.get_agent_config(agent.name)
        method = agent_conf.get("skills_method") or agent.method

        # NOTE: Cleanup is now managed by the centralize() pipeline,
    

        # Apply the chosen method
        result = None
        if method == "native":
            result = {
                "success": True,
                "method": "native",
                "message": f"Reads from {self.global_skills_dir} (native support)",
            }

        elif method == "config":
            try:
                self._apply_config_method(agent)
                result = {
                    "success": True,
                    "method": "config",
                    "message": "Updated agent config to include global skills",
                }
            except Exception as e:
                # Fallback to copy if config failed and it's not a user override
                if agent_conf.get("skills_method"):
                     return {"success": False, "method": "config", "message": f"Config update failed: {e}"}
                # Else continue to copy fallback

        if not result:
            # Default fallback (copy) or explicit copy
            # IMPORTANT: Only copy if agent directory already exists - don't create new ones
            if agent.skills_path.exists():
                try:
                    copied = self._copy_skills_to_agent(agent)
                    result = {
                        "success": True,
                        "method": "copy",
                        "message": f"Copied {copied} skills to {agent.skills_path}",
                    }
                except Exception as e:
                    result = {
                        "success": False,
                        "method": "copy",
                        "message": f"Copy failed: {e}",
                    }
            else:
                # Agent directory doesn't exist - skip copy, don't create
                result = {
                    "success": True,
                    "method": "skip",
                    "message": f"Agent directory doesn't exist (not installed): {agent.skills_path}",
                }

        # Save successful method to config if not already there
        if result["success"] and not agent_conf.get("skills_method"):
            user_config.set_skills_method(agent.name, result["method"])

        return result

    def _apply_config_method(self, agent: BaseAgent) -> None:
        """Apply config method dynamically using registry data."""
        config_update = agent.data.get("config_update")
        if not config_update:
            # Fallback for old opencode style if not in registry
            if agent.name == "opencode":
                config_update = {"path": "skills.paths", "action": "append"}
            else:
                raise ValueError(f"Agent {agent.name} has method 'config' but no config_update defined")

        config = agent.get_config() or {}
        path = config_update.get("path", "")
        action = config_update.get("action", "set")
        value = str(self.global_skills_dir)

        # Navigate and update nested dict
        parts = path.split(".")
        curr = config
        for part in parts[:-1]:
            if part not in curr or not isinstance(curr[part], dict):
                curr[part] = {}
            curr = curr[part]

        last_part = parts[-1]
        if action == "append":
            if last_part not in curr or not isinstance(curr[last_part], list):
                curr[last_part] = []
            if value not in curr[last_part]:
                curr[last_part].append(value)
        else:
            curr[last_part] = value

        agent.save_config(config)

    def _cleanup_agent_local_skills(self, agent: BaseAgent) -> int:
        """Remove all local skills from agent directory (centralized approach).

        After centralize(), all skills live in ~/.agents/skills/.
        Agent directories should only have symlinks or config pointing to it.

        Returns:
            Number of skills removed
        """
        if not agent.skills_path.exists():
            return 0

        removed_count = 0

        for item in agent.skills_path.iterdir():
            # Skip symlinks (like _global in claude-code)
            if item.is_symlink():
                continue

            # Remove skill directories
            if item.is_dir() and (item / "SKILL.md").exists():
                shutil.rmtree(item)
                removed_count += 1
            # Remove skill files
            elif item.is_file() and item.suffix in [".md", ".py", ".sh"]:
                item.unlink()
                removed_count += 1

        return removed_count

    def _copy_skills_to_agent(self, agent: BaseAgent) -> int:
        """Copy all skills from global dir to agent skills directory.

        IMPORTANT: This method assumes agent.skills_path already exists.
        It will NOT create the directory - that check is done in _configure_agent.
        """
        if not self.global_skills_dir.exists():
            return 0

        # Skip if the paths are actually the same (native support or same dir)
        if self.global_skills_dir.resolve() == agent.skills_path.resolve():
            return 0

        # Directory should already exist - don't create it
        copied = 0

        for skill_dir in self.global_skills_dir.iterdir():
            if skill_dir.name.startswith("."):
                continue

            dest = agent.skills_path / skill_dir.name

            # Skip if already exists (don't overwrite)
            if dest.exists():
                continue

            if skill_dir.is_dir():
                shutil.copytree(skill_dir, dest)
                copied += 1

        return copied

    def get_summary(self) -> dict:
        """Get summary of skills configuration."""
        skill_count = 0

        if self.global_skills_dir.exists():
            for item in self.global_skills_dir.iterdir():
                # Count only valid skills (directories with SKILL.md)
                if item.is_dir() and (item / "SKILL.md").exists():
                    skill_count += 1

        return {
            "global_skills_dir": str(self.global_skills_dir),
            "exists": self.global_skills_dir.exists(),
            "skill_count": skill_count,
        }

    def distribute_to_all_agents(self) -> dict:
        """Copy all skills from ~/.agents/skills/ to all agent directories.

        This is useful for:
        - Backup: local copies in each agent directory
        - Testing: verify agents read from local vs global
        - Debug: troubleshoot symlink/config issues

        Returns:
            dict with 'distributed' count and 'agents_configured' count
        """
        import hashlib

        stats = {
            "distributed": 0,
            "agents_configured": 0,
            "skipped": 0,
        }

        if not self.global_skills_dir.exists():
            console.print("[yellow]No skills found in ~/.agents/skills/[/yellow]\n")
            return stats

        console.print(f"Source: [cyan]{self.global_skills_dir}[/cyan]\n")

        for agent in get_all_agents():
            if agent.name == "global-skills":
                continue

            console.print(f"  Distributing to {agent.name}...")

            # Ensure agent skills directory exists
            agent.skills_path.mkdir(parents=True, exist_ok=True)

            agent_count = 0
            for skill_item in self.global_skills_dir.iterdir():
                if skill_item.name.startswith("."):
                    continue  # Skip .DS_Store, etc.

                dest = agent.skills_path / skill_item.name

                if not dest.exists():
                    # Copy if doesn't exist
                    if skill_item.is_dir():
                        shutil.copytree(skill_item, dest)
                    else:
                        shutil.copy2(skill_item, dest)
                    agent_count += 1
                    stats["distributed"] += 1
                else:
                    # Check if different (idempotent)
                    if skill_item.is_file() and dest.is_file():
                        src_hash = hashlib.md5(skill_item.read_bytes()).hexdigest()
                        dest_hash = hashlib.md5(dest.read_bytes()).hexdigest()

                        if src_hash != dest_hash:
                            # Files differ, skip to avoid overwriting local changes
                            console.print(
                                f"    [yellow]⚠ {skill_item.name} differs, skipping[/yellow]"
                            )
                        else:
                            stats["skipped"] += 1
                    else:
                        stats["skipped"] += 1

            if agent_count > 0:
                console.print(f"    [green]✓ {agent_count} skills copied[/green]")
                stats["agents_configured"] += 1
            else:
                console.print("    [dim]No new skills to copy[/dim]")

        console.print()
        return stats
