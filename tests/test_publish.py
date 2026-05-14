import pytest
import subprocess
import json
from unittest.mock import MagicMock, patch, ANY
from pathlib import Path
from agent_sync.publish import publish_skills

class TestPublish:
    """Tests for publishing functionality."""

    @pytest.fixture
    def mock_skills(self):
        # Use existing paths or mock Path objects to avoid FileNotFoundError in shutil
        return [{"name": "skill1", "path": MagicMock(spec=Path)}]

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.Config")
    @patch("agent_sync.publish.Prompt.ask")
    @patch("agent_sync.publish.Confirm.ask")
    @patch("agent_sync.publish.subprocess.run")
    @patch("agent_sync.publish.shutil.copytree")
    @patch("agent_sync.publish.shutil.copy2")
    @patch("agent_sync.publish.Path.write_text")
    @patch("agent_sync.publish.PUBLISH_CONFIG_PATH")
    def test_publish_skills_happy_path(
        self, mock_publish_config_path, mock_write_text, mock_copy2, mock_copytree,
        mock_run, mock_confirm, mock_prompt, mock_config, mock_get_skills, mock_skills
    ):
        # Setup
        mock_get_skills.return_value = mock_skills
        mock_config_instance = mock_config.return_value
        mock_config_instance.published_skills = []
        mock_publish_config_path.exists.return_value = False

        # Adjust mock_skills to not trigger shutil real calls
        mock_skills[0]["path"].is_dir.return_value = False

        # Responses for prompts
        # 1. "a" for all available
        # 2. Repo URL
        mock_prompt.side_effect = ["a", "https://github.com/user/repo"]
        # 1. Confirm selection summary
        # 2. Confirm publishing
        mock_confirm.side_effect = [True, True]

        # Mock subprocess.run for various calls
        def run_side_effect(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "gh" in cmd and "api" in cmd and "user" in cmd:
                mock.stdout = "user"
            elif "gh" in cmd and "api" in cmd and "repos/" in cmd:
                mock.stdout = json.dumps({"private": False, "login": "user"})
            return mock

        mock_run.side_effect = run_side_effect

        # Execute
        result = publish_skills(interactive=True)

        # Verify
        assert result is True
        # Check that git push was called
        mock_run.assert_any_call(
            ["git", "push", "-u", "origin", "main", "--force"],
            cwd=ANY, capture_output=True, check=True, timeout=120
        )

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.Config")
    @patch("agent_sync.publish.Confirm.ask")
    @patch("agent_sync.publish.subprocess.run")
    @patch("agent_sync.publish.shutil.copytree")
    @patch("agent_sync.publish.shutil.copy2")
    @patch("agent_sync.publish.Path.write_text")
    def test_publish_skills_git_push_failure(
        self, mock_write_text, mock_copy2, mock_copytree, mock_run, mock_confirm, mock_config, mock_get_skills, mock_skills
    ):
        # Setup
        mock_get_skills.return_value = mock_skills
        mock_config_instance = mock_config.return_value
        mock_config_instance.published_skills = ["skill1"]
        mock_skills[0]["path"].is_dir.return_value = False

        mock_confirm.return_value = True

        # Mock subprocess.run to fail on git push
        def run_side_effect(cmd, **kwargs):
            if "git" in cmd and "push" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"Push failed")
            mock = MagicMock()
            mock.returncode = 0
            if "gh" in cmd and "api" in cmd and "repos/" in cmd:
                mock.stdout = json.dumps({"private": False})
            return mock

        mock_run.side_effect = run_side_effect

        # Execute
        result = publish_skills(repo_url="https://github.com/user/repo", interactive=False)

        # Verify
        assert result is False
        mock_run.assert_any_call(
            ["git", "push", "-u", "origin", "main", "--force"],
            cwd=ANY, capture_output=True, check=True, timeout=120
        )

    @patch("agent_sync.publish.get_available_skills")
    @patch("agent_sync.publish.Config")
    @patch("agent_sync.publish.Confirm.ask")
    @patch("agent_sync.publish.subprocess.run")
    @patch("agent_sync.publish.shutil.copytree")
    @patch("agent_sync.publish.shutil.copy2")
    @patch("agent_sync.publish.Path.write_text")
    def test_publish_skills_git_init_failure(
        self, mock_write_text, mock_copy2, mock_copytree, mock_run, mock_confirm, mock_config, mock_get_skills, mock_skills
    ):
        # Setup
        mock_get_skills.return_value = mock_skills
        mock_config_instance = mock_config.return_value
        mock_config_instance.published_skills = ["skill1"]
        mock_skills[0]["path"].is_dir.return_value = False
        mock_confirm.return_value = True

        # Mock subprocess.run to fail on git init
        def run_side_effect(cmd, **kwargs):
            if "git" in cmd and "init" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"Init failed")
            mock = MagicMock()
            mock.returncode = 0
            if "gh" in cmd and "api" in cmd and "repos/" in cmd:
                mock.stdout = json.dumps({"private": False})
            return mock

        mock_run.side_effect = run_side_effect

        # Execute
        result = publish_skills(repo_url="https://github.com/user/repo", interactive=False)

        # Verify
        assert result is False
        mock_run.assert_any_call(["git", "init"], cwd=ANY, capture_output=True, check=True, timeout=15)

    @patch("agent_sync.publish.get_available_skills")
    def test_publish_skills_no_skills_available(self, mock_get_skills):
        mock_get_skills.return_value = []
        result = publish_skills()
        assert result is False

    @patch("agent_sync.publish.validate_github_url")
    def test_publish_skills_invalid_url(self, mock_validate):
        mock_validate.return_value = False
        result = publish_skills(repo_url="invalid-url")
        assert result is False
