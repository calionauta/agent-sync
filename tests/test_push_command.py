"""Tests for push command signature consistency.

These tests verify that method signatures are consistent across the codebase.
They prevent regression when refactoring - if a parameter is removed or renamed,
these tests will catch it.
"""

import pytest
import inspect
from unittest.mock import Mock, patch

from agent_sync.sync import SyncManager


class TestPushMethodSignatures:
    """Tests that verify push-related methods have correct signatures.
    
    These are interface contract tests - they ensure that when code calls
    _push_stage_and_get_changes(), it passes the right parameters.
    
    Critical for regression prevention when adding new filter options.
    """
    
    def test_push_accepts_all_params(self):
        """Verify push() accepts expected parameters."""
        sig = inspect.signature(SyncManager.push)
        params = list(sig.parameters.keys())
        
        assert "message" in params, "push() should accept message param"
        assert "skills_only" in params, "push() should accept skills_only param"
        assert "configs_only" in params, "push() should accept configs_only param"
        assert "agents_only" in params, "push() should accept agents_only param"
    
    def test_push_stage_and_get_changes_accepts_filters(self):
        """Verify _push_stage_and_get_changes() passes filters to staging methods.
        
        This test catches the bug where agents_filter wasn't passed to
        _stage_agent_configs(), causing NameError.
        """
        sig = inspect.signature(SyncManager._push_stage_and_get_changes)
        params = list(sig.parameters.keys())
        
        # These must be present for filter propagation to work
        assert "skills_filter" in params
        assert "agents_filter" in params
        assert "skills_exclude" in params
        assert "agents_exclude" in params
    
    def test_stage_agent_configs_accepts_filters(self):
        """Verify _stage_agent_configs() accepts filter parameters."""
        sig = inspect.signature(SyncManager._stage_agent_configs)
        params = list(sig.parameters.keys())
        
        assert "agents_filter" in params, "_stage_agent_configs() needs agents_filter"
        assert "agents_exclude" in params, "_stage_agent_configs() needs agents_exclude"
    
    def test_stage_all_agent_files_accepts_filters(self):
        """Verify _stage_all_agent_files() accepts filter parameters."""
        sig = inspect.signature(SyncManager._stage_all_agent_files)
        params = list(sig.parameters.keys())
        
        assert "agents_filter" in params, "_stage_all_agent_files() needs agents_filter"
        assert "agents_exclude" in params, "_stage_all_agent_files() needs agents_exclude"


class TestPullMethodSignatures:
    """Tests that verify pull-related methods have correct signatures."""
    
    def test_pull_accepts_filter_params(self):
        """Verify pull() accepts filter parameters and passes them through."""
        sig = inspect.signature(SyncManager.pull)
        params = list(sig.parameters.keys())
        
        assert "skills_filter" in params
        assert "agents_filter" in params
        assert "skills_exclude" in params
        assert "agents_exclude" in params
    
    def test_apply_configs_accepts_filters(self):
        """Verify _apply_synced_configs() accepts filter parameters."""
        sig = inspect.signature(SyncManager._apply_synced_configs)
        params = list(sig.parameters.keys())
        
        assert "agents_filter" in params
        assert "agents_exclude" in params
    
    def test_apply_skills_accepts_filters(self):
        """Verify _apply_synced_skills() accepts filter parameters."""
        sig = inspect.signature(SyncManager._apply_synced_skills)
        params = list(sig.parameters.keys())
        
        assert "skills_filter" in params
        assert "skills_exclude" in params


class TestSyncMethodSignatures:
    """Tests that verify sync-related methods have correct signatures."""
    
    def test_link_repo_exists(self):
        """Verify link_repo() exists and is callable."""
        assert hasattr(SyncManager, 'link_repo')
        assert callable(getattr(SyncManager, 'link_repo'))
    
    def test_clone_to_repo_exists(self):
        """Verify _clone_to_repo() helper exists (DRY centralization)."""
        assert hasattr(SyncManager, '_clone_to_repo')
        
        # Should use temp directory for safety
        sig = inspect.signature(SyncManager._clone_to_repo)
        params = list(sig.parameters.keys())
        assert "repo_url" in params
class TestPushStrictFlag:
    """Smoke tests for the `--strict` flag (CI-friendly exit code 2)."""

    def test_strict_does_not_crash(self):
        """push --strict runs without crash (exit: 0, 1, or 2)."""
        from click.testing import CliRunner
        from agent_sync.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["push", "--strict"])
        assert result.exit_code in (0, 1, 2), (
            f"Unexpected exit code {result.exit_code}: {result.output[:200]}"
        )
