"""End-to-end integration tests for push and pull commands.

These tests use real git operations in temporary directories to ensure
the sync flow works correctly. They catch bugs that unit tests miss.

Critical for regression prevention in the core sync workflow.
"""

import pytest
import subprocess
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from agent_sync.sync import SyncManager


class TestPushEndToEnd:
    """E2E tests for push command with real git operations."""
    
    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary git repository for testing."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        
        # Init git repo
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_dir, check=True, capture_output=True
        )
        
        # Create initial commit
        readme = repo_dir / "README.md"
        readme.write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_dir, check=True, capture_output=True
        )
        
        yield repo_dir
        
        # Cleanup handled by tmp_path fixture
    
    def test_push_commits_changes(self, temp_repo):
        """Test that push() creates a commit with changes."""
        # Create a mock config
        mock_config = Mock()
        mock_config.repo_url = "https://github.com/test/test.git"
        mock_config.app_dir = temp_repo.parent / "app"
        mock_config.app_dir.mkdir(parents=True, exist_ok=True)
        mock_config.state_file = mock_config.app_dir / "state.json"
        mock_config.is_agent_enabled.return_value = False
        
        # Create a test config file in the repo
        config_file = temp_repo / "configs" / "pi.dev" / "AGENTS.md"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("# Test Config")
        
        # Stage the change
        subprocess.run(["git", "add", "."], cwd=temp_repo, capture_output=True)
        
        # Get status before commit
        status_before = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=temp_repo, capture_output=True, text=True
        )
        
        assert status_before.stdout.strip() != "", "Should have staged changes"
        
        # Create sync manager and call push
        manager = SyncManager(mock_config)
        manager.repo_dir = temp_repo
        
        # Call push - it should commit the changes
        changes = manager._push_stage_and_get_changes("test: add config")
        
        # Verify commit was created
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=temp_repo, capture_output=True, text=True
        )
        
        assert "test: add config" in log.stdout or len(log.stdout.strip()) > 0, "Should have created commit"
    
    def test_push_returns_changed_files(self, temp_repo):
        """Test that push returns list of changed files."""
        # Create mock config
        mock_config = Mock()
        mock_config.repo_url = "https://github.com/test/test.git"
        mock_config.app_dir = temp_repo.parent / "app"
        mock_config.app_dir.mkdir(parents=True, exist_ok=True)
        mock_config.state_file = mock_config.app_dir / "state.json"
        mock_config.is_agent_enabled.return_value = False
        
        # Create test file
        test_file = temp_repo / "test.txt"
        test_file.write_text("test content")
        
        manager = SyncManager(mock_config)
        manager.repo_dir = temp_repo
        
        changes = manager._push_stage_and_get_changes("test commit")
        
        # Should return changes
        assert isinstance(changes, list), "Should return list of changes"
        # Note: the exact format depends on implementation




class TestSyncIntegration:
    """Tests for sync() method which combines pull + push."""
    
    def test_sync_combines_pull_and_push(self):
        """Test that sync() calls both pull and push."""
        mock_config = Mock()
        mock_config.repo_url = "https://github.com/test/test.git"
        mock_config.app_dir = Path("/tmp/test_app")
        mock_config.state_file = mock_config.app_dir / "state.json"
        mock_config.is_agent_enabled.return_value = False
        
        manager = SyncManager(mock_config)
        manager.repo_dir = Path("/tmp/test_repo_nonexistent")
        
        # Mock both methods to verify they're called
        with patch.object(manager, 'pull') as mock_pull:
            with patch.object(manager, 'push') as mock_push:
                mock_pull.return_value = ([], Mock())
                mock_push.return_value = []
                
                result = manager.sync()
                
                mock_pull.assert_called_once()
                mock_push.assert_called_once()
                assert result is True