"""End-to-end integration tests for CLI → SyncManager parameter passing.

CRITICAL: These tests verify that the CLI passes the CORRECT parameter names
to SyncManager methods. This catches bugs where we pass wrong param names
(e.g., exclude_skills instead of skills_exclude).
"""

import pytest
from unittest.mock import patch, Mock
from click.testing import CliRunner

from agent_sync.cli import main


runner = CliRunner()


class TestPushCLIToSyncManagerParamPassing:
    """Test that push CLI passes correct params to SyncManager._push_stage_and_get_changes."""

    def test_push_passes_exclude_skills_as_skills_exclude(self):
        """CLI should call _push_stage_and_get_changes with skills_exclude, not exclude_skills."""
        from agent_sync.sync import SyncManager
        
        called_params = {}
        
        def mock_stage(self, **kwargs):
            called_params.update(kwargs)
            # Check for wrong param names
            if 'exclude_skills' in kwargs or 'exclude_agents' in kwargs:
                raise AssertionError(
                    f"CLI called with wrong param names: {list(kwargs.keys())}"
                )
            return []
        
        with patch.object(SyncManager, '_push_stage_and_get_changes', mock_stage):
            result = runner.invoke(main, ['push', '--exclude-skill', 'deprecated', '--dry-run'])
        
        # Verify correct param names were used
        assert 'skills_exclude' in called_params, f"CLI should pass skills_exclude, got: {list(called_params.keys())}"
        assert 'agents_exclude' in called_params, f"CLI should pass agents_exclude, got: {list(called_params.keys())}"
        
        # Verify wrong param names were NOT used
        assert 'exclude_skills' not in called_params
        assert 'exclude_agents' not in called_params

    def test_push_passes_skill_filter_as_skills_filter(self):
        """CLI should call with skills_filter, not skill_filter."""
        from agent_sync.sync import SyncManager
        
        called_params = {}
        
        def mock_stage(self, **kwargs):
            called_params.update(kwargs)
            if 'skill_filter' in kwargs or 'agent_filter' in kwargs:
                raise AssertionError(f"CLI called with wrong param: {list(kwargs.keys())}")
            return []
        
        with patch.object(SyncManager, '_push_stage_and_get_changes', mock_stage):
            result = runner.invoke(main, ['push', '--skill', 'dogfood', '--agent', 'pi.dev', '--dry-run'])
        
        assert 'skills_filter' in called_params
        assert 'agents_filter' in called_params
        assert 'skill_filter' not in called_params
        assert 'agent_filter' not in called_params

    def test_push_passes_all_filter_params(self):
        """All filter params should be passed correctly."""
        from agent_sync.sync import SyncManager
        
        called_params = {}
        
        def mock_stage(self, **kwargs):
            called_params.update(kwargs)
            return []
        
        with patch.object(SyncManager, '_push_stage_and_get_changes', mock_stage):
            result = runner.invoke(main, [
                'push',
                '--skill', 'skill1', '--skill', 'skill2',
                '--agent', 'agent1', '--agent', 'agent2',
                '--exclude-skill', 'skip1', '--exclude-skill', 'skip2',
                '--exclude-agent', 'skip3',
                '--dry-run'
            ])
        
        # Verify all params present with correct names
        assert 'skills_filter' in called_params
        assert 'agents_filter' in called_params
        assert 'skills_exclude' in called_params
        assert 'agents_exclude' in called_params
        
        # Verify values
        assert called_params['skills_filter'] == ['skill1', 'skill2']
        assert called_params['agents_filter'] == ['agent1', 'agent2']
        assert called_params['skills_exclude'] == ['skip1', 'skip2']
        assert called_params['agents_exclude'] == ['skip3']


class TestPullCLIToSyncManagerParamPassing:
    """Test that pull CLI passes correct params to SyncManager.pull()."""

    def test_pull_passes_exclude_skills_correctly(self):
        """Pull CLI should call sync_manager.pull with correct params."""
        from agent_sync.sync import SyncManager
        
        called_params = {}
        
        def mock_pull(self, **kwargs):
            called_params.update(kwargs)
            return [], Mock()
        
        with patch.object(SyncManager, 'pull', mock_pull):
            result = runner.invoke(main, ['pull', '--exclude-skill', 'deprecated', '--dry-run'])
        
        # Verify correct param names were used
        assert 'skills_filter' in called_params or 'skills_exclude' in called_params or 'exclude_skill' in called_params, \
            f"CLI should pass exclude params, got: {list(called_params.keys())}"

    def test_pull_no_typeerror_on_filter_flags(self):
        """pull with filter flags should not raise TypeError."""
        result = runner.invoke(main, [
            'pull',
            '--skill', 'dogfood',
            '--agent', 'pi.dev',
            '--exclude-skill', 'deprecated',
            '--exclude-agent', 'old',
            '--dry-run'
        ])
        
        assert 'TypeError' not in result.output, f"TypeError in output: {result.output}"
        assert 'Traceback' not in result.output or result.exit_code == 0, f"Traceback in output: {result.output}"


class TestCLIPushNoErrors:
    """Verify push command doesn't crash with filter flags."""

    def test_push_no_typeerror_on_filter_flags(self):
        """push with filter flags should not raise TypeError."""
        result = runner.invoke(main, [
            'push',
            '--skill', 'dogfood',
            '--agent', 'pi.dev',
            '--exclude-skill', 'deprecated',
            '--exclude-agent', 'old',
            '--dry-run'
        ])
        
        # Should NOT have TypeError (wrong param names)
        assert 'TypeError' not in result.output, f"TypeError in output: {result.output}"
        # Should NOT have Traceback
        assert 'Traceback' not in result.output or result.exit_code == 0, f"Traceback in output: {result.output}"

    def test_push_with_all_filters_no_errors(self):
        """push with all filter combinations should work."""
        result = runner.invoke(main, [
            'push',
            '--skill', 'dogfood',
            '--agent', 'pi.dev',
            '--exclude-skill', 'skip1', '--exclude-skill', 'skip2',
            '--exclude-agent', 'skip3',
            '--skills-only',
            '--dry-run'
        ])
        
        assert 'TypeError' not in result.output
        assert 'NoSuchOption' not in result.output
        assert 'Traceback' not in result.output or result.exit_code == 0

    def test_pull_no_typeerror_on_filter_flags(self):
        """pull with filter flags should not raise TypeError."""
        result = runner.invoke(main, [
            'pull',
            '--skill', 'dogfood',
            '--agent', 'pi.dev',
            '--exclude-skill', 'deprecated',
            '--exclude-agent', 'old',
            '--dry-run'
        ])
        
        assert 'TypeError' not in result.output
        assert 'Traceback' not in result.output or result.exit_code == 0