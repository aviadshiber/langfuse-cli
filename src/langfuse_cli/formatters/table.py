"""Table formatting utilities (Rich tables and TSV)."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table


def render_rich_table(
    rows: list[dict[str, Any]],
    columns: list[str],
    *,
    title: str | None = None,
) -> None:
    """Render a Rich table to the console."""
    console = Console()
    table = Table(title=title, show_edge=False, pad_edge=False)

    for col in columns:
        table.add_column(col.upper(), no_wrap=True)

    for row in rows:
        table.add_row(*[_fmt(row.get(col, "")) for col in columns])

    console.print(table)


def _fmt(value: Any) -> str:
    """Format a value for table display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        import json

        return json.dumps(value, default=str)
    return str(value)
