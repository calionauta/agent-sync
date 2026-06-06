"""Integration tests for all skills configuration methods (native, config, copy)."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from agent_sync.agents import BaseAgent
from agent_sync.skills import SkillsManager


def setup_mock_environment(tmp_path):
    """Helper to setup a clean mock environment for each test."""
    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)

    # Create a global skill
    (global_dir / "global-skill").mkdir()
    (global_dir / "global-skill" / "SKILL.md").write_text("global content")

    return home, global_dir


def test_method_native_does_no_copy(tmp_path):
    """Test that 'native' method just confirms the path without copying."""
    home, global_dir = setup_mock_environment(tmp_path)
    agent_home = home / ".native-agent"
    agent_home.mkdir(parents=True)

    agent = BaseAgent("native-agent", {
        "method": "native",
        "config_dir": str(agent_home),
        "skills_dir_name": "skills",
        "check": {"always": True}
    })

    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]):
        result = manager._configure_agent(agent)

    assert result["method"] == "native"
    assert not (agent_home / "skills").exists()  # No copy should happen


def test_method_config_updating_json(tmp_path):
    """Test that 'config' method updates the agent JSON configuration."""
    home, global_dir = setup_mock_environment(tmp_path)
    agent_home = home / ".config-agent"
    agent_home.mkdir(parents=True)
    config_file = agent_home / "config.json"
    config_file.write_text(json.dumps({"settings": {"paths": []}}))

    agent = BaseAgent("config-agent", {
        "method": "config",
        "config_dir": str(agent_home),
        "config_filename": "config.json",
        "skills_dir_name": "skills",
        "check": {"always": True},
        "config_update": {"path": "settings.paths", "action": "append"}
    })

    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]):
        result = manager._configure_agent(agent)

    assert result["method"] == "config"

    # Verify JSON update
    updated_config = json.loads(config_file.read_text())
    assert str(global_dir) in updated_config["settings"]["paths"]


def test_method_copy_performs_physical_copy(tmp_path):
    """Test that 'copy' method physically copies skills to the agent directory."""
    home, global_dir = setup_mock_environment(tmp_path)
    agent_home = home / ".copy-agent"
    agent_home.mkdir(parents=True)

    # Create agent skills directory (required for copy method)
    agent_skills_dir = agent_home / "plugins"
    agent_skills_dir.mkdir(parents=True)

    agent = BaseAgent("copy-agent", {
        "method": "copy",
        "config_dir": str(agent_home),
        "skills_dir_name": "plugins", # different name to test flexibility
        "check": {"always": True}
    })

    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]):
        result = manager._configure_agent(agent)

    assert result["method"] == "copy"
    assert (agent_home / "plugins" / "global-skill" / "SKILL.md").exists()
    assert (agent_home / "plugins" / "global-skill" / "SKILL.md").read_text() == "global content"


def test_centralize_with_conflicts(tmp_path):
    """Test centralization when multiple agents have the same skill."""
    home, global_dir = setup_mock_environment(tmp_path)

    # Setup Agent A with skill X
    agent_a_home = home / ".agent-a"
    (agent_a_home / "skills" / "shared-skill").mkdir(parents=True)
    (agent_a_home / "skills" / "shared-skill" / "SKILL.md").write_text("content A")

    # Setup Agent B with same skill X
    agent_b_home = home / ".agent-b"
    (agent_b_home / "skills" / "shared-skill").mkdir(parents=True)
    (agent_b_home / "skills" / "shared-skill" / "SKILL.md").write_text("content B")

    agent_a = BaseAgent("agent-a", {"method": "copy", "config_dir": str(agent_a_home), "skills_dir_name": "skills", "check": {"always": True}})
    agent_b = BaseAgent("agent-b", {"method": "copy", "config_dir": str(agent_b_home), "skills_dir_name": "skills", "check": {"always": True}})

    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent_a, agent_b]), \
         patch.object(manager, '_sync_from_repo', return_value=0):
        stats = manager.centralize(move=True)

    assert stats["orphans_found"] >= 1
    assert (global_dir / "shared-skill" / "SKILL.md").exists()


def test_centralize_does_not_move_extension_skills(tmp_path):
    """Test that centralize does NOT move skills from extension subdirectories.

    Extension skills (e.g., ~/.config/opencode/superpowers/skills/) should:
    - Stay in their original location
    - Only be backed up via symlinks during push
    - NOT be moved to ~/.agents/skills/
    """
    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)

    # Setup opencode agent with extension subdirectory
    agent_home = home / ".config" / "opencode"
    agent_home.mkdir(parents=True)

    # Create extension subdirectory with skills
    extension_dir = agent_home / "superpowers" / "skills"
    extension_dir.mkdir(parents=True)
    (extension_dir / "extension-skill").mkdir()
    (extension_dir / "extension-skill" / "SKILL.md").write_text("extension content")

    # Create regular skills directory with a skill
    skills_dir = agent_home / "skills"
    skills_dir.mkdir()
    (skills_dir / "regular-skill").mkdir()
    (skills_dir / "regular-skill" / "SKILL.md").write_text("regular content")

    # Create symlink from skills/superpowers -> ../superpowers/skills/
    # This simulates the extension symlink
    (skills_dir / "superpowers").symlink_to(Path("..") / "superpowers" / "skills")

    agent = BaseAgent("opencode", {
        "method": "native",  # Use native to avoid copying skills back
        "config_dir": str(agent_home),
        "skills_dir_name": "skills",
        "check": {"always": True}
    })

    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0):
        manager.centralize(dry_run=False, move=True)

    # Extension skill should NOT be moved to global directory
    assert not (global_dir / "extension-skill").exists(), \
        "Extension skills should NOT be centralized"

    # Extension skill should still exist in original location
    assert (extension_dir / "extension-skill" / "SKILL.md").exists(), \
        "Extension skills should remain in original location"

    # Regular skill SHOULD be moved to global directory
    assert (global_dir / "regular-skill" / "SKILL.md").exists(), \
        "Regular skills should be centralized"

    # Regular skill should be removed from original location (moved, not copied)
    # Note: With method=native, skills are NOT copied back to agent directory
    assert not (skills_dir / "regular-skill").exists(), \
        "Regular skills should be moved (not copied)"


def test_centralize_auto_imports_orphans(tmp_path):
    """Test that --yes skip_orphans=True does NOT import orphans."""
    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)
    (global_dir / "existing-skill").mkdir()
    (global_dir / "existing-skill" / "SKILL.md").write_text("hub content")

    agent_home = home / ".agent-x"
    (agent_home / "skills" / "orphan-skill").mkdir(parents=True)
    (agent_home / "skills" / "orphan-skill" / "SKILL.md").write_text("orphan")

    agent = BaseAgent("agent-x", {"method": "copy", "config_dir": str(agent_home),
                       "skills_dir_name": "skills", "check": {"always": True}})
    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0):
        stats = manager.centralize(move=True)

    # Orphan SHOULD be auto-imported to hub
    assert (global_dir / "orphan-skill" / "SKILL.md").exists(), \
        "orphan-skill should be in hub"
    assert stats["orphans_imported"] == 1
    # Phase 5 (configure_agents) re-populates copy-method agents from hub,
    # so the skill is ALSO in the agent (copied from hub, not the orphan copy)
    assert (agent_home / "skills" / "orphan-skill" / "SKILL.md").exists(), \
        "configure_agents() re-populates copy agents from hub"


def test_centralize_copy_mode_keeps_originals(tmp_path):
    """Test that --copy mode imports orphans but keeps originals in agents."""
    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)
    (global_dir / "existing-skill").mkdir()
    (global_dir / "existing-skill" / "SKILL.md").write_text("hub content")

    agent_home = home / ".agent-y"
    (agent_home / "skills" / "orphan-skill").mkdir(parents=True)
    (agent_home / "skills" / "orphan-skill" / "SKILL.md").write_text("orphan")

    agent = BaseAgent("agent-y", {"method": "copy", "config_dir": str(agent_home),
                       "skills_dir_name": "skills", "check": {"always": True}})
    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0):
        stats = manager.centralize(move=False)

    # Orphan SHOULD have been imported
    assert (global_dir / "orphan-skill" / "SKILL.md").exists(), \
        "--copy should import orphan-skill"
    assert stats["orphans_imported"] == 1
    # With move=False, orphan should remain in agent
    assert (agent_home / "skills" / "orphan-skill" / "SKILL.md").exists(), \
        "--copy mode should keep originals"


def test_centralize_fresh_setup_auto_import(tmp_path):
    """Test that empty hub (fresh setup) auto-imports all orphans."""
    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)  # Empty hub - fresh setup!

    agent_home = home / ".agent-z"
    (agent_home / "skills" / "fresh-skill").mkdir(parents=True)
    (agent_home / "skills" / "fresh-skill" / "SKILL.md").write_text("fresh")

    agent = BaseAgent("agent-z", {"method": "copy", "config_dir": str(agent_home),
                       "skills_dir_name": "skills", "check": {"always": True}})
    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0):
        stats = manager.centralize(move=True)

    # Should auto-import fresh-skill
    assert (global_dir / "fresh-skill" / "SKILL.md").exists(), \
        "Fresh setup should auto-import"
    assert stats["orphans_imported"] == 1


def test_centralize_dry_run_does_not_move(tmp_path):
    """Test that dry_run=True does not modify anything."""
    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)

    agent_home = home / ".agent-dry"
    (agent_home / "skills" / "dry-skill").mkdir(parents=True)
    (agent_home / "skills" / "dry-skill" / "SKILL.md").write_text("dry")

    agent = BaseAgent("agent-dry", {"method": "copy", "config_dir": str(agent_home),
                       "skills_dir_name": "skills", "check": {"always": True}})
    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0):
        # dry_run=True with fresh setup - should report but not move
        stats = manager.centralize(dry_run=True, move=True)

    # Hub should be empty (nothing was moved)
    items = [i for i in global_dir.iterdir() if not i.name.startswith(".")]
    assert len(items) == 0, f"Dry run should not move files, found {len(items)}"
    # Orphan should still be in agent
    assert (agent_home / "skills" / "dry-skill" / "SKILL.md").exists(), \
        "Dry run should not delete from agent"


def test_compute_dir_hash(tmp_path):
    """Test _compute_dir_hash produces consistent hashes."""
    from agent_sync.skills import SkillsManager

    # Create two identical skill directories
    d1 = tmp_path / "skill-a"
    d1.mkdir()
    (d1 / "SKILL.md").write_text("same content")
    (d1 / "script.py").write_text("print('hello')")

    d2 = tmp_path / "skill-b"
    d2.mkdir()
    (d2 / "SKILL.md").write_text("same content")
    (d2 / "script.py").write_text("print('hello')")

    # Create a different skill directory
    d3 = tmp_path / "skill-c"
    d3.mkdir()
    (d3 / "SKILL.md").write_text("different content")

    h1 = SkillsManager._compute_dir_hash(d1)
    h2 = SkillsManager._compute_dir_hash(d2)
    h3 = SkillsManager._compute_dir_hash(d3)

    assert h1 == h2, "Identical directories should have same hash"
    assert h1 != h3, "Different directories should have different hashes"
    assert len(h1) == 32, "MD5 hash should be 32 hex chars"


def test_find_orphans_empty_hub(tmp_path):
    """Test _find_orphans with no hub skills (fresh setup)."""
    from agent_sync.skills import SkillsManager

    # Build skills_found dict (mimicking scan_all_agents output)
    agent_dir = tmp_path / "agent"
    (agent_dir / "skills" / "my-skill").mkdir(parents=True)
    (agent_dir / "skills" / "my-skill" / "SKILL.md").write_text("test")

    skills_found = {
        "test-agent": [agent_dir / "skills" / "my-skill"]
    }

    orphans = SkillsManager._find_orphans(set(), skills_found)
    assert "my-skill" in orphans
    assert len(orphans["my-skill"]["agents"]) == 1
    assert orphans["my-skill"]["agents"][0][0] == "test-agent"


def test_find_orphans_skill_in_hub(tmp_path):
    """Test _find_orphans skips skills that already exist in hub."""
    from agent_sync.skills import SkillsManager

    agent_dir = tmp_path / "agent"
    (agent_dir / "skills" / "my-skill").mkdir(parents=True)
    (agent_dir / "skills" / "my-skill" / "SKILL.md").write_text("test")
    (agent_dir / "skills" / "another-skill").mkdir(parents=True)
    (agent_dir / "skills" / "another-skill" / "SKILL.md").write_text("test2")

    skills_found = {
        "test-agent": [
            agent_dir / "skills" / "my-skill",
            agent_dir / "skills" / "another-skill",
        ]
    }

    # my-skill is in hub, another-skill is not
    orphans = SkillsManager._find_orphans({"my-skill"}, skills_found)
    assert "my-skill" not in orphans, "Skills in hub should not be orphans"
    assert "another-skill" in orphans, "Skills not in hub should be orphans"


def test_find_orphans_skips_retired_skills(tmp_path):
    """Test that _find_orphans excludes retired skills."""
    from agent_sync.skills import SkillsManager

    agent_dir = tmp_path / "agent"
    (agent_dir / "skills" / "retired-old").mkdir(parents=True)
    (agent_dir / "skills" / "retired-old" / "SKILL.md").write_text("old version")
    (agent_dir / "skills" / "active-new").mkdir(parents=True)
    (agent_dir / "skills" / "active-new" / "SKILL.md").write_text("new version")

    skills_found = {
        "test-agent": [
            agent_dir / "skills" / "retired-old",
            agent_dir / "skills" / "active-new",
        ]
    }

    # Pass retired set: retired-old should be excluded, active-new should remain
    orphans = SkillsManager._find_orphans(set(), skills_found, retired={"retired-old"})
    assert "retired-old" not in orphans, "Retired skills should be excluded"
    assert "active-new" in orphans, "Non-retired skills should still be found"
    assert len(orphans) == 1, "Only non-retired skill should be in orphans"


def test_find_orphans_retired_none_is_backward_compat(tmp_path):
    """Test that _find_orphans works without retired param (backward compat)."""
    from agent_sync.skills import SkillsManager

    agent_dir = tmp_path / "agent"
    (agent_dir / "skills" / "some-skill").mkdir(parents=True)
    (agent_dir / "skills" / "some-skill" / "SKILL.md").write_text("test")

    skills_found = {"test-agent": [agent_dir / "skills" / "some-skill"]}

    # No retired param = old behavior
    orphans = SkillsManager._find_orphans(set(), skills_found)
    assert "some-skill" in orphans, "Default should not filter anything"


def test_centralize_skips_retired_orphans(tmp_path):
    """Test that centralize does NOT import retired skills as orphans.

    Regression guard: retired skills (deleted from git history) must never
    be re-imported, even if stale copies exist in agent directories.
    """
    from agent_sync.skills import SkillsManager
    from agent_sync.agents import BaseAgent

    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)
    (global_dir / "existing-skill").mkdir()
    (global_dir / "existing-skill" / "SKILL.md").write_text("hub content")

    # Agent has BOTH a retired skill (should be skipped) and a real orphan
    agent_home = home / ".agent-retired"
    (agent_home / "skills" / "retired-old").mkdir(parents=True)
    (agent_home / "skills" / "retired-old" / "SKILL.md").write_text("old copy")
    (agent_home / "skills" / "real-orphan").mkdir(parents=True)
    (agent_home / "skills" / "real-orphan" / "SKILL.md").write_text("new orphan")

    agent = BaseAgent("agent-retired", {
        "method": "copy", "config_dir": str(agent_home),
        "skills_dir_name": "skills", "check": {"always": True},
    })
    manager = SkillsManager(global_skills_dir=global_dir)

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0), \
         patch.object(manager, '_get_retired_skill_names', return_value={"retired-old"}):
        stats = manager.centralize(move=True)

    # Retired skill must NOT be imported
    assert not (global_dir / "retired-old" / "SKILL.md").exists(), \
        "Retired skill should NOT be imported to hub"
    # Real orphan should still be imported
    assert (global_dir / "real-orphan" / "SKILL.md").exists(), \
        "Real orphan should still be imported"
    assert stats["orphans_imported"] == 1, \
        "Only real orphan should be imported"


def test_get_retired_skill_names_from_git_history(tmp_path):
    """Retirement is derived from git history. A skill deleted and
    NOT re-added is retired. A skill deleted and RE-ADDED is NOT.
    A skill never deleted is NOT.
    """
    import subprocess
    from unittest.mock import patch

    def _git(*a):
        subprocess.run(["git", "-C", str(repo_dir)] + list(a),
                       capture_output=True, check=True)
    repo_dir = tmp_path / "repo"
    (repo_dir / "skills").mkdir(parents=True)
    for s in ["alive", "dead"]:
        (repo_dir / "skills" / s).mkdir(parents=True)
        (repo_dir / "skills" / s / "SKILL.md").write_text(f"# {s}\n")
    _git("init")
    _git("config", "user.email", "t@t")
    _git("config", "user.name", "T")
    _git("add", "-A")
    _git("commit", "-m", "add both")

    import shutil
    shutil.rmtree(repo_dir / "skills" / "dead")
    _git("add", "-A")
    _git("commit", "-m", "delete dead")

    # Re-add dead (simulating user putting it back)
    (repo_dir / "skills" / "dead").mkdir()
    (repo_dir / "skills" / "dead" / "SKILL.md").write_text("# dead (back)\n")
    _git("add", "-A")
    _git("commit", "-m", "re-add dead")

    manager = SkillsManager(global_skills_dir=tmp_path / "hub")
    with patch('agent_sync.paths.REPO_DIR', repo_dir):
        retired = manager._get_retired_skill_names()

    assert "alive" not in retired, "alive was never deleted"
    assert "dead" not in retired, "dead was re-added to HEAD"

    # Now test truly deleted (never re-added)
    shutil.rmtree(repo_dir / "skills" / "dead")
    _git("add", "-A")
    _git("commit", "-m", "delete dead again")

    with patch('agent_sync.paths.REPO_DIR', repo_dir):
        retired = manager._get_retired_skill_names()
    assert "dead" in retired, "dead was deleted and NOT re-added"
    assert "alive" not in retired, "alive was never deleted"


def test_centralize_lock_prevents_concurrent(tmp_path):
    """Test that centralize lock prevents a second process from running."""
    from agent_sync.skills import SkillsManager
    from agent_sync.agents import BaseAgent

    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)

    agent = BaseAgent("test-agent", {
        "method": "native", "config_dir": str(home),
        "skills_dir_name": "skills", "check": {"always": True},
    })
    manager = SkillsManager(global_skills_dir=global_dir)

    lock = manager._centralize_lock_dir()
    lock.mkdir()  # Simulate another process holding the lock

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0), \
         patch.object(manager, '_get_retired_skill_names', return_value=set()):
        stats = manager.centralize(move=True)

    assert stats["errors"] == 1, "Concurrent lock should cause an error"
    assert lock.exists(), "Existing lock should NOT be removed by second process"

    lock.rmdir()


def test_centralize_lock_acquire_and_release(tmp_path):
    """Test that centralize acquires and releases the lock."""
    from agent_sync.skills import SkillsManager
    from agent_sync.agents import BaseAgent

    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)
    (global_dir / "existing-skill").mkdir()
    (global_dir / "existing-skill" / "SKILL.md").write_text("content")

    agent = BaseAgent("test-agent", {
        "method": "native", "config_dir": str(home),
        "skills_dir_name": "skills", "check": {"always": True},
    })
    manager = SkillsManager(global_skills_dir=global_dir)

    lock = manager._centralize_lock_dir()
    assert not lock.exists(), "Lock should not exist before centralize"

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0), \
         patch.object(manager, '_get_retired_skill_names', return_value=set()):
        stats = manager.centralize(move=True)

    assert stats["errors"] == 0, "No errors expected"
    assert not lock.exists(), "Lock should be released after centralize"


def test_centralize_stale_lock_is_cleared(tmp_path):
    """Test that a stale lock is removed and re-acquired."""
    from agent_sync.skills import SkillsManager
    import time

    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)

    manager = SkillsManager(global_skills_dir=global_dir)
    lock = manager._centralize_lock_dir()
    lock.mkdir()

    old_time = time.time() - 3600  # 1 hour ago
    os.utime(lock, (old_time, old_time))

    assert manager._acquire_centralize_lock(), "Stale lock should be acquired"
    assert lock.exists(), "New lock should exist"
    assert lock.stat().st_mtime >= time.time() - 5, "New lock should have recent mtime"

    lock.rmdir()


def test_centralize_dry_run_skips_lock(tmp_path):
    """Test that dry-run does NOT acquire the lock."""
    from agent_sync.skills import SkillsManager
    from agent_sync.agents import BaseAgent

    home = tmp_path / "home"
    global_dir = home / ".agents" / "skills"
    global_dir.mkdir(parents=True)
    (global_dir / "some-skill").mkdir()
    (global_dir / "some-skill" / "SKILL.md").write_text("content")

    agent = BaseAgent("test-agent", {
        "method": "native", "config_dir": str(home),
        "skills_dir_name": "skills", "check": {"always": True},
    })
    manager = SkillsManager(global_skills_dir=global_dir)

    lock = manager._centralize_lock_dir()
    assert not lock.exists(), "Lock should not exist before"

    with patch("agent_sync.skills.get_all_agents", return_value=[agent]), \
         patch.object(manager, '_sync_from_repo', return_value=0), \
         patch.object(manager, '_get_retired_skill_names', return_value=set()):
        stats = manager.centralize(dry_run=True, move=True)

    assert not lock.exists(), "Dry-run should not create a lock"
    assert stats["errors"] == 0, "No errors expected"
