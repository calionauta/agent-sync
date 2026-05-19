"""Tests for PublishStateManager."""

import tempfile
from pathlib import Path

import pytest

from agent_sync.publish.config import PublishState, PublishStateManager


class TestPublishState:
    """Tests for PublishState dataclass."""

    def test_creates_empty_state(self):
        """Empty state has no selections."""
        state = PublishState()
        assert state.get_total_count() == 0
        assert state.is_empty()
        assert state.timestamp is None

    def test_counts_skills(self):
        """Counts skills correctly."""
        state = PublishState(
            skills={"local": ["a", "b"], "ext": ["c"]},
        )
        assert state.get_skills_count() == 3

    def test_counts_agents(self):
        """Counts agents correctly."""
        state = PublishState(
            agents={"agents": ["opencode", "pi.dev"]},
        )
        assert state.get_agents_count() == 2

    def test_counts_total(self):
        """Counts total items."""
        state = PublishState(
            skills={"local": ["a"]},
            agents={"agents": ["b", "c"]},
        )
        assert state.get_total_count() == 3

    def test_get_all_source_ids(self):
        """Gets all source IDs."""
        state = PublishState(
            skills={"local": ["a"], "ext": ["b"]},
            agents={"agents": ["c"]},
        )
        source_ids = state.get_all_source_ids()
        assert source_ids == {"local", "ext", "agents"}

    def test_to_dict(self):
        """Serializes to dict."""
        state = PublishState(
            timestamp="2026-05-19T20:00:00",
            skills={"local": ["a"]},
            agents={"agents": ["b"]},
        )
        d = state.to_dict()
        assert d["timestamp"] == "2026-05-19T20:00:00"
        assert d["skills"] == {"local": ["a"]}
        assert d["agents"] == {"agents": ["b"]}

    def test_from_dict(self):
        """Deserializes from dict."""
        data = {
            "timestamp": "2026-05-19T20:00:00",
            "skills": {"local": ["a"]},
            "agents": {"agents": ["b"]},
        }
        state = PublishState.from_dict(data)
        assert state.timestamp == "2026-05-19T20:00:00"
        assert state.skills == {"local": ["a"]}
        assert state.agents == {"agents": ["b"]}

    def test_from_dict_empty(self):
        """Handles empty dict."""
        state = PublishState.from_dict(None)
        assert state.get_total_count() == 0

    def test_from_dict_partial(self):
        """Handles partial data."""
        data = {"skills": {"local": ["a"]}}
        state = PublishState.from_dict(data)
        assert state.skills == {"local": ["a"]}
        assert state.agents == {}


class TestPublishStateManager:
    """Tests for PublishStateManager (using temp config)."""

    @pytest.fixture
    def temp_config_path(self, tmp_path):
        """Create a temp config file."""
        config_file = tmp_path / "publish.yaml"
        return config_file

    def test_load_empty_when_no_config(self, tmp_path, monkeypatch):
        """Loads empty state when no config exists."""
        # Mock CONFIG_PATH
        config_path = tmp_path / "publish.yaml"
        monkeypatch.setattr(
            "agent_sync.publish.config.CONFIG_PATH",
            config_path,
        )
        
        state = PublishStateManager.load()
        assert state.is_empty()

    def test_save_and_load(self, tmp_path, monkeypatch):
        """Saves and loads state correctly."""
        config_path = tmp_path / "publish.yaml"
        monkeypatch.setattr(
            "agent_sync.publish.config.CONFIG_PATH",
            config_path,
        )
        
        skills = {"local": ["a", "b"], "ext": ["c"]}
        agents = {"agents": ["opencode"]}
        
        PublishStateManager.save(skills, agents)
        
        state = PublishStateManager.load()
        assert state.skills == skills
        assert state.agents == agents
        assert state.timestamp is not None

    def test_save_overwrites_previous(self, tmp_path, monkeypatch):
        """Save overwrites previous state."""
        config_path = tmp_path / "publish.yaml"
        monkeypatch.setattr(
            "agent_sync.publish.config.CONFIG_PATH",
            config_path,
        )
        
        # First save
        PublishStateManager.save({"local": ["a"]}, {"agents": []})
        
        # Second save
        PublishStateManager.save({"local": ["b", "c"]}, {"agents": ["pi.dev"]})
        
        state = PublishStateManager.load()
        assert state.skills == {"local": ["b", "c"]}
        assert state.agents == {"agents": ["pi.dev"]}

    def test_clear(self, tmp_path, monkeypatch):
        """Clears state from config."""
        config_path = tmp_path / "publish.yaml"
        monkeypatch.setattr(
            "agent_sync.publish.config.CONFIG_PATH",
            config_path,
        )
        
        # Save first
        PublishStateManager.save({"local": ["a"]}, {"agents": []})
        
        # Then clear
        PublishStateManager.clear()
        
        state = PublishStateManager.load()
        assert state.is_empty()

    def test_get_source_state_skills(self, tmp_path, monkeypatch):
        """Gets selected items for a skill source."""
        config_path = tmp_path / "publish.yaml"
        monkeypatch.setattr(
            "agent_sync.publish.config.CONFIG_PATH",
            config_path,
        )
        
        PublishStateManager.save(
            {"local": ["a", "b"], "ext": ["c"]},
            {"agents": ["opencode"]},
        )
        
        state = PublishStateManager.load()
        
        local_items = PublishStateManager.get_source_state(state, "local")
        assert local_items == {"a", "b"}
        
        ext_items = PublishStateManager.get_source_state(state, "ext")
        assert ext_items == {"c"}
        
        agents_items = PublishStateManager.get_source_state(state, "agents")
        assert agents_items == {"opencode"}

    def test_get_source_state_missing_source(self, tmp_path, monkeypatch):
        """Returns empty set for missing source."""
        config_path = tmp_path / "publish.yaml"
        monkeypatch.setattr(
            "agent_sync.publish.config.CONFIG_PATH",
            config_path,
        )
        
        PublishStateManager.save({"local": ["a"]}, {})
        
        state = PublishStateManager.load()
        
        items = PublishStateManager.get_source_state(state, "nonexistent")
        assert items == set()