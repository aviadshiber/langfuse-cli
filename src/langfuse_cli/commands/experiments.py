"""Experiment run commands."""

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
def list_experiments(
    dataset_name: str = typer.Argument(help="Dataset name to list runs for."),
) -> None:
    """List experiment runs for a dataset."""
    client, output = _get_client()
    try:
        runs = client.list_dataset_runs(dataset_name)
        output.render_table(
            runs,
            columns=["name", "description", "createdAt", "updatedAt"],
        )
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()


@app.command("compare")
def compare_experiments(
    dataset_name: str = typer.Argument(help="Dataset name."),
    run1: str = typer.Argument(help="First run name."),
    run2: str = typer.Argument(help="Second run name."),
) -> None:
    """Compare two experiment runs side-by-side."""
    client, output = _get_client()
    try:
        data1 = client.get_dataset_run(dataset_name, run1)
        data2 = client.get_dataset_run(dataset_name, run2)

        if output.is_json_mode:
            output.render_json({
                "dataset": dataset_name,
                "run1": {"name": run1, "data": data1},
                "run2": {"name": run2, "data": data2},
            })
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
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()
