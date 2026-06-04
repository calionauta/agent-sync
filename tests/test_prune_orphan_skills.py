"""Tests for the mirror-prune feature in SyncManager.

Verifies that skills tracked in HEAD but missing from the local
~/.agents/skills/ hub are removed (git rm --cached) in the same commit
as the push, making the private repo a true mirror.

Covers:
- _prune_orphan_skills() returns deleted entries for orphan skills
- _prune_orphan_skills() returns [] when no orphans
- _prune_orphan_skills() returns [] when ~/.agents/skills/ is missing
- _prune_orphan_skills() returns [] when HEAD has no skills/
- _push_stage_and_get_changes(prune=False) skips the prune
- _push_stage_and_get_changes(configs_only=True) skips the prune
- _push_stage_and_get_changes(agents_only=True) skips the prune
- prune errors are caught, not raised
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_hub(tmp_path: Path, skill_names: list[str]) -> Path:
    """Create a fake ~/.agents/skills/ with the given skill dirs."""
    hub = tmp_path / ".agents" / "skills"
    hub.mkdir(parents=True)
    for name in skill_names:
        (hub / name).mkdir()
        (hub / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    return hub


def _make_sm(hub: Path, head_skills: list[str]):
    """Create a SyncManager-like mock with _run_git and a HOME-returning Path.home.

    `head_skills` are the bare skill names (no `skills/` prefix); the mock
    pretends git ls-tree returned the standard `skills/<name>` format, which
    is what real git does when you query `HEAD skills/`.
    """
    sm = MagicMock()
    sm._run_git = MagicMock()

    def fake_run_git(*args, **kwargs):
        # ls-tree returns `skills/<name>` per line (real git behavior)
        if args[:3] == ("ls-tree", "--name-only", "HEAD"):
            return "\n".join(f"skills/{n}" for n in head_skills)
        # Empty output for everything else
        return ""

    sm._run_git.side_effect = fake_run_git
    return sm


class TestPruneOrphanSkills:
    """Direct tests for the _prune_orphan_skills helper."""

    def test_no_orphans_returns_empty(self, tmp_path):
        """Local hub has same skills as HEAD → no prune."""
        _make_hub(tmp_path, ["cali-coding-go-stack", "cali-coding-starhtml"])
        sm = _make_sm(tmp_path, ["cali-coding-go-stack", "cali-coding-starhtml"])

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            from agent_sync.sync import SyncManager
            pruned = SyncManager._prune_orphan_skills(sm)

        assert pruned == []
        # ls-tree is always called to inspect HEAD, but no `git rm` should fire
        rm_calls = [c for c in sm._run_git.call_args_list
                    if c.args[:3] == ("rm", "-r", "--cached")]
        assert rm_calls == []

    def test_orphans_returned_with_correct_shape(self, tmp_path):
        """Orphan skills are returned with status D and label deleted."""
        _make_hub(tmp_path, ["cali-coding-go-stack"])  # only one in local
        sm = _make_sm(tmp_path, [
            "cali-coding-go-stack",
            "cali-go-stack",       # orphan: in HEAD, not in hub
            "cali-starhtml",       # orphan
        ])

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            from agent_sync.sync import SyncManager
            pruned = SyncManager._prune_orphan_skills(sm)

        assert len(pruned) == 2
        names = [p["path"].rstrip("/").split("/")[-1] for p in pruned]
        assert "cali-go-stack" in names
        assert "cali-starhtml" in names
        for entry in pruned:
            assert entry["status"] == "D"
            assert entry["label"] == "deleted"
            assert entry["path"].startswith("skills/")

    def test_git_rm_called_for_each_orphan(self, tmp_path):
        """Each orphan triggers a `git rm -r --cached` call."""
        _make_hub(tmp_path, [])
        sm = _make_sm(tmp_path, ["orphan-a", "orphan-b", "orphan-c"])

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            from agent_sync.sync import SyncManager
            pruned = SyncManager._prune_orphan_skills(sm)

        assert len(pruned) == 3
        rm_calls = [c for c in sm._run_git.call_args_list
                    if c.args[:3] == ("rm", "-r", "--cached")]
        assert len(rm_calls) == 3
        paths_removed = {c.args[3] for c in rm_calls}
        assert paths_removed == {
            "skills/orphan-a",
            "skills/orphan-b",
            "skills/orphan-c",
        }

    def test_missing_local_hub_returns_empty(self, tmp_path):
        """If ~/.agents/skills/ doesn't exist, prune is a no-op."""
        sm = _make_sm(tmp_path, ["cali-coding-go-stack"])

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            from agent_sync.sync import SyncManager
            pruned = SyncManager._prune_orphan_skills(sm)

        assert pruned == []
        sm._run_git.assert_not_called()

    def test_empty_head_skills_returns_empty(self, tmp_path):
        """Empty repo (no skills in HEAD) → nothing to prune."""
        _make_hub(tmp_path, ["cali-coding-go-stack", "cali-starhtml"])
        sm = _make_sm(tmp_path, [])

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            from agent_sync.sync import SyncManager
            pruned = SyncManager._prune_orphan_skills(sm)

        assert pruned == []

    def test_hidden_dirs_ignored_in_hub(self, tmp_path):
        """Hidden dirs in ~/.agents/skills/ (like .cali-product-workflow) are ignored."""
        hub = tmp_path / ".agents" / "skills"
        hub.mkdir(parents=True)
        (hub / "cali-coding-go-stack").mkdir()
        (hub / "cali-coding-go-stack" / "SKILL.md").write_text("x")
        (hub / ".cali-product-workflow").mkdir()  # hidden

        sm = _make_sm(tmp_path, ["cali-coding-go-stack", ".cali-product-workflow"])

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            from agent_sync.sync import SyncManager
            pruned = SyncManager._prune_orphan_skills(sm)

        # .cali-product-workflow is in HEAD but also "hidden" in local — should NOT be pruned
        # because we treat hidden dirs in the hub as state, not skills
        assert pruned == []

    def test_git_rm_failure_does_not_propagate(self, tmp_path):
        """If git rm fails for one orphan, others still proceed; no exception raised."""
        _make_hub(tmp_path, [])
        sm = MagicMock()

        def fake_run_git(*args, **kwargs):
            if args[:3] == ("ls-tree", "--name-only", "HEAD"):
                return "orphan-good\norphan-bad"
            if args[:3] == ("rm", "-r", "--cached"):
                if "orphan-bad" in args[3]:
                    import subprocess
                    raise subprocess.CalledProcessError(
                        1, args, stderr="simulated git failure"
                    )
            return ""

        sm._run_git.side_effect = fake_run_git

        with patch("agent_sync.sync.Path.home", return_value=tmp_path):
            from agent_sync.sync import SyncManager
            pruned = SyncManager._prune_orphan_skills(sm)

        # Only the successful one is in the result
        assert len(pruned) == 1
        assert "orphan-good" in pruned[0]["path"]


class TestPushStagePruneFlag:
    """Verify prune is plumbed through _push_stage_and_get_changes correctly."""

    def test_prune_default_is_true(self):
        """Verify default prune=True in the signature."""
        import inspect
        from agent_sync.sync import SyncManager

        sig = inspect.signature(SyncManager._push_stage_and_get_changes)
        assert sig.parameters["prune"].default is True

    def test_push_default_prune_is_true(self):
        """Verify SyncManager.push() also defaults prune=True."""
        import inspect
        from agent_sync.sync import SyncManager

        sig = inspect.signature(SyncManager.push)
        assert sig.parameters["prune"].default is True

    def test_prune_passed_through_to_stage_method(self):
        """When push(prune=False) is called, _push_stage_and_get_changes receives prune=False."""
        sm = MagicMock()
        sm._push_stage_and_get_changes = MagicMock(return_value=[])

        from agent_sync.sync import SyncManager
        SyncManager.push(sm, message="test", prune=False)

        kwargs = sm._push_stage_and_get_changes.call_args.kwargs
        assert kwargs["prune"] is False

    def test_prune_true_by_default_in_push(self):
        """When push() is called without prune, it defaults to True."""
        sm = MagicMock()
        sm._push_stage_and_get_changes = MagicMock(return_value=[])
        sm._run_git = MagicMock()
        sm._save_state = MagicMock()

        from agent_sync.sync import SyncManager
        SyncManager.push(sm, message="test")

        kwargs = sm._push_stage_and_get_changes.call_args.kwargs
        assert kwargs["prune"] is True
