"""Prompt management commands (SDK path for caching)."""

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
def list_prompts() -> None:
    """List all prompts in the project."""
    client, output = _get_client()
    try:
        prompts = client.list_prompts()
        output.render_table(
            prompts,
            columns=["name", "version", "type", "labels", "tags"],
        )
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()


@app.command("get")
def get_prompt(
    name: str = typer.Argument(help="Prompt name."),
    version: int | None = typer.Option(None, "--version", help="Specific version number."),
    label: str | None = typer.Option(None, "--label", help="Label (e.g., 'production')."),
) -> None:
    """Get a specific prompt by name, version, or label."""
    client, output = _get_client()
    try:
        prompt = client.get_prompt(name, version=version, label=label)
        data = {
            "name": prompt.name,
            "version": prompt.version,
            "type": getattr(prompt, "type", "text"),
            "labels": getattr(prompt, "labels", []),
            "config": getattr(prompt, "config", {}),
        }

        # Add content based on type
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
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    except Exception as e:
        output.error(f"error: {e}")
        raise typer.Exit(1) from None
    finally:
        client.close()


@app.command("compile")
def compile_prompt(
    name: str = typer.Argument(help="Prompt name."),
    var: list[str] = typer.Option([], "--var", help="Variables as key=value pairs."),
    version: int | None = typer.Option(None, "--version", help="Specific version number."),
    label: str | None = typer.Option(None, "--label", help="Label (e.g., 'production')."),
) -> None:
    """Compile a prompt with variables."""
    client, output = _get_client()
    try:
        variables = {}
        for v in var:
            if "=" not in v:
                output.error(f"error: invalid variable format `{v}`, expected key=value")
                raise typer.Exit(1)
            key, value = v.split("=", 1)
            variables[key] = value

        kwargs = {}
        if version is not None:
            kwargs["version"] = version
        if label is not None:
            kwargs["label"] = label

        compiled = client.compile_prompt(name, variables, **kwargs)
        output.render_json(compiled)
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()


@app.command("diff")
def diff_prompts(
    name: str = typer.Argument(help="Prompt name."),
    v1: int = typer.Option(..., "--v1", help="First version number."),
    v2: int = typer.Option(..., "--v2", help="Second version number."),
) -> None:
    """Compare two versions of a prompt side-by-side."""
    client, output = _get_client()
    try:
        prompt1 = client.get_prompt(name, version=v1)
        prompt2 = client.get_prompt(name, version=v2)

        text1 = getattr(prompt1, "prompt", None) or str(getattr(prompt1, "messages", ""))
        text2 = getattr(prompt2, "prompt", None) or str(getattr(prompt2, "messages", ""))

        if output.is_json_mode:
            output.render_json({
                "name": name,
                "v1": {"version": v1, "content": text1},
                "v2": {"version": v2, "content": text2},
            })
            return

        from langfuse_cli.formatters.diff import render_diff

        render_diff(text1, text2, labels=(f"v{v1}", f"v{v2}"))
    except LangfuseAPIError as e:
        output.error(f"error: {e}")
        raise typer.Exit(e.exit_code) from None
    finally:
        client.close()
