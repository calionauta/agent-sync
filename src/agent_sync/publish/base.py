from __future__ import annotations

"""Base types for skill sources."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SourceStatus(Enum):
    """Status of a skill source."""

    ACTIVE = "active"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


@dataclass
class SkillSource:
    """Represents a discovered skill.

    Attributes:
        name: Skill name (e.g., "cali-shape-up")
        path: Local path to the skill directory
        source_type: "local" or "external"
        source_url: GitHub URL for external, "local" for local
        source_id: Normalized ID (e.g., "calionauta/repo" or "local")
    """

    name: str
    path: Path
    source_type: str  # "local" or "external"
    source_url: str
    source_id: str

    @property
    def display_name(self) -> str:
        """Full display name with source prefix for external skills."""
        if self.source_type == "external":
            return f"{self.source_id}/{self.name}"
        return self.name

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "name": self.name,
            "path": str(self.path),
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_id": self.source_id,
        }


@dataclass
class SourceConfig:
    """Configuration for a skill source.

    Attributes:
        url: GitHub repository URL
        status: Current status (active/failed/skipped)
        last_success: ISO date string of last successful discovery
        cache_ttl_hours: How long to cache before refresh
    """

    url: str
    status: SourceStatus = SourceStatus.UNKNOWN
    last_success: str | None = None
    cache_ttl_hours: int = 24

    @property
    def repo_id(self) -> str:
        """Extract owner/repo from URL."""
        # Normalizes github.com/owner/repo -> owner/repo
        url = self.url.replace("https://github.com/", "").replace("http://github.com/", "")
        url = url.replace("git@github.com:", "").replace(".git", "").rstrip("/")
        return url

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "url": self.url,
            "status": self.status.value,
            "last_success": self.last_success,
            "cache_ttl_hours": self.cache_ttl_hours,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SourceConfig:
        """Create from dict."""
        return cls(
            url=data["url"],
            status=SourceStatus(data.get("status", "unknown")),
            last_success=data.get("last_success"),
            cache_ttl_hours=data.get("cache_ttl_hours", 24),
        )


@dataclass
class SourceWithSkills:
    """A source with its discovered skills (for internal use in publish)."""

    source_id: str
    source_url: str
    status: SourceStatus
    skills: list
    is_local: bool = False
    staleness: str | None = None

    @property
    def label(self) -> str:
        """Get display label for this source.

        Shows full repo name for external sources, not truncated.
        """
        if self.source_id == "local":
            return "LOCAL"
        if self.source_id == "agents":
            return "AGENTS"
        # External: owner/repo -> show full name
        parts = self.source_id.split("/")
        if len(parts) >= 2:
            return parts[1]  # Show full repo name
        return self.source_id


@dataclass
class PublishConfig:
    """Root configuration for the publish feature.

    Attributes:
        published_repo: Target repo for publishing skills
        skill_sources: List of external source configurations
        selected_skills: Mapping of source_id to selected skill names
        cache_dir: Directory for caching cloned repos
        cache_ttl_hours: Default TTL for cache
        auto_push_private: If True (default), `publish run` also syncs the
            full local state to the private repo (config.repo_url) after
            publishing the curated subset to the public repo. Disable with
            `agent-sync publish --no-private` or set this field to False.
    """

    published_repo: str
    skill_sources: list[SourceConfig] = field(default_factory=list)
    selected_skills: dict[str, list[str]] = field(default_factory=dict)
    cache_dir: Path = Path.home() / ".cache" / "agent-sync" / "repos"
    cache_ttl_hours: int = 24
    auto_push_private: bool = True

    def get_skills_for_source(self, source_id: str) -> list[str]:
        """Get selected skills for a source."""
        return self.selected_skills.get(source_id, [])

    def set_skills_for_source(self, source_id: str, skills: list[str]) -> None:
        """Set selected skills for a source."""
        self.selected_skills[source_id] = skills

    def add_source(self, url: str) -> SourceConfig:
        """Add a new source."""
        source = SourceConfig(url=url)
        self.skill_sources.append(source)
        return source

    def remove_source(self, url: str) -> bool:
        """Remove a source by URL. Returns True if removed."""
        for i, source in enumerate(self.skill_sources):
            if source.url == url:
                self.skill_sources.pop(i)
                # Also remove from selected_skills
                repo_id = source.repo_id
                if repo_id in self.selected_skills:
                    del self.selected_skills[repo_id]
                return True
        return False

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "published_repo": self.published_repo,
            "skill_sources": [s.to_dict() for s in self.skill_sources],
            "selected_skills": self.selected_skills,
            "cache_dir": str(self.cache_dir),
            "cache_ttl_hours": self.cache_ttl_hours,
            "auto_push_private": self.auto_push_private,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PublishConfig:
        """Create from dict."""
        cache_dir = data.get("cache_dir")
        if cache_dir:
            cache_dir = Path(cache_dir)
        else:
            cache_dir = Path.home() / ".cache" / "agent-sync" / "repos"

        return cls(
            published_repo=data.get("published_repo", ""),
            skill_sources=[SourceConfig.from_dict(s) for s in data.get("skill_sources", [])],
            selected_skills=data.get("selected_skills", {}),
            cache_dir=cache_dir,
            cache_ttl_hours=data.get("cache_ttl_hours", 24),
            auto_push_private=data.get("auto_push_private", True),
        )
