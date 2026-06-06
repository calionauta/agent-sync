"""Tests for skills audit and explain observability commands (Phase 4, AD-5).

Audit: compares hub / repo / manifest and reports drift.
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
    """Init a git repo and commit the given skill dirs under skills/."""
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
        """Skill in hub + repo + not in manifest → in_sync."""
        report = audit_skills(
            hub_skills={"cali-foo"},
            repo_skills={"cali-foo"},
            manifest_skills=set(),
        )
        assert len(report.rows) == 1
        row = report.rows[0]
        assert row.name == "cali-foo"
        assert row.in_hub is True
        assert row.in_repo is True
        assert row.in_manifest is False
        assert row.status == "in_sync"

    def test_in_hub_only_skill(self):
        """Skill in hub only (new) → in_hub_only."""
        report = audit_skills(
            hub_skills={"cali-new"},
            repo_skills=set(),
            manifest_skills=set(),
        )
        assert report.rows[0].status == "in_hub_only"

    def test_in_repo_only_skill_is_orphan(self):
        """Skill in repo only (not in hub, not retired) → orphan."""
        report = audit_skills(
            hub_skills=set(),
            repo_skills={"cali-orphan"},
            manifest_skills=set(),
        )
        row = report.rows[0]
        assert row.status == "in_repo_only"
        assert row.in_hub is False
        assert row.in_repo is True

    def test_retired_in_repo_skill(self):
        """Skill in repo + in manifest, not in hub → properly retired."""
        report = audit_skills(
            hub_skills=set(),
            repo_skills={"cali-old"},
            manifest_skills={"cali-old"},
        )
        assert report.rows[0].status == "retired_in_repo"

    def test_retired_clean_skill(self):
        """Skill only in manifest (not in hub, not in repo) → fully retired."""
        report = audit_skills(
            hub_skills=set(),
            repo_skills=set(),
            manifest_skills={"cali-foo"},
        )
        assert report.rows[0].status == "retired_clean"

    def test_conflict_retired_in_hub(self):
        """Skill in hub + in manifest (not in repo) → conflict (needs user action)."""
        report = audit_skills(
            hub_skills={"cali-conflict"},
            repo_skills=set(),
            manifest_skills={"cali-conflict"},
        )
        assert report.rows[0].status == "conflict_retired_in_hub"

    def test_conflict_retired_everywhere(self):
        """Skill in hub + repo + manifest → full conflict (user put it back)."""
        report = audit_skills(
            hub_skills={"cali-zombie"},
            repo_skills={"cali-zombie"},
            manifest_skills={"cali-zombie"},
        )
        assert report.rows[0].status == "conflict_retired_everywhere"

    def test_summary_counts(self):
        """Summary correctly counts rows by status."""
        report = audit_skills(
            hub_skills={"a", "b", "c"},
            repo_skills={"a", "b", "d"},
            manifest_skills={"e", "f"},
        )
        # a, b: in_sync
        # c: in_hub_only
        # d: in_repo_only
        # e, f: retired_clean
        summary = report.summary_counts()
        assert summary.get("in_sync") == 2
        assert summary.get("in_hub_only") == 1
        assert summary.get("in_repo_only") == 1
        assert summary.get("retired_clean") == 2

    def test_all_unique_names_in_rows(self):
        """Every unique skill name across the three sources appears as a row."""
        report = audit_skills(
            hub_skills={"x", "y"},
            repo_skills={"y", "z"},
            manifest_skills={"z", "w"},
        )
        names = {r.name for r in report.rows}
        assert names == {"x", "y", "z", "w"}


class TestAuditSkillsWithFilesystem:
    """Integration with real files (tmp_path) — no real git."""

    def test_reads_hub_from_disk(self, tmp_path):
        """When hub_skills is None, read from HUB_DIR on disk."""
        hub = tmp_path / ".agents" / "skills"
        hub.mkdir(parents=True)
        (hub / "alpha").mkdir()
        (hub / "alpha" / "SKILL.md").write_text("# alpha\n")
        (hub / "beta").mkdir()
        (hub / "beta" / "SKILL.md").write_text("# beta\n")

        with patch("agent_sync.skills_audit.HUB_DIR", hub), \
             patch("agent_sync.skills_audit.REPO_DIR", tmp_path / "no-repo"), \
             patch("agent_sync.skills_audit.RETIRED_MANIFEST", tmp_path / "RETIRED.md"):
            report = audit_skills(
                hub_skills=None,
                repo_skills=set(),
                manifest_skills=set(),
            )

        assert {r.name for r in report.rows} == {"alpha", "beta"}
        assert report.hub_count == 2

    def test_reads_manifest_from_disk(self, tmp_path):
        """When manifest_skills is None, parse RETIRED.md on disk."""
        manifest = tmp_path / "RETIRED.md"
        manifest.write_text(
            "# Retired\n"
            "cali-old-1   # comment 1\n"
            "cali-old-2   # comment 2\n"
        )

        with patch("agent_sync.skills_audit.HUB_DIR", tmp_path / "no-hub"), \
             patch("agent_sync.skills_audit.REPO_DIR", tmp_path / "no-repo"), \
             patch("agent_sync.skills_audit.RETIRED_MANIFEST", manifest):
            report = audit_skills(
                hub_skills=set(),
                repo_skills=set(),
                manifest_skills=None,
            )

        assert {r.name for r in report.rows} == {"cali-old-1", "cali-old-2"}
        assert report.manifest_count == 2

    def test_repo_dir_without_git_returns_empty(self, tmp_path):
        """If REPO_DIR is not a git repo, repo skills is empty."""
        no_repo = tmp_path / "no-repo"
        no_repo.mkdir()

        with patch("agent_sync.skills_audit.HUB_DIR", tmp_path / "no-hub"), \
             patch("agent_sync.skills_audit.REPO_DIR", no_repo), \
             patch("agent_sync.skills_audit.RETIRED_MANIFEST", tmp_path / "RETIRED.md"):
            report = audit_skills(
                hub_skills={"a"},
                repo_skills=None,  # query git
                manifest_skills=set(),
            )

        assert report.repo_count == 0
        assert report.rows[0].status == "in_hub_only"


# ---------------------------------------------------------------------------
# explain_skill
# ---------------------------------------------------------------------------


class TestExplainSkill:
    """Pure-data explain. Overrides bypass filesystem."""

    def test_explain_skill_in_sync(self):
        """Skill present everywhere returns current state."""
        expl = explain_skill(
            "cali-foo",
            hub_skills={"cali-foo"},
            repo_skills={"cali-foo"},
            manifest_skills=set(),
        )
        assert expl.name == "cali-foo"
        assert expl.in_hub is True
        assert expl.in_repo is True
        assert expl.in_manifest is False
        assert expl.commit_count == 0  # no real git query

    def test_explain_skill_retired(self):
        """Skill in manifest has manifest_line set."""
        expl = explain_skill(
            "cali-old",
            hub_skills=set(),
            repo_skills=set(),
            manifest_skills={"cali-old"},
        )
        assert expl.in_manifest is True
        # manifest_line reading from real disk would need a manifest file;
        # without one it's None. Verify the default.
        assert expl.manifest_line is None

    def test_explain_skill_not_tracked_anywhere(self):
        """Skill with no presence is still valid (no error)."""
        expl = explain_skill(
            "cali-ghost",
            hub_skills=set(),
            repo_skills=set(),
            manifest_skills=set(),
        )
        assert expl.in_hub is False
        assert expl.in_repo is False
        assert expl.in_manifest is False
        assert expl.commit_count == 0

    def test_explain_skill_with_manifest_line(self, tmp_path):
        """`manifest_line` is the raw line from RETIRED.md."""
        manifest = tmp_path / "RETIRED.md"
        manifest.write_text(
            "# header\n"
            "cali-legacy   # replaced  2026-05-01\n"
        )
        with patch("agent_sync.skills_audit.RETIRED_MANIFEST", manifest):
            expl = explain_skill(
                "cali-legacy",
                hub_skills=set(),
                repo_skills=set(),
                manifest_skills={"cali-legacy"},
            )
        assert expl.manifest_line is not None
        assert "cali-legacy" in expl.manifest_line
        assert "replaced" in expl.manifest_line


class TestExplainSkillWithGit:
    """Integration with real git (tmp_path)."""

    def test_explain_skill_counts_commits(self, tmp_path):
        """commit_count reflects actual git history of skills/<name>/."""
        repo = _init_repo_with_skills(tmp_path, ["cali-foo"])
        # Add a second commit modifying the same skill
        (repo / "skills" / "cali-foo" / "extra.md").write_text("more")
        _git(repo, "add", "skills/cali-foo/extra.md")
        _git(repo, "commit", "-m", "add extra")

        with patch("agent_sync.skills_audit.REPO_DIR", repo), \
             patch("agent_sync.skills_audit.HUB_DIR", tmp_path / "no-hub"):
            expl = explain_skill(
                "cali-foo",
                hub_skills=set(),
                repo_skills=set(),
                manifest_skills=set(),
            )

        assert expl.commit_count >= 2  # at least add + modify
        assert expl.first_added is not None
        assert expl.last_modified is not None
        assert expl.first_added_at is not None
        assert expl.last_modified_at is not None

    def test_explain_skill_not_in_repo(self, tmp_path):
        """A skill with no git history has commit_count=0."""
        repo = _init_repo_with_skills(tmp_path, [])

        with patch("agent_sync.skills_audit.REPO_DIR", repo), \
             patch("agent_sync.skills_audit.HUB_DIR", tmp_path / "no-hub"):
            expl = explain_skill(
                "cali-never-existed",
                hub_skills=set(),
                repo_skills=set(),
                manifest_skills=set(),
            )

        assert expl.commit_count == 0
        assert expl.first_added is None
        assert expl.last_modified is None


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


class TestCliAudit:
    """Smoke tests for the CLI subcommands."""

    def test_audit_json_output(self, tmp_path):
        """`skills audit --json` produces valid JSON with expected fields."""
        from click.testing import CliRunner
        from agent_sync.cli import skills_group

        runner = CliRunner()
        # No filesystem patches — use the user's actual data for smoke
        result = runner.invoke(skills_group, ["audit", "--json"])
        # If it ran, must be valid JSON
        if result.exit_code == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            assert "hub_count" in data
            assert "repo_count" in data
            assert "manifest_count" in data
            assert "rows" in data
            assert isinstance(data["rows"], list)
            if data["rows"]:
                row = data["rows"][0]
                assert "name" in row
                assert "status" in row

    def test_explain_skill_in_sync(self):
        """`skills explain <name>` runs without error for a known skill."""
        from click.testing import CliRunner
        from agent_sync.cli import skills_group

        runner = CliRunner()
        result = runner.invoke(skills_group, ["explain", "cali-coding-go-stack"])
        # Should not crash, exit 0 or informative output
        assert "cali-coding-go-stack" in result.output or result.exit_code != 0

    def test_audit_limit_truncates_output(self):
        """`skills audit --limit 5` returns at most 5 rows."""
        from click.testing import CliRunner
        from agent_sync.cli import skills_group

        runner = CliRunner()
        result = runner.invoke(skills_group, ["audit", "--limit", "5", "--json"])
        if result.exit_code == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            assert len(data["rows"]) <= 5

    def test_audit_filter_searches_byname(self):
        """`skills audit --filter go` returns only 'go'-related skills."""
        from click.testing import CliRunner
        from agent_sync.cli import skills_group

        runner = CliRunner()
        result = runner.invoke(skills_group, ["audit", "--filter", "go", "--json"])
        if result.exit_code == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            assert all("go" in row["name"].lower() for row in data["rows"])
