"""Tests for _stage_pi_extra_paths directory coverage.

Regression test for the bug where `prompts` and `themes` keys in
extra_paths were present in the registry and read by restore, but
silently absent from the stage category_map. Result: themes with content
on disk never made it to the private backup repo.
"""

from pathlib import Path
from unittest.mock import Mock

from agent_sync.sync import SyncManager


def _make_sm(repo_dir: Path) -> SyncManager:
    """Build a SyncManager whose repo_dir points to tmp_path."""
    sm = SyncManager.__new__(SyncManager)
    sm.repo_dir = repo_dir
    return sm


def _make_pi_agent(tmp_path: Path) -> Mock:
    """Build a fake pi.dev agent with realistic extra_paths."""
    prompts_src = tmp_path / "prompts_src"
    themes_src = tmp_path / "themes_src"
    extensions_src = tmp_path / "extensions_src"
    hooks_src = tmp_path / "hooks_src"
    prompts_src.mkdir()
    themes_src.mkdir()
    extensions_src.mkdir()
    hooks_src.mkdir()

    (prompts_src / "foo.md").write_text("prompt content")
    (themes_src / "opencode.json").write_text('{"name":"opencode"}')
    (extensions_src / "ext1.ts").write_text("// ext")
    (hooks_src / "hooks.yaml").write_text("tool.after.bash: go build")

    agent = Mock()
    agent.name = "pi.dev"
    agent.prompts_paths = [prompts_src]
    agent.themes_paths = [themes_src]
    agent.extensions_paths = [extensions_src]
    agent.hooks_paths = [hooks_src]
    agent.lsp_paths = []
    agent.models_paths = []
    agent.pyrightconfig_paths = []
    agent.packages_paths = []
    return agent


class TestStagePiExtraPaths:
    """Coverage test for the stage category_map."""

    def test_prompts_dir_staged(self, tmp_path: Path) -> None:
        """prompts/ must be written to configs/pi.dev/prompts/."""
        sm = _make_sm(tmp_path / "repo")
        sm._stage_pi_extra_paths(_make_pi_agent(tmp_path))

        dest = sm.repo_dir / "configs" / "pi.dev" / "prompts"
        assert dest.exists(), f"prompts/ not staged at {dest}"
        assert (dest / "foo.md").read_text() == "prompt content"

    def test_themes_dir_staged(self, tmp_path: Path) -> None:
        """themes/ must be written to configs/pi.dev/themes/."""
        sm = _make_sm(tmp_path / "repo")
        sm._stage_pi_extra_paths(_make_pi_agent(tmp_path))

        dest = sm.repo_dir / "configs" / "pi.dev" / "themes"
        assert dest.exists(), f"themes/ not staged at {dest}"
        assert (dest / "opencode.json").read_text() == '{"name":"opencode"}'

    def test_hooks_dir_staged(self, tmp_path: Path) -> None:
        """hooks/ must be written to configs/pi.dev/hooks/."""
        sm = _make_sm(tmp_path / "repo")
        sm._stage_pi_extra_paths(_make_pi_agent(tmp_path))

        dest = sm.repo_dir / "configs" / "pi.dev" / "hook"
        assert dest.exists(), f"hook/ not staged at {dest}"
        assert (dest / "hooks.yaml").read_text() == "tool.after.bash: go build"

    def test_extensions_dir_still_staged(self, tmp_path: Path) -> None:
        """Existing extensions/ coverage must not regress."""
        sm = _make_sm(tmp_path / "repo")
        sm._stage_pi_extra_paths(_make_pi_agent(tmp_path))

        dest = sm.repo_dir / "configs" / "pi.dev" / "extensions"
        assert dest.exists(), "extensions/ should still be staged"
        assert (dest / "ext1.ts").read_text() == "// ext"
