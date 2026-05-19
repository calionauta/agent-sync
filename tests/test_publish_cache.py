"""Tests for publish.cache module."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta

from agent_sync.publish.cache import (
    cache_dir,
    get_cache_path,
    is_cache_valid,
    normalize_repo_id,
)


class TestNormalizeRepoId:
    def test_https(self):
        assert normalize_repo_id("https://github.com/user/repo") == "user/repo"
    
    def test_https_with_git_suffix(self):
        assert normalize_repo_id("https://github.com/user/repo.git") == "user/repo"
    
    def test_git_at_shorthand(self):
        assert normalize_repo_id("git@github.com:user/repo.git") == "user/repo"
    
    def test_with_trailing_slash(self):
        assert normalize_repo_id("https://github.com/user/repo/") == "user/repo"
    
    def test_no_protocol(self):
        # URLs without protocol aren't auto-detected - expected behavior
        result = normalize_repo_id("github.com/user/repo")
        assert "github.com" in result


class TestGetCachePath:
    def test_returns_path_with_underscores(self):
        path = get_cache_path(Path("/cache"), "https://github.com/user/repo")
        assert str(path) == "/cache/user_repo"
    
    def test_normalizes_different_formats(self):
        path1 = get_cache_path(Path("/cache"), "https://github.com/user/repo")
        path2 = get_cache_path(Path("/cache"), "git@github.com:user/repo.git")
        assert path1 == path2


class TestIsCacheValid:
    def test_returns_false_for_nonexistent_path(self, tmp_path):
        fake_path = tmp_path / "nonexistent"
        assert is_cache_valid(fake_path) is False
    
    def test_returns_true_for_recently_created(self, tmp_path):
        cache_path = tmp_path / "recent"
        cache_path.mkdir()
        
        # Created just now, should be valid
        assert is_cache_valid(cache_path, ttl_hours=24) is True
    
    def test_returns_false_for_old_cache(self, tmp_path):
        cache_path = tmp_path / "old"
        cache_path.mkdir()
        
        # Set modification time to 48 hours ago
        old_time = datetime.now().timestamp() - (48 * 3600)
        cache_path.parent.chmod(0o755)
        cache_path.chmod(0o755)
        
        import os
        os.utime(cache_path, (old_time, old_time))
        
        assert is_cache_valid(cache_path, ttl_hours=24) is False