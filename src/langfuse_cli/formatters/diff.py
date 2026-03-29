"""Diff formatter for prompt version comparison."""

from __future__ import annotations

import difflib

from rich.console import Console
from rich.syntax import Syntax


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
