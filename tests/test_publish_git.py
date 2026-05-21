"""Tests for git_publish module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_sync.publish.git_publish import (
    do_git_publish,
    publish_skills,
    publish_agents,
    generate_skills_readme,
    generate_agents_readme,
)


class TestDoGitPublish:
    """Tests for do_git_publish."""

    def test_creates_subdir(self):
        """Creates subdirectory for items."""
        with patch("agent_sync.publish.git_publish.git_commit_and_push"):
            with patch("agent_sync.publish.git_publish.shutil.copytree"):
                with patch("agent_sync.publish.git_publish.shutil.copy2"):
                    with patch("agent_sync.publish.git_publish.tempfile.mkdtemp", return_value="/tmp/test"):
                        with patch("agent_sync.publish.git_publish.Path") as mock_path:
                            mock_path.return_value = Path("/tmp/test")
                            mock_path.mkdir = MagicMock()
                            mock_path.write_text = MagicMock()
                            
                            mock_items = [(MagicMock(), "test.txt")]
                            mock_readme = MagicMock()
                            
                            result = do_git_publish(
                                items=mock_items,
                                subdir="skills",
                                readme_generator=mock_readme,
                                count=1,
                                item_name="skills",
                                repo="https://github.com/test/repo",
                            )
                            
                            assert result is True


class TestPublishSkills:
    """Tests for publish_skills."""

    def test_no_skills_selected(self):
        """Returns False when no skills selected."""
        with patch("agent_sync.publish.git_publish.console.print") as mock_print:
            result = publish_skills({}, [], "https://github.com/test/repo")
            
            assert result is False

    def test_handles_missing_source(self):
        """Handles missing source gracefully."""
        mock_source = MagicMock()
        mock_source.source_id = "local"
        mock_source.skills = []
        
        with patch("agent_sync.publish.git_publish.console.print") as mock_print:
            result = publish_skills(
                {"local": ["nonexistent"]},
                [mock_source],
                "https://github.com/test/repo",
            )
            
            assert result is False


class TestPublishAgents:
    """Tests for publish_agents."""

    def test_no_agents_selected(self):
        """Returns False when no agents selected."""
        with patch("agent_sync.publish.git_publish.console.print") as mock_print:
            result = publish_agents({}, "https://github.com/test/repo")
            
            assert result is False


class TestGenerateSkillsReadme:
    """Tests for generate_skills_readme."""

    def test_generates_markdown(self):
        """Generates valid markdown."""
        tmp_dir = Path(tempfile.mkdtemp())
        items = [
            (Path("/tmp/s1"), "local/skill1"),
            (Path("/tmp/s2"), "ext/skill2"),
        ]
        
        generate_skills_readme(tmp_dir, items, "https://github.com/test/repo")
        
        readme_path = tmp_dir / "README.md"
        assert readme_path.exists()
        
        content = readme_path.read_text()
        assert "# Skills" in content

    def test_includes_install_command(self):
        """Includes install command."""
        tmp_dir = Path(tempfile.mkdtemp())
        items = [(Path("/tmp/s1"), "local/skill1")]
        
        generate_skills_readme(tmp_dir, items, "https://github.com/test/repo")
        
        readme_path = tmp_dir / "README.md"
        content = readme_path.read_text()
        
        assert "npx skills add https://github.com/test/repo" in content


class TestGenerateAgentsReadme:
    """Tests for generate_agents_readme."""

    def test_generates_markdown(self):
        """Generates valid markdown."""
        tmp_dir = Path(tempfile.mkdtemp())
        items = [
            (Path("/tmp/a1"), "agents/agent1.md"),
            (Path("/tmp/a2"), "agents/agent2.md"),
        ]
        
        generate_agents_readme(tmp_dir, items, "https://github.com/test/repo")
        
        readme_path = tmp_dir / "README.md"
        assert readme_path.exists()
        
        content = readme_path.read_text()
        assert "# Agents" in content