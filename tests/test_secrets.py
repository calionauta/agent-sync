"""Tests for agent-sync secrets management."""

from pathlib import Path

from agent_sync.secrets import SecretsManager


class TestSecretsManager:
    """Test secrets management."""

    def test_secrets_manager_initialization(self, tmp_path):
        """Test secrets manager initializes correctly."""
        mgr = SecretsManager()
        mgr.env_file = tmp_path / ".env"
        assert mgr.env_file.parent.exists()

    def test_get_secret_paths(self, tmp_path):
        """Test getting secret paths for agents."""
        mgr = SecretsManager()
        mgr.env_file = tmp_path / ".env"
        paths = mgr.get_secret_paths("opencode")
        assert len(paths) > 0
