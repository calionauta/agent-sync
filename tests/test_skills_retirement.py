"""Regression tests for skill retirement detection.

A skill deleted in a past commit and re-added in a later commit is NOT
retired — only skills still absent from HEAD count. This prevents a
temporary deletion (e.g. accidental `agent-sync centralize` with wrong
filter) from permanently blacklisting a skill.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_sync.skills import SkillsManager
from agent_sync.sync import SyncManager


def _git(cwd: Path, *args: str) -> str:
    """Run a git command in cwd and return stdout."""
    result = subprocess.run(
        ["git", "-C", str(cwd)] + list(args),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _commit_file(repo: Path, relpath: str, content: str, msg: str) -> None:
    """Write a file and commit it under skills/."""
    full = repo / relpath
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    _git(repo, "add", relpath)
    _git(repo, "commit", "-m", msg)


def _init_repo_with_skill(tmp_path: Path, name: str) -> Path:
    """Init a git repo with a single skill under skills/<name>."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "Test")
    _commit_file(
        repo,
        f"skills/{name}/SKILL.md",
        f"# {name}\n",
        f"add {name}",
    )
    return repo


def test_re_added_skill_is_not_retired(tmp_path):
    """A skill deleted in commit N and re-added in commit N+1 must NOT be retired."""
    repo = _init_repo_with_skill(tmp_path, "cali-coding-tmp")

    # Delete the skill
    _git(repo, "rm", "-r", "skills/cali-coding-tmp")
    _git(repo, "commit", "-m", "delete cali-coding-tmp")

    # Re-add the skill
    _commit_file(
        repo,
        "skills/cali-coding-tmp/SKILL.md",
        "# cali-coding-tmp\n",
        "re-add cali-coding-tmp",
    )

    manager = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch.object(SyncManager, "DEFAULT_REPO_DIR", repo):
        retired = manager._get_retired_skill_names()

    assert "cali-coding-tmp" not in retired, (
        f"Skill re-added in HEAD must not be retired, got: {retired}"
    )


def test_never_deleted_skill_is_not_retired(tmp_path):
    """A skill that was never deleted must obviously not be retired."""
    repo = _init_repo_with_skill(tmp_path, "cali-coding-persistent")
    # Add a second commit to make history non-trivial
    _commit_file(
        repo,
        "skills/cali-coding-persistent/references/note.md",
        "note",
        "add note",
    )

    manager = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch.object(SyncManager, "DEFAULT_REPO_DIR", repo):
        retired = manager._get_retired_skill_names()

    assert "cali-coding-persistent" not in retired


def test_truly_deleted_skill_is_retired(tmp_path):
    """A skill deleted in HEAD (no re-add) MUST be in retired set."""
    repo = _init_repo_with_skill(tmp_path, "cali-legacy")
    _git(repo, "rm", "-r", "skills/cali-legacy")
    _git(repo, "commit", "-m", "delete cali-legacy for good")

    manager = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch.object(SyncManager, "DEFAULT_REPO_DIR", repo):
        retired = manager._get_retired_skill_names()

    assert "cali-legacy" in retired, (
        f"Skill absent from HEAD must be retired, got: {retired}"
    )


def test_mixed_history_only_truly_retired_count(tmp_path):
    """Repo with multiple skills: some re-added, some gone, some untouched."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "Test")

    # Add three skills
    for name in ("alive", "resurrected", "dead"):
        _commit_file(
            repo, f"skills/{name}/SKILL.md", f"# {name}\n", f"add {name}"
        )

    # Delete `resurrected`, then re-add it
    _git(repo, "rm", "-r", "skills/resurrected")
    _git(repo, "commit", "-m", "temp delete resurrected")
    _commit_file(
        repo,
        "skills/resurrected/SKILL.md",
        "# resurrected\n",
        "re-add resurrected",
    )

    # Delete `dead` permanently
    _git(repo, "rm", "-r", "skills/dead")
    _git(repo, "commit", "-m", "perm delete dead")

    manager = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch.object(SyncManager, "DEFAULT_REPO_DIR", repo):
        retired = manager._get_retired_skill_names()

    assert "alive" not in retired
    assert "resurrected" not in retired, (
        f"resurrected (deleted+readded) must not be retired: {retired}"
    )
    assert "dead" in retired


def test_empty_repo_returns_empty_set(tmp_path):
    """A repo with no commits at all should yield no retired skills (defensive)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")

    manager = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch.object(SyncManager, "DEFAULT_REPO_DIR", repo):
        retired = manager._get_retired_skill_names()

    assert retired == set()


def test_subdir_paths_dont_pollute_retirement(tmp_path):
    """Files nested inside a skill (e.g. references/foo.md) must contribute
    the parent skill name, and re-adding the skill must still clear it.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "Test")

    # Skill with nested files
    _commit_file(
        repo, "skills/cali-foo/SKILL.md", "# cali-foo\n", "add cali-foo"
    )
    _commit_file(
        repo, "skills/cali-foo/references/deep.md", "deep", "add ref"
    )

    # Delete the whole skill
    _git(repo, "rm", "-r", "skills/cali-foo")
    _git(repo, "commit", "-m", "delete cali-foo")

    # Re-add only the SKILL.md (skill exists in HEAD, but missing references)
    _commit_file(
        repo,
        "skills/cali-foo/SKILL.md",
        "# cali-foo\n",
        "partial readd cali-foo",
    )

    manager = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch.object(SyncManager, "DEFAULT_REPO_DIR", repo):
        retired = manager._get_retired_skill_names()

    assert "cali-foo" not in retired
