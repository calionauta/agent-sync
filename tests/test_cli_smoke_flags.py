"""Smoke tests for CLI flags - catch NoSuchOption errors.

CRITICAL: These tests verify that ALL flags are actually accepted by the CLI,
not just that they appear in --help. This catches typos, missing options, etc.

Each test invokes the command with the flag and checks for NoSuchOption errors.
"""

from click.testing import CliRunner

from agent_sync.cli import main

runner = CliRunner()


# =============================================================================
# PUSH command flags - EVERY flag must work
# =============================================================================


class TestPushFlags:
    """Every push flag must be recognized by click."""

    def test_push_dry_run(self):
        """--dry-run must be accepted and run without errors."""
        result = runner.invoke(main, ["push", "--dry-run"])
        assert "No such option: --dry-run" not in result.output
        assert "NoSuchOption" not in result.output
        # Also check for runtime errors
        assert "TypeError" not in result.output
        assert "Traceback" not in result.output or result.exit_code == 0

    def test_push_skill(self):
        """--skill must be accepted without errors."""
        result = runner.invoke(main, ["push", "--skill", "dogfood"])
        assert "No such option: --skill" not in result.output
        assert "TypeError" not in result.output

    def test_push_skill_short(self):
        """-s (short for --skill) must be accepted."""
        result = runner.invoke(main, ["push", "-s", "dogfood"])
        assert "No such option: -s" not in result.output
        assert "TypeError" not in result.output

    def test_push_agent(self):
        """--agent must be accepted without errors."""
        result = runner.invoke(main, ["push", "--agent", "pi.dev"])
        assert "No such option: --agent" not in result.output
        assert "TypeError" not in result.output

    def test_push_agent_short(self):
        """-a (short for --agent) must be accepted."""
        result = runner.invoke(main, ["push", "-a", "pi.dev"])
        assert "No such option: -a" not in result.output
        assert "TypeError" not in result.output

    def test_push_exclude_skill(self):
        """--exclude-skill must be accepted without errors."""
        result = runner.invoke(main, ["push", "--exclude-skill", "deprecated"])
        assert "No such option: --exclude-skill" not in result.output
        assert "TypeError" not in result.output

    def test_push_exclude_agent(self):
        """--exclude-agent must be accepted without errors."""
        result = runner.invoke(main, ["push", "--exclude-agent", "old-agent"])
        assert "No such option: --exclude-agent" not in result.output
        assert "TypeError" not in result.output

    def test_push_skills_only(self):
        """--skills-only must be accepted without errors."""
        result = runner.invoke(main, ["push", "--skills-only"])
        assert "No such option: --skills-only" not in result.output
        assert "TypeError" not in result.output

    def test_push_configs_only(self):
        """--configs-only must be accepted without errors."""
        result = runner.invoke(main, ["push", "--configs-only"])
        assert "No such option: --configs-only" not in result.output
        assert "TypeError" not in result.output

    def test_push_message(self):
        """--message/-m must be accepted without errors."""
        result = runner.invoke(main, ["push", "--message", "test commit"])
        assert "No such option: --message" not in result.output
        assert "TypeError" not in result.output

    def test_push_message_short(self):
        """-m (short for --message) must be accepted."""
        result = runner.invoke(main, ["push", "-m", "test commit"])
        assert "No such option: -m" not in result.output
        assert "TypeError" not in result.output

    def test_push_multiple_skills(self):
        """Multiple --skill flags must work without errors."""
        result = runner.invoke(
            main, ["push", "--skill", "dogfood", "--skill", "cali-product-workflow"]
        )
        assert "No such option: --skill" not in result.output
        assert "TypeError" not in result.output


# =============================================================================
# PULL command flags - EVERY flag must work
# =============================================================================


class TestPullFlags:
    """Every pull flag must be recognized by click."""

    def test_pull_dry_run(self):
        """--dry-run must be accepted."""
        result = runner.invoke(main, ["pull", "--dry-run"])
        assert "No such option: --dry-run" not in result.output

    def test_pull_force(self):
        """--force must be accepted."""
        result = runner.invoke(main, ["pull", "--force"])
        assert "No such option: --force" not in result.output

    def test_pull_interactive(self):
        """--interactive must be accepted."""
        result = runner.invoke(main, ["pull", "--interactive"])
        assert "No such option: --interactive" not in result.output

    def test_pull_no_interactive(self):
        """--no-interactive must be accepted."""
        result = runner.invoke(main, ["pull", "--no-interactive"])
        assert "No such option: --no-interactive" not in result.output

    def test_pull_skill(self):
        """--skill must be accepted."""
        result = runner.invoke(main, ["pull", "--skill", "dogfood"])
        assert "No such option: --skill" not in result.output

    def test_pull_skill_short(self):
        """-s (short for --skill) must be accepted."""
        result = runner.invoke(main, ["pull", "-s", "dogfood"])
        assert "No such option: -s" not in result.output

    def test_pull_agent(self):
        """--agent must be accepted."""
        result = runner.invoke(main, ["pull", "--agent", "pi.dev"])
        assert "No such option: --agent" not in result.output

    def test_pull_agent_short(self):
        """-a (short for --agent) must be accepted."""
        result = runner.invoke(main, ["pull", "-a", "pi.dev"])
        assert "No such option: -a" not in result.output

    def test_pull_exclude_skill(self):
        """--exclude-skill must be accepted."""
        result = runner.invoke(main, ["pull", "--exclude-skill", "deprecated"])
        assert "No such option: --exclude-skill" not in result.output

    def test_pull_exclude_agent(self):
        """--exclude-agent must be accepted."""
        result = runner.invoke(main, ["pull", "--exclude-agent", "old-agent"])
        assert "No such option: --exclude-agent" not in result.output

    def test_pull_skills_only(self):
        """--skills-only must be accepted."""
        result = runner.invoke(main, ["pull", "--skills-only"])
        assert "No such option: --skills-only" not in result.output

    def test_pull_configs_only(self):
        """--configs-only must be accepted."""
        result = runner.invoke(main, ["pull", "--configs-only"])
        assert "No such option: --configs-only" not in result.output


# =============================================================================
# SYNC command flags
# =============================================================================


class TestSyncFlags:
    """Every sync flag must be recognized by click."""

    def test_sync_force(self):
        """--force must be accepted."""
        result = runner.invoke(main, ["sync", "--force"])
        assert "No such option: --force" not in result.output

    def test_sync_skills_only(self):
        """--skills-only must be accepted."""
        result = runner.invoke(main, ["sync", "--skills-only"])
        assert "No such option: --skills-only" not in result.output

    def test_sync_configs_only(self):
        """--configs-only must be accepted."""
        result = runner.invoke(main, ["sync", "--configs-only"])
        assert "No such option: --configs-only" not in result.output

    def test_sync_agents_only(self):
        """--agents-only must be accepted."""
        result = runner.invoke(main, ["sync", "--agents-only"])
        assert "No such option: --agents-only" not in result.output


# =============================================================================
# MCP command flags
# =============================================================================


class TestMCPFlags:
    """Every mcp flag must be recognized by click."""

    def test_mcp_dry_run(self):
        """--dry-run must be accepted."""
        result = runner.invoke(main, ["mcp", "--dry-run"])
        assert "No such option: --dry-run" not in result.output

    def test_mcp_force(self):
        """--force must be accepted."""
        result = runner.invoke(main, ["mcp", "--force"])
        assert "No such option: --force" not in result.output

    def test_mcp_conflicts(self):
        """--conflicts must be accepted."""
        result = runner.invoke(main, ["mcp", "--conflicts"])
        assert "No such option: --conflicts" not in result.output

    def test_mcp_source(self):
        """--source/-s must be accepted."""
        result = runner.invoke(main, ["mcp", "--source", "/path/to/config.json"])
        assert "No such option: --source" not in result.output

    def test_mcp_output(self):
        """--output must be accepted."""
        result = runner.invoke(main, ["mcp", "--output", "/path/to/output.json"])
        assert "No such option: --output" not in result.output


# =============================================================================
# SKILLS CENTRALIZE flags
# =============================================================================


class TestSkillsCentralizeFlags:
    """Every skills centralize flag must be recognized by click."""

    def test_centralize_copy(self):
        """--copy must be accepted."""
        result = runner.invoke(main, ["skills", "centralize", "--copy"])
        assert "No such option: --copy" not in result.output

    def test_centralize_push(self):
        """--push must be accepted."""
        result = runner.invoke(main, ["skills", "centralize", "--push"])
        assert "No such option: --push" not in result.output

    def test_centralize_dry_run(self):
        """--dry-run must be accepted."""
        result = runner.invoke(main, ["skills", "centralize", "--dry-run"])
        assert "No such option: --dry-run" not in result.output


# =============================================================================
# SKILLS PRUNE flags
# =============================================================================


class TestSkillsPruneFlags:
    """Every skills prune flag must be recognized by click."""

    def test_prune_dry_run(self):
        """--dry-run must be accepted without errors."""
        result = runner.invoke(main, ["skills", "prune", "--dry-run"])
        assert "No such option: --dry-run" not in result.output
        assert "TypeError" not in result.output
        assert "Traceback" not in result.output or result.exit_code == 0

    def test_prune_yes(self):
        """--yes/-y must be accepted without errors."""
        result = runner.invoke(main, ["skills", "prune", "--yes"])
        assert "No such option: --yes" not in result.output
        assert "No such option: -y" not in result.output
        assert "TypeError" not in result.output
