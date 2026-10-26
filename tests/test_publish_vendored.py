"""Tests for vendored (pinned) third-party skill sources."""

import subprocess
from pathlib import Path

import pytest

from agent_sync.publish.vendored import (
    LOCK_FILENAME,
    LockEntry,
    VendorError,
    VendorSource,
    find_skill_dir,
    materialize,
    read_lock,
    write_lock,
)


def _git(*args, cwd):
    subprocess.run(
        ["git", "-c", "user.email=t@t.t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _make_upstream(root: Path, version: str = "1.0.0") -> Path:
    """Build a fake upstream repo with skills/demo/SKILL.md at a tag."""
    repo = root / "upstream"
    skill = repo / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f'---\nname: demo\nversion: "{version}"\n---\nbody\n')
    (skill / ".gitignore").write_text("ignored\n")
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__" / "x.pyc").write_text("junk")
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", f"v{version}", cwd=repo)
    _git("tag", f"v{version}", cwd=repo)
    return repo


class TestVendorSource:
    def test_source_id_separate_from_local(self):
        """Vendored skills never share the `local` source id."""
        src = VendorSource(name="demo", url="https://github.com/o/r", ref="v1.0.0")
        assert src.source_id == "vendor/o/r"
        assert "local" not in src.source_id

    def test_roundtrip_dict(self):
        src = VendorSource(name="demo", url="https://github.com/o/r", ref="v1", path="a/b")
        assert VendorSource.from_dict(src.to_dict()) == src

    def test_dict_omits_empty_path(self):
        src = VendorSource(name="demo", url="https://github.com/o/r")
        assert "path" not in src.to_dict()


class TestMaterialize:
    def test_pins_exact_ref(self, tmp_path):
        """Content comes from the declared ref, not the default branch."""
        upstream = _make_upstream(tmp_path, "1.0.0")
        skill = upstream / "skills" / "demo"
        (skill / "SKILL.md").write_text('---\nname: demo\nversion: "2.0.0"\n---\n')
        _git("commit", "-qam", "v2", cwd=upstream)

        out = tmp_path / "publish"
        out.mkdir()
        entries = materialize(
            [VendorSource(name="demo", url=str(upstream), ref="v1.0.0", path="skills/demo")],
            out,
        )

        published = (out / "skills" / "local" / "demo" / "SKILL.md").read_text()
        assert 'version: "1.0.0"' in published
        assert entries[0].ref == "v1.0.0"
        assert entries[0].path == "skills/demo"
        assert entries[0].published_path == "skills/local/demo"

    def test_records_resolved_commit(self, tmp_path):
        upstream = _make_upstream(tmp_path)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=upstream,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        out = tmp_path / "publish"
        out.mkdir()
        entries = materialize(
            [VendorSource(name="demo", url=str(upstream), ref="v1.0.0", path="skills/demo")],
            out,
        )
        assert entries[0].commit == head

    def test_drops_vcs_and_cache_junk(self, tmp_path):
        upstream = _make_upstream(tmp_path)
        out = tmp_path / "publish"
        out.mkdir()
        materialize(
            [VendorSource(name="demo", url=str(upstream), ref="v1.0.0", path="skills/demo")],
            out,
        )
        published = out / "skills" / "local" / "demo"
        assert not (published / ".git").exists()
        assert not (published / "__pycache__").exists()
        assert not (published / ".gitignore").exists()

    def test_unknown_ref_publishes_nothing(self, tmp_path):
        """A wrong pin must fail loudly, never fall back to a stale copy."""
        upstream = _make_upstream(tmp_path)
        out = tmp_path / "publish"
        out.mkdir()

        with pytest.raises(VendorError):
            materialize(
                [VendorSource(name="demo", url=str(upstream), ref="v9.9.9", path="skills/demo")],
                out,
            )
        assert not (out / "skills").exists()

    def test_one_failure_blocks_the_whole_publish(self, tmp_path):
        """Partial vendoring would ship a repo with a silently missing skill."""
        upstream = _make_upstream(tmp_path)
        out = tmp_path / "publish"
        out.mkdir()

        with pytest.raises(VendorError):
            materialize(
                [
                    VendorSource(name="demo", url=str(upstream), ref="v1.0.0", path="skills/demo"),
                    VendorSource(name="ghost", url=str(upstream), ref="v9.9.9"),
                ],
                out,
            )

    def test_skips_inactive_sources(self, tmp_path):
        upstream = _make_upstream(tmp_path)
        out = tmp_path / "publish"
        out.mkdir()
        entries = materialize(
            [
                VendorSource(
                    name="demo",
                    url=str(upstream),
                    ref="v1.0.0",
                    path="skills/demo",
                    status="disabled",
                )
            ],
            out,
        )
        assert entries == []
        assert not (out / "skills").exists()


class TestFindSkillDir:
    def test_explicit_path_wins(self, tmp_path):
        (tmp_path / "custom" / "demo").mkdir(parents=True)
        (tmp_path / "custom" / "demo" / "SKILL.md").write_text("x")
        src = VendorSource(name="demo", url="u", path="custom/demo")
        assert find_skill_dir(tmp_path, src) == tmp_path / "custom" / "demo"

    def test_explicit_path_without_skill_md_raises(self, tmp_path):
        (tmp_path / "custom").mkdir()
        src = VendorSource(name="demo", url="u", path="custom")
        with pytest.raises(VendorError, match="no SKILL.md"):
            find_skill_dir(tmp_path, src)

    def test_finds_skills_name(self, tmp_path):
        (tmp_path / "skills" / "demo").mkdir(parents=True)
        (tmp_path / "skills" / "demo" / "SKILL.md").write_text("x")
        assert (
            find_skill_dir(tmp_path, VendorSource(name="demo", url="u"))
            == tmp_path / "skills" / "demo"
        )

    def test_finds_single_nested_match(self, tmp_path):
        (tmp_path / "agent_skills" / "demo").mkdir(parents=True)
        (tmp_path / "agent_skills" / "demo" / "SKILL.md").write_text("x")
        assert (
            find_skill_dir(tmp_path, VendorSource(name="demo", url="u"))
            == tmp_path / "agent_skills" / "demo"
        )

    def test_ambiguous_match_raises(self, tmp_path):
        for parent in ("a", "b"):
            (tmp_path / parent / "demo").mkdir(parents=True)
            (tmp_path / parent / "demo" / "SKILL.md").write_text("x")
        with pytest.raises(VendorError, match="ambiguous"):
            find_skill_dir(tmp_path, VendorSource(name="demo", url="u"))


class TestLockFile:
    def test_write_and_read_roundtrip(self, tmp_path):
        entries = [
            LockEntry(
                name="b",
                url="https://github.com/o/b",
                ref="v2",
                commit="c2",
                path="skills/b",
                published_path="skills/local/b",
            ),
            LockEntry(
                name="a",
                url="https://github.com/o/a",
                ref="v1",
                commit="c1",
                path="skills/a",
                published_path="skills/local/a",
            ),
        ]
        write_lock(tmp_path, entries)

        lock = read_lock(tmp_path)
        assert sorted(lock) == ["a", "b"]
        assert lock["a"].commit == "c1"

    def test_lock_is_sorted_by_name(self, tmp_path):
        write_lock(
            tmp_path,
            [
                LockEntry(name="z", url="u", ref="r", commit="c", path="p", published_path="pp"),
                LockEntry(name="a", url="u", ref="r", commit="c", path="p", published_path="pp"),
            ],
        )
        text = (tmp_path / LOCK_FILENAME).read_text()
        assert text.index("name: a") < text.index("name: z")

    def test_missing_lock_reads_empty(self, tmp_path):
        assert read_lock(tmp_path) == {}
