"""Hello world command — simple GET /api/hello endpoint."""

from __future__ import annotations

import typer

from langfuse_cli.commands import command_context

app = typer.Typer(no_args_is_help=False)


@app.callback(invoke_without_command=True)
def hello() -> None:
    """Say hello — calls GET /api/hello on the configured Langfuse host."""
    with command_context("calling hello endpoint") as (client, output):
        data = client.get_hello()
        if output.is_json_mode:
            output.render_json(data)
            return
        message = data.get("message", "Hello, World!")
        output.status(message)
