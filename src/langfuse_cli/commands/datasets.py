"""Dataset browsing commands."""

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
def list_datasets(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of results."),
) -> None:
    """List all datasets."""
    client, output = _get_client()
    try:
        datasets = client.list_datasets(limit=limit)
        output.render_table(
            datasets,
            columns=["name", "description", "createdAt", "updatedAt"],
        )
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()


@app.command("get")
def get_dataset(
    name: str = typer.Argument(help="Dataset name."),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of items to show."),
) -> None:
    """Get dataset details and list its items."""
    client, output = _get_client()
    try:
        dataset = client.get_dataset(name)

        if output.is_json_mode:
            items = client.list_dataset_items(name, limit=limit)
            output.render_json({"dataset": dataset, "items": items})
            return

        # Show dataset metadata first
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

        # Then list items
        items = client.list_dataset_items(name, limit=limit)
        if items:
            output.status(f"\nItems ({len(items)}):")
            output.render_table(
                items,
                columns=["id", "status", "createdAt"],
            )
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()
