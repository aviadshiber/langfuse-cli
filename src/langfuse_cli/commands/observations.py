"""Observation browsing commands."""

from __future__ import annotations

import typer

from langfuse_cli.commands import command_context

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_observations(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
    trace_id: str | None = typer.Option(None, "--trace-id", "-t", help="Filter by trace ID."),
    observation_type: str | None = typer.Option(None, "--type", help="Filter by type (GENERATION, SPAN, EVENT)."),
    name: str | None = typer.Option(None, "--name", "-n", help="Filter by observation name."),
) -> None:
    """List observations with optional filters."""
    with command_context("listing observations") as (client, output):
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
