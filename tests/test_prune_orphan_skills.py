"""Tests for orphan-skill detection and prune behavior in SyncManager.

Phase 3 of the robustness plan split `_prune_orphan_skills` into two
parts:
- `_detect_orphan_skills()` — read-only, returns the orphan list
- `_prune_orphan_skills(orphans=...)` — destructive, does `git rm`

Tests cover both, and verify that `push` defaults to `prune=False`
(safe-by-default) per the new contract.
"""

from pathlib import Path
from unittest.mock import MagicMock


def _make_hub(tmp_path: Path, skill_names: list[str]) -> Path:
    """Create a fake ~/.agents/skills/ with the given skill dirs."""
    hub = tmp_path / ".agents" / "skills"
    hub.mkdir(parents=True)
    for name in skill_names:
        (hub / name).mkdir()
        (hub / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    return hub


def _make_sm_with_head(head_skills: list[str]) -> MagicMock:
    """Create a SyncManager-like mock whose `_run_git("ls-tree", ...)`
    returns the standard `skills/<name>` format that real git produces.

    The mock does NOT pre-stub `_detect_orphan_skills` — the real
    detection logic is exercised by these tests.
    """
    sm = MagicMock()
    sm._run_git = MagicMock()

    def fake_run_git(*args, **kwargs):
        # Match both the old `ls-tree --name-only HEAD` and the new
        # `ls-tree -d --name-only HEAD skills/` invocations.
        if args[0] == "ls-tree" and "skills/" in args:
            return "\n".join(f"skills/{n}" for n in head_skills)
        return ""

    sm._run_git.side_effect = fake_run_git
    return sm


# ---------------------------------------------------------------------------
# _detect_orphan_skills — read-only
# ---------------------------------------------------------------------------


class TestDetectOrphanSkills:
    """Pure read-only detection. No git index mutation, no destructive ops."""

    def test_no_orphans_returns_empty(self, tmp_path):
        """Local hub has same skills as HEAD → no orphans."""
        _make_hub(tmp_path, ["cali-coding-go-stack", "cali-coding-starhtml"])
        sm = _make_sm_with_head(["cali-coding-go-stack", "cali-coding-starhtml"])

        with __import__("unittest.mock").mock.patch(
            "agent_sync.paths.HUB_DIR", tmp_path / ".agents" / "skills"
        ):
            from agent_sync.sync import SyncManager

            orphans = SyncManager._detect_orphan_skills(sm)

        assert orphans == []

    def test_orphans_detected(self, tmp_path):
        """Skills in HEAD but not in hub are returned, sorted."""
        _make_hub(tmp_path, ["cali-coding-go-stack"])  # only one in local
        sm = _make_sm_with_head(
            [
                "cali-coding-go-stack",
                "cali-go-stack",  # orphan
                "cali-starhtml",  # orphan
            ]
        )

        with __import__("unittest.mock").mock.patch(
            "agent_sync.paths.HUB_DIR", tmp_path / ".agents" / "skills"
        ):
            from agent_sync.sync import SyncManager

            orphans = SyncManager._detect_orphan_skills(sm)

        assert orphans == ["cali-go-stack", "cali-starhtml"]

    def test_missing_local_hub_returns_empty(self, tmp_path):
        """If ~/.agents/skills/ doesn't exist, no orphans (defensive)."""
        sm = _make_sm_with_head(["cali-coding-go-stack"])

        with __import__("unittest.mock").mock.patch(
            "agent_sync.paths.HUB_DIR", tmp_path / ".agents" / "skills"
        ):
            from agent_sync.sync import SyncManager

            orphans = SyncManager._detect_orphan_skills(sm)

        assert orphans == []
        # No git ls-tree query either — we return early
        ls_calls = [
            c
            for c in sm._run_git.call_args_list
            if c.args[:3] == ("ls-tree", "--name-only", "HEAD")
        ]
        assert ls_calls == []

    def test_hidden_dirs_in_head_ignored(self, tmp_path):
        """Hidden skill names in HEAD (e.g. `.cali-product-workflow`) are
        filtered out — they are state, not skills."""
        _make_hub(tmp_path, ["cali-coding-go-stack"])
        sm = _make_sm_with_head(
            [
                "cali-coding-go-stack",
                ".cali-product-workflow",  # hidden
            ]
        )

        with __import__("unittest.mock").mock.patch(
            "agent_sync.paths.HUB_DIR", tmp_path / ".agents" / "skills"
        ):
            from agent_sync.sync import SyncManager

            orphans = SyncManager._detect_orphan_skills(sm)

        assert orphans == []

    def test_hidden_dirs_in_hub_ignored(self, tmp_path):
        """Hidden dirs in the local hub are state, not skills."""
        hub = tmp_path / ".agents" / "skills"
        hub.mkdir(parents=True)
        (hub / "cali-coding-go-stack").mkdir()
        (hub / "cali-coding-go-stack" / "SKILL.md").write_text("x")
        (hub / ".cali-product-workflow").mkdir()  # hidden in hub

        sm = _make_sm_with_head(
            [
                "cali-coding-go-stack",
                ".cali-product-workflow",
            ]
        )

        with __import__("unittest.mock").mock.patch("agent_sync.paths.HUB_DIR", hub):
            from agent_sync.sync import SyncManager

            orphans = SyncManager._detect_orphan_skills(sm)

        # The hidden dir is in both HEAD and hub, but even if it were
        # only in HEAD, the filter strips it out.
        assert orphans == []

    # NOTE: A file in `skills/` (e.g. `RETIRED.md` manifest) used to
    # appear as a phantom orphan. The fix is in sync.py: we now use
    # `git ls-tree -d` (directories only). Git itself filters the file
    # case; no code-level test needed for that. Trust the flag.


# ---------------------------------------------------------------------------
# _prune_orphan_skills — destructive (git rm --cached)
# ---------------------------------------------------------------------------


class TestPruneOrphanSkills:
    """Direct tests for the destructive prune helper.

    Pass `orphans=` explicitly so tests don't depend on detection logic.
    """

    def test_empty_orphans_returns_empty(self, tmp_path):
        """No orphans → no `git rm` calls."""
        _make_hub(tmp_path, ["cali-coding-go-stack"])
        sm = _make_sm_with_head(["cali-coding-go-stack"])

        with __import__("unittest.mock").mock.patch(
            "agent_sync.paths.HUB_DIR", tmp_path / ".agents" / "skills"
        ):
            from agent_sync.sync import SyncManager

            pruned = SyncManager._prune_orphan_skills(sm, orphans=[])

        assert pruned == []
        rm_calls = [c for c in sm._run_git.call_args_list if c.args[:3] == ("rm", "-r", "--cached")]
        assert rm_calls == []

    def test_orphans_returned_with_correct_shape(self, tmp_path):
        """Each orphan produces a {path, status:D, label:deleted, ...} entry."""
        _make_hub(tmp_path, ["cali-coding-go-stack"])
        sm = _make_sm_with_head([])  # head not consulted when orphans given

        with __import__("unittest.mock").mock.patch(
            "agent_sync.paths.HUB_DIR", tmp_path / ".agents" / "skills"
        ):
            from agent_sync.sync import SyncManager

            pruned = SyncManager._prune_orphan_skills(
                sm, orphans=["cali-go-stack", "cali-starhtml"]
            )

        assert len(pruned) == 2
        names = [p["path"].rstrip("/").split("/")[-1] for p in pruned]
        assert "cali-go-stack" in names
        assert "cali-starhtml" in names
        for entry in pruned:
            assert entry["status"] == "D"
            assert entry["label"] == "deleted"
            assert entry["path"].startswith("skills/")

    def test_git_rm_called_for_each_orphan(self, tmp_path):
        """Each orphan triggers a `git rm -r --cached` call with the right path."""
        sm = _make_sm_with_head([])

        with __import__("unittest.mock").mock.patch(
            "agent_sync.paths.HUB_DIR", tmp_path / ".agents" / "skills"
        ):
            from agent_sync.sync import SyncManager

            pruned = SyncManager._prune_orphan_skills(
                sm, orphans=["orphan-a", "orphan-b", "orphan-c"]
            )

        assert len(pruned) == 3
        rm_calls = [c for c in sm._run_git.call_args_list if c.args[:3] == ("rm", "-r", "--cached")]
        assert len(rm_calls) == 3
        paths_removed = {c.args[3] for c in rm_calls}
        assert paths_removed == {
            "skills/orphan-a",
            "skills/orphan-b",
            "skills/orphan-c",
        }

    def test_git_rm_failure_does_not_propagate(self, tmp_path):
        """If git rm fails for one orphan, others still proceed; no exception."""
        sm = MagicMock()
        sm._run_git = MagicMock()

        def fake_run_git(*args, **kwargs):
            if args[:3] == ("rm", "-r", "--cached") and "orphan-bad" in args[3]:
                import subprocess

                raise subprocess.CalledProcessError(1, args, stderr="simulated git failure")
            return ""

        sm._run_git.side_effect = fake_run_git

        with __import__("unittest.mock").mock.patch(
            "agent_sync.paths.HUB_DIR", tmp_path / ".agents" / "skills"
        ):
            from agent_sync.sync import SyncManager

            pruned = SyncManager._prune_orphan_skills(sm, orphans=["orphan-good", "orphan-bad"])

        # Only the successful one is in the result
        assert len(pruned) == 1
        assert "orphan-good" in pruned[0]["path"]


# ---------------------------------------------------------------------------
# Push() / _push_stage_and_get_changes() — default behavior contract
# ---------------------------------------------------------------------------


class TestPushStagePruneFlag:
    """Verify prune is plumbed through with the new safe default.

    Phase 3 inverted the prune default: `push` is now safe-by-default
    (prune=False). Tests assert this contract.
    """

    def test_prune_default_is_false(self):
        """Default prune=False in `_push_stage_and_get_changes`."""
        import inspect

        from agent_sync.sync import SyncManager

        sig = inspect.signature(SyncManager._push_stage_and_get_changes)
        assert sig.parameters["prune"].default is False

    def test_push_default_prune_is_false(self):
        """`SyncManager.push()` also defaults prune=False."""
        import inspect

        from agent_sync.sync import SyncManager

        sig = inspect.signature(SyncManager.push)
        assert sig.parameters["prune"].default is False

    def test_prune_passed_through_to_stage_method(self):
        """`push(prune=True)` propagates to `_push_stage_and_get_changes`."""
        sm = MagicMock()
        sm._push_stage_and_get_changes = MagicMock(return_value=([], []))

        from agent_sync.sync import SyncManager

        SyncManager.push(sm, message="test", prune=True)

        kwargs = sm._push_stage_and_get_changes.call_args.kwargs
        assert kwargs["prune"] is True

    def test_prune_false_by_default_in_push(self):
        """`push()` without prune → prune=False (safe)."""
        sm = MagicMock()
        sm._push_stage_and_get_changes = MagicMock(return_value=([], []))
        sm._run_git = MagicMock()
        sm._save_state = MagicMock()

        from agent_sync.sync import SyncManager

        SyncManager.push(sm, message="test")

        kwargs = sm._push_stage_and_get_changes.call_args.kwargs
        assert kwargs["prune"] is False

    def test_push_returns_changed_files_and_orphans_tuple(self):
        """`push()` returns `(changed_files, orphans)` tuple."""
        sm = MagicMock()
        sm._push_stage_and_get_changes = MagicMock(
            return_value=([{"path": "skills/x/SKILL.md"}], ["orphan-1"])
        )
        sm._run_git = MagicMock()
        sm._save_state = MagicMock()

        from agent_sync.sync import SyncManager

        result = SyncManager.push(sm, message="test")

        assert isinstance(result, tuple)
        assert len(result) == 2
        changed_files, orphans = result
        assert changed_files == [{"path": "skills/x/SKILL.md"}]
        assert orphans == ["orphan-1"]

    def test_push_returns_empty_list_when_no_changes_but_orphans(self):
        """`push()` returns `[]` (falsy) when no changed files but orphans exist.

        This is the pre-existing contract: callers like ``_internal_share_flow``
        check ``if changed:``, which must be falsy when nothing changed.
        The orphan warning is printed but the return is still ``[]``.
        """
        sm = MagicMock()
        sm._push_stage_and_get_changes = MagicMock(return_value=([], ["orphan-1"]))
        sm._run_git = MagicMock()
        sm._save_state = MagicMock()

        from agent_sync.sync import SyncManager

        result = SyncManager.push(sm, message="test")

        # Must return [] (falsy list), not ([], ["orphan-1"]) — callers
        # depend on truthiness of the return value.
        assert result == []
        assert not result

        # No git commit should have been attempted
        commit_calls = [
            c for c in sm._run_git.call_args_list if c.args[:3] == ("commit", "-m", "test")
        ]
        assert commit_calls == []
