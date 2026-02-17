"""Dataset browsing commands."""

from __future__ import annotations

import typer

from langfuse_cli.commands import command_context

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_datasets(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
) -> None:
    """List all datasets."""
    with command_context("listing datasets") as (client, output):
        datasets = client.list_datasets(limit=limit)
        output.render_table(
            datasets,
            columns=["name", "description", "createdAt", "updatedAt"],
        )


@app.command("get")
def get_dataset(
    name: str = typer.Argument(help="Dataset name."),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of items to show."),
) -> None:
    """Get dataset details and list its items."""
    with command_context("getting dataset") as (client, output):
        dataset = client.get_dataset(name)

        if output.is_json_mode:
            items = client.list_dataset_items(name, limit=limit)
            output.render_json({"dataset": dataset, "items": items})
            return

        output.render_detail(
            dataset,
            fields=[
                ("Name", "name"),
                ("Description", "description"),
                ("Created", "createdAt"),
                ("Updated", "updatedAt"),
                ("Metadata", "metadata"),
            ],
        )

        items = client.list_dataset_items(name, limit=limit)
        if items:
            output.status(f"\nItems ({len(items)}):")
            output.render_table(
                items,
                columns=["id", "status", "createdAt"],
            )
