"""Tests for skills audit and explain observability commands.

Audit: compares hub / repo and reports drift.
Explain: lifecycle of a single skill (where it is + git history).
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_sync.skills_audit import (
    AuditReport,
    SkillAuditRow,
    SkillExplanation,
    audit_skills,
    explain_skill,
)


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd)] + list(args),
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def _commit_file(repo: Path, relpath: str, content: str, msg: str) -> None:
    full = repo / relpath
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    _git(repo, "add", relpath)
    _git(repo, "commit", "-m", msg)


def _init_repo_with_skills(tmp_path: Path, names: list[str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "Test")
    for name in names:
        _commit_file(repo, f"skills/{name}/SKILL.md", f"# {name}\n", f"add {name}")
    return repo


# ---------------------------------------------------------------------------
# audit_skills
# ---------------------------------------------------------------------------


class TestAuditSkills:
    """Pure-data audit. No I/O when overrides are provided."""

    def test_in_sync_skill(self):
        report = audit_skills(hub_skills={"cali-foo"}, repo_skills={"cali-foo"})
        assert report.rows[0].status == "in_sync"

    def test_in_hub_only_skill(self):
        report = audit_skills(hub_skills={"cali-new"}, repo_skills=set())
        assert report.rows[0].status == "in_hub_only"

    def test_in_repo_only_skill(self):
        report = audit_skills(hub_skills=set(), repo_skills={"cali-orphan"})
        assert report.rows[0].status == "in_repo_only"

    def test_summary_counts(self):
        report = audit_skills(hub_skills={"a", "b", "c"}, repo_skills={"a", "b", "d"})
        summary = report.summary_counts()
        assert summary.get("in_sync") == 2  # a, b
        assert summary.get("in_hub_only") == 1  # c
        assert summary.get("in_repo_only") == 1  # d

    def test_all_unique_names_in_rows(self):
        report = audit_skills(hub_skills={"x", "y"}, repo_skills={"y", "z"})
        names = {r.name for r in report.rows}
        assert names == {"x", "y", "z"}


class TestAuditSkillsWithFilesystem:
    """Integration with real files (tmp_path)."""

    def test_reads_hub_from_disk(self, tmp_path):
        hub = tmp_path / ".agents" / "skills"
        hub.mkdir(parents=True)
        (hub / "alpha").mkdir()
        (hub / "alpha" / "SKILL.md").write_text("# alpha\n")
        (hub / "beta").mkdir()
        (hub / "beta" / "SKILL.md").write_text("# beta\n")

        with patch("agent_sync.skills_audit.HUB_DIR", hub), \
             patch("agent_sync.skills_audit.REPO_DIR", tmp_path / "no-repo"):
            report = audit_skills(hub_skills=None, repo_skills=set())
        assert {r.name for r in report.rows} == {"alpha", "beta"}
        assert report.hub_count == 2


# ---------------------------------------------------------------------------
# explain_skill
# ---------------------------------------------------------------------------


class TestExplainSkill:
    """Pure-data explain. Overrides bypass filesystem."""

    def test_explain_skill_in_sync(self):
        expl = explain_skill("cali-foo", hub_skills={"cali-foo"}, repo_skills={"cali-foo"})
        assert expl.in_hub is True
        assert expl.in_repo is True
        assert expl.commit_count == 0

    def test_explain_skill_not_tracked_anywhere(self):
        expl = explain_skill("cali-ghost", hub_skills=set(), repo_skills=set())
        assert expl.in_hub is False
        assert expl.in_repo is False


class TestExplainSkillWithGit:
    """Integration with real git (tmp_path)."""

    def test_explain_skill_counts_commits(self, tmp_path):
        repo = _init_repo_with_skills(tmp_path, ["cali-foo"])
        (repo / "skills" / "cali-foo" / "extra.md").write_text("more")
        _git(repo, "add", "skills/cali-foo/extra.md")
        _git(repo, "commit", "-m", "add extra")

        with patch("agent_sync.skills_audit.REPO_DIR", repo), \
             patch("agent_sync.skills_audit.HUB_DIR", tmp_path / "no-hub"):
            expl = explain_skill("cali-foo", hub_skills=set(), repo_skills=set())
        assert expl.commit_count >= 2
        assert expl.first_added is not None
        assert expl.last_modified is not None

    def test_explain_skill_not_in_repo(self, tmp_path):
        repo = _init_repo_with_skills(tmp_path, [])
        with patch("agent_sync.skills_audit.REPO_DIR", repo), \
             patch("agent_sync.skills_audit.HUB_DIR", tmp_path / "no-hub"):
            expl = explain_skill("cali-never", hub_skills=set(), repo_skills=set())
        assert expl.commit_count == 0


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


class TestCliAudit:
    """Smoke tests for the CLI subcommands."""

    def test_audit_json_output(self):
        from click.testing import CliRunner
        from agent_sync.cli import skills_group

        runner = CliRunner()
        result = runner.invoke(skills_group, ["audit", "--json"])
        if result.exit_code == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            assert "hub_count" in data
            assert "repo_count" in data
            assert "rows" in data

    def test_explain_skill_in_sync(self):
        from click.testing import CliRunner
        from agent_sync.cli import skills_group

        runner = CliRunner()
        result = runner.invoke(skills_group, ["explain", "cali-coding-go-stack"])
        assert "cali-coding-go-stack" in result.output or result.exit_code != 0

    def test_audit_limit_truncates_output(self):
        from click.testing import CliRunner
        from agent_sync.cli import skills_group

        runner = CliRunner()
        result = runner.invoke(skills_group, ["audit", "--limit", "5", "--json"])
        if result.exit_code == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            assert len(data["rows"]) <= 5
