"""Trace inspection commands."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import typer

from langfuse_cli.client import LangfuseAPIError, LangfuseClient

if TYPE_CHECKING:
    from langfuse_cli.output import OutputContext

app = typer.Typer(no_args_is_help=True)


def _get_client() -> tuple[LangfuseClient, OutputContext]:
    from langfuse_cli.main import state

    return LangfuseClient(state.config), state.output


@app.command("list")
def list_traces(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
    user_id: str | None = typer.Option(None, "--user-id", "-u", help="Filter by user ID."),
    session_id: str | None = typer.Option(None, "--session-id", help="Filter by session ID."),
    tags: str | None = typer.Option(None, "--tags", help="Filter by tags (comma-separated)."),
    name: str | None = typer.Option(None, "--name", "-n", help="Filter by trace name."),
    from_date: datetime | None = typer.Option(None, "--from", help="Start time filter (ISO 8601)."),
    to_date: datetime | None = typer.Option(None, "--to", help="End time filter (ISO 8601)."),
) -> None:
    """List traces with optional filters."""
    client, output = _get_client()
    try:
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
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()


@app.command("get")
def get_trace(
    trace_id: str = typer.Argument(help="Trace ID to inspect."),
) -> None:
    """Get detailed information about a specific trace."""
    client, output = _get_client()
    try:
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
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()


@app.command("tree")
def tree_trace(
    trace_id: str = typer.Argument(help="Trace ID to visualize."),
) -> None:
    """Display trace hierarchy as a tree of spans, generations, and events."""
    client, output = _get_client()
    try:
        trace = client.get_trace(trace_id)
        observations = client.list_observations(trace_id=trace_id, limit=200)

        if output.is_json_mode:
            output.render_json({"trace": trace, "observations": observations})
            return

        from langfuse_cli.formatters.tree import render_trace_tree

        render_trace_tree(trace, observations)
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()
