"""Tests for publish README generation.

Note: generate_readme is in the root publish.py (legacy function),
not in the publish/ submodule. These tests are skipped unless
the function can be imported directly.
"""

import pytest

# Try to import from root module, not submodule
generate_readme = None
try:
    # This will only work if we're not in the submodule context
    import sys
    from pathlib import Path
    
    # Read the root publish.py directly and exec it to get the function
    root_path = Path(__file__).parent.parent / "src" / "agent_sync" / "publish.py"
    if root_path.exists():
        namespace = {}
        exec(open(root_path).read(), namespace)
        generate_readme = namespace.get('generate_readme')
except Exception:
    pass


@pytest.fixture
def skip_if_no_generate_readme():
    """Skip test if generate_readme is not available."""
    if generate_readme is None:
        pytest.skip("generate_readme not accessible (legacy function)")


class TestGenerateReadme:
    """Tests for generate_readme()."""

    def test_generates_valid_markdown(self, skip_if_no_generate_readme):
        """README contains expected markdown sections."""
        skills = [{"name": "test-skill"}]
        result = generate_readme(skills, "https://github.com/user/repo")
        assert result.startswith("# Agent Skills")
        assert "## Installation" in result
        assert "## Skills" in result
        assert "## About" in result

    def test_lists_all_skills(self, skip_if_no_generate_readme):
        """All selected skills appear in the skills list."""
        skills = [{"name": "skill-a"}, {"name": "skill-b"}]
        result = generate_readme(skills, "https://github.com/user/repo.git")
        assert "- skill-a" in result
        assert "- skill-b" in result

    def test_uses_repo_name_in_install_command(self, skip_if_no_generate_readme):
        """Install command uses correct repo name from URL."""
        skills = [{"name": "test"}]
        result = generate_readme(skills, "https://github.com/owner/repo-name")
        assert "npx skills add owner/repo-name" in result

    def test_strips_git_suffix_from_url(self, skip_if_no_generate_readme):
        """.git suffix is stripped from repo URL."""
        skills = [{"name": "test"}]
        result = generate_readme(skills, "https://github.com/user/repo.git")
        assert "npx skills add user/repo" in result

    def test_fallback_repo_name(self, skip_if_no_generate_readme):
        """Fallback to 'your-repo' when URL doesn't contain owner/repo."""
        skills = [{"name": "test"}]
        result = generate_readme(skills, "https://github.com/only-owner")
        assert "your-repo" in result

    def test_empty_skills_list(self, skip_if_no_generate_readme):
        """Empty skills list produces README with empty skills section."""
        result = generate_readme([], "https://github.com/user/repo")
        assert "## Skills" in result
        assert "## About" in result