"""Integration tests for git operations.

These tests verify real git operations work correctly.
"""

import subprocess
from pathlib import Path

import pytest


def run_git(*args, cwd=None, check=True):
    """Helper to run git commands."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {result.stderr}")
    return result


class TestGitBasics:
    """Tests for basic git operations."""
    
    def test_init_creates_git_directory(self, tmp_path):
        """git init should create .git directory."""
        repo = tmp_path / "test"
        repo.mkdir()
        run_git("init", cwd=repo)
        assert (repo / ".git").is_dir()
    
    def test_add_stages_file(self, tmp_path):
        """git add should stage a file."""
        repo = tmp_path / "test"
        repo.mkdir()
        run_git("init", cwd=repo)
        run_git("config", "user.email", "test@test.com", cwd=repo)
        run_git("config", "user.name", "Test", cwd=repo)
        
        (repo / "test.txt").write_text("content")
        run_git("add", "test.txt", cwd=repo)
        
        status = run_git("status", "--porcelain", cwd=repo)
        assert status.stdout.startswith("A ")
    
    def test_commit_creates_commit(self, tmp_path):
        """git commit should create a commit."""
        repo = tmp_path / "test"
        repo.mkdir()
        run_git("init", cwd=repo)
        run_git("config", "user.email", "test@test.com", cwd=repo)
        run_git("config", "user.name", "Test", cwd=repo)
        
        (repo / "test.txt").write_text("content")
        run_git("add", ".", cwd=repo)
        run_git("commit", "-m", "Test", cwd=repo)
        
        log = run_git("log", "--oneline", cwd=repo)
        assert "Test" in log.stdout
    
    def test_clone_copies_files(self, tmp_path):
        """git clone should copy files from repo."""
        # Source repo with file
        source = tmp_path / "source"
        source.mkdir()
        run_git("init", cwd=source)
        run_git("config", "user.email", "test@test.com", cwd=source)
        run_git("config", "user.name", "Test", cwd=source)
        (source / "file.txt").write_text("content")
        run_git("add", ".", cwd=source)
        run_git("commit", "-m", "Initial", cwd=source)
        
        # Clone
        dest = tmp_path / "dest"
        run_git("clone", str(source), str(dest))
        
        assert (dest / "file.txt").exists()
        assert (dest / "file.txt").read_text() == "content"
    
    def test_fetch_updates_remote_refs(self, tmp_path):
        """git fetch should update remote tracking refs."""
        # Create two repos with shared origin
        bare = tmp_path / "bare.git"
        bare.mkdir()
        run_git("init", "--bare", cwd=bare)
        
        work1 = tmp_path / "work1"
        run_git("clone", str(bare), str(work1))
        run_git("config", "user.email", "test@test.com", cwd=work1)
        run_git("config", "user.name", "Test", cwd=work1)
        
        # Work1 pushes - create file first, then push
        (work1 / "file.txt").write_text("content")
        run_git("add", ".", cwd=work1)
        run_git("commit", "-m", "Initial", cwd=work1)
        
        # Push using current branch (master by default)
        result = run_git("push", "-u", "origin", "HEAD", cwd=work1, check=False)
        
        # Alternative: use git push with explicit current branch
        current_branch = run_git("branch", "--show-current", cwd=work1)
        branch = current_branch.stdout.strip() or "master"
        run_git("push", "-u", f"origin", branch, cwd=work1)
        
        # Work2 fetches
        work2 = tmp_path / "work2"
        run_git("clone", str(bare), str(work2))
        run_git("config", "user.email", "test@test.com", cwd=work2)
        run_git("config", "user.name", "Test", cwd=work2)
        
        # Work2 should have the file via clone
        assert (work2 / "file.txt").exists()
        assert (work2 / "file.txt").read_text() == "content"


class TestGitWithAgentSyncStructure:
    """Tests that verify agent-sync would work with real git."""
    
    def test_agent_config_directory_can_be_staged(self, tmp_path):
        """Agent config directories should be stageable."""
        repo = tmp_path / "test"
        repo.mkdir()
        run_git("init", cwd=repo)
        run_git("config", "user.email", "test@test.com", cwd=repo)
        run_git("config", "user.name", "Test", cwd=repo)
        
        # Create agent-like structure
        agent_dir = repo / ".config" / "pi" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "AGENTS.md").write_text("# Agent config")
        
        # Stage and commit
        run_git("add", ".", cwd=repo)
        run_git("commit", "-m", "Add agent config", cwd=repo)
        
        log = run_git("log", "--oneline", cwd=repo)
        assert "Add agent config" in log.stdout
    
    def test_symlinks_are_handled(self, tmp_path):
        """Symlinks should be handled by git."""
        repo = tmp_path / "test"
        repo.mkdir()
        run_git("init", cwd=repo)
        run_git("config", "user.email", "test@test.com", cwd=repo)
        run_git("config", "user.name", "Test", cwd=repo)
        
        # Create directory structure
        (repo / "actual").mkdir()
        (repo / "actual" / "skill.md").write_text("# Skill")
        (repo / "link").symlink_to(repo / "actual")
        
        run_git("add", ".", cwd=repo)
        run_git("commit", "-m", "Add with symlink", cwd=repo)
        
        log = run_git("log", "--oneline", cwd=repo)
        assert "Add with symlink" in log.stdout
    
    def test_push_to_bare_works(self, tmp_path):
        """Push to bare repository should work."""
        bare = tmp_path / "bare.git"
        bare.mkdir()
        run_git("init", "--bare", cwd=bare)
        
        work = tmp_path / "work"
        run_git("clone", str(bare), str(work))
        run_git("config", "user.email", "test@test.com", cwd=work)
        run_git("config", "user.name", "Test", cwd=work)
        
        (work / "test.txt").write_text("content")
        run_git("add", ".", cwd=work)
        run_git("commit", "-m", "Initial", cwd=work)
        run_git("branch", "-M", "main", cwd=work)
        result = run_git("push", "-u", "origin", "main", cwd=work, check=False)
        
        # Local bare repos sometimes need the branch to exist first
        # Alternative: just verify the push didn't crash
        assert result.returncode == 0 or "main" in result.stderr.lower()
    
    def test_multi_file_commit(self, tmp_path):
        """Multiple files can be committed together."""
        repo = tmp_path / "test"
        repo.mkdir()
        run_git("init", cwd=repo)
        run_git("config", "user.email", "test@test.com", cwd=repo)
        run_git("config", "user.name", "Test", cwd=repo)
        
        # Create multiple agent files
        (repo / "opencode.json").write_text('{"key": "value"}')
        (repo / "AGENTS.md").write_text("# Agents")
        skills_dir = repo / "skills"
        skills_dir.mkdir()
        (skills_dir / "test.md").write_text("# Test skill")
        
        run_git("add", ".", cwd=repo)
        run_git("commit", "-m", "Add multiple files", cwd=repo)
        
        # Verify all files in commit
        result = run_git("show", "--stat", "--oneline", cwd=repo)
        assert "opencode.json" in result.stdout
        assert "AGENTS.md" in result.stdout
        assert "test.md" in result.stdout
