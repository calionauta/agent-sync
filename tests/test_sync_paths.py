"""Tests for agent file sync with paths support."""

from agent_sync.agents import BaseAgent
from agent_sync.config import Config
from agent_sync.sync import SyncManager


def setup_mock_environment(tmp_path):
    """Helper to setup a clean mock environment."""
    home = tmp_path / "home"
    home.mkdir(parents=True)

    # Create mock agent directory
    agent_home = home / ".config" / "opencode"
    agent_home.mkdir(parents=True)

    # Create config file
    config_file = agent_home / "opencode.jsonc"
    config_file.write_text('{"settings": {}}')

    # Create plugins directory
    plugins_dir = agent_home / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "test-plugin.js").write_text("console.log('test')")

    # Create commands directory
    commands_dir = agent_home / "commands"
    commands_dir.mkdir()
    (commands_dir / "test.md").write_text("# Test command")

    # Create hidden directory
    hidden_dir = agent_home / ".opencode"
    hidden_dir.mkdir()
    (hidden_dir / "config.json").write_text("{}")

    # Create a symlink
    (plugins_dir / "link.js").symlink_to(commands_dir / "test.md")

    return home, agent_home


def test_stage_agent_files_all_files(tmp_path):
    """Test staging all agent files with all_files: true."""
    home, agent_home = setup_mock_environment(tmp_path)

    # Setup config
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("""
agents_config:
  opencode:
    sync:
      configs: true
      all_files: true
      exclude:
        - "**/*.lock"
""")

    config = Config(config_path=config_file)

    # Create sync manager
    sync_manager = SyncManager(config)
    sync_manager.repo_dir = tmp_path / "repo"
    sync_manager.repo_dir.mkdir()

    agent = BaseAgent("opencode", {
        "method": "copy",
        "config_dir": str(agent_home),
        "config_filename": "opencode.jsonc",
        "skills_dir_name": "skills",
        "check": {"always": True}
    })

    # Stage files
    sync_manager._stage_agent_files(agent)

    # Verify all files were copied
    repo_agent_dir = sync_manager.repo_dir / "configs" / "opencode"
    assert (repo_agent_dir / "opencode.jsonc").exists()
    assert (repo_agent_dir / "plugins" / "test-plugin.js").exists()
    assert (repo_agent_dir / "commands" / "test.md").exists()
    assert (repo_agent_dir / ".opencode" / "config.json").exists()
    # Symlink should be preserved
    assert (repo_agent_dir / "plugins" / "link.js").is_symlink()


def test_stage_agent_files_specific_paths(tmp_path):
    """Test staging specific paths."""
    home, agent_home = setup_mock_environment(tmp_path)

    # Setup config with specific paths
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("""
agents_config:
  opencode:
    sync:
      configs: true
      paths:
        - plugins/
        - commands/
""")

    config = Config(config_path=config_file)

    # Create sync manager
    sync_manager = SyncManager(config)
    sync_manager.repo_dir = tmp_path / "repo"
    sync_manager.repo_dir.mkdir()

    agent = BaseAgent("opencode", {
        "method": "copy",
        "config_dir": str(agent_home),
        "config_filename": "opencode.jsonc",
        "skills_dir_name": "skills",
        "check": {"always": True}
    })

    # Stage files
    sync_manager._stage_agent_files(agent)

    # Verify only specified paths were copied
    repo_agent_dir = sync_manager.repo_dir / "configs" / "opencode"
    assert (repo_agent_dir / "plugins" / "test-plugin.js").exists()
    assert (repo_agent_dir / "commands" / "test.md").exists()
    # Hidden directory should NOT be copied (not in paths)
    assert not (repo_agent_dir / ".opencode").exists()


def test_stage_agent_files_with_glob_pattern(tmp_path):
    """Test staging with glob patterns."""
    home, agent_home = setup_mock_environment(tmp_path)

    # Add more test files
    (agent_home / "test.js").write_text("var x = 1;")
    (agent_home / "test.py").write_text("x = 1")

    # Setup config with glob pattern
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("""
agents_config:
  opencode:
    sync:
      configs: false  # Only test paths
      paths:
        - "**/*.js"
""")

    config = Config(config_path=config_file)

    # Create sync manager
    sync_manager = SyncManager(config)
    sync_manager.repo_dir = tmp_path / "repo"
    sync_manager.repo_dir.mkdir()

    agent = BaseAgent("opencode", {
        "method": "copy",
        "config_dir": str(agent_home),
        "config_filename": "opencode.jsonc",
        "skills_dir_name": "skills",
        "check": {"always": True}
    })

    # Stage files
    sync_manager._stage_agent_files(agent)

    # Verify only .js files were copied
    repo_agent_dir = sync_manager.repo_dir / "configs" / "opencode"
    assert (repo_agent_dir / "test.js").exists()
    assert (repo_agent_dir / "plugins" / "test-plugin.js").exists()
    # .py file should NOT be copied
    assert not (repo_agent_dir / "test.py").exists()


def test_stage_agent_files_with_exclusions(tmp_path):
    """Test staging with exclusions."""
    home, agent_home = setup_mock_environment(tmp_path)

    # Add excluded file
    (agent_home / "test.lock").write_text("lock")
    (agent_home / "test.js").write_text("var x = 1;")

    # Setup config with exclusions
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("""
agents_config:
  opencode:
    sync:
      configs: false
      all_files: true
      exclude:
        - "**/*.lock"
""")

    config = Config(config_path=config_file)

    # Create sync manager
    sync_manager = SyncManager(config)
    sync_manager.repo_dir = tmp_path / "repo"
    sync_manager.repo_dir.mkdir()

    agent = BaseAgent("opencode", {
        "method": "copy",
        "config_dir": str(agent_home),
        "config_filename": "opencode.jsonc",
        "skills_dir_name": "skills",
        "check": {"always": True}
    })

    # Stage files
    sync_manager._stage_agent_files(agent)

    # Verify exclusions worked
    repo_agent_dir = sync_manager.repo_dir / "configs" / "opencode"
    assert (repo_agent_dir / "test.js").exists()
    # .lock file should NOT be copied
    assert not (repo_agent_dir / "test.lock").exists()


def test_copy_directory_preserves_symlinks(tmp_path):
    """Test that _copy_directory preserves symlinks."""
    home, agent_home = setup_mock_environment(tmp_path)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("")

    config = Config(config_path=config_file)

    sync_manager = SyncManager(config)
    sync_manager.repo_dir = tmp_path / "repo"
    sync_manager.repo_dir.mkdir()

    dest_dir = sync_manager.repo_dir / "test_dest"

    # Copy directory
    sync_manager._copy_directory(
        src=agent_home / "plugins",
        dest=dest_dir,
        preserve_symlinks=True,
    )

    # Verify symlink was preserved
    assert (dest_dir / "link.js").is_symlink()


def test_get_sync_options_with_defaults(tmp_path):
    """Test that get_sync_options returns proper defaults."""
    home, agent_home = setup_mock_environment(tmp_path)

    # Setup minimal config
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("""
agents_config:
  opencode:
    sync:
      configs: true
""")

    config = Config(config_path=config_file)

    # Get sync options
    options = config.get_sync_options("opencode")

    # Verify defaults
    assert options["configs"] is True
    assert options["all_files"] is False
    assert options["paths"] is None
    assert options["exclude"] == []
