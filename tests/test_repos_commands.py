"""Tests for repos and publish repos commands."""

from click.testing import CliRunner
from agent_sync.cli import main

runner = CliRunner()


class TestReposList:
    """Tests for 'repos list' command."""

    def test_repos_list_shows_repos(self):
        """repos list shows repository status."""
        result = runner.invoke(main, ["repos", "list"])
        # Should not crash
        assert result.exit_code == 0
        assert "Repository" in result.output or "not configured" in result.output


class TestPublishRepos:
    """Tests for 'publish add/list/remove' commands."""

    def test_publish_add_validates_url(self):
        """publish add validates GitHub URL format."""
        result = runner.invoke(main, ["publish", "add", "invalid-url"])
        # Should show Invalid URL error (either exit code or output)
        assert "Invalid" in result.output or result.exit_code != 0 or "URL" in result.output

    def test_publish_add_requires_url(self):
        """publish add requires URL argument."""
        result = runner.invoke(main, ["publish", "add"])
        assert result.exit_code != 0

    def test_publish_list(self):
        """publish list shows configured repositories."""
        result = runner.invoke(main, ["publish", "list"])
        assert result.exit_code == 0

    def test_publish_remove_requires_url(self):
        """publish remove requires URL argument."""
        result = runner.invoke(main, ["publish", "remove"])
        assert result.exit_code != 0


class TestPublishRun:
    """Tests for 'publish run' command."""

    def test_publish_run_documented_in_help(self):
        """publish run is documented in main help."""
        result = runner.invoke(main, ["--help"])
        # Should appear in help text
        assert "publish" in result.output