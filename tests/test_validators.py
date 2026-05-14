"""Tests for validator utilities."""

from agent_sync.validators import validate_github_url, validate_repo_name


class TestValidators:
    """Tests for repository name and URL validators."""

    def test_validate_repo_name_valid(self):
        """Test valid repository names."""
        assert validate_repo_name("agent-sync") is True
        assert validate_repo_name("agent_sync") is True
        assert validate_repo_name("agent.sync") is True
        assert validate_repo_name("Agent-Sync-123") is True
        assert validate_repo_name("a") is True
        assert validate_repo_name("owner/repo") is True
        assert validate_repo_name("my-org/agent_sync.repo") is True

    def test_validate_repo_name_invalid(self):
        """Test invalid repository names."""
        assert validate_repo_name("") is False
        assert validate_repo_name("-agent-sync") is False  # Starts with hyphen
        assert validate_repo_name(".agent-sync") is False  # Starts with period
        assert validate_repo_name("agent sync") is False
        assert validate_repo_name("agent$sync") is False
        assert validate_repo_name("a" * 101) is False
        assert validate_repo_name("/") is False
        assert validate_repo_name("owner/repo/extra") is False
        assert validate_repo_name("owner//repo") is False
        assert validate_repo_name("/repo") is False

    def test_validate_github_url_valid(self):
        """Test valid GitHub URLs."""
        assert validate_github_url("https://github.com/owner/repo") is True
        assert validate_github_url("https://github.com/owner/repo.git") is True
        assert validate_github_url("https://github.com/my-org/my_repo") is True
        assert validate_github_url("https://github.com/123owner/123repo.git") is True

    def test_validate_github_url_invalid_format(self):
        """Test invalidly formatted GitHub URLs."""
        assert validate_github_url("") is False
        assert validate_github_url("http://github.com/owner/repo") is False  # Must be https
        assert validate_github_url("https://gitlab.com/owner/repo") is False # Must be github.com
        assert validate_github_url("https://github.com/owner") is False      # Missing repo
        assert validate_github_url("https://github.com/owner/repo/extra") is False # Too many parts
        assert validate_github_url("https://github.com/owner/repo?query=1") is False # No query
        assert validate_github_url("https://github.com/owner/repo#frag") is False   # No fragment

    def test_validate_github_url_injection_attempts(self):
        """Test URLs with argument injection attempts."""
        assert validate_github_url("https://github.com/owner/repo --upload-pack") is False
        assert validate_github_url("https://github.com/owner/-repo") is False # Repo starts with hyphen
        assert validate_github_url("https://github.com/-owner/repo") is False # Owner starts with hyphen
        assert validate_github_url("https://github.com/owner/repo;ls") is False
        assert validate_github_url("https://github.com/owner/repo\nls") is False
        assert validate_github_url("https://github.com/owner/repo' -oProxyCommand") is False
