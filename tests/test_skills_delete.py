"""Tests for skills deletion management."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from agent_sync.skills_delete import SkillsDeleter

@pytest.fixture
def deleter():
    """Create a SkillsDeleter instance with mocked dependencies."""
    with patch("agent_sync.config.Config"), \
         patch("agent_sync.agents.get_agents") as mock_get_agents:
        mock_get_agents.return_value = []
        return SkillsDeleter()

def test_count_skill_files_empty_dir(deleter, tmp_path):
    """Should return 0 for an empty directory."""
    skill_dir = tmp_path / "empty_skill"
    skill_dir.mkdir()
    assert deleter.count_skill_files(skill_dir) == 0

def test_count_skill_files_with_files(deleter, tmp_path):
    """Should count files in the directory."""
    skill_dir = tmp_path / "skill_with_files"
    skill_dir.mkdir()
    (skill_dir / "file1.txt").write_text("content")
    (skill_dir / "file2.md").write_text("content")
    # Directories themselves should not be counted
    (skill_dir / "subdir").mkdir()
    assert deleter.count_skill_files(skill_dir) == 2

def test_count_skill_files_nested(deleter, tmp_path):
    """Should count files in subdirectories recursively."""
    skill_dir = tmp_path / "nested_skill"
    skill_dir.mkdir()
    (skill_dir / "file1.txt").write_text("content")
    sub_dir = skill_dir / "sub"
    sub_dir.mkdir()
    (sub_dir / "file2.md").write_text("content")
    (sub_dir / "subsub").mkdir()
    (sub_dir / "subsub" / "file3.py").write_text("content")
    assert deleter.count_skill_files(skill_dir) == 3

def test_count_skill_files_non_existent(deleter, tmp_path):
    """Should return 0 for non-existent paths."""
    skill_dir = tmp_path / "non_existent"
    assert deleter.count_skill_files(skill_dir) == 0

def test_count_skill_files_not_a_dir(deleter, tmp_path):
    """Should return 0 if path is a file, not a directory."""
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("content")
    assert deleter.count_skill_files(not_a_dir) == 0

def test_count_skill_files_hidden_files(deleter, tmp_path):
    """Should count hidden files."""
    skill_dir = tmp_path / "hidden_skill"
    skill_dir.mkdir()
    (skill_dir / ".hidden_file").write_text("content")
    (skill_dir / "visible_file").write_text("content")
    assert deleter.count_skill_files(skill_dir) == 2
