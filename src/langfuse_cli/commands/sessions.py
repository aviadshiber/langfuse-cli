"""Session browsing commands."""

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
def list_sessions(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
    from_date: datetime | None = typer.Option(None, "--from", help="Start time filter (ISO 8601)."),
    to_date: datetime | None = typer.Option(None, "--to", help="End time filter (ISO 8601)."),
) -> None:
    """List sessions with optional filters."""
    client, output = _get_client()
    try:
        sessions = client.list_sessions(
            limit=limit,
            from_timestamp=from_date,
            to_timestamp=to_date,
        )
        output.render_table(
            sessions,
            columns=["id", "createdAt", "projectId"],
        )
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()


@app.command("get")
def get_session(
    session_id: str = typer.Argument(help="Session ID to inspect."),
) -> None:
    """Get detailed information about a specific session."""
    client, output = _get_client()
    try:
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
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()
