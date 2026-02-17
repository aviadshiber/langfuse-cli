"""Observation browsing commands."""

from __future__ import annotations

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
def list_observations(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
    trace_id: str | None = typer.Option(None, "--trace-id", "-t", help="Filter by trace ID."),
    observation_type: str | None = typer.Option(None, "--type", help="Filter by type (GENERATION, SPAN, EVENT)."),
    name: str | None = typer.Option(None, "--name", "-n", help="Filter by observation name."),
) -> None:
    """List observations with optional filters."""
    client, output = _get_client()
    try:
        observations = client.list_observations(
            limit=limit,
            trace_id=trace_id,
            observation_type=observation_type,
            name=name,
        )
        output.render_table(
            observations,
            columns=["id", "traceId", "type", "name", "startTime", "model", "usage"],
        )
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()
