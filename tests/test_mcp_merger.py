"""Tests for MCPMerger."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import json


class TestMCPMerger:
    """Tests for MCPMerger class."""

    def test_merge_empty_sources(self):
        """merge() handles empty sources gracefully."""
        from agent_sync.mcp_merger import MCPMerger

        merger = MCPMerger(sources=[])
        result = merger.merge()

        assert isinstance(result, dict)
        assert "version" in result
        assert "servers" in result
        assert "conflicts" in result

    def test_merge_includes_version(self):
        """merge() includes correct version."""
        from agent_sync.mcp_merger import MCPMerger

        merger = MCPMerger(sources=[])
        result = merger.merge()

        assert result["version"] == "1.0"
        assert result["generated_by"] == "agent-sync"

    def test_merge_skips_nonexistent_sources(self, tmp_path):
        """merge() skips sources that don't exist."""
        from agent_sync.mcp_merger import MCPMerger

        fake_source = tmp_path / "nonexistent.json"
        merger = MCPMerger(sources=[fake_source])
        result = merger.merge()

        # Should not crash and return empty servers
        assert result["servers"] == {}

    def test_merge_parses_valid_json(self, tmp_path):
        """merge() parses valid MCP JSON."""
        from agent_sync.mcp_merger import MCPMerger

        mcp_file = tmp_path / "mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "filesystem": {"command": "npx", "args": ["-y", "some-server"]}
            }
        }))

        merger = MCPMerger(sources=[mcp_file])
        result = merger.merge()

        assert "filesystem" in result["servers"]

    def test_merge_handles_servers_key(self, tmp_path):
        """merge() handles 'servers' key (alternative format)."""
        from agent_sync.mcp_merger import MCPMerger

        mcp_file = tmp_path / "mcp.json"
        mcp_file.write_text(json.dumps({
            "servers": {
                "github": {"command": "npx", "args": ["-y", "github-mcp"]}
            }
        }))

        merger = MCPMerger(sources=[mcp_file])
        result = merger.merge()

        assert "github" in result["servers"]

    def test_merge_detects_conflicts(self, tmp_path):
        """merge() detects server name conflicts."""
        from agent_sync.mcp_merger import MCPMerger

        # Create two MCP configs with same server
        mcp1 = tmp_path / "mcp1.json"
        mcp1.write_text(json.dumps({
            "mcpServers": {"duplicate": {"command": "npx", "args": ["-y", "server1"]}}
        }))

        mcp2 = tmp_path / "mcp2.json"
        mcp2.write_text(json.dumps({
            "mcpServers": {"duplicate": {"command": "npx", "args": ["-y", "server2"]}}
        }))

        merger = MCPMerger(sources=[mcp1, mcp2])
        result = merger.merge()

        assert len(result["conflicts"]) > 0
        assert result["conflicts"][0]["server"] == "duplicate"

    def test_conflict_strategy_first_keeps_first(self, tmp_path):
        """merge() with strategy='first' keeps first server."""
        from agent_sync.mcp_merger import MCPMerger

        mcp1 = tmp_path / "mcp1.json"
        mcp1.write_text(json.dumps({
            "mcpServers": {"duplicate": {"command": "first", "args": []}}
        }))

        mcp2 = tmp_path / "mcp2.json"
        mcp2.write_text(json.dumps({
            "mcpServers": {"duplicate": {"command": "second", "args": []}}
        }))

        merger = MCPMerger(sources=[mcp1, mcp2])
        result = merger.merge()

        # With 'first' strategy, should have one entry (first wins)
        assert result["servers"]["duplicate"]["command"] == "first"

    def test_find_mcp_configs_returns_list(self):
        """find_mcp_configs() returns a list."""
        from agent_sync.mcp_merger import MCPMerger

        merger = MCPMerger()
        result = merger.find_mcp_configs()

        assert isinstance(result, list)

    def test_to_json_returns_string(self, tmp_path):
        """to_json() returns valid JSON string."""
        from agent_sync.mcp_merger import MCPMerger

        mcp_file = tmp_path / "mcp.json"
        mcp_file.write_text(json.dumps({"mcpServers": {}}))

        merger = MCPMerger(sources=[mcp_file])
        result = merger.to_json()

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "servers" in parsed

    def test_save_creates_file(self, tmp_path):
        """save() creates the output file."""
        from agent_sync.mcp_merger import MCPMerger

        mcp_file = tmp_path / "mcp.json"
        mcp_file.write_text(json.dumps({"mcpServers": {}}))

        merger = MCPMerger(sources=[mcp_file])
        output_file = tmp_path / "unified.json"
        merger.save(output_file)

        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)
        assert "servers" in data

    def test_get_conflict_report_no_conflicts(self, tmp_path):
        """get_conflict_report() handles no conflicts."""
        from agent_sync.mcp_merger import MCPMerger

        mcp_file = tmp_path / "mcp.json"
        mcp_file.write_text(json.dumps({"mcpServers": {}}))

        merger = MCPMerger(sources=[mcp_file])
        merger.merge()

        report = merger.get_conflict_report()
        assert "No conflicts" in report

    def test_default_output_path(self):
        """DEFAULT_OUTPUT points to ~/.agents/mcp.json."""
        from agent_sync.mcp_merger import MCPMerger

        assert str(MCPMerger.DEFAULT_OUTPUT).endswith(".agents/mcp.json")