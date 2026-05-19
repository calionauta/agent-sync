"""Tests for discovery module."""

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from agent_sync.publish.discovery import (
    discover_skills_sources,
    skills_to_source_infos,
    build_initial_selection,
    discover_agents_sources,
    discover_all_sources,
    load_saved_selection,
    _truncate_url,
    get_source_label,
)
from agent_sync.publish.models import SourceInfo


class TestTruncateUrl:
    """Tests for _truncate_url helper."""

    def test_short_url_unchanged(self):
        """Short URLs are unchanged."""
        result = _truncate_url("short", 40)
        assert result == "short"

    def test_long_url_truncated(self):
        """Long URLs are truncated with ellipsis."""
        url = "https://github.com/owner/very-long-repository-name"
        result = _truncate_url(url, 30)
        assert "..." in result or len(result) < len(url)

    def test_local_unchanged(self):
        """'local' returns unchanged."""
        result = _truncate_url("local", 40)
        assert result == "local"

    def test_empty_url_unchanged(self):
        """Empty URL returns unchanged."""
        result = _truncate_url("", 40)
        assert result == ""


class TestGetSourceLabel:
    """Tests for get_source_label."""

    def test_local_label(self):
        """Local source has LOCAL label."""
        assert get_source_label("local") == "LOCAL"

    def test_agents_label(self):
        """Agents source has AGENTS label."""
        assert get_source_label("agents") == "AGENTS"

    def test_external_label(self):
        """External source has truncated repo name."""
        label = get_source_label("owner/my-repo")
        assert len(label) <= 6

    def test_short_label(self):
        """Short source IDs are truncated."""
        label = get_source_label("x")
        assert len(label) <= 6


class TestDiscoverSkillsSources:
    """Tests for discover_skills_sources."""

    def test_includes_local(self):
        """Always includes local source."""
        mock_config = MagicMock()
        mock_config.skill_sources = []
        mock_config.cache_dir = Path("/tmp")
        
        with patch("agent_sync.publish.discovery.discover_local_skills", return_value=[]):
            sources = discover_skills_sources(mock_config)
        
        assert any(s.source_id == "local" for s in sources)

    def test_local_skills_added(self):
        """Local skills are added to source."""
        mock_config = MagicMock()
        mock_config.skill_sources = []
        mock_config.cache_dir = Path("/tmp")
        
        mock_skill = MagicMock()
        mock_skill.name = "test-skill"
        
        with patch("agent_sync.publish.discovery.discover_local_skills", return_value=[mock_skill]):
            sources = discover_skills_sources(mock_config)
        
        local_source = next(s for s in sources if s.source_id == "local")
        assert len(local_source.skills) == 1


class TestSkillsToSourceInfos:
    """Tests for skills_to_source_infos."""

    def test_converts_local_source(self):
        """Converts local source correctly."""
        from agent_sync.publish.base import SourceWithSkills, SourceStatus
        
        mock_skill = MagicMock()
        mock_skill.name = "test-skill"
        
        mock_source = SourceWithSkills(
            source_id="local",
            source_url="local",
            status=SourceStatus.ACTIVE,
            skills=[mock_skill],
            is_local=True,
        )
        
        infos = skills_to_source_infos([mock_source])
        
        assert len(infos) == 1
        assert infos[0].source_id == "local"
        assert infos[0].label == "LOCAL"
        assert "test-skill" in infos[0].items

    def test_converts_external_source(self):
        """Converts external source correctly."""
        from agent_sync.publish.base import SourceWithSkills, SourceStatus
        
        mock_skill = MagicMock()
        mock_skill.name = "ext-skill"
        
        mock_source = SourceWithSkills(
            source_id="owner/repo",
            source_url="https://github.com/owner/repo",
            status=SourceStatus.ACTIVE,
            skills=[mock_skill],
            is_local=False,
            staleness="2 days",
        )
        
        infos = skills_to_source_infos([mock_source])
        
        assert len(infos) == 1
        assert infos[0].source_id == "owner/repo"
        assert "github.com" in infos[0].subtitle
        assert infos[0].extra == "2 days"


class TestDiscoverAgentsSources:
    """Tests for discover_agents_sources."""

    def test_returns_empty_when_no_agents(self):
        """Returns empty list when no agents."""
        with patch("agent_sync.publish.discovery.discover_local_agents", return_value=[]):
            result = discover_agents_sources()
        
        assert result == []

    def test_returns_agents_source(self):
        """Returns agents source when agents exist."""
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        
        with patch("agent_sync.publish.discovery.discover_local_agents", return_value=[mock_agent]):
            result = discover_agents_sources()
        
        assert len(result) == 1
        assert result[0].source_id == "agents"
        assert "test-agent" in result[0].items


class TestDiscoverAllSources:
    """Tests for discover_all_sources."""

    def test_returns_tuple(self):
        """Returns tuple of sources."""
        mock_config = MagicMock()
        mock_config.skill_sources = []
        mock_config.cache_dir = Path("/tmp")
        
        with patch("agent_sync.publish.discovery.load_config", return_value=mock_config):
            with patch("agent_sync.publish.discovery.discover_local_skills", return_value=[]):
                with patch("agent_sync.publish.discovery.discover_local_agents", return_value=[]):
                    result = discover_all_sources()
        
        assert isinstance(result, tuple)
        assert len(result) == 3


class TestLoadSavedSelection:
    """Tests for load_saved_selection."""

    def test_empty_when_no_saved_state(self):
        """Returns empty selection when no saved state."""
        mock_state = MagicMock()
        mock_state.skills = {}
        mock_state.agents = {}
        
        with patch("agent_sync.publish.discovery.PublishStateManager.load", return_value=mock_state):
            sources = [MagicMock(source_id="local")]
            result = load_saved_selection(sources)
        
        assert result == {"local": set()}

    def test_restores_saved_selection(self):
        """Restores saved selection."""
        mock_state = MagicMock()
        mock_state.skills = {"local": ["a", "b"]}
        mock_state.agents = {"agents": ["test-agent"]}
        
        with patch("agent_sync.publish.discovery.PublishStateManager.load", return_value=mock_state):
            sources = [
                MagicMock(source_id="local"),
                MagicMock(source_id="agents"),
            ]
            result = load_saved_selection(sources)
        
        assert result["local"] == {"a", "b"}
        assert result["agents"] == {"test-agent"}