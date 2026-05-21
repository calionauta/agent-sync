"""Tests for pull command with conflict detection."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from rich.prompt import Prompt

from agent_sync.sync import PullConflict, PullSummary, SyncManager
from agent_sync.config import Config


class TestPullConflict:
    """Tests for PullConflict dataclass."""
    
    def test_display_name(self):
        """Test display_name property."""
        conflict = PullConflict(
            agent_name="pi.dev",
            filename="AGENTS.md",
            local_path=Path("/home/.pi/agent/AGENTS.md"),
            remote_path=Path("configs/pi.dev/AGENTS.md"),
        )
        assert conflict.display_name == "pi.dev/AGENTS.md"
    
    def test_diff_summary_added_only(self):
        """Test diff_summary with only additions."""
        conflict = PullConflict(
            agent_name="pi.dev",
            filename="AGENTS.md",
            local_path=Path("/home/.pi/agent/AGENTS.md"),
            remote_path=Path("configs/pi.dev/AGENTS.md"),
            diff_stats={"added": 10, "removed": 0},
        )
        assert conflict.diff_summary == "10 +l"
    
    def test_diff_summary_removed_only(self):
        """Test diff_summary with only removals."""
        conflict = PullConflict(
            agent_name="pi.dev",
            filename="AGENTS.md",
            local_path=Path("/home/.pi/agent/AGENTS.md"),
            remote_path=Path("configs/pi.dev/AGENTS.md"),
            diff_stats={"added": 0, "removed": 5},
        )
        assert conflict.diff_summary == "5 -l"
    
    def test_diff_summary_both(self):
        """Test diff_summary with both additions and removals."""
        conflict = PullConflict(
            agent_name="pi.dev",
            filename="AGENTS.md",
            local_path=Path("/home/.pi/agent/AGENTS.md"),
            remote_path=Path("configs/pi.dev/AGENTS.md"),
            diff_stats={"added": 12, "removed": 5},
        )
        assert conflict.diff_summary == "12 +l / 5 -l"
    
    def test_diff_summary_empty(self):
        """Test diff_summary with no changes."""
        conflict = PullConflict(
            agent_name="pi.dev",
            filename="AGENTS.md",
            local_path=Path("/home/.pi/agent/AGENTS.md"),
            remote_path=Path("configs/pi.dev/AGENTS.md"),
            diff_stats={"added": 0, "removed": 0},
        )
        assert conflict.diff_summary == ""


class TestPullSummary:
    """Tests for PullSummary dataclass."""
    
    def test_has_conflicts_true(self):
        """Test has_conflicts when there are conflicts."""
        conflict = PullConflict(
            agent_name="pi.dev",
            filename="AGENTS.md",
            local_path=Path("/home/.pi/agent/AGENTS.md"),
            remote_path=Path("configs/pi.dev/AGENTS.md"),
        )
        summary = PullSummary(conflicts=[conflict])
        assert summary.has_conflicts is True
    
    def test_has_conflicts_false(self):
        """Test has_conflicts when there are no conflicts."""
        summary = PullSummary()
        assert summary.has_conflicts is False
    
    def test_total_changes(self):
        """Test total_changes calculation."""
        conflict = PullConflict(
            agent_name="pi.dev",
            filename="AGENTS.md",
            local_path=Path("/home/.pi/agent/AGENTS.md"),
            remote_path=Path("configs/pi.dev/AGENTS.md"),
        )
        summary = PullSummary(
            conflicts=[conflict],
            new_files=5,
            updated_files=10,
            deleted_files=2,
        )
        assert summary.total_changes == 18  # 1 + 5 + 10 + 2


class TestPullCommandFlags:
    """Tests for pull command CLI flags."""
    
    def test_pull_with_force_flag(self):
        """Test pull command accepts --force flag."""
        from click.testing import CliRunner
        from agent_sync.cli import main
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--help"])
        assert "--force" in result.output
    
    def test_pull_with_dry_run_flag(self):
        """Test pull command accepts --dry-run flag."""
        from click.testing import CliRunner
        from agent_sync.cli import main
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--help"])
        assert "--dry-run" in result.output
    
    def test_pull_with_interactive_flag(self):
        """Test pull command accepts --interactive flag."""
        from click.testing import CliRunner
        from agent_sync.cli import main
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--help"])
        assert "--interactive" in result.output


class TestDetectConflicts:
    """Tests for conflict detection logic."""
    
    @pytest.fixture
    def mock_sync_manager(self, tmp_path, monkeypatch):
        """Create a mock SyncManager for testing."""
        # Create a mock config
        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        mock_config.state_file = tmp_path / "state.json"
        
        # Create mock repo directory
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        
        # Patch the SyncManager to avoid real git operations
        with patch("agent_sync.config.Config") as MockConfig:
            MockConfig.return_value = mock_config
            manager = SyncManager(mock_config)
            manager.repo_dir = repo_dir
            manager.config = mock_config
            
            return manager
    
    def test_detect_conflicts_empty_repo(self, tmp_path):
        """Test detect_conflicts returns empty list when no changes detected."""
        from agent_sync.sync import SyncManager
        from unittest.mock import Mock
        
        mock_config = Mock()
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        
        manager = SyncManager(mock_config)
        manager.repo_dir = tmp_path / "repo"
        manager.repo_dir.mkdir()
        (manager.repo_dir / ".git").mkdir()
        
        # When no unstaged changes, detect_conflicts should return empty
        with patch.object(manager, '_run_git', return_value=""):
            conflicts = manager._detect_conflicts()
            assert conflicts == []


class TestSelectivePull:
    """Tests for selective pull with filters."""
    
    def test_pull_accepts_skill_filter(self):
        """Test pull command accepts --skill flag."""
        from click.testing import CliRunner
        from agent_sync.cli import main
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--help"])
        assert "--skill" in result.output
    
    def test_pull_accepts_agent_filter(self):
        """Test pull command accepts --agent flag."""
        from click.testing import CliRunner
        from agent_sync.cli import main
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--help"])
        assert "--agent" in result.output
    
    def test_pull_accepts_exclude_skill(self):
        """Test pull command accepts --exclude-skill flag."""
        from click.testing import CliRunner
        from agent_sync.cli import main
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--help"])
        assert "--exclude-skill" in result.output
    
    def test_pull_accepts_exclude_agent(self):
        """Test pull command accepts --exclude-agent flag."""
        from click.testing import CliRunner
        from agent_sync.cli import main
        
        runner = CliRunner()
        result = runner.invoke(main, ["pull", "--help"])
        assert "--exclude-agent" in result.output
    
    def test_apply_configs_accepts_filter_param(self, tmp_path):
        """Test _apply_synced_configs accepts agents_filter parameter."""
        from agent_sync.sync import SyncManager
        from unittest.mock import Mock
        
        mock_config = Mock()
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        
        manager = SyncManager(mock_config)
        
        # Just check the method accepts the parameter (signature test)
        import inspect
        sig = inspect.signature(manager._apply_synced_configs)
        params = list(sig.parameters.keys())
        
        assert "agents_filter" in params, "agents_filter parameter missing"
        assert "agents_exclude" in params, "agents_exclude parameter missing"
    
    def test_apply_skills_accepts_filter_param(self, tmp_path):
        """Test _apply_synced_skills accepts skills_filter parameter."""
        from agent_sync.sync import SyncManager
        from unittest.mock import Mock
        
        mock_config = Mock()
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        
        manager = SyncManager(mock_config)
        
        # Check method signature
        import inspect
        sig = inspect.signature(manager._apply_synced_skills)
        params = list(sig.parameters.keys())
        
        assert "skills_filter" in params, "skills_filter parameter missing"
        assert "skills_exclude" in params, "skills_exclude parameter missing"




class TestDryRun:
    """Tests for dry-run functionality."""
    
    def test_dry_run_shows_preview(self, tmp_path):
        """Test that --dry-run shows preview without applying changes."""
        from click.testing import CliRunner
        from agent_sync.cli import main
        from unittest.mock import patch
        from agent_sync.sync import SyncManager, PullSummary
        
        runner = CliRunner()
        
        # Mock the SyncManager.pull to return without actually running git
        with patch.object(SyncManager, 'pull') as mock_pull:
            mock_pull.return_value = ([], PullSummary())
            
            result = runner.invoke(main, ["pull", "--dry-run"])
            
            # Check that pull was called with dry_run=True
            mock_pull.assert_called_once()
            call_kwargs = mock_pull.call_args[1]
            assert call_kwargs.get('dry_run') is True

class TestLinkRepoSafety:
    """Tests for link_repo safety improvements."""
    
    def test_link_repo_uses_temp_directory(self, tmp_path):
        """Test that link_repo uses tempfile.TemporaryDirectory for safety."""
        from agent_sync.sync import SyncManager
        from unittest.mock import Mock, patch
        
        mock_config = Mock()
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        
        manager = SyncManager(mock_config)
        manager.repo_dir = tmp_path / "repo"
        manager.repo_dir.mkdir()
        
        # Verify the _clone_to_repo helper uses tempfile (DRY safety)
        import inspect
        source = inspect.getsource(manager._clone_to_repo)
        
        # Check that TemporaryDirectory is used
        assert "TemporaryDirectory" in source, "_clone_to_repo should use tempfile.TemporaryDirectory"


class TestInteractiveConflictResolution:
    """Tests for interactive conflict resolution."""
    
    def test_handle_conflicts_shows_options(self, tmp_path):
        """Test that conflict handler shows all options."""
        from agent_sync.sync import SyncManager, PullConflict
        from unittest.mock import patch, Mock
        
        conflict = PullConflict(
            agent_name="pi.dev",
            filename="AGENTS.md",
            local_path=Path("/home/.pi/agent/AGENTS.md"),
            remote_path=Path("configs/pi.dev/AGENTS.md"),
            diff_stats={"added": 10, "removed": 5},
        )
        
        # Create mock sync manager
        mock_config = Mock(spec=Config)
        mock_config.repo_url = "https://github.com/test/repo"
        mock_config.app_dir = tmp_path
        
        manager = SyncManager(mock_config)
        manager.repo_dir = tmp_path / "repo"
        
        # Mock _run_git to avoid actual git operations
        with patch.object(manager, '_run_git') as mock_git:
            with patch('rich.prompt.Prompt.ask') as mock_prompt:
                mock_prompt.return_value = ""  # Default - keep local
                
                # Should not raise exception
                manager._handle_conflicts_interactive([conflict])
                
                # Verify Prompt was called
                mock_prompt.assert_called()