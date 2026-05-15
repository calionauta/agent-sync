"""Tests for security_scanner module."""

import pytest
from pathlib import Path
import tempfile
import os

from agent_sync.security_scanner import (
    ScanResult,
    Issue,
    scan_file,
    scan_multiple,
    scan_and_report,
    get_severity_color,
    format_issues_for_display,
    PATTERNS,
)


class TestScanResult:
    """Test ScanResult dataclass."""

    def test_creation(self):
        """Test creating a ScanResult."""
        result = ScanResult(safe=True, issues=[], summary="")
        assert result.safe is True
        assert result.issues == []
        assert result.summary == ""

    def test_with_issues(self):
        """Test ScanResult with issues."""
        issue = Issue(rule="TEST", severity="high", snippet="/Users/test/")
        result = ScanResult(safe=False, issues=[issue], summary="")
        assert result.safe is False
        assert len(result.issues) == 1
        assert result.issues[0]["rule"] == "TEST"


class TestScanFile:
    """Test scan_file function."""

    def test_safe_file(self):
        """Test scanning a file with no sensitive content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Safe content\nJust some regular markdown.")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            assert result.safe is True
            assert len(result.issues) == 0
            assert result.summary == ""
        finally:
            os.unlink(temp_path)

    def test_detects_unix_path(self):
        """Test detection of Unix absolute paths."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("My home directory is /Users/testuser/Projects")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            # ABS_PATH_UNIX has severity "high", not "critical", so safe=True
            # But the issue should still be detected
            assert any(i["rule"] == "ABS_PATH_UNIX" for i in result.issues)
            assert any(i["snippet"] == "/Users/testuser/" for i in result.issues)
        finally:
            os.unlink(temp_path)

    def test_detects_root_path(self):
        """Test detection of /root/ paths."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Server config at /root/server.yml")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            assert any(i["rule"] == "ABS_PATH_ROOT" for i in result.issues)
        finally:
            os.unlink(temp_path)

    def test_detects_openai_token(self):
        """Test detection of OpenAI API tokens."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("API key: sk-1234567890abcdefghijklmnopqrstuvwxyzAB")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            assert any(i["rule"] == "TOKEN_OPENAI" for i in result.issues)
            assert any(i["severity"] == "critical" for i in result.issues)
        finally:
            os.unlink(temp_path)

    def test_detects_github_token(self):
        """Test detection of GitHub tokens."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("GitHub token: ghp_abcdefghijklmnopqrstuvwxyz1234567890")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            assert any(i["rule"] == "TOKEN_GITHUB" for i in result.issues)
        finally:
            os.unlink(temp_path)

    def test_detects_ctx_commands(self):
        """Test detection of ctx_* function calls."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Use ctx_batch_execute() for parallel queries")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            assert any(i["rule"] == "INTERNAL_CMD_CTX" for i in result.issues)
        finally:
            os.unlink(temp_path)

    def test_detects_server_path(self):
        """Test detection of server paths."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Check server.renatocaliari.com for status")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            assert any(i["rule"] == "SERVER_PATH" for i in result.issues)
        finally:
            os.unlink(temp_path)

    def test_deduplication(self):
        """Test that duplicate issues are removed."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            # Same pattern twice
            f.write("/Users/test/ /Users/test/ /Users/test/")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            # Should only have one ABS_PATH_UNIX issue
            abs_issues = [i for i in result.issues if i["rule"] == "ABS_PATH_UNIX"]
            assert len(abs_issues) == 1
        finally:
            os.unlink(temp_path)

    def test_nonexistent_file(self):
        """Test scanning a file that doesn't exist."""
        result = scan_file(Path("/nonexistent/file.md"))
        assert result.safe is False
        assert result.summary != ""

    def test_snippet_truncation(self):
        """Test that long snippets are truncated."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            # Create a very long path
            long_path = "/Users/testuser/" + "a" * 100
            f.write(f"Path: {long_path}")
            temp_path = f.name

        try:
            result = scan_file(Path(temp_path))
            for issue in result.issues:
                assert len(issue["snippet"]) <= 63  # 60 + "..."
        finally:
            os.unlink(temp_path)


class TestScanMultiple:
    """Test scan_multiple function."""

    def test_empty_list(self):
        """Test scanning an empty list."""
        result = scan_multiple([])
        assert result == {}

    def test_single_file(self):
        """Test scanning a single file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Safe content")
            temp_path = f.name

        try:
            results = scan_multiple([Path(temp_path)])
            assert len(results) == 1
            assert Path(temp_path) in results
        finally:
            os.unlink(temp_path)

    def test_multiple_files(self):
        """Test scanning multiple files."""
        paths = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(f"Content {i}")
                paths.append(Path(f.name))

        try:
            results = scan_multiple(paths)
            assert len(results) == 3
            for p in paths:
                assert p in results
        finally:
            for p in paths:
                os.unlink(p)


class TestGetSeverityColor:
    """Test get_severity_color function."""

    def test_critical_returns_red(self):
        """Test critical severity returns red."""
        assert get_severity_color("critical") == "red"

    def test_high_returns_yellow(self):
        """Test high severity returns yellow."""
        assert get_severity_color("high") == "yellow"

    def test_medium_returns_magenta(self):
        """Test medium severity returns magenta."""
        assert get_severity_color("medium") == "magenta"

    def test_low_returns_cyan(self):
        """Test low severity returns cyan."""
        assert get_severity_color("low") == "cyan"

    def test_unknown_returns_white(self):
        """Test unknown severity returns white."""
        assert get_severity_color("unknown") == "white"


class TestFormatIssuesForDisplay:
    """Test format_issues_for_display function."""

    def test_empty_issues(self):
        """Test formatting empty issues list."""
        result = format_issues_for_display([])
        assert "No issues detected" in result

    def test_single_issue(self):
        """Test formatting a single issue."""
        issues = [Issue(rule="TEST", severity="high", snippet="/Users/test/")]
        result = format_issues_for_display(issues)
        assert "TEST" in result
        assert "/Users/test/" in result

    def test_multiple_issues(self):
        """Test formatting multiple issues."""
        issues = [
            Issue(rule="ABS_PATH_UNIX", severity="high", snippet="/Users/test/"),
            Issue(rule="TOKEN_OPENAI", severity="critical", snippet="sk-123456"),
        ]
        result = format_issues_for_display(issues)
        assert "ABS_PATH_UNIX" in result
        assert "TOKEN_OPENAI" in result


class TestPatterns:
    """Test that all expected patterns are defined."""

    def test_all_expected_rules_present(self):
        """Test all expected rules are defined in PATTERNS."""
        expected_rules = [
            "ABS_PATH_UNIX",
            "ABS_PATH_HOME",
            "ABS_PATH_ROOT",
            "ABS_PATH_WINDOWS",
            "TOKEN_OPENAI",
            "TOKEN_GITHUB",
            "TOKEN_GITHUB_ALT",
            "INTERNAL_CMD_CTX",
            "SERVER_PATH",
            "SSH_KEY",
        ]
        actual_rules = [p[0] for p in PATTERNS]
        for rule in expected_rules:
            assert rule in actual_rules, f"Missing rule: {rule}"

    def test_all_critical_have_critical_severity(self):
        """Test that token patterns have critical severity."""
        critical_rules = ["TOKEN"]
        for pattern in PATTERNS:
            rule = pattern[0]
            severity = pattern[1]
            if any(cr in rule for cr in critical_rules):
                assert severity == "critical", f"Rule {rule} should be critical, not {severity}"