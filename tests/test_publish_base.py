"""Tests for publish.base module."""

import pytest
from pathlib import Path

from agent_sync.publish.base import (
    PublishConfig,
    SkillSource,
    SourceConfig,
    SourceStatus,
)


class TestSourceStatus:
    def test_enum_values(self):
        assert SourceStatus.ACTIVE.value == "active"
        assert SourceStatus.FAILED.value == "failed"
        assert SourceStatus.SKIPPED.value == "skipped"
        assert SourceStatus.UNKNOWN.value == "unknown"


class TestSkillSource:
    def test_creation(self, tmp_path):
        skill_md = tmp_path / "test-skill" / "SKILL.md"
        skill_md.parent.mkdir(parents=True)
        skill_md.write_text("# Test")
        
        skill = SkillSource(
            name="test-skill",
            path=skill_md.parent,
            source_type="local",
            source_url="local",
            source_id="local",
        )
        
        assert skill.name == "test-skill"
        assert skill.source_type == "local"
        assert skill.source_id == "local"
    
    def test_display_name_local(self):
        skill = SkillSource(
            name="my-skill",
            path=Path("/fake"),
            source_type="local",
            source_url="local",
            source_id="local",
        )
        assert skill.display_name == "my-skill"
    
    def test_display_name_external(self):
        skill = SkillSource(
            name="my-skill",
            path=Path("/fake"),
            source_type="external",
            source_url="https://github.com/user/repo",
            source_id="user/repo",
        )
        assert skill.display_name == "user/repo/my-skill"
    
    def test_to_dict(self, tmp_path):
        skill = SkillSource(
            name="test",
            path=tmp_path / "test",
            source_type="local",
            source_url="local",
            source_id="local",
        )
        
        d = skill.to_dict()
        assert d["name"] == "test"
        assert d["source_type"] == "local"
        assert d["source_id"] == "local"


class TestSourceConfig:
    def test_creation(self):
        source = SourceConfig(url="https://github.com/user/repo")
        assert source.url == "https://github.com/user/repo"
        assert source.status == SourceStatus.UNKNOWN
    
    def test_repo_id_https(self):
        source = SourceConfig(url="https://github.com/user/repo")
        assert source.repo_id == "user/repo"
    
    def test_repo_id_git(self):
        source = SourceConfig(url="git@github.com:user/repo.git")
        assert source.repo_id == "user/repo"
    
    def test_repo_id_with_trailing_slash(self):
        source = SourceConfig(url="https://github.com/user/repo/")
        assert source.repo_id == "user/repo"
    
    def test_to_dict(self):
        source = SourceConfig(
            url="https://github.com/user/repo",
            status=SourceStatus.ACTIVE,
            last_success="2026-05-19",
        )
        
        d = source.to_dict()
        assert d["url"] == "https://github.com/user/repo"
        assert d["status"] == "active"
        assert d["last_success"] == "2026-05-19"
    
    def test_from_dict(self):
        data = {
            "url": "https://github.com/user/repo",
            "status": "failed",
            "last_success": "2026-05-18",
            "cache_ttl_hours": 12,
        }
        
        source = SourceConfig.from_dict(data)
        assert source.url == "https://github.com/user/repo"
        assert source.status == SourceStatus.FAILED
        assert source.cache_ttl_hours == 12


class TestPublishConfig:
    def test_creation(self):
        config = PublishConfig(published_repo="https://github.com/user/repo")
        assert config.published_repo == "https://github.com/user/repo"
        assert config.skill_sources == []
        assert config.selected_skills == {}
    
    def test_add_source(self):
        config = PublishConfig(published_repo="https://github.com/user/repo")
        source = config.add_source("https://github.com/other/project")
        
        assert len(config.skill_sources) == 1
        assert config.skill_sources[0].url == "https://github.com/other/project"
        assert source.repo_id == "other/project"
    
    def test_remove_source(self):
        config = PublishConfig(published_repo="https://github.com/user/repo")
        config.add_source("https://github.com/other/project")
        
        result = config.remove_source("https://github.com/other/project")
        
        assert result is True
        assert len(config.skill_sources) == 0
    
    def test_remove_source_not_found(self):
        config = PublishConfig(published_repo="https://github.com/user/repo")
        result = config.remove_source("https://github.com/nonexistent/repo")
        assert result is False
    
    def test_get_set_skills(self):
        config = PublishConfig(published_repo="https://github.com/user/repo")
        config.set_skills_for_source("local", ["skill-a", "skill-b"])
        
        skills = config.get_skills_for_source("local")
        assert skills == ["skill-a", "skill-b"]
    
    def test_to_dict(self):
        config = PublishConfig(
            published_repo="https://github.com/user/repo",
            cache_ttl_hours=48,
        )
        config.add_source("https://github.com/other/project")
        
        d = config.to_dict()
        
        assert d["published_repo"] == "https://github.com/user/repo"
        assert d["cache_ttl_hours"] == 48
        assert len(d["skill_sources"]) == 1
    
    def test_from_dict(self):
        data = {
            "published_repo": "https://github.com/user/repo",
            "skill_sources": [
                {"url": "https://github.com/a/b", "status": "active"}
            ],
            "selected_skills": {"local": ["skill-1"]},
            "cache_ttl_hours": 36,
        }
        
        config = PublishConfig.from_dict(data)
        
        assert config.published_repo == "https://github.com/user/repo"
        assert config.cache_ttl_hours == 36
        assert len(config.skill_sources) == 1
        assert config.selected_skills["local"] == ["skill-1"]