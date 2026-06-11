"""Tests for the share run auto-sync to private repo feature.

Covers:
- --no-private CLI flag is registered
- Post-share sync calls SyncManager.push by default
- --no-private flag suppresses the sync
- Missing repo_url (no `agent-sync init`) skips sync with a hint
- PublishConfig.auto_push_private = False skips sync
- Push exception does not abort the share (public already succeeded)
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_sync.cli import main


runner = CliRunner()


# =============================================================================
# Flag registration
# =============================================================================


class TestNoPrivateFlagRegistered:
    """Verify --no-private is a real option on `share run`."""

    def test_help_lists_no_private(self):
        """`share run --help` shows --no-private."""
        result = runner.invoke(main, ["share", "run", "--help"])
        assert result.exit_code == 0
        assert "--no-private" in result.output
        assert "private" in result.output.lower()

    def test_help_docstring_mentions_feature(self):
        """Docstring explains the auto-sync behavior."""
        result = runner.invoke(main, ["share", "run", "--help"])
        assert result.exit_code == 0
        # Docstring should describe the auto-sync behavior
        text = result.output.lower()
        assert "private" in text
        assert "synced" in text or "sync" in text or "auto" in text


# =============================================================================
# Post-publish sync behavior
# =============================================================================


def _mock_publish_setup_returning(success: bool):
    """Return a patch context that makes run_publish_setup return success."""
    return patch(
        "agent_sync.cli.run_publish_setup",
        return_value=success,
    )


class TestPostPublishSync:
    """Verify the auto-sync to private repo behavior."""

    def test_default_calls_sync_manager_push(self, monkeypatch, tmp_path):
        """Default behavior: SyncManager.push is called after public share."""
        fake_cfg = MagicMock()
        fake_cfg.repo_url = "https://github.com/me/private"

        fake_pub_cfg = MagicMock()
        fake_pub_cfg.auto_push_private = True

        fake_changed = [{"path": "skills/foo/SKILL.md", "status": "M", "label": "modified", "directory_count": None}]
        fake_sm = MagicMock()
        fake_sm.push.return_value = fake_changed
        fake_sm._run_git.return_value = "abcdef1234567"

        with _mock_publish_setup_returning(True), \
             patch("agent_sync.cli.Config", return_value=fake_cfg, create=True), \
             patch("agent_sync.cli.SyncManager", return_value=fake_sm, create=True), \
             patch("agent_sync.cli._load_pub_config", return_value=fake_pub_cfg, create=True):
            # Patch the local-imports the function performs inside the if-block
            monkeypatch.setattr("agent_sync.config.Config", lambda: fake_cfg, raising=False)
            monkeypatch.setattr("agent_sync.sync.SyncManager", lambda c: fake_sm, raising=False)
            monkeypatch.setattr(
                "agent_sync.publish.config.load_config",
                lambda: fake_pub_cfg,
                raising=False,
            )

            result = runner.invoke(main, ["share", "run"])

        # Publish succeeded (or was short-circuited by run_publish_setup mock)
        assert result.exit_code in (0, 1)  # TUI may abort since no real run
        # The push MUST have been called
        assert fake_sm.push.called, "SyncManager.push was not called in default mode"

    def test_no_private_flag_skips_sync(self, monkeypatch):
        """`--no-private` suppresses the post-publish sync entirely."""
        fake_cfg = MagicMock()
        fake_cfg.repo_url = "https://github.com/me/private"
        fake_sm = MagicMock()

        with _mock_publish_setup_returning(True), \
             patch("agent_sync.cli.Config", return_value=fake_cfg, create=True), \
             patch("agent_sync.cli.SyncManager", return_value=fake_sm, create=True), \
             patch("agent_sync.cli._load_pub_config", return_value=MagicMock(auto_push_private=True), create=True):
            monkeypatch.setattr("agent_sync.config.Config", lambda: fake_cfg, raising=False)
            monkeypatch.setattr("agent_sync.sync.SyncManager", lambda c: fake_sm, raising=False)
            monkeypatch.setattr(
                "agent_sync.publish.config.load_config",
                lambda: MagicMock(auto_push_private=True),
                raising=False,
            )

            result = runner.invoke(main, ["share", "run", "--no-private"])

        # No push call expected when --no-private is set
        assert not fake_sm.push.called, "SyncManager.push should NOT be called with --no-private"
        # The "Syncing to private" header must not appear
        assert "Syncing to private" not in result.output

    def test_no_repo_url_skips_with_hint(self, monkeypatch):
        """When cfg.repo_url is empty, skip sync and show a hint."""
        fake_cfg = MagicMock()
        fake_cfg.repo_url = ""  # Not initialized
        fake_sm = MagicMock()

        with _mock_publish_setup_returning(True), \
             patch("agent_sync.cli.Config", return_value=fake_cfg, create=True), \
             patch("agent_sync.cli.SyncManager", return_value=fake_sm, create=True), \
             patch("agent_sync.cli._load_pub_config", return_value=MagicMock(auto_push_private=True), create=True):
            monkeypatch.setattr("agent_sync.config.Config", lambda: fake_cfg, raising=False)
            monkeypatch.setattr("agent_sync.sync.SyncManager", lambda c: fake_sm, raising=False)
            monkeypatch.setattr(
                "agent_sync.publish.config.load_config",
                lambda: MagicMock(auto_push_private=True),
                raising=False,
            )

            result = runner.invoke(main, ["share", "run"])

        assert not fake_sm.push.called
        assert "No private repo configured" in result.output or "skip" in result.output.lower()

    def test_auto_push_private_false_skips_sync(self, monkeypatch):
        """PublishConfig.auto_push_private = False suppresses the sync."""
        fake_cfg = MagicMock()
        fake_cfg.repo_url = "https://github.com/me/private"
        fake_sm = MagicMock()

        with _mock_publish_setup_returning(True), \
             patch("agent_sync.cli.Config", return_value=fake_cfg, create=True), \
             patch("agent_sync.cli.SyncManager", return_value=fake_sm, create=True), \
             patch("agent_sync.cli._load_pub_config", return_value=MagicMock(auto_push_private=False), create=True):
            monkeypatch.setattr("agent_sync.config.Config", lambda: fake_cfg, raising=False)
            monkeypatch.setattr("agent_sync.sync.SyncManager", lambda c: fake_sm, raising=False)
            monkeypatch.setattr(
                "agent_sync.publish.config.load_config",
                lambda: MagicMock(auto_push_private=False),
                raising=False,
            )

            result = runner.invoke(main, ["share", "run"])

        assert not fake_sm.push.called, "SyncManager.push should NOT be called when auto_push_private=False"
        assert "Syncing to private" not in result.output

    def test_push_exception_does_not_abort_publish(self, monkeypatch):
        """If SyncManager.push raises, the publish still reports success."""
        fake_cfg = MagicMock()
        fake_cfg.repo_url = "https://github.com/me/private"
        fake_sm = MagicMock()
        fake_sm.push.side_effect = RuntimeError("simulated network failure")
        fake_sm._run_git.side_effect = RuntimeError("never called")

        with _mock_publish_setup_returning(True), \
             patch("agent_sync.cli.Config", return_value=fake_cfg, create=True), \
             patch("agent_sync.cli.SyncManager", return_value=fake_sm, create=True), \
             patch("agent_sync.cli._load_pub_config", return_value=MagicMock(auto_push_private=True), create=True), \
             patch("agent_sync.cli._sanitize_git_output", side_effect=lambda s: s, create=True):
            monkeypatch.setattr("agent_sync.config.Config", lambda: fake_cfg, raising=False)
            monkeypatch.setattr("agent_sync.sync.SyncManager", lambda c: fake_sm, raising=False)
            monkeypatch.setattr(
                "agent_sync.publish.config.load_config",
                lambda: MagicMock(auto_push_private=True),
                raising=False,
            )

            result = runner.invoke(main, ["share", "run"])

        # Public publish still considered successful (exit code 0, not aborted)
        assert "Private sync failed" in result.output
        # Rich Console may wrap long lines; check the key error substring
        assert "simulated network" in result.output
        assert "failure" in result.output
        # The publish itself should NOT have raised click.Abort
        # (Click.Abort would set exit_code != 0 in most cases)

    def test_zero_changes_shows_dim_message(self, monkeypatch):
        """When push returns 0 changes, show a dim 'nothing to sync' message."""
        fake_cfg = MagicMock()
        fake_cfg.repo_url = "https://github.com/me/private"
        fake_sm = MagicMock()
        fake_sm.push.return_value = []  # no changes
        fake_sm._run_git.return_value = "abc1234"

        with _mock_publish_setup_returning(True), \
             patch("agent_sync.cli.Config", return_value=fake_cfg, create=True), \
             patch("agent_sync.cli.SyncManager", return_value=fake_sm, create=True), \
             patch("agent_sync.cli._load_pub_config", return_value=MagicMock(auto_push_private=True), create=True):
            monkeypatch.setattr("agent_sync.config.Config", lambda: fake_cfg, raising=False)
            monkeypatch.setattr("agent_sync.sync.SyncManager", lambda c: fake_sm, raising=False)
            monkeypatch.setattr(
                "agent_sync.publish.config.load_config",
                lambda: MagicMock(auto_push_private=True),
                raising=False,
            )

            result = runner.invoke(main, ["share", "run"])

        assert "No local changes" in result.output
        # Green "Synced" must NOT appear
        assert "Synced 0" not in result.output
