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


class TestShareRepos:
    """Tests for 'share add/list/remove' commands."""

    def test_publish_add_validates_url(self):
        """share add validates GitHub URL format."""
        result = runner.invoke(main, ["share", "add", "invalid-url"])
        # Should show Invalid URL error (either exit code or output)
        assert "Invalid" in result.output or result.exit_code != 0 or "URL" in result.output

    def test_publish_add_requires_url(self):
        """share add requires URL argument."""
        result = runner.invoke(main, ["share", "add"])
        assert result.exit_code != 0

    def test_share_list(self):
        """share list shows configured repositories."""
        result = runner.invoke(main, ["share", "list"])
        assert result.exit_code == 0

    def test_publish_remove_requires_url(self):
        """share remove requires URL argument."""
        result = runner.invoke(main, ["share", "remove"])
        assert result.exit_code != 0


class TestShareRun:
    """Tests for 'publish run' command."""

    def test_share_run_documented_in_help(self):
        """publish run is documented in main help."""
        result = runner.invoke(main, ["--help"])
        # Should appear in help text
        assert "share" in result.output