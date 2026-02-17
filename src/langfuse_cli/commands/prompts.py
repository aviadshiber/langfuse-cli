"""Prompt management commands (SDK path for caching)."""

from __future__ import annotations

import typer

from langfuse_cli.commands import command_context

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_prompts() -> None:
    """List all prompts in the project."""
    with command_context("listing prompts") as (client, output):
        prompts = client.list_prompts()
        output.render_table(
            prompts,
            columns=["name", "version", "type", "labels", "tags"],
        )


@app.command("get")
def get_prompt(
    name: str = typer.Argument(help="Prompt name."),
    version: int | None = typer.Option(None, "--version", help="Specific version number."),
    label: str | None = typer.Option(None, "--label", help="Label (e.g., 'production')."),
) -> None:
    """Get a specific prompt by name, version, or label."""
    with command_context("getting prompt", catch_all=True) as (client, output):
        prompt = client.get_prompt(name, version=version, label=label)
        data = {
            "name": prompt.name,
            "version": prompt.version,
            "type": getattr(prompt, "type", "text"),
            "labels": getattr(prompt, "labels", []),
            "config": getattr(prompt, "config", {}),
        }

        if hasattr(prompt, "prompt"):
            data["prompt"] = prompt.prompt
        if hasattr(prompt, "messages"):
            data["messages"] = prompt.messages

        output.render_detail(
            data,
            fields=[
                ("Name", "name"),
                ("Version", "version"),
                ("Type", "type"),
                ("Labels", "labels"),
                ("Config", "config"),
                ("Content", "prompt"),
                ("Messages", "messages"),
            ],
        )


@app.command("compile")
def compile_prompt(
    name: str = typer.Argument(help="Prompt name."),
    var: list[str] = typer.Option([], "--var", help="Variables as key=value pairs."),
    version: int | None = typer.Option(None, "--version", help="Specific version number."),
    label: str | None = typer.Option(None, "--label", help="Label (e.g., 'production')."),
) -> None:
    """Compile a prompt with variables."""
    with command_context("compiling prompt") as (client, output):
        variables = {}
        for v in var:
            if "=" not in v:
                output.error(f"error: invalid variable format `{v}`, expected key=value")
                raise typer.Exit(1)
            key, value = v.split("=", 1)
            variables[key] = value

        kwargs: dict[str, int | str] = {}
        if version is not None:
            kwargs["version"] = version
        if label is not None:
            kwargs["label"] = label

        compiled = client.compile_prompt(name, variables, **kwargs)
        output.render_json(compiled)


@app.command("diff")
def diff_prompts(
    name: str = typer.Argument(help="Prompt name."),
    v1: int = typer.Option(..., "--v1", help="First version number."),
    v2: int = typer.Option(..., "--v2", help="Second version number."),
) -> None:
    """Compare two versions of a prompt side-by-side."""
    with command_context("comparing prompt versions") as (client, output):
        prompt1 = client.get_prompt(name, version=v1)
        prompt2 = client.get_prompt(name, version=v2)

        text1 = getattr(prompt1, "prompt", None) or str(getattr(prompt1, "messages", ""))
        text2 = getattr(prompt2, "prompt", None) or str(getattr(prompt2, "messages", ""))

        if output.is_json_mode:
            output.render_json(
                {
                    "name": name,
                    "v1": {"version": v1, "content": text1},
                    "v2": {"version": v2, "content": text2},
                }
            )
            return

        from langfuse_cli.formatters.diff import render_diff

        render_diff(text1, text2, labels=(f"v{v1}", f"v{v2}"))
