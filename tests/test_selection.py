"""Tests for TUI selection utilities."""

from agent_sync._selection import parse_multiselect_input


class TestParseMultiselectInput:
    """Test parse_multiselect_input with various inputs."""

    def test_done_returns_none(self):
        """"done" returns None to signal loop exit."""
        result = parse_multiselect_input("done", ["a", "b", "c"], {"a"})
        assert result is None

    def test_empty_returns_none(self):
        """Empty string returns None to signal loop exit."""
        result = parse_multiselect_input("", ["a", "b", "c"], {"a"})
        assert result is None

    def test_all_selects_everything(self):
        """"all" returns full set of items."""
        items = ["a", "b", "c"]
        result = parse_multiselect_input("all", items, set())
        assert result == {"a", "b", "c"}

    def test_all_keeps_existing_selections(self):
        """"all" returns full set even if already partially selected."""
        items = ["a", "b", "c"]
        result = parse_multiselect_input("all", items, {"a"})
        assert result == {"a", "b", "c"}

    def test_none_clears_selection(self):
        """"none" returns empty set."""
        items = ["a", "b", "c"]
        result = parse_multiselect_input("none", items, {"a", "b"})
        assert result == set()

    def test_toggle_single_item(self):
        """Toggling an item removes it if already selected."""
        items = ["skill1", "skill2", "skill3"]
        result = parse_multiselect_input("1", items, {"skill1"})
        assert "skill1" not in result  # toggled off

    def test_toggle_single_item_off(self):
        """Toggling an item adds it if not already selected."""
        items = ["skill1", "skill2", "skill3"]
        result = parse_multiselect_input("1", items, set())
        assert "skill1" in result
        assert len(result) == 1

    def test_toggle_multiple_items(self):
        """Comma-separated numbers toggle multiple items."""
        items = ["a", "b", "c", "d"]
        result = parse_multiselect_input("1,3", items, {"b"})
        assert "a" in result    # toggled on
        assert "b" in result    # unchanged
        assert "c" in result    # toggled on
        assert "d" not in result  # unchanged
        assert len(result) == 3

    def test_toggle_mixed_selection(self):
        """Mix of adding and removing in one input."""
        items = ["a", "b", "c"]
        result = parse_multiselect_input("1,2", items, {"a", "c"})
        assert "a" not in result  # toggled off
        assert "b" in result      # toggled on
        assert "c" in result      # unchanged

    def test_invalid_number_ignored(self):
        """Numbers outside range are silently ignored."""
        items = ["a", "b", "c"]
        result = parse_multiselect_input("99", items, {"a"})
        assert result == {"a"}

    def test_invalid_input_does_nothing(self):
        """Garbage input leaves selection unchanged."""
        items = ["a", "b", "c"]
        result = parse_multiselect_input("xyz", items, {"a"})
        assert result == {"a"}

    def test_case_insensitive_all(self):
        """"ALL" works case-insensitively."""
        items = ["a", "b"]
        result = parse_multiselect_input("ALL", items, set())
        assert result == {"a", "b"}

    def test_case_insensitive_none(self):
        """"NONE" works case-insensitively."""
        items = ["a", "b"]
        result = parse_multiselect_input("NONE", items, {"a", "b"})
        assert result == set()

    def test_case_insensitive_done(self):
        """"DONE" works case-insensitively."""
        result = parse_multiselect_input("DONE", ["a"], {"a"})
        assert result is None

    def test_empty_items_list(self):
        """Empty items list with "all" returns empty set."""
        result = parse_multiselect_input("all", [], set())
        assert result == set()

    def test_single_item_toggle(self):
        """Single-item list works correctly."""
        items = ["only-one"]
        result = parse_multiselect_input("1", items, set())
        assert result == {"only-one"}
        result = parse_multiselect_input("1", items, result)
        assert result == set()
