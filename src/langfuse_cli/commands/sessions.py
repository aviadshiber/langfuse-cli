"""Session browsing commands."""

from __future__ import annotations

from datetime import datetime

import typer

from langfuse_cli.commands import command_context

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_sessions(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
    from_date: datetime | None = typer.Option(None, "--from", help="Start time filter (ISO 8601)."),
    to_date: datetime | None = typer.Option(None, "--to", help="End time filter (ISO 8601)."),
) -> None:
    """List sessions with optional filters."""
    with command_context("listing sessions") as (client, output):
        sessions = client.list_sessions(
            limit=limit,
            from_timestamp=from_date,
            to_timestamp=to_date,
        )
        output.render_table(
            sessions,
            columns=["id", "createdAt", "projectId"],
        )


@app.command("get")
def get_session(
    session_id: str = typer.Argument(help="Session ID to inspect."),
) -> None:
    """Get detailed information about a specific session."""
    with command_context("getting session") as (client, output):
        session = client.get_session(session_id)
        output.render_detail(
            session,
            fields=[
                ("ID", "id"),
                ("Created At", "createdAt"),
                ("Project ID", "projectId"),
                ("Traces", "traces"),
            ],
        )
