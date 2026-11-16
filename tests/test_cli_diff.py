"""Tests for `agent-sync diff`.

`diff` used to be a stub: it printed bare "Skills Diff:" / "Configs Diff:"
headers and nothing else, while being advertised in the top-level help.
These tests pin the real contract — report what `backup` would push,
honour `--skills` / `--configs`, never commit, and support `--exit-code`
for CI.
"""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from agent_sync.cli import main

runner = CliRunner()

REPO = "https://github.com/me/private"


def _fake_config(repo_url: str | None = REPO):
    cfg = MagicMock()
    cfg.repo_url = repo_url
    return cfg


def _change(path: str, status: str = "M", count: int | None = None) -> dict:
    return {
        "path": path,
        "status": status,
        "label": "modified",
        "directory_count": count,
    }


def _invoke(args: list[str], changes: list[dict], orphans: list[str] | None = None, repo_url=REPO):
    """Run the CLI with SyncManager stubbed to report `changes`."""
    fake_sm = MagicMock()
    fake_sm._push_stage_and_get_changes.return_value = (changes, orphans or [])
    with (
        patch("agent_sync.cli.Config", return_value=_fake_config(repo_url)),
        patch("agent_sync.cli.SyncManager", return_value=fake_sm),
    ):
        result = runner.invoke(main, args)
    return result, fake_sm


class TestDiffReportsChanges:
    def test_lists_skill_changes(self):
        result, _ = _invoke(["diff"], [_change("skills/foo/SKILL.md")])

        assert result.exit_code == 0
        assert "foo/SKILL.md" in result.output
        assert "1 item(s)" in result.output

    def test_is_no_longer_a_stub(self):
        """The old stub printed 'Skills Diff:' with no content."""
        result, _ = _invoke(["diff"], [_change("skills/foo/SKILL.md")])

        assert "Skills Diff:" not in result.output
        assert "Configs Diff:" not in result.output

    def test_reports_clean_state(self):
        result, _ = _invoke(["diff"], [])

        assert result.exit_code == 0
        assert "Nothing to push" in result.output

    def test_warns_about_orphans(self):
        result, _ = _invoke(["diff"], [], orphans=["ghost-skill"])

        assert "ghost-skill" in result.output

    def test_never_commits_or_pushes(self):
        result, fake_sm = _invoke(["diff"], [_change("skills/foo/SKILL.md")])

        fake_sm._run_git.assert_not_called()
        assert "Pushed" not in result.output


class TestDiffExitCode:
    def test_exit_code_zero_when_clean(self):
        result, _ = _invoke(["diff", "--exit-code"], [])
        assert result.exit_code == 0

    def test_exit_code_one_when_dirty(self):
        result, _ = _invoke(["diff", "--exit-code"], [_change("skills/foo/SKILL.md")])
        assert result.exit_code == 1

    def test_exit_code_ignored_without_flag(self):
        result, _ = _invoke(["diff"], [_change("skills/foo/SKILL.md")])
        assert result.exit_code == 0


class TestDiffScope:
    """--skills / --configs must filter the report, not just the staging."""

    def test_skills_only_hides_config_changes(self):
        result, _ = _invoke(
            ["diff", "--skills"],
            [_change("skills/foo/SKILL.md"), _change("configs/claude.json")],
        )

        assert "foo/SKILL.md" in result.output
        assert "claude.json" not in result.output

    def test_configs_only_hides_skill_changes(self):
        result, _ = _invoke(
            ["diff", "--configs"],
            [_change("skills/foo/SKILL.md"), _change("configs/claude.json")],
        )

        assert "claude.json" in result.output
        assert "foo/SKILL.md" not in result.output

    def test_exit_code_uses_visible_changes_only(self):
        """Dirty configs must not fail `diff --skills --exit-code`."""
        result, _ = _invoke(
            ["diff", "--skills", "--exit-code"],
            [_change("configs/claude.json")],
        )
        assert result.exit_code == 0

    def test_staging_filters_reach_sync_manager(self):
        _, fake_sm = _invoke(["diff", "--skills"], [])
        kwargs = fake_sm._push_stage_and_get_changes.call_args.kwargs

        assert kwargs["skills_only"] is True
        assert kwargs["configs_only"] is False


class TestDiffUninitialized:
    def test_not_initialized_is_graceful(self):
        result, fake_sm = _invoke(["diff"], [], repo_url=None)

        assert result.exit_code == 0
        assert "Not initialized" in result.output
        fake_sm._push_stage_and_get_changes.assert_not_called()
