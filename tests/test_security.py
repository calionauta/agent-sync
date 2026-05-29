"""Security regression tests for agent-sync."""

from agent_sync.skills_delete import SkillsDeleter
from agent_sync.validators import validate_github_url, validate_repo_name, validate_skill_name


def test_validate_repo_name_argument_injection():
    """Verify argument injection prevention in repo names."""
    assert validate_repo_name("-bad/repo") is False
    assert validate_repo_name("owner/repo") is True


def test_validate_github_url_argument_injection():
    """Verify argument injection prevention in GitHub URLs."""
    assert validate_github_url("https://github.com/-bad/repo") is False
    assert validate_github_url("https://github.com/owner/repo") is True


def test_validate_skill_name_security():
    """Verify that validate_skill_name blocks dangerous names."""
    # Safe names
    assert validate_skill_name("my-skill") is True
    assert validate_skill_name("skill.v1") is True
    assert validate_skill_name("skill_2") is True

    # Path traversal attempts
    assert validate_skill_name("../dangerous") is False
    assert validate_skill_name("..") is False
    assert validate_skill_name("/") is False
    assert validate_skill_name("/etc/passwd") is False
    assert validate_skill_name("skills/../base") is False

    # Newline injection
    assert validate_skill_name("skill\n") is False
    assert validate_skill_name("skill\r\n") is False

    # Shell characters
    assert validate_skill_name("skill;ls") is False
    assert validate_skill_name("skill|rm") is False
    assert validate_skill_name("skill&whoami") is False
    assert validate_skill_name("skill`id`") is False
    assert validate_skill_name("skill$(id)") is False


def test_validate_repo_name_newline_injection():
    """Verify that validate_repo_name blocks newline injection."""
    assert validate_repo_name("repo\n") is False
    assert validate_repo_name("repo\r") is False
    assert validate_repo_name("owner/repo\n") is False


def test_validate_github_url_newline_injection():
    """Verify that validate_github_url blocks newline injection."""
    assert validate_github_url("https://github.com/owner/repo\n") is False
    assert validate_github_url("https://github.com/owner/repo\r.git") is False


def test_skills_deleter_path_traversal_blocking(tmp_path, monkeypatch):
    """Verify that SkillsDeleter blocks path traversal attempts."""
    # Setup mock environment
    hub_dir = tmp_path / "hub"
    hub_dir.mkdir()

    # Create a dummy skill
    skill_dir = hub_dir / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("dummy")

    # Create a file outside the hub
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret content")

    class MockConfig:
        def __init__(self):
            pass

    class MockAgent:
        def __init__(self, name, path):
            self.name = name
            self.skills_path = path

    monkeypatch.setattr("agent_sync.config.Config", MockConfig)

    deleter = SkillsDeleter()
    deleter.global_skills_dir = hub_dir
    deleter.agents = []

    # Attempt to delete using path traversal
    # Note: validate_skill_name will block this first
    stats = deleter.delete_skills(["../secret.txt"])

    assert stats["errors"] == 1
    assert outside_file.exists()

    # Attempt another traversal that might pass validate_skill_name if it was weak
    # (though our regex is quite strict now)
    stats = deleter.delete_skills([".."])
    assert stats["errors"] == 1
    assert hub_dir.exists()


# ---------------------------------------------------------------------------
# Token sanitization tests
# ---------------------------------------------------------------------------

import subprocess
from unittest.mock import patch, MagicMock

from agent_sync.sync import _sanitize_git_output


def test_sanitize_masks_url_with_token():
    """Verify tokens in remote URLs are masked."""
    text = "fatal: https://ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh@github.com/u/r.git not found"
    result = _sanitize_git_output(text)
    assert "ghp_" not in result
    assert "https://***@github.com" in result


def test_sanitize_masks_bare_token():
    """Verify bare tokens (not in URL) are masked."""
    text = "Token leaked: ghp_aB3dE5gH7iJ9kL1mN3oP5qR7sT9uV1wX3yZ"
    result = _sanitize_git_output(text)
    assert "ghp_" not in result
    assert "***" in result


def test_sanitize_preserves_clean_errors():
    """Verify non-token text passes through unchanged."""
    text = "fatal: 'origin' does not appear to be a git repository"
    assert _sanitize_git_output(text) == text


def test_sanitize_handles_none_and_empty():
    """Verify edge cases don't crash."""
    assert _sanitize_git_output(None) is None
    assert _sanitize_git_output("") == ""


def test_sanitize_short_token_not_masked():
    """Verify tokens <20 chars are NOT masked (avoid false positives)."""
    text = "short: ghp_abc"
    assert _sanitize_git_output(text) == text


def test_run_git_sanitizes_stderr_on_failure(tmp_path):
    """Integration: _run_git must sanitize CalledProcessError stderr.

    This is the real security contract — when git fails and its stderr
    contains a token, the exception must NOT expose it.
    """
    from agent_sync.sync import SyncManager

    # Create a fake repo so _run_git has somewhere to run
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)

    sm = SyncManager.__new__(SyncManager)
    sm.repo_dir = repo
    sm.config = MagicMock()
    sm.state_file = tmp_path / "state.json"

    # Mock subprocess.run to simulate git failure with token in stderr
    fake_result = MagicMock()
    fake_result.returncode = 128
    fake_result.stdout = ""
    fake_result.stderr = "fatal: https://ghp_SECRET_TOKEN_XXXXXXXXXXXXXXXX@github.com/u/r.git not found"

    with patch("agent_sync.sync.subprocess.run", return_value=fake_result):
        try:
            sm._run_git("remote", "update")
            assert False, "Should have raised CalledProcessError"
        except subprocess.CalledProcessError as e:
            assert "ghp_SECRET_TOKEN" not in e.stderr, (
                "Token leaked through CalledProcessError.stderr!"
            )
            assert "***" in e.stderr, (
                "Sanitization marker missing — stderr was not sanitized"
            )
