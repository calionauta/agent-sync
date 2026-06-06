"""Tests for ConfigExporter."""
import pytest
from pathlib import Path
import json


class TestConfigExporter:
    """Tests for ConfigExporter class."""

    def test_export_returns_dict(self):
        """export() returns a dictionary with required keys."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.export()

        assert isinstance(result, dict)
        assert "version" in result
        assert "generated_by" in result
        assert "skills_hub" in result
        assert "agents" in result
        assert "sync" in result

    def test_export_includes_version(self):
        """export() includes correct version."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.export()

        assert result["version"] == "1.0"
        assert result["generated_by"] == "agent-sync"

    def test_export_includes_skills_hub(self):
        """export() includes skills_hub path."""
        from agent_sync.config_exporter import ConfigExporter
        from agent_sync.paths import HUB_DIR

        exporter = ConfigExporter()
        result = exporter.export()

        assert "skills_hub" in result
        assert str(HUB_DIR) in result["skills_hub"]

    def test_export_has_agents_section(self):
        """export() has agents section (may not be empty due to real agents)."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.export()

        assert "agents" in result
        assert isinstance(result["agents"], dict)

    def test_export_sync_includes_repo(self):
        """export() includes sync section with repo URL."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.export()

        assert "sync" in result
        assert "method" in result["sync"]
        assert "repo_url" in result["sync"]

    def test_to_json_returns_string(self):
        """to_json() returns valid JSON string."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.to_json()

        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert "version" in parsed

    def test_to_json_with_custom_indent(self):
        """to_json() respects indent parameter."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.to_json(indent=4)

        # Check that JSON is formatted with 4 spaces
        lines = result.split('\n')
        if len(lines) > 1:
            assert lines[1].startswith('    "version"')

    def test_save_creates_file(self, tmp_path):
        """save() creates the output file."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        output_file = tmp_path / "config.json"
        exporter.save(output_file)

        assert output_file.exists()
        # Verify it's valid JSON
        with open(output_file) as f:
            data = json.load(f)
        assert "version" in data

    def test_save_creates_parent_dirs(self, tmp_path):
        """save() creates parent directories if needed."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        output_file = tmp_path / "subdir" / "nested" / "config.json"
        exporter.save(output_file)

        assert output_file.exists()

    def test_version_constant(self):
        """VERSION constant is correct."""
        from agent_sync.config_exporter import ConfigExporter

        assert ConfigExporter.VERSION == "1.0"

    def test_generated_by_field(self):
        """export() includes generated_by field."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.export()

        assert result["generated_by"] == "agent-sync"

    def test_generated_at_field(self):
        """export() includes generated_at field."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.export()

        assert "generated_at" in result
        # Should be ISO format timestamp with T separator
        assert "T" in result["generated_at"]

    def test_model_field_exists(self):
        """export() includes model field (may be empty)."""
        from agent_sync.config_exporter import ConfigExporter

        exporter = ConfigExporter()
        result = exporter.export()

        assert "model" in result
        assert isinstance(result["model"], dict)