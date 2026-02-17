"""Langfuse CLI entrypoint."""

from __future__ import annotations

import typer

from langfuse_cli import __version__
from langfuse_cli.config import LangfuseConfig, resolve_config
from langfuse_cli.output import OutputContext

app = typer.Typer(
    name="lf",
    help="Observability-first CLI for the Langfuse LLM platform.",
    no_args_is_help=True,
)


class State:
    """Global state shared across commands."""

    config: LangfuseConfig
    output: OutputContext


state = State()


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"lf {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    host: str | None = typer.Option(None, "--host", envvar="LANGFUSE_HOST", help="Langfuse host URL."),
    profile: str | None = typer.Option(None, "--profile", envvar="LANGFUSE_PROFILE", help="Config profile name."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    json_fields: str | None = typer.Option(
        None, "--fields", help="Filter JSON to FIELDS (comma-separated). Implies --json."
    ),
    jq_expr: str | None = typer.Option(None, "--jq", help="Filter JSON with jq expression. Implies --json."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress status messages."),
) -> None:
    """Langfuse CLI - observability-first access to your LLM platform."""
    state.config = resolve_config(host=host, profile=profile)

    # --fields and --jq imply --json
    is_json = output_json or json_fields is not None or jq_expr is not None
    parsed_fields = json_fields.split(",") if json_fields else None

    state.output = OutputContext(
        json_fields=parsed_fields if is_json else None,
        jq_expr=jq_expr,
        quiet=quiet,
        force_json=is_json,
    )


# Import and register command groups
from langfuse_cli.commands import datasets, experiments, observations, prompts, scores, sessions, traces  # noqa: E402

app.add_typer(traces.app, name="traces", help="Inspect traces and observations.")
app.add_typer(observations.app, name="observations", help="Browse observations (generations, spans, events).")
app.add_typer(prompts.app, name="prompts", help="Manage and inspect prompts.")
app.add_typer(scores.app, name="scores", help="View scores and evaluations.")
app.add_typer(datasets.app, name="datasets", help="Browse datasets.")
app.add_typer(experiments.app, name="experiments", help="View and compare experiment runs.")
app.add_typer(sessions.app, name="sessions", help="Browse sessions.")

if __name__ == "__main__":
    app()
