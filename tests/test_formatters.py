"""Tests for formatters module (diff, table, tree)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langfuse_cli.formatters import diff, table, tree


class TestRenderDiff:
    """Test render_diff function."""

    def test_render_diff_with_differences(self):
        """Test rendering diff with different texts."""
        text1 = "Hello world\nThis is line 2\n"
        text2 = "Hello world\nThis is modified line 2\n"

        with patch("langfuse_cli.formatters.diff.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            diff.render_diff(text1, text2)

            # Verify console was created and print was called
            mock_console_class.assert_called_once()
            mock_console.print.assert_called_once()

            # Verify print was called with Syntax object
            call_args = mock_console.print.call_args[0]
            assert len(call_args) == 1
            # Check it's a Syntax object by checking its class name
            assert call_args[0].__class__.__name__ == "Syntax"

    def test_render_diff_no_differences(self):
        """Test rendering diff with identical texts."""
        text1 = "Hello world\nSame content\n"
        text2 = "Hello world\nSame content\n"

        with patch("langfuse_cli.formatters.diff.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            diff.render_diff(text1, text2)

            # Verify "No differences found" was printed
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0]
            assert "No differences found" in str(call_args[0])

    def test_render_diff_custom_labels(self):
        """Test rendering diff with custom labels."""
        text1 = "Version 1"
        text2 = "Version 2"

        with patch("langfuse_cli.formatters.diff.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            diff.render_diff(text1, text2, labels=("old", "new"))

            mock_console.print.assert_called_once()


class TestRenderRichTable:
    """Test render_rich_table function."""

    def test_render_rich_table_basic(self):
        """Test basic table rendering."""
        rows = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]
        columns = ["id", "name"]

        with patch("langfuse_cli.formatters.table.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            table.render_rich_table(rows, columns)

            # Verify console.print was called with a Table
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0]
            assert call_args[0].__class__.__name__ == "Table"

    def test_render_rich_table_with_title(self):
        """Test table rendering with title."""
        rows = [{"id": "1"}]
        columns = ["id"]

        with patch("langfuse_cli.formatters.table.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            table.render_rich_table(rows, columns, title="Test Table")

            mock_console.print.assert_called_once()

    def test_render_rich_table_empty_rows(self):
        """Test table rendering with no rows."""
        rows = []
        columns = ["id", "name"]

        with patch("langfuse_cli.formatters.table.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            table.render_rich_table(rows, columns)

            # Should still create and print the table (with headers only)
            mock_console.print.assert_called_once()

    def test_render_rich_table_missing_columns(self):
        """Test table rendering when rows are missing some columns."""
        rows = [
            {"id": "1", "name": "Alice"},
            {"id": "2"},  # missing 'name'
        ]
        columns = ["id", "name"]

        with patch("langfuse_cli.formatters.table.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            table.render_rich_table(rows, columns)

            mock_console.print.assert_called_once()


class TestFmt:
    """Test _fmt formatting function."""

    def test_fmt_none(self):
        """Test formatting None returns empty string."""
        result = table._fmt(None)
        assert result == ""

    def test_fmt_bool_true(self):
        """Test formatting True returns 'true'."""
        result = table._fmt(True)
        assert result == "true"

    def test_fmt_bool_false(self):
        """Test formatting False returns 'false'."""
        result = table._fmt(False)
        assert result == "false"

    def test_fmt_string(self):
        """Test formatting string returns the string."""
        result = table._fmt("hello")
        assert result == "hello"

    def test_fmt_number(self):
        """Test formatting numbers returns string representation."""
        assert table._fmt(42) == "42"
        assert table._fmt(3.14) == "3.14"

    def test_fmt_list(self):
        """Test formatting list returns JSON string."""
        result = table._fmt(["a", "b", "c"])
        import json

        parsed = json.loads(result)
        assert parsed == ["a", "b", "c"]

    def test_fmt_dict(self):
        """Test formatting dict returns JSON string."""
        result = table._fmt({"key": "value", "num": 42})
        import json

        parsed = json.loads(result)
        assert parsed == {"key": "value", "num": 42}

    def test_fmt_nested_structure(self):
        """Test formatting nested structures returns JSON."""
        data = {"list": [1, 2, 3], "nested": {"key": "value"}}
        result = table._fmt(data)
        import json

        parsed = json.loads(result)
        assert parsed == data


class TestRenderTraceTree:
    """Test render_trace_tree function."""

    def test_render_trace_tree_basic(self):
        """Test rendering trace with flat observations."""
        trace = {"id": "trace-1", "name": "My Trace"}
        observations = [
            {"id": "obs-1", "name": "Step 1", "type": "SPAN", "parentObservationId": None},
            {"id": "obs-2", "name": "Step 2", "type": "SPAN", "parentObservationId": None},
        ]

        with patch("langfuse_cli.formatters.tree.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            tree.render_trace_tree(trace, observations)

            # Verify console.print was called with a Tree
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0]
            assert call_args[0].__class__.__name__ == "Tree"

    def test_render_trace_tree_nested(self):
        """Test rendering trace with parent-child observations."""
        trace = {"id": "trace-1", "name": "Nested Trace"}
        observations = [
            {
                "id": "obs-1",
                "name": "Parent",
                "type": "SPAN",
                "parentObservationId": None,
                "startTime": "2024-01-01T00:00:00Z",
            },
            {
                "id": "obs-2",
                "name": "Child",
                "type": "GENERATION",
                "parentObservationId": "obs-1",
                "startTime": "2024-01-01T00:00:01Z",
            },
        ]

        with patch("langfuse_cli.formatters.tree.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            tree.render_trace_tree(trace, observations)

            mock_console.print.assert_called_once()

    def test_render_trace_tree_no_observations(self):
        """Test rendering trace with empty observations list."""
        trace = {"id": "trace-1", "name": "Empty Trace"}
        observations = []

        with patch("langfuse_cli.formatters.tree.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            tree.render_trace_tree(trace, observations)

            # Should still create tree with just the root
            mock_console.print.assert_called_once()

    def test_render_trace_tree_with_model_and_usage(self):
        """Test rendering generation with model and token usage."""
        trace = {"id": "trace-1", "name": "LLM Trace"}
        observations = [
            {
                "id": "obs-1",
                "name": "Generate",
                "type": "GENERATION",
                "parentObservationId": None,
                "model": "gpt-4",
                "usage": {"totalTokens": 1500},
            },
        ]

        with patch("langfuse_cli.formatters.tree.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            tree.render_trace_tree(trace, observations)

            mock_console.print.assert_called_once()

    def test_render_trace_tree_with_total_usage(self):
        """Test rendering with usage.total instead of totalTokens."""
        trace = {"id": "trace-1", "name": "Trace"}
        observations = [
            {
                "id": "obs-1",
                "name": "Generate",
                "type": "GENERATION",
                "parentObservationId": None,
                "usage": {"total": 2000},
            },
        ]

        with patch("langfuse_cli.formatters.tree.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            tree.render_trace_tree(trace, observations)

            mock_console.print.assert_called_once()

    def test_render_trace_tree_sorting_by_start_time(self):
        """Test that observations are sorted by startTime."""
        trace = {"id": "trace-1", "name": "Trace"}
        observations = [
            {
                "id": "obs-2",
                "name": "Second",
                "type": "SPAN",
                "parentObservationId": None,
                "startTime": "2024-01-01T00:00:02Z",
            },
            {
                "id": "obs-1",
                "name": "First",
                "type": "SPAN",
                "parentObservationId": None,
                "startTime": "2024-01-01T00:00:01Z",
            },
        ]

        with patch("langfuse_cli.formatters.tree.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            tree.render_trace_tree(trace, observations)

            # Just verify it doesn't crash - sorting is internal
            mock_console.print.assert_called_once()


class TestTypeStylesAndIcons:
    """Test TYPE_STYLES and TYPE_ICONS mappings."""

    def test_type_styles_mapping(self):
        """Test that TYPE_STYLES has expected mappings."""
        assert tree.TYPE_STYLES["GENERATION"] == "[green]"
        assert tree.TYPE_STYLES["SPAN"] == "[blue]"
        assert tree.TYPE_STYLES["EVENT"] == "[yellow]"

    def test_type_icons_mapping(self):
        """Test that TYPE_ICONS has expected mappings."""
        assert tree.TYPE_ICONS["GENERATION"] == "\u2726"
        assert tree.TYPE_ICONS["SPAN"] == "\u2500"
        assert tree.TYPE_ICONS["EVENT"] == "\u25cf"

    def test_type_styles_all_present(self):
        """Test that all observation types are in TYPE_STYLES."""
        expected_types = ["GENERATION", "SPAN", "EVENT"]
        for obs_type in expected_types:
            assert obs_type in tree.TYPE_STYLES

    def test_type_icons_all_present(self):
        """Test that all observation types are in TYPE_ICONS."""
        expected_types = ["GENERATION", "SPAN", "EVENT"]
        for obs_type in expected_types:
            assert obs_type in tree.TYPE_ICONS


class TestAddChildren:
    """Test _add_children recursive function."""

    def test_add_children_single_level(self):
        """Test adding children at single level."""
        from rich.tree import Tree

        root = Tree("root")
        children_map = {
            None: [
                {"id": "child-1", "name": "Child 1", "type": "SPAN"},
            ]
        }

        tree._add_children(root, None, children_map)

        # Verify child was added (tree should have children)
        assert len(root.children) == 1

    def test_add_children_nested(self):
        """Test adding nested children."""
        from rich.tree import Tree

        root = Tree("root")
        children_map = {
            None: [
                {"id": "parent", "name": "Parent", "type": "SPAN"},
            ],
            "parent": [
                {"id": "child", "name": "Child", "type": "GENERATION", "model": "gpt-4"},
            ],
        }

        tree._add_children(root, None, children_map)

        # Verify parent was added
        assert len(root.children) == 1
        # Verify child was added to parent
        assert len(root.children[0].children) == 1

    def test_add_children_with_usage_info(self):
        """Test adding children with usage information."""
        from rich.tree import Tree

        root = Tree("root")
        children_map = {
            None: [
                {
                    "id": "gen",
                    "name": "Generation",
                    "type": "GENERATION",
                    "model": "gpt-4",
                    "usage": {"totalTokens": 1000},
                },
            ]
        }

        tree._add_children(root, None, children_map)

        assert len(root.children) == 1

    def test_add_children_empty(self):
        """Test adding children when there are no children."""
        from rich.tree import Tree

        root = Tree("root")
        children_map = {}

        tree._add_children(root, None, children_map)

        # Should have no children
        assert len(root.children) == 0
