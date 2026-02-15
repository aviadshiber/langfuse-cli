"""gh-ux output manager: --json/--jq, TTY detection, Rich tables, semantic colors."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from langfuse_cli._tty import is_tty, should_use_color


@dataclass
class OutputContext:
    """Manages output rendering based on flags and terminal state.

    Follows gh-ux patterns:
    - TTY: Rich tables with aligned columns and semantic colors
    - Non-TTY: Tab-separated values for piping
    - --json: JSON output, optionally filtered to specific fields
    - --jq: Filter JSON with jq expression
    - --quiet: Suppress status messages, keep IDs/URLs/errors
    """

    json_fields: list[str] | None = None
    jq_expr: str | None = None
    quiet: bool = False
    force_json: bool = False
    _is_tty: bool = field(default_factory=is_tty)
    _use_color: bool = field(default_factory=should_use_color)

    @property
    def is_json_mode(self) -> bool:
        """Check if JSON output is requested."""
        return self.force_json or self.json_fields is not None or self.jq_expr is not None

    def render_table(self, rows: list[dict[str, Any]], columns: list[str]) -> None:
        """Render data as a table (Rich in TTY, TSV in pipe)."""
        if self.is_json_mode:
            self._render_json(rows)
            return

        if not rows:
            self.status("No results found.")
            return

        if self._is_tty:
            self._render_rich_table(rows, columns)
        else:
            self._render_tsv(rows, columns)

    def render_json(self, data: Any) -> None:
        """Render raw JSON output."""
        self._render_json(data if isinstance(data, list) else [data])

    def render_detail(self, data: dict[str, Any], fields: list[tuple[str, str]]) -> None:
        """Render a single item's detail view.

        Args:
            data: The item data dict.
            fields: List of (label, key) pairs to display.
        """
        if self.is_json_mode:
            self._render_json([data])
            return

        if self._is_tty:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Field", style="bold cyan")
            table.add_column("Value")
            for label, key in fields:
                value = _deep_get(data, key)
                table.add_row(label, _format_value(value))
            console.print(table)
        else:
            for label, key in fields:
                value = _deep_get(data, key)
                sys.stdout.write(f"{label}\t{_format_value(value)}\n")

    def status(self, msg: str) -> None:
        """Print a status message (suppressed in --quiet mode)."""
        if not self.quiet:
            sys.stderr.write(f"{msg}\n")

    def error(self, msg: str) -> None:
        """Print an error message (always shown)."""
        sys.stderr.write(f"{msg}\n")

    # ── Private rendering methods ─────────────────────────────────────────

    def _render_json(self, data: list[Any]) -> None:
        """Render JSON output with optional field filtering and jq."""
        if self.json_fields:
            data = [_pick_fields(item, self.json_fields) for item in data]

        json_str = json.dumps(data, indent=2, default=str)

        if self.jq_expr:
            json_str = _apply_jq(json_str, self.jq_expr)

        sys.stdout.write(json_str + "\n")

    def _render_rich_table(self, rows: list[dict[str, Any]], columns: list[str]) -> None:
        """Render a Rich table for TTY output."""
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_edge=False, pad_edge=False)

        for col in columns:
            table.add_column(col.upper(), no_wrap=True)

        for row in rows:
            table.add_row(*[_format_value(row.get(col, "")) for col in columns])

        console.print(table)

    def _render_tsv(self, rows: list[dict[str, Any]], columns: list[str]) -> None:
        """Render tab-separated values for piped output."""
        for row in rows:
            values = [_format_value(row.get(col, "")) for col in columns]
            sys.stdout.write("\t".join(values) + "\n")


def _pick_fields(item: dict[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    """Pick specified fields from a dict."""
    return {f: _deep_get(item, f) for f in fields}


def _deep_get(data: dict[str, Any], key: str) -> Any:
    """Get a value from a nested dict using dot notation."""
    keys = key.split(".")
    result: Any = data
    for k in keys:
        if isinstance(result, dict):
            result = result.get(k)
        else:
            return None
    return result


def _format_value(value: Any) -> str:
    """Format a value for display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=str)
    return str(value)


def _apply_jq(json_str: str, expr: str) -> str:
    """Apply a jq expression to JSON string."""
    try:
        result = subprocess.run(
            ["jq", expr],
            input=json_str,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.rstrip()
    except FileNotFoundError:
        sys.stderr.write("error: `jq` is required for --jq flag but was not found in PATH\n")
        raise SystemExit(1) from None
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"error: jq failed: {e.stderr.strip()}\n")
        raise SystemExit(1) from None
