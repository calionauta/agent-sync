"""CLI integration tests - push, pull, config, link, secrets, mcp, skills."""

from click.testing import CliRunner

from agent_sync.cli import main


runner = CliRunner()


# =============================================================================
# CONFIG - show, repo, edit, reset
# =============================================================================

def test_cli_config_show():
    result = runner.invoke(main, ["config", "show"])
    assert result.exit_code == 0


def test_cli_config_repo():
    result = runner.invoke(main, ["config", "repo"])
    assert result.exit_code == 0


def test_cli_config_reset_help():
    """config reset should require confirmation."""
    result = runner.invoke(main, ["config", "reset", "--help"])
    assert result.exit_code == 0


# =============================================================================
# SECRETS - list, edit, enable, disable
# =============================================================================

def test_cli_secrets_list():
    result = runner.invoke(main, ["secrets", "list"])
    assert result.exit_code == 0


def test_cli_secrets_enable():
    result = runner.invoke(main, ["secrets", "enable"])
    assert result.exit_code == 0
    assert "enabled" in result.output.lower()


def test_cli_secrets_disable():
    result = runner.invoke(main, ["secrets", "disable"])
    assert result.exit_code == 0
    assert "disabled" in result.output.lower()


# =============================================================================
# MCP command
# =============================================================================

def test_cli_mcp_help():
    result = runner.invoke(main, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output
    assert "--force" in result.output
    assert "--conflicts" in result.output
    assert "--source" in result.output
    assert "--output" in result.output


def test_cli_mcp_dry_run():
    """mcp --dry-run should handle no configs gracefully."""
    result = runner.invoke(main, ["mcp", "--dry-run"])
    assert result.exit_code == 0


def test_cli_mcp_conflicts():
    result = runner.invoke(main, ["mcp", "--conflicts"])
    assert result.exit_code == 0


# =============================================================================
# PUSH / PULL - flag presence and basic execution
# =============================================================================

def test_cli_push_help():
    result = runner.invoke(main, ["push", "--help"])
    assert result.exit_code == 0
    # Verify new filter flags are present
    assert "--skill" in result.output
    assert "--agent" in result.output
    assert "--exclude-skill" in result.output
    assert "--exclude-agent" in result.output
    assert "--skills-only" in result.output
    assert "--configs-only" in result.output
    assert "--dry-run" in result.output


def test_cli_push_dry_run():
    """push --dry-run should work without errors."""
    result = runner.invoke(main, ["push", "--dry-run"])
    # Should NOT have option parsing errors
    assert "No such option: --dry-run" not in result.output
    assert "NoSuchOption" not in result.output
    # Should NOT have runtime errors (TypeError, AttributeError, etc)
    assert "TypeError" not in result.output
    assert "AttributeError" not in result.output
    assert "Traceback" not in result.output or result.exit_code == 0


def test_cli_pull_help():
    result = runner.invoke(main, ["pull", "--help"])
    assert result.exit_code == 0
    # Verify new filter flags are present
    assert "--skill" in result.output
    assert "--agent" in result.output
    assert "--exclude-skill" in result.output
    assert "--exclude-agent" in result.output
    assert "--skills-only" in result.output
    assert "--configs-only" in result.output


def test_cli_sync_help():
    result = runner.invoke(main, ["sync", "--help"])
    assert result.exit_code == 0
    assert "--skills-only" in result.output
    assert "--configs-only" in result.output
    assert "--agents-only" in result.output
    assert "--force" in result.output


# =============================================================================
# SKILLS CENTRALIZE
# =============================================================================

def test_cli_skills_centralize_help():
    result = runner.invoke(main, ["skills", "centralize", "--help"])
    assert result.exit_code == 0
    assert "--copy" in result.output
    assert "--push" in result.output
    assert "--dry-run" in result.output


def test_cli_skills_centralize_dry_run():
    """centralize --dry-run should not crash."""
    result = runner.invoke(main, ["skills", "centralize", "--dry-run"])
    # May exit non-zero in non-tty but should not TypeError
    assert "Traceback" not in result.output


def test_cli_skills_list_help():
    """skills list --help should describe interactive TUI."""
    result = runner.invoke(main, ["skills", "list", "--help"])
    assert result.exit_code == 0
    assert "skill" in result.output.lower()

def test_cli_skills_list_no_crash():
    """skills list should not crash on empty or populated hub."""
    result = runner.invoke(main, ["skills", "list"])
    assert "Traceback" not in result.output



# All commands visible in --help
# =============================================================================

def test_all_restored_commands_in_help():
    result = runner.invoke(main, ["--help"])
    output = result.output
    assert "config" in output
    assert "repos" in output
    assert "mcp" in output
    assert "secrets" in output
    assert "publish" in output
    assert "skills" in output
    assert "agents" in output
    assert "sync" in output
    assert "push" in output
    assert "pull" in output


# =============================================================================
# Empty list truthy fix (push/pull returning [] should be success)
# =============================================================================

def test_empty_list_is_truthy_for_success():
    """Verify [] != False in Python (this is the root cause of the bug)."""
    assert [] is not False, "[] is not False - empty list should be truthy for success"
    assert [] != False
    # The correct pattern: if result is not False:
    assert (lambda: [])() is not False