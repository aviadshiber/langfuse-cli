"""Side-by-side diff formatter for prompt version comparison."""

from __future__ import annotations

import difflib

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table


def render_diff(text1: str, text2: str, labels: tuple[str, str] = ("left", "right")) -> None:
    """Render a unified diff between two text versions."""
    console = Console()

    lines1 = text1.splitlines(keepends=True)
    lines2 = text2.splitlines(keepends=True)

    diff = difflib.unified_diff(
        lines1,
        lines2,
        fromfile=labels[0],
        tofile=labels[1],
    )

    diff_text = "".join(diff)

    if not diff_text:
        console.print("[dim]No differences found.[/dim]")
        return

    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
    console.print(syntax)


def render_side_by_side(text1: str, text2: str, labels: tuple[str, str] = ("left", "right")) -> None:
    """Render two texts side-by-side in a table."""
    console = Console()

    table = Table(title="Prompt Comparison", show_lines=True)
    table.add_column(labels[0], ratio=1)
    table.add_column(labels[1], ratio=1)

    lines1 = text1.splitlines()
    lines2 = text2.splitlines()

    max_lines = max(len(lines1), len(lines2))
    for i in range(max_lines):
        l1 = lines1[i] if i < len(lines1) else ""
        l2 = lines2[i] if i < len(lines2) else ""
        table.add_row(l1, l2)

    console.print(table)
