"""Experiment run commands."""

from __future__ import annotations

import typer

from langfuse_cli.commands import command_context

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_experiments(
    dataset_name: str = typer.Argument(help="Dataset name to list runs for."),
) -> None:
    """List experiment runs for a dataset."""
    with command_context("listing experiments") as (client, output):
        runs = client.list_dataset_runs(dataset_name)
        output.render_table(
            runs,
            columns=["name", "description", "createdAt", "updatedAt"],
        )


@app.command("compare")
def compare_experiments(
    dataset_name: str = typer.Argument(help="Dataset name."),
    run1: str = typer.Argument(help="First run name."),
    run2: str = typer.Argument(help="Second run name."),
) -> None:
    """Compare two experiment runs side-by-side."""
    with command_context("comparing experiments") as (client, output):
        data1 = client.get_dataset_run(dataset_name, run1)
        data2 = client.get_dataset_run(dataset_name, run2)

        if output.is_json_mode:
            output.render_json(
                {
                    "dataset": dataset_name,
                    "run1": {"name": run1, "data": data1},
                    "run2": {"name": run2, "data": data2},
                }
            )
            return

        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title=f"Comparison: {run1} vs {run2}")
        table.add_column("Field")
        table.add_column(run1)
        table.add_column(run2)

        for field in ["name", "description", "createdAt", "updatedAt", "metadata"]:
            v1 = str(data1.get(field, ""))
            v2 = str(data2.get(field, ""))
            table.add_row(field, v1, v2)

        console.print(table)
