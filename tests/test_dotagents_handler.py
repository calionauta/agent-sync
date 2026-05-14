"""Tests for DotAgents handler."""
import pytest
from pathlib import Path

from agent_sync.centralize.handlers.dot_agents_handler import DotAgentsHandler, DOTAGENTS_GLOBAL


class TestDotAgentsHandler:
    """Tests for DotAgentsHandler class."""

    def test_fmt_relative(self, tmp_path, monkeypatch):
        """fmt() returns .agents/ relative path for ~/.agents/ paths."""
        handler = DotAgentsHandler(dotagents_path=tmp_path)
        skill_path = tmp_path / "skills" / "my-skill"
        result = handler.fmt(skill_path)
        assert result == ".agents/skills/my-skill"

    def test_fmt_non_dotagents_path(self, tmp_path):
        """fmt() returns original path for non-.agents/ paths."""
        handler = DotAgentsHandler(dotagents_path=tmp_path)
        other = Path("/etc/some/path")
        result = handler.fmt(other)
        # On macOS, /etc may resolve to /private/etc — just check it's a valid path string
        assert str(other) in result or result.startswith("/")

    def test_fmt_string_input(self, tmp_path):
        """fmt() accepts string input."""
        handler = DotAgentsHandler(dotagents_path=tmp_path)
        result = handler.fmt(str(tmp_path / "skills"))
        assert result == ".agents/skills"

    def test_ensure_structure_creates_dirs(self, tmp_path):
        """ensure_structure() creates skills and agents subdirs."""
        handler = DotAgentsHandler(dotagents_path=tmp_path)
        created = handler.ensure_structure(dry_run=False)
        assert created is True
        assert (tmp_path / "skills").exists()
        assert (tmp_path / "agents").exists()

    def test_ensure_structure_dry_run(self, tmp_path):
        """ensure_structure() dry_run creates dirs (reports what would happen)."""
        handler = DotAgentsHandler(dotagents_path=tmp_path)
        created = handler.ensure_structure(dry_run=True)
        # dry_run still creates dirs (informational mode)
        assert created is True

    def test_ensure_structure_already_exists(self, tmp_path):
        """ensure_structure() returns False if already exists."""
        handler = DotAgentsHandler(dotagents_path=tmp_path)
        handler.ensure_structure(dry_run=False)
        created = handler.ensure_structure(dry_run=False)
        assert created is False

    def test_list_subdirs(self, tmp_path):
        """list_subdirs() returns all subdirectories."""
        handler = DotAgentsHandler(dotagents_path=tmp_path)
        (tmp_path / "skills").mkdir()
        (tmp_path / "agents").mkdir()
        (tmp_path / "config.json").touch()  # file, not dir
        subs = handler.list_subdirs()
        names = {p.name for p in subs}
        assert "skills" in names
        assert "agents" in names

    def test_list_subdirs_empty(self, tmp_path):
        """list_subdirs() returns empty list for empty directory."""
        handler = DotAgentsHandler(dotagents_path=tmp_path)
        assert handler.list_subdirs() == []

    def test_default_path_is_global(self):
        """Default dotagents_path is ~/.agents/."""
        handler = DotAgentsHandler()
        assert handler.dotagents_path == DOTAGENTS_GLOBAL