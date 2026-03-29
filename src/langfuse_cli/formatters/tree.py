"""Rich Tree formatter for trace hierarchy visualization."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.tree import Tree


def render_trace_tree(trace: dict[str, Any], observations: list[dict[str, Any]]) -> None:
    """Render a trace and its observations as a Rich tree."""
    console = Console()

    trace_name = trace.get("name", trace.get("id", "trace"))
    root = Tree(f"[bold]{trace_name}[/bold] [dim]({trace.get('id', '')})[/dim]")

    # Build parent-child relationships
    children_map: dict[str | None, list[dict[str, Any]]] = {}
    for obs in observations:
        parent_id = obs.get("parentObservationId")
        children_map.setdefault(parent_id, []).append(obs)

    # Sort by start time within each level
    for _key, children in children_map.items():
        children.sort(key=lambda o: o.get("startTime", ""))

    # Recursively build tree
    _add_children(root, None, children_map)

    console.print(root)


TYPE_STYLES = {
    "GENERATION": "[green]",
    "SPAN": "[blue]",
    "EVENT": "[yellow]",
}

TYPE_ICONS = {
    "GENERATION": "\u2726",  # ✦
    "SPAN": "\u2500",  # ─
    "EVENT": "\u25cf",  # ●
}


def _add_children(
    parent_node: Tree,
    parent_id: str | None,
    children_map: dict[str | None, list[dict[str, Any]]],
) -> None:
    """Recursively add child observations to the tree."""
    children = children_map.get(parent_id, [])
    for obs in children:
        obs_type = obs.get("type", "SPAN")
        style = TYPE_STYLES.get(obs_type, "[white]")
        icon = TYPE_ICONS.get(obs_type, "-")
        name = obs.get("name", obs.get("id", "?"))
        obs_id = obs.get("id", "")

        # Build label with type, name, and optional metadata
        label = f"{style}{icon} {name}[/] [dim]({obs_type.lower()})[/dim]"

        # Add model info for generations
        model = obs.get("model")
        if model:
            label += f" [cyan]{model}[/cyan]"

        # Add token usage for generations
        usage = obs.get("usage")
        if usage:
            total = usage.get("totalTokens") or usage.get("total")
            if total:
                label += f" [dim]{total} tokens[/dim]"

        child_node = parent_node.add(label)
        _add_children(child_node, obs_id, children_map)
