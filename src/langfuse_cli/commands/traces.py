"""Trace inspection commands."""

from __future__ import annotations

from datetime import datetime

import typer

from langfuse_cli.commands import command_context

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_traces(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
    user_id: str | None = typer.Option(None, "--user-id", "-u", help="Filter by user ID."),
    session_id: str | None = typer.Option(None, "--session-id", "-s", help="Filter by session ID."),
    tags: str | None = typer.Option(None, "--tags", help="Filter by tags (comma-separated)."),
    name: str | None = typer.Option(None, "--name", "-n", help="Filter by trace name."),
    from_date: datetime | None = typer.Option(None, "--from", help="Start time filter (ISO 8601)."),
    to_date: datetime | None = typer.Option(None, "--to", help="End time filter (ISO 8601)."),
) -> None:
    """List traces with optional filters."""
    with command_context("listing traces") as (client, output):
        traces = client.list_traces(
            limit=limit,
            user_id=user_id,
            session_id=session_id,
            tags=tags.split(",") if tags else None,
            from_timestamp=from_date,
            to_timestamp=to_date,
            name=name,
        )
        output.render_table(
            traces,
            columns=["id", "name", "userId", "sessionId", "timestamp", "tags"],
        )


@app.command("get")
def get_trace(
    trace_id: str = typer.Argument(help="Trace ID to inspect."),
) -> None:
    """Get detailed information about a specific trace."""
    with command_context("getting trace") as (client, output):
        trace = client.get_trace(trace_id)
        output.render_detail(
            trace,
            fields=[
                ("ID", "id"),
                ("Name", "name"),
                ("User", "userId"),
                ("Session", "sessionId"),
                ("Timestamp", "timestamp"),
                ("Tags", "tags"),
                ("Input", "input"),
                ("Output", "output"),
                ("Metadata", "metadata"),
            ],
        )


@app.command("tree")
def tree_trace(
    trace_id: str = typer.Argument(help="Trace ID to visualize."),
) -> None:
    """Display trace hierarchy as a tree of spans, generations, and events."""
    with command_context("building trace tree") as (client, output):
        trace = client.get_trace(trace_id)
        observations = client.list_observations(trace_id=trace_id, limit=200)

        if output.is_json_mode:
            output.render_json({"trace": trace, "observations": observations})
            return

        from langfuse_cli.formatters.tree import render_trace_tree

        render_trace_tree(trace, observations)
