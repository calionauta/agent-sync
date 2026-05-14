"""Tests for custom agents backup and restore functionality."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_sync.agents import get_agent
from agent_sync.config import Config
from agent_sync.sync import SyncManager


class TestCustomAgentsBackup:
    """Test _stage_agents() functionality."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        temp_repo = Path(tempfile.mkdtemp())
        temp_home = Path(tempfile.mkdtemp())

        # Create test agents
        claude_agents = temp_home / ".claude" / "agents"
        opencode_agents = temp_home / ".config" / "opencode" / "agents"
        claude_agents.mkdir(parents=True, exist_ok=True)
        opencode_agents.mkdir(parents=True, exist_ok=True)

        # Create test agent files
        (claude_agents / "test-reviewer.md").write_text(
            "---\nname: test-reviewer\ndescription: Test agent\n---\nContent"
        )
        (opencode_agents / "test-researcher.md").write_text(
            "---\nname: test-researcher\ndescription: Test agent\n---\nContent"
        )

        yield temp_repo, temp_home, claude_agents, opencode_agents

        # Cleanup
        shutil.rmtree(temp_repo)
        shutil.rmtree(temp_home)

    def test_stage_agents_creates_directory_structure(self, temp_dirs):
        """Test that _stage_agents creates correct directory structure."""
        temp_repo, temp_home, claude_agents, opencode_agents = temp_dirs

        with patch.dict("os.environ", {"HOME": str(temp_home)}):
            config = Config()
            sync_mgr = SyncManager(config)
            sync_mgr.repo_dir = temp_repo

            # Run staging
            sync_mgr._stage_agents()

            # Check directory structure
            agents_dir = temp_repo / "agents"
            assert agents_dir.exists()

            # Check claude-code agents
            claude_dir = agents_dir / "claude-code"
            assert claude_dir.exists()
            assert (claude_dir / "project").exists()
            assert (claude_dir / "global").exists()
            assert (claude_dir / "project" / "test-reviewer.md").exists()
            assert (claude_dir / "global" / "test-reviewer.md").exists()

            # Check opencode agents
            opencode_dir = agents_dir / "opencode"
            assert opencode_dir.exists()
            assert (opencode_dir / "project").exists()
            assert (opencode_dir / "global").exists()
            assert (opencode_dir / "project" / "test-researcher.md").exists()
            assert (opencode_dir / "global" / "test-researcher.md").exists()

    def test_stage_agents_preserves_content(self, temp_dirs):
        """Test that _stage_agents preserves agent file content."""
        temp_repo, temp_home, claude_agents, opencode_agents = temp_dirs

        original_content = "---\nname: test\ndescription: Test\n---\nTest content"
        (claude_agents / "test.md").write_text(original_content)

        with patch.dict("os.environ", {"HOME": str(temp_home)}):
            config = Config()
            sync_mgr = SyncManager(config)
            sync_mgr.repo_dir = temp_repo

            sync_mgr._stage_agents()

            staged_file = temp_repo / "agents" / "claude-code" / "project" / "test.md"
            assert staged_file.read_text() == original_content

    def test_stage_agents_removes_deleted_agents(self, temp_dirs):
        """Test that _stage_agents removes agents that no longer exist locally."""
        temp_repo, temp_home, claude_agents, opencode_agents = temp_dirs

        with patch.dict("os.environ", {"HOME": str(temp_home)}):
            config = Config()
            sync_mgr = SyncManager(config)
            sync_mgr.repo_dir = temp_repo

            # First staging
            sync_mgr._stage_agents()

            # Verify agent is staged
            assert (temp_repo / "agents" / "claude-code" / "project" / "test-reviewer.md").exists()

            # Delete local agent
            (claude_agents / "test-reviewer.md").unlink()

            # Second staging
            sync_mgr._stage_agents()

            # Verify agent is removed from repo
            assert not (temp_repo / "agents" / "claude-code" / "project" / "test-reviewer.md").exists()


class TestCustomAgentsRestore:
    """Test _apply_synced_agents() functionality."""

    @pytest.fixture
    def temp_repo_with_agents(self):
        """Create temporary repo with agents."""
        temp_repo = Path(tempfile.mkdtemp())
        agents_dir = temp_repo / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Create test agents in repo
        claude_dir = agents_dir / "claude-code"
        claude_project = claude_dir / "project"
        claude_project.mkdir(parents=True, exist_ok=True)
        (claude_project / "restored-agent.md").write_text(
            "---\nname: restored\n---\nRestored content"
        )

        opencode_dir = agents_dir / "opencode"
        opencode_global = opencode_dir / "global"
        opencode_global.mkdir(parents=True, exist_ok=True)
        (opencode_global / "restored-global.md").write_text(
            "---\nname: global\n---\nGlobal content"
        )

        yield temp_repo

        shutil.rmtree(temp_repo)

    @pytest.fixture
    def temp_home_dir(self):
        """Create temporary home directory."""
        temp_home = Path(tempfile.mkdtemp())

        # Create agent directories
        (temp_home / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
        (temp_home / ".config" / "opencode" / "agents").mkdir(parents=True, exist_ok=True)

        yield temp_home

        shutil.rmtree(temp_home)

    def test_apply_synced_agents_restores_project_agents(self, temp_repo_with_agents, temp_home_dir):
        """Test that _apply_synced_agents restores project-level agents."""
        with patch.dict("os.environ", {"HOME": str(temp_home_dir)}):
            config = Config()
            sync_mgr = SyncManager(config)
            sync_mgr.repo_dir = temp_repo_with_agents

            changes = sync_mgr._apply_synced_agents()

            # Check restoration
            restored_file = temp_home_dir / ".claude" / "agents" / "restored-agent.md"
            assert restored_file.exists()
            assert "Restored content" in restored_file.read_text()

            # Check changes reported
            assert any("claude-code/project" in c for c in changes)

    def test_apply_synced_agents_restores_global_agents(self, temp_repo_with_agents, temp_home_dir):
        """Test that _apply_synced_agents restores global agents."""
        with patch.dict("os.environ", {"HOME": str(temp_home_dir)}):
            config = Config()
            sync_mgr = SyncManager(config)
            sync_mgr.repo_dir = temp_repo_with_agents

            changes = sync_mgr._apply_synced_agents()

            # Check restoration
            restored_file = temp_home_dir / ".config" / "opencode" / "agents" / "restored-global.md"
            assert restored_file.exists()
            assert "Global content" in restored_file.read_text()

            # Check changes reported
            assert any("opencode/global" in c for c in changes)

    def test_apply_synced_agents_preserves_directory_structure(self, temp_repo_with_agents, temp_home_dir):
        """Test that _apply_synced_agents preserves subdirectory structure."""
        # Create nested agent in repo
        nested_dir = temp_repo_with_agents / "agents" / "claude-code" / "project" / "subdir"
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / "nested-agent.md").write_text("---\nname: nested\n---\nNested")

        with patch.dict("os.environ", {"HOME": str(temp_home_dir)}):
            config = Config()
            sync_mgr = SyncManager(config)
            sync_mgr.repo_dir = temp_repo_with_agents

            sync_mgr._apply_synced_agents()

            # Check nested structure is preserved
            nested_file = temp_home_dir / ".claude" / "agents" / "subdir" / "nested-agent.md"
            assert nested_file.exists()


class TestCustomAgentsCLI:
    """Test custom agents CLI commands."""

    def test_supports_custom_agents_method(self):
        """Test that agents have supports_custom_agents() method."""
        claude = get_agent("claude-code")
        opencode = get_agent("opencode")

        assert claude.supports_custom_agents()
        assert opencode.supports_custom_agents()

    def test_agents_paths_are_configured(self):
        """Test that agents have correct paths configured."""
        claude = get_agent("claude-code")
        opencode = get_agent("opencode")

        # Check claude-code paths
        assert claude.agents_dir_name == "agents"
        assert str(claude.agents_path_global).endswith(".claude/agents")

        # Check opencode paths
        assert opencode.agents_dir_name == "agents"
        assert str(opencode.agents_path_global).endswith(".config/opencode/agents")
