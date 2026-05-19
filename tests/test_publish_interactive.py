"""Tests for the new TUI-based interactive selection system."""

from unittest.mock import MagicMock

from agent_sync.publish.models import (
    SelectionState,
    SourceInfo,
    SourcePickerItem,
    build_picker_items,
    parse_number_input,
    handle_number_input_for_state,
)


class TestSelectionState:
    """Tests for SelectionState core logic."""

    def test_creates_empty_state(self):
        """Empty state has no selections."""
        state = SelectionState()
        assert state.get_total_count() == 0
        assert state.get_selected_count() == 0

    def test_adds_items(self):
        """State tracks items from sources."""
        state = SelectionState()
        state.items = {"local": ["a", "b", "c"]}
        assert state.get_total_count() == 3

    def test_toggle_selects_item(self):
        """Toggle adds item to selection."""
        state = SelectionState()
        state.items = {"local": ["a", "b"]}
        state.selected = {"local": set()}
        
        state.toggle("local", "a")
        assert state.is_selected("local", "a")
        assert state.get_selected_count() == 1

    def test_toggle_deselects_item(self):
        """Toggle removes item from selection."""
        state = SelectionState()
        state.items = {"local": ["a"]}
        state.selected = {"local": {"a"}}
        
        state.toggle("local", "a")
        assert not state.is_selected("local", "a")
        assert state.get_selected_count() == 0

    def test_select_all(self):
        """Select all selects everything."""
        state = SelectionState()
        state.items = {"local": ["a", "b"], "ext": ["c"]}
        state.selected = {"local": set(), "ext": set()}
        
        state.select_all()
        assert state.get_selected_count() == 3

    def test_select_none(self):
        """Select none clears everything."""
        state = SelectionState()
        state.items = {"local": ["a", "b"]}
        state.selected = {"local": {"a", "b"}}
        
        state.select_none()
        assert state.get_selected_count() == 0

    def test_select_all_in_source(self):
        """Select all in specific source."""
        state = SelectionState()
        state.items = {"local": ["a", "b"], "ext": ["c"]}
        state.selected = {"local": set(), "ext": set()}
        
        state.select_all_in_source("local")
        assert state.get_selected_count() == 2
        assert state.is_selected("local", "a")
        assert state.is_selected("local", "b")
        assert not state.is_selected("ext", "c")

    def test_select_none_in_source(self):
        """Select none in specific source."""
        state = SelectionState()
        state.items = {"local": ["a", "b"]}
        state.selected = {"local": {"a", "b"}}
        
        state.select_none_in_source("local")
        assert state.get_selected_count() == 0

    def test_build_index(self):
        """Index maps numbers to items."""
        state = SelectionState()
        state.items = {"local": ["a", "b"], "ext": ["c"]}
        state.build_index()
        
        assert state.item_index[1] == ("local", "a")
        assert state.item_index[2] == ("local", "b")
        assert state.item_index[3] == ("ext", "c")

    def test_toggle_by_index(self):
        """Toggle by index works."""
        state = SelectionState()
        state.items = {"local": ["a", "b"]}
        state.selected = {"local": set()}
        state.build_index()
        
        state.toggle_by_index(1)
        assert state.is_selected("local", "a")
        
        state.toggle_by_index(1)
        assert not state.is_selected("local", "a")

    def test_get_selected_names_sorted(self):
        """Selected names are returned sorted."""
        state = SelectionState()
        state.items = {"local": ["c", "a", "b"]}
        state.selected = {"local": {"c", "a"}}
        
        names = state.get_selected_names()
        assert names == ["a", "c"]

    def test_get_selection_dict(self):
        """Returns selection as dict."""
        state = SelectionState()
        state.items = {"local": ["a", "b"]}
        state.selected = {"local": {"b"}}
        
        result = state.get_selection_dict()
        assert result == {"local": ["b"]}

    def test_get_source_range(self):
        """Gets index range for a source."""
        state = SelectionState()
        state.items = {"local": ["a", "b", "c"], "ext": ["x", "y"]}
        state.build_index()
        
        local_range = state.get_source_range("local")
        assert local_range == (1, 3)
        
        ext_range = state.get_source_range("ext")
        assert ext_range == (4, 5)

    def test_get_all_source_ranges(self):
        """Gets ranges for all sources."""
        state = SelectionState()
        state.items = {"local": ["a", "b"], "ext": ["x", "y", "z"]}
        state.build_index()
        
        ranges = state.get_all_source_ranges()
        assert ranges == {"local": (1, 2), "ext": (3, 5)}


class TestSourceInfo:
    """Tests for SourceInfo dataclass."""

    def test_creates_source_info(self):
        """SourceInfo stores source metadata."""
        info = SourceInfo(
            source_id="local",
            label="LOCAL",
            subtitle="~/.agents/skills/",
            items=["skill1", "skill2"],
            status="active",
        )
        
        assert info.source_id == "local"
        assert info.label == "LOCAL"
        assert len(info.items) == 2


class TestParseNumberInput:
    """Tests for parse_number_input function."""

    def test_single_number(self):
        """Parses single number."""
        indices = parse_number_input("1")
        assert indices == [1]

    def test_comma_separated(self):
        """Parses comma separated."""
        indices = parse_number_input("1,3,5")
        assert indices == [1, 3, 5]

    def test_range(self):
        """Parses range."""
        indices = parse_number_input("1-5")
        assert indices == [1, 2, 3, 4, 5]

    def test_mixed(self):
        """Parses mixed input."""
        indices = parse_number_input("1,3-5,7")
        assert indices == [1, 3, 4, 5, 7]

    def test_with_spaces(self):
        """Handles spaces."""
        indices = parse_number_input("1, 3, 5")
        assert indices == [1, 3, 5]

    def test_empty_parts_ignored(self):
        """Empty parts are ignored."""
        indices = parse_number_input("1,,3")
        assert indices == [1, 3]


class TestHandleNumberInputForState:
    """Tests for handle_number_input_for_state function."""

    def test_selects_items(self):
        """Selects items by index."""
        state = SelectionState()
        state.items = {"local": ["a", "b", "c"]}
        state.selected = {"local": set()}
        state.build_index()
        
        handle_number_input_for_state(state, "local", "1,3")
        
        assert state.is_selected("local", "a")
        assert not state.is_selected("local", "b")
        assert state.is_selected("local", "c")

    def test_replaces_selection(self):
        """Replaces existing selection."""
        state = SelectionState()
        state.items = {"local": ["a", "b", "c"]}
        state.selected = {"local": {"a", "b"}}
        state.build_index()
        
        handle_number_input_for_state(state, "local", "3")
        
        # a and b should be removed, only c selected
        assert not state.is_selected("local", "a")
        assert not state.is_selected("local", "b")
        assert state.is_selected("local", "c")

    def test_invalid_input_ignored(self):
        """Invalid input is ignored."""
        state = SelectionState()
        state.items = {"local": ["a", "b"]}
        state.selected = {"local": {"a"}}
        state.build_index()
        
        handle_number_input_for_state(state, "local", "invalid")
        
        # Selection unchanged
        assert state.is_selected("local", "a")
        assert not state.is_selected("local", "b")


class TestSourcePickerItem:
    """Tests for SourcePickerItem."""

    def test_creates_picker_item(self):
        """PickerItem stores data correctly."""
        item = SourcePickerItem(
            source_id="local",
            label="LOCAL",
            item_count=24,
            selected_count=5,
            subtitle="~/.agents/skills/",
        )
        
        assert item.source_id == "local"
        assert item.label == "LOCAL"
        assert item.item_count == 24
        assert item.selected_count == 5
        assert not item.is_empty

    def test_is_empty_flag(self):
        """is_empty flag is set when empty."""
        item = SourcePickerItem(
            source_id="empty",
            label="EMPTY",
            item_count=0,
            selected_count=0,
            is_empty=True,
        )
        
        assert item.is_empty


class TestBuildPickerItems:
    """Tests for build_picker_items function."""

    def test_builds_items_from_source_infos(self):
        """Builds picker items from source infos."""
        sources = [
            SourceInfo(source_id="local", label="LOCAL", items=["a", "b"]),
            SourceInfo(source_id="ext", label="EXTERNAL", items=["x"]),
        ]
        selection = {
            "local": {"a"},
            "ext": set(),
        }
        
        items = build_picker_items(sources, selection)
        
        assert len(items) == 2
        assert items[0].source_id == "local"
        assert items[0].item_count == 2
        assert items[0].selected_count == 1
        assert items[1].source_id == "ext"
        assert items[1].item_count == 1
        assert items[1].selected_count == 0

    def test_marks_empty_sources(self):
        """Empty sources are marked as is_empty."""
        sources = [
            SourceInfo(source_id="local", label="LOCAL", items=[]),
            SourceInfo(source_id="ext", label="EXTERNAL", items=["x"]),
        ]
        selection = {"local": set(), "ext": {"x"}}
        
        items = build_picker_items(sources, selection)
        
        assert items[0].is_empty
        assert not items[1].is_empty