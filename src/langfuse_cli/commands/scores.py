"""Score and evaluation commands."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import typer

from langfuse_cli.commands import command_context

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_scores(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
    trace_id: str | None = typer.Option(None, "--trace-id", "-t", help="Filter by trace ID."),
    name: str | None = typer.Option(None, "--name", "-n", help="Filter by score name."),
    from_date: datetime | None = typer.Option(None, "--from", help="Start time filter (ISO 8601)."),
    to_date: datetime | None = typer.Option(None, "--to", help="End time filter (ISO 8601)."),
) -> None:
    """List scores with optional filters."""
    with command_context("listing scores") as (client, output):
        scores = client.list_scores(
            limit=limit,
            trace_id=trace_id,
            name=name,
            from_timestamp=from_date,
            to_timestamp=to_date,
        )
        output.render_table(
            scores,
            columns=["id", "traceId", "name", "value", "observationId", "timestamp"],
        )


@app.command("summary")
def summary_scores(
    name: str | None = typer.Option(None, "--name", "-n", help="Score name to summarize."),
    from_date: datetime | None = typer.Option(None, "--from", help="Start time filter (ISO 8601)."),
    to_date: datetime | None = typer.Option(None, "--to", help="End time filter (ISO 8601)."),
) -> None:
    """Show aggregated score statistics."""
    with command_context("summarizing scores") as (client, output):
        scores = client.list_scores(
            limit=500,
            name=name,
            from_timestamp=from_date,
            to_timestamp=to_date,
        )

        if not scores:
            output.status("No scores found.")
            return

        by_name: dict[str, list[float]] = defaultdict(list)
        for s in scores:
            score_name = s.get("name", "unknown")
            value = s.get("value")
            if value is not None:
                by_name[score_name].append(float(value))

        summary_rows = []
        for score_name, values in sorted(by_name.items()):
            summary_rows.append(
                {
                    "name": score_name,
                    "count": len(values),
                    "mean": round(sum(values) / len(values), 4) if values else 0,
                    "min": round(min(values), 4) if values else 0,
                    "max": round(max(values), 4) if values else 0,
                }
            )

        output.render_table(
            summary_rows,
            columns=["name", "count", "mean", "min", "max"],
        )
