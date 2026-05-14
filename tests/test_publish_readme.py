"""Tests for publish README generation."""

from agent_sync.publish import generate_readme


class TestGenerateReadme:
    """Tests for generate_readme()."""

    def test_generates_valid_markdown(self):
        """README contains expected markdown sections."""
        skills = [{"name": "test-skill"}]
        result = generate_readme(skills, "https://github.com/user/repo")
        assert result.startswith("# Agent Skills")
        assert "## Installation" in result
        assert "## Skills" in result
        assert "## About" in result

    def test_lists_all_skills(self):
        """All selected skills appear in the skills list."""
        skills = [{"name": "skill-a"}, {"name": "skill-b"}]
        result = generate_readme(skills, "https://github.com/user/repo.git")
        assert "- skill-a" in result
        assert "- skill-b" in result

    def test_uses_repo_name_in_install_command(self):
        """Install command uses correct repo name from URL."""
        skills = [{"name": "test"}]
        result = generate_readme(skills, "https://github.com/owner/repo-name")
        assert "npx skills add owner/repo-name" in result

    def test_strips_git_suffix_from_url(self):
        """.git suffix is stripped from repo URL."""
        skills = [{"name": "test"}]
        result = generate_readme(skills, "https://github.com/user/repo.git")
        assert "npx skills add user/repo" in result

    def test_fallback_repo_name(self):
        """Fallback to 'your-repo' when URL doesn't contain owner/repo."""
        skills = [{"name": "test"}]
        result = generate_readme(skills, "https://github.com/only-owner")
        assert "your-repo" in result

    def test_empty_skills_list(self):
        """Empty skills list produces README with empty skills section."""
        result = generate_readme([], "https://github.com/user/repo")
        assert "## Skills" in result
        assert "## About" in result
