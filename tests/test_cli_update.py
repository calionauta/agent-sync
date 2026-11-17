"""Tests for `agent-sync update` and `agent-sync version`.

agent-sync is distributed from its GitHub tags, not PyPI: the `agent-sync`
distribution on PyPI belongs to an unrelated project. So `update` must:

1. never run `pipx upgrade` for a source checkout (it would either fail or
   install something else),
2. tell the user the exact command for the way *this* copy was installed,
3. report the latest release without raising when the network is down.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_sync.cli import (
    _describe_install,
    _install_kind,
    _latest_release_tag,
    _safe_version,
    _update_command,
    main,
)

runner = CliRunner()


def _dist_with(direct_url: dict | None, raw_text: str | None = None):
    """Fake importlib.metadata distribution.

    `raw_text=None` means "no direct_url.json at all" (plain index install).
    """
    dist = MagicMock()
    if raw_text is not None:
        dist.read_text.return_value = raw_text
    elif direct_url is None:
        dist.read_text.return_value = None
    else:
        dist.read_text.return_value = json.dumps(direct_url)
    return dist


EDITABLE = {"url": "file:///Users/me/agent-sync", "dir_info": {"editable": True}}
VCS = {
    "url": "https://github.com/calionauta/agent-sync.git",
    "vcs_info": {"vcs": "git", "requested_revision": "v0.44.6-alpha", "commit_id": "abc1234def"},
}


class TestInstallKind:
    def test_editable_checkout(self):
        with patch("importlib.metadata.distribution", return_value=_dist_with(EDITABLE)):
            kind, detail = _install_kind()
        assert kind == "editable"
        assert detail["dir_info"]["editable"] is True

    def test_git_install(self):
        with patch("importlib.metadata.distribution", return_value=_dist_with(VCS)):
            assert _install_kind()[0] == "vcs"

    def test_plain_index_install_has_no_direct_url(self):
        with patch("importlib.metadata.distribution", return_value=_dist_with(None, raw_text=None)):
            assert _install_kind()[0] == "pypi"

    def test_missing_metadata_does_not_raise(self):
        with patch("importlib.metadata.distribution", side_effect=Exception("nope")):
            assert _install_kind() == ("unknown", {})

    def test_malformed_direct_url_does_not_raise(self):
        with patch("importlib.metadata.distribution", return_value=_dist_with(None, "{oops")):
            assert _install_kind()[0] == "unknown"


class TestDescribeInstall:
    def test_editable_hides_file_scheme(self):
        text = _describe_install("editable", EDITABLE)
        assert "editable source checkout" in text
        assert "file://" not in text
        assert "/Users/me/agent-sync" in text

    def test_vcs_includes_ref(self):
        text = _describe_install("vcs", VCS)
        assert "v0.44.6-alpha" in text

    def test_unknown(self):
        assert "unknown" in _describe_install("unknown", {})


class TestUpdateCommand:
    def test_editable_uses_git_pull(self):
        cmd = _update_command("editable", EDITABLE, "v0.44.6-alpha")
        assert cmd == "git pull --ff-only && uv pip install -e ."

    def test_vcs_pins_the_release_tag(self):
        cmd = _update_command("vcs", VCS, "v0.44.7-alpha")
        assert cmd == (
            'pipx install --force "git+https://github.com/calionauta/agent-sync.git@v0.44.7-alpha"'
        )

    def test_unknown_kind_points_at_the_releases_page(self):
        cmd = _update_command("unknown", {}, None)
        assert "github.com/calionauta/agent-sync/releases/latest" in cmd


class TestLatestReleaseTag:
    def test_returns_tag(self):
        response = MagicMock()
        response.json.return_value = {"tag_name": "v0.44.6-alpha"}
        with patch("requests.get", return_value=response):
            assert _latest_release_tag() == ("v0.44.6-alpha", None)

    def test_network_error_is_not_fatal(self):
        with patch("requests.get", side_effect=OSError("no route to host")):
            tag, error = _latest_release_tag()
        assert tag is None
        assert "no route" in error

    def test_missing_tag_is_reported(self):
        response = MagicMock()
        response.json.return_value = {}
        with patch("requests.get", return_value=response):
            tag, error = _latest_release_tag()
        assert tag is None
        assert "no tag" in error


class TestSafeVersion:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("v0.44.6-alpha", "0.44.6a0"),
            ("0.44.6a0", "0.44.6a0"),
            ("1.2.0", "1.2.0"),
        ],
    )
    def test_normalizes_tags(self, raw, expected):
        assert str(_safe_version(raw)) == expected

    def test_garbage_is_none(self):
        assert _safe_version("not-a-version") is None


class TestUpdateCLI:
    def _invoke(self, args, kind="editable", detail=None, tag="v0.44.6-alpha", error=None):
        detail = EDITABLE if detail is None else detail
        response = MagicMock()
        response.json.return_value = {"tag_name": tag}

        with (
            # Version comes from hatch-vcs, which reports 0.1.devN on a shallow
            # clone (CI checks out with fetch-depth: 1 and no tags). Pin it so
            # the comparison under test does not depend on the checkout depth.
            patch("agent_sync.__version__", "0.44.6a0"),
            patch("agent_sync.cli._install_kind", return_value=(kind, detail)),
            patch(
                "agent_sync.cli._latest_release_tag",
                return_value=(tag, error),
            ),
            patch("agent_sync.cli.subprocess.run") as run,
        ):
            result = runner.invoke(main, ["update", *args])
        return result, run

    def test_check_reports_up_to_date(self):
        result, run = self._invoke(["--check"])
        assert result.exit_code == 0
        assert "Up to date" in result.output
        run.assert_not_called()

    def test_check_reports_newer_release(self):
        result, _ = self._invoke(["--check"], tag="v0.44.7-alpha")
        assert "Newer release available: v0.44.7-alpha" in result.output

    def test_check_survives_network_failure(self):
        result, _ = self._invoke(["--check"], tag=None, error="timed out")
        assert result.exit_code == 0
        assert "Could not check GitHub" in result.output

    def test_editable_never_runs_pipx(self):
        result, run = self._invoke([])
        run.assert_not_called()
        assert "not upgraded here" in result.output
        assert "git pull --ff-only" in result.output

    def test_vcs_never_runs_pipx_either(self):
        result, run = self._invoke([], kind="vcs", detail=VCS)
        run.assert_not_called()
        assert "pipx install --force" in result.output

    def test_version_shows_install_source(self):
        with patch("agent_sync.cli._install_kind", return_value=("editable", EDITABLE)):
            result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert "editable source checkout" in result.output
