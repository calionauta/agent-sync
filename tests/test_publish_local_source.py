"""Tests for publish.local_source module."""

import pytest
from pathlib import Path

from agent_sync.publish.local_source import (
    discover_local_skills,
    get_local_source_status,
    SKILLS_DIR,
    _is_valid_skill_name,
)


class TestIsValidSkillName:
    def test_valid_names(self):
        assert _is_valid_skill_name("my-skill") is True
        assert _is_valid_skill_name("cali-shape-up") is True
        assert _is_valid_skill_name("test123") is True
        assert _is_valid_skill_name("a") is True
    
    def test_invalid_names(self):
        assert _is_valid_skill_name("My-Skill") is False  # uppercase
        assert _is_valid_skill_name("my_skill") is False  # underscore
        assert _is_valid_skill_name("my--skill") is False  # consecutive hyphens
        assert _is_valid_skill_name("-skill") is False  # starts with hyphen
        assert _is_valid_skill_name("my-skill-") is False  # ends with hyphen


class TestDiscoverLocalSkills:
    def test_returns_empty_when_no_skills_dir(self, tmp_path, monkeypatch):
        # Mock SKILLS_DIR to tmp_path
        fake_skills_dir = tmp_path / "skills"
        monkeypatch.setattr("agent_sync.publish.local_source.SKILLS_DIR", fake_skills_dir)
        
        skills = discover_local_skills()
        assert skills == []
    
    def test_discovers_skills_with_skill_md(self, tmp_path, monkeypatch):
        fake_skills_dir = tmp_path / "skills"
        fake_skills_dir.mkdir(parents=True)
        
        # Create a valid skill
        skill_dir = fake_skills_dir / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\n# Test")
        
        # Create invalid skill (no SKILL.md)
        invalid_dir = fake_skills_dir / "invalid-skill"
        invalid_dir.mkdir()
        
        monkeypatch.setattr("agent_sync.publish.local_source.SKILLS_DIR", fake_skills_dir)
        
        skills = discover_local_skills()
        
        assert len(skills) == 1
        assert skills[0].name == "test-skill"
        assert skills[0].source_type == "local"
        assert skills[0].source_id == "local"
    
    def test_ignores_hidden_directories(self, tmp_path, monkeypatch):
        fake_skills_dir = tmp_path / "skills"
        fake_skills_dir.mkdir(parents=True)
        
        # Create hidden directory
        hidden_dir = fake_skills_dir / ".hidden-skill"
        hidden_dir.mkdir()
        (hidden_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\n# Test")
        
        monkeypatch.setattr("agent_sync.publish.local_source.SKILLS_DIR", fake_skills_dir)
        
        skills = discover_local_skills()
        
        assert len(skills) == 0


class TestGetLocalSourceStatus:
    def test_returns_active_when_dir_exists(self, tmp_path, monkeypatch):
        fake_skills_dir = tmp_path / "skills"
        fake_skills_dir.mkdir(parents=True)
        monkeypatch.setattr("agent_sync.publish.local_source.SKILLS_DIR", fake_skills_dir)
        
        from agent_sync.publish.base import SourceStatus
        status = get_local_source_status()
        assert status == SourceStatus.ACTIVE
    
    def test_returns_unknown_when_dir_missing(self, tmp_path, monkeypatch):
        fake_skills_dir = tmp_path / "nonexistent"
        monkeypatch.setattr("agent_sync.publish.local_source.SKILLS_DIR", fake_skills_dir)
        
        from agent_sync.publish.base import SourceStatus
        status = get_local_source_status()
        assert status == SourceStatus.UNKNOWN