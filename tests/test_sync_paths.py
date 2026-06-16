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


class TestExcludePatternMatching:
    """Tests for SyncManager._should_exclude and _matches_pattern.

    Regression coverage for two bugs fixed in v0.40.0-alpha and v0.41.0-alpha:
    - Generic `state.json` no longer excluded from backups.
    - Custom user `sync.exclude` patterns now recurse into subdirectories
      (the same as the hardcoded EXCLUDE_PATTERNS).
    """

    def test_default_state_json_is_not_excluded(self):
        """`state.json` must not be excluded by default — it broke backups
        for tools (e.g. agentmemory-snapshots) that store state in subdirs.
        """
        sync = SyncManager.__new__(SyncManager)

        assert sync._should_exclude("state.json", None) is False
        assert sync._should_exclude("agentmemory-snapshots/state.json", None) is False
        assert sync._should_exclude("skills/x/state.json", None) is False

    def test_default_nested_git_dir_excluded(self):
        """Nested `.git/` directories must be excluded (avoids git-in-git in
        backups of tools that version their own subdirs).
        """
        sync = SyncManager.__new__(SyncManager)

        assert sync._should_exclude(".git", None) is True
        assert sync._should_exclude(".git/HEAD", None) is True
        assert sync._should_exclude(".git/objects/abc", None) is True
        assert sync._should_exclude("a/.git/HEAD", None) is True
        assert sync._should_exclude("agentmemory-snapshots/.git/HEAD", None) is True

    def test_custom_dir_pattern_with_slash_recurses(self):
        """`node_modules/` (trailing slash) should exclude subdirs at any depth."""
        sync = SyncManager.__new__(SyncManager)
        exclude = ["node_modules/"]

        assert sync._should_exclude("node_modules", exclude) is True
        assert sync._should_exclude("node_modules/foo.js", exclude) is True
        assert sync._should_exclude("node_modules/sub/file.js", exclude) is True
        assert sync._should_exclude("a/node_modules/b.js", exclude) is True
        # Unrelated files must NOT be excluded
        assert sync._should_exclude("node_modules_helper.txt", exclude) is False
        assert sync._should_exclude("state.json", exclude) is False

    def test_custom_dir_pattern_without_slash_recurses(self):
        """`node_modules` (no trailing slash) should also recurse — convenience."""
        sync = SyncManager.__new__(SyncManager)
        exclude = ["node_modules"]

        assert sync._should_exclude("node_modules/foo.js", exclude) is True
        assert sync._should_exclude("a/node_modules/b.js", exclude) is True
        assert sync._should_exclude("node_modules", exclude) is True

    def test_custom_glob_pattern_still_works(self):
        """Glob patterns in custom exclude must still work as before."""
        sync = SyncManager.__new__(SyncManager)
        exclude = ["*.bak", "**/*.lock"]

        assert sync._should_exclude("file.bak", exclude) is True
        assert sync._should_exclude("sub/dir/file.bak", exclude) is True
        assert sync._should_exclude("test.lock", exclude) is True
        assert sync._should_exclude("sub/test.lock", exclude) is True
        assert sync._should_exclude("file.txt", exclude) is False

    def test_custom_doublestar_prefix_recurses(self):
        """`**/name` style patterns should match at any depth."""
        sync = SyncManager.__new__(SyncManager)
        exclude = ["**/state.json"]

        assert sync._should_exclude("state.json", exclude) is True
        assert sync._should_exclude("foo/state.json", exclude) is True
        assert sync._should_exclude("a/b/state.json", exclude) is True
        # `state.json.bak` is excluded by default *.bak pattern, not by
        # `**/state.json`. Use a path that doesn't trigger other excludes.
        assert sync._should_exclude("foo/state.json", exclude) is True
        assert sync._should_exclude("state.jsonx", exclude) is False

    def test_custom_exclude_priority_over_default(self):
        """Custom patterns in user config should be checked before defaults."""
        sync = SyncManager.__new__(SyncManager)
        # `state.json` is no longer in defaults, but if user adds it
        # explicitly via sync.exclude, it should still work.
        custom = ["state.json"]

        assert sync._should_exclude("state.json", custom) is True
        assert sync._should_exclude("foo/state.json", custom) is True

    def test_empty_pattern_does_not_match(self):
        """Empty pattern must not match anything (defensive)."""
        sync = SyncManager.__new__(SyncManager)

        assert sync._should_exclude("state.json", [""]) is False
        assert sync._should_exclude("anything", [""]) is False
