"""Integration tests for all skills configuration methods (native, config, copy)."""

import json
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

    with patch("agent_sync.skills.get_all_agents", return_value=[agent_a, agent_b]):
        # Mocking console input might be tricky, but centralize should detect conflicts
        # and resolve them using the first one found if not interactive
        stats = manager.centralize(move=True)

    assert stats["conflicts_resolved"] >= 1
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
        # Use dry_run=False to actually move files, move=True to move (not copy)
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
