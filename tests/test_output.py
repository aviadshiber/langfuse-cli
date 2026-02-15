"""Tests for output rendering module."""

from __future__ import annotations

import io
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from langfuse_cli.output import (
    OutputContext,
    _apply_jq,
    _deep_get,
    _format_value,
    _pick_fields,
)


class TestOutputContext:
    """Test OutputContext dataclass and properties."""

    def test_default_values(self):
        """Test that OutputContext has correct defaults."""
        ctx = OutputContext()
        assert ctx.json_fields is None
        assert ctx.jq_expr is None
        assert ctx.quiet is False
        assert ctx.force_json is False

    def test_custom_values(self):
        """Test that custom values can be set."""
        ctx = OutputContext(
            json_fields=["id", "name"],
            jq_expr=".[] | .id",
            quiet=True,
            force_json=True,
        )
        assert ctx.json_fields == ["id", "name"]
        assert ctx.jq_expr == ".[] | .id"
        assert ctx.quiet is True
        assert ctx.force_json is True


class TestIsJsonMode:
    """Test is_json_mode property."""

    def test_force_json_true(self):
        """Test that force_json triggers JSON mode."""
        ctx = OutputContext(force_json=True)
        assert ctx.is_json_mode is True

    def test_json_fields_set(self):
        """Test that json_fields triggers JSON mode."""
        ctx = OutputContext(json_fields=["id", "name"])
        assert ctx.is_json_mode is True

    def test_jq_expr_set(self):
        """Test that jq_expr triggers JSON mode."""
        ctx = OutputContext(jq_expr=".[] | .id")
        assert ctx.is_json_mode is True

    def test_no_json_mode(self):
        """Test that default is not JSON mode."""
        ctx = OutputContext()
        assert ctx.is_json_mode is False

    def test_multiple_json_flags(self):
        """Test that multiple JSON flags all trigger JSON mode."""
        ctx = OutputContext(
            force_json=True,
            json_fields=["id"],
            jq_expr=".[] | .id",
        )
        assert ctx.is_json_mode is True


class TestRenderTable:
    """Test render_table method."""

    def test_json_mode_outputs_json(self, capsys):
        """Test that JSON mode outputs valid JSON."""
        ctx = OutputContext(force_json=True)
        rows = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]
        ctx.render_table(rows, ["id", "name"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert len(output) == 2
        assert output[0] == {"id": "1", "name": "Alice"}
        assert output[1] == {"id": "2", "name": "Bob"}

    def test_empty_rows_shows_status(self, capsys):
        """Test that empty rows prints 'No results found.' to stderr."""
        ctx = OutputContext(_is_tty=False)
        ctx.render_table([], ["id", "name"])

        captured = capsys.readouterr()
        assert captured.out == ""
        assert "No results found." in captured.err

    def test_non_tty_outputs_tsv(self, capsys):
        """Test that non-TTY mode outputs tab-separated values."""
        ctx = OutputContext(_is_tty=False)
        rows = [
            {"id": "1", "name": "Alice", "age": 30},
            {"id": "2", "name": "Bob", "age": 25},
        ]
        ctx.render_table(rows, ["id", "name", "age"])

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "1\tAlice\t30"
        assert lines[1] == "2\tBob\t25"

    def test_tty_mode_uses_rich_table(self, capsys):
        """Test that TTY mode uses Rich table rendering."""
        # Patch Console where it's imported (inside the method)
        with patch("rich.console.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            ctx = OutputContext(_is_tty=True)
            rows = [{"id": "1", "name": "Alice"}]
            ctx.render_table(rows, ["id", "name"])

            # Verify Console was created and print was called
            mock_console_class.assert_called_once()
            mock_console.print.assert_called_once()

    def test_missing_columns_show_empty(self, capsys):
        """Test that missing columns show as empty strings."""
        ctx = OutputContext(_is_tty=False)
        rows = [{"id": "1"}]  # missing 'name' column
        ctx.render_table(rows, ["id", "name"])

        captured = capsys.readouterr()
        # strip() removes trailing tabs, so just check the line ends with tab + newline
        assert captured.out == "1\t\n"

    def test_json_mode_with_empty_rows(self, capsys):
        """Test that JSON mode outputs empty array for empty rows."""
        ctx = OutputContext(force_json=True)
        ctx.render_table([], ["id", "name"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output == []


class TestRenderJson:
    """Test render_json method."""

    def test_renders_single_item_as_array(self, capsys):
        """Test that single item is wrapped in array."""
        ctx = OutputContext()
        ctx.render_json({"id": "1", "name": "Alice"})

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output, list)
        assert len(output) == 1
        assert output[0] == {"id": "1", "name": "Alice"}

    def test_renders_list_as_is(self, capsys):
        """Test that list is rendered as-is."""
        ctx = OutputContext()
        data = [{"id": "1"}, {"id": "2"}]
        ctx.render_json(data)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output == data


class TestRenderDetail:
    """Test render_detail method."""

    def test_json_mode_outputs_json(self, capsys):
        """Test that JSON mode outputs the data dict."""
        ctx = OutputContext(force_json=True)
        data = {"id": "1", "name": "Alice", "age": 30}
        fields = [("ID", "id"), ("Name", "name")]
        ctx.render_detail(data, fields)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert len(output) == 1
        assert output[0] == data

    def test_non_tty_outputs_label_value(self, capsys):
        """Test that non-TTY mode outputs label\\tvalue format."""
        ctx = OutputContext(_is_tty=False)
        data = {"id": "1", "name": "Alice", "age": 30}
        fields = [("ID", "id"), ("Name", "name"), ("Age", "age")]
        ctx.render_detail(data, fields)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "ID\t1"
        assert lines[1] == "Name\tAlice"
        assert lines[2] == "Age\t30"

    def test_tty_mode_uses_rich_table(self, capsys):
        """Test that TTY mode uses Rich table for detail view."""
        with patch("rich.console.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            ctx = OutputContext(_is_tty=True)
            data = {"id": "1", "name": "Alice"}
            fields = [("ID", "id"), ("Name", "name")]
            ctx.render_detail(data, fields)

            mock_console_class.assert_called_once()
            mock_console.print.assert_called_once()

    def test_nested_field_access(self, capsys):
        """Test that nested fields work with dot notation."""
        ctx = OutputContext(_is_tty=False)
        data = {"user": {"name": "Alice", "email": "alice@example.com"}}
        fields = [("Name", "user.name"), ("Email", "user.email")]
        ctx.render_detail(data, fields)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines[0] == "Name\tAlice"
        assert lines[1] == "Email\talice@example.com"

    def test_missing_field_shows_empty(self, capsys):
        """Test that missing field shows empty string."""
        ctx = OutputContext(_is_tty=False)
        data = {"id": "1"}
        fields = [("ID", "id"), ("Name", "name")]
        ctx.render_detail(data, fields)

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines[0] == "ID\t1"
        # Second line will be "Name\t" but strip() removes the trailing tab
        assert lines[1] == "Name"


class TestStatus:
    """Test status method."""

    def test_status_printed_when_not_quiet(self, capsys):
        """Test that status is printed to stderr when not quiet."""
        ctx = OutputContext(quiet=False)
        ctx.status("Processing...")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Processing...\n"

    def test_status_suppressed_when_quiet(self, capsys):
        """Test that status is suppressed in quiet mode."""
        ctx = OutputContext(quiet=True)
        ctx.status("Processing...")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestError:
    """Test error method."""

    def test_error_always_shown(self, capsys):
        """Test that error is always shown even in quiet mode."""
        ctx = OutputContext(quiet=True)
        ctx.error("Error occurred!")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Error occurred!\n"

    def test_error_shown_when_not_quiet(self, capsys):
        """Test that error is shown when not quiet."""
        ctx = OutputContext(quiet=False)
        ctx.error("Error occurred!")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Error occurred!\n"


class TestPickFields:
    """Test _pick_fields function."""

    def test_pick_single_field(self):
        """Test picking a single field."""
        item = {"id": "1", "name": "Alice", "age": 30}
        result = _pick_fields(item, ["name"])
        assert result == {"name": "Alice"}

    def test_pick_multiple_fields(self):
        """Test picking multiple fields."""
        item = {"id": "1", "name": "Alice", "age": 30, "city": "NYC"}
        result = _pick_fields(item, ["id", "name"])
        assert result == {"id": "1", "name": "Alice"}

    def test_pick_nested_fields(self):
        """Test picking nested fields with dot notation."""
        item = {
            "id": "1",
            "user": {"name": "Alice", "email": "alice@example.com"},
        }
        result = _pick_fields(item, ["id", "user.name"])
        assert result == {"id": "1", "user.name": "Alice"}

    def test_pick_missing_field(self):
        """Test picking missing field returns None."""
        item = {"id": "1", "name": "Alice"}
        result = _pick_fields(item, ["id", "age"])
        assert result == {"id": "1", "age": None}


class TestDeepGet:
    """Test _deep_get function."""

    def test_get_top_level_key(self):
        """Test getting top-level key."""
        data = {"id": "1", "name": "Alice"}
        result = _deep_get(data, "name")
        assert result == "Alice"

    def test_get_nested_key(self):
        """Test getting nested key with dot notation."""
        data = {
            "user": {
                "profile": {"name": "Alice", "age": 30},
            }
        }
        result = _deep_get(data, "user.profile.name")
        assert result == "Alice"

    def test_get_missing_key(self):
        """Test getting missing key returns None."""
        data = {"id": "1"}
        result = _deep_get(data, "name")
        assert result is None

    def test_get_missing_nested_key(self):
        """Test getting missing nested key returns None."""
        data = {"user": {"name": "Alice"}}
        result = _deep_get(data, "user.email")
        assert result is None

    def test_get_from_non_dict(self):
        """Test getting from non-dict in path returns None."""
        data = {"user": "Alice"}
        result = _deep_get(data, "user.name")
        assert result is None

    def test_get_deeply_nested(self):
        """Test getting deeply nested value."""
        data = {
            "a": {
                "b": {
                    "c": {
                        "d": "value",
                    }
                }
            }
        }
        result = _deep_get(data, "a.b.c.d")
        assert result == "value"


class TestFormatValue:
    """Test _format_value function."""

    def test_format_none(self):
        """Test formatting None returns empty string."""
        assert _format_value(None) == ""

    def test_format_true(self):
        """Test formatting True returns 'true'."""
        assert _format_value(True) == "true"

    def test_format_false(self):
        """Test formatting False returns 'false'."""
        assert _format_value(False) == "false"

    def test_format_string(self):
        """Test formatting string returns string."""
        assert _format_value("hello") == "hello"

    def test_format_number(self):
        """Test formatting number returns string representation."""
        assert _format_value(42) == "42"
        assert _format_value(3.14) == "3.14"

    def test_format_list(self):
        """Test formatting list returns JSON."""
        result = _format_value(["a", "b", "c"])
        assert json.loads(result) == ["a", "b", "c"]

    def test_format_dict(self):
        """Test formatting dict returns JSON."""
        result = _format_value({"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_format_nested_structure(self):
        """Test formatting nested structure returns JSON."""
        data = {"list": [1, 2, 3], "nested": {"key": "value"}}
        result = _format_value(data)
        assert json.loads(result) == data


class TestApplyJq:
    """Test _apply_jq function."""

    def test_apply_simple_filter(self):
        """Test applying simple jq filter."""
        json_str = json.dumps([{"id": "1"}, {"id": "2"}])
        result = _apply_jq(json_str, ".[] | .id")
        # jq returns each ID on a separate line
        assert '"1"' in result
        assert '"2"' in result

    def test_apply_select_filter(self):
        """Test applying jq select filter."""
        json_str = json.dumps([{"id": "1", "active": True}, {"id": "2", "active": False}])
        result = _apply_jq(json_str, ".[] | select(.active)")
        output = json.loads(result)
        assert output["id"] == "1"
        assert output["active"] is True

    def test_jq_not_found(self, monkeypatch):
        """Test that missing jq command raises SystemExit."""
        monkeypatch.setattr("subprocess.run", MagicMock(side_effect=FileNotFoundError))

        with pytest.raises(SystemExit) as exc_info:
            _apply_jq('{"test": "data"}', ".")

        assert exc_info.value.code == 1

    def test_jq_error(self, monkeypatch):
        """Test that jq error raises SystemExit."""
        mock_result = MagicMock()
        mock_result.stderr = "jq: parse error"
        mock_run = MagicMock(side_effect=subprocess.CalledProcessError(1, "jq", stderr="jq: parse error"))

        monkeypatch.setattr("subprocess.run", mock_run)

        with pytest.raises(SystemExit) as exc_info:
            _apply_jq('{"test": "data"}', "invalid syntax")

        assert exc_info.value.code == 1

    def test_jq_strips_trailing_newline(self):
        """Test that jq output has trailing newline stripped."""
        json_str = json.dumps({"test": "value"})
        result = _apply_jq(json_str, ".")
        # Result should not end with newline (rstrip in function)
        assert not result.endswith("\n\n")


class TestJsonFieldFiltering:
    """Test JSON field filtering in render methods."""

    def test_render_table_with_json_fields(self, capsys):
        """Test that json_fields filters output fields."""
        ctx = OutputContext(json_fields=["id", "name"])
        rows = [
            {"id": "1", "name": "Alice", "age": 30, "city": "NYC"},
            {"id": "2", "name": "Bob", "age": 25, "city": "LA"},
        ]
        ctx.render_table(rows, ["id", "name", "age", "city"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert len(output) == 2
        assert output[0] == {"id": "1", "name": "Alice"}
        assert output[1] == {"id": "2", "name": "Bob"}
        assert "age" not in output[0]
        assert "city" not in output[0]

    def test_render_table_with_nested_json_fields(self, capsys):
        """Test that json_fields works with nested field notation."""
        ctx = OutputContext(json_fields=["id", "user.name"])
        rows = [
            {"id": "1", "user": {"name": "Alice", "email": "alice@example.com"}},
        ]
        ctx.render_table(rows, ["id", "user"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output[0] == {"id": "1", "user.name": "Alice"}

    def test_render_json_with_json_fields(self, capsys):
        """Test that render_json respects json_fields."""
        ctx = OutputContext(json_fields=["id"])
        ctx.render_json([{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}])

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output == [{"id": "1"}, {"id": "2"}]


class TestJqIntegration:
    """Test jq integration in render methods."""

    def test_render_table_with_jq(self, capsys):
        """Test that jq_expr processes output."""
        ctx = OutputContext(jq_expr=".[0]")
        rows = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        ctx.render_table(rows, ["id", "name"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        # Should only get first item due to .[0] filter
        assert output == {"id": "1", "name": "Alice"}

    def test_render_table_with_json_fields_and_jq(self, capsys):
        """Test that json_fields and jq work together."""
        ctx = OutputContext(json_fields=["id"], jq_expr=".[0]")
        rows = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        ctx.render_table(rows, ["id", "name"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        # First filter to id field, then take first element
        assert output == {"id": "1"}


class TestTtyDetection:
    """Test TTY detection integration."""

    def test_tty_true_uses_rich(self):
        """Test that _is_tty=True uses Rich tables."""
        with patch("rich.console.Console") as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console

            ctx = OutputContext(_is_tty=True)
            ctx.render_table([{"id": "1"}], ["id"])

            mock_console_class.assert_called_once()
            mock_console.print.assert_called_once()

    def test_tty_false_uses_tsv(self, capsys):
        """Test that _is_tty=False uses TSV output."""
        ctx = OutputContext(_is_tty=False)
        ctx.render_table([{"id": "1", "name": "Alice"}], ["id", "name"])

        captured = capsys.readouterr()
        assert captured.out == "1\tAlice\n"

    def test_tty_overridden_by_json_mode(self, capsys):
        """Test that JSON mode overrides TTY detection."""
        ctx = OutputContext(_is_tty=True, force_json=True)
        ctx.render_table([{"id": "1"}], ["id"])

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output == [{"id": "1"}]
