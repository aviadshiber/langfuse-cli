# CLAUDE.md

## Project Overview

**langfuse-cli** (`lf`) is a Python CLI for the [Langfuse](https://langfuse.com) LLM observability platform. It provides trace inspection, prompt management, score aggregation, dataset browsing, and experiment comparison. Follows [gh-ux patterns](https://cli.github.com/manual/) for CLI design.

## Quick Reference

```bash
uv sync                          # Install dependencies
uv run pytest                    # Run tests (96%+ coverage required)
uv run ruff check src/ tests/    # Lint
uv run ruff format src/ tests/   # Format
uv run mypy src/                 # Type check (strict mode)
uv run lf --help                 # Run the CLI locally
```

## Project Structure

```
src/langfuse_cli/
  main.py              # Typer app entry point, global state, command registration
  client.py            # Hybrid SDK + REST client (httpx for REST, langfuse SDK for prompts/datasets)
  config.py            # Config resolution: CLI flags > env vars > TOML file > keyring > defaults
  output.py            # Output manager: Rich tables (TTY), TSV (piped), JSON (--json), jq support
  _tty.py              # TTY detection, NO_COLOR/CLICOLOR support
  _exit_codes.py       # Semantic exit codes: SUCCESS=0, ERROR=1, NOT_FOUND=2, CANCELLED=3
  _defaults.py         # Default constants
  commands/
    __init__.py        # command_context() - shared lifecycle for all commands
    traces.py          # list, get, tree
    observations.py    # list observations
    prompts.py         # get, compile, diff, history
    scores.py          # list, summary
    sessions.py        # list sessions
    datasets.py        # list datasets
    experiments.py     # compare experiment runs
  formatters/
    tree.py            # Rich tree visualization for trace hierarchies
    diff.py            # Unified diff for prompt version comparison
tests/                 # One test module per feature, uses pytest + respx + CliRunner
scripts/
  pre-push             # Git hook that mirrors CI (ruff lint, ruff format, mypy, pytest)
  generate-formula.py  # Homebrew formula generation
```

## Architecture Patterns

### Command Pattern
Every command follows this structure:
```python
app = typer.Typer(no_args_is_help=True)

@app.command("subcommand")
def handler(...):
    with command_context("operation") as (client, output):
        data = client.method(...)
        output.render_table(data, columns=[...])
```

`command_context()` handles client initialization, error catching with semantic exit codes, and cleanup.

### Client Layer
- **REST (httpx)**: traces, observations, scores, sessions
- **SDK (langfuse)**: prompts (with caching), datasets
- Custom `LangfuseAPIError` with status codes mapped to exit codes

### Config Resolution Chain
CLI flags -> `LANGFUSE_*` env vars -> `~/.config/langfuse/config.toml` -> system keyring -> defaults

### Output Modes
- TTY: Rich tables with colors
- Piped (non-TTY): TSV
- `--json`: JSON array with optional `--fields` and `--jq` filtering
- `--quiet`: Suppress status messages

## Code Conventions

- **Python 3.10+** minimum
- **`from __future__ import annotations`** in every file
- **Type annotations required** on all public functions (mypy strict)
- **Ruff** for linting and formatting: 120 char line length, double quotes, spaces
- **Ruff rules**: E, W, F, I, N, UP, PL, RUF, B, C4, T20, PT
- **No `print()` calls** - use `output.status()` or `output.error()` from OutputContext

## Testing

- **Framework**: pytest with pytest-cov, pytest-mock, respx
- **Coverage minimum**: 60% (enforced), actual: 96%+
- **Patterns**:
  - Mock `LangfuseClient` via `patch("langfuse_cli.commands.LangfuseClient")`
  - Use `CliRunner` from Typer for end-to-end command tests
  - Use `respx` for HTTP mocking
  - Monkeypatch for config/env var tests
- **Run**: `uv run pytest` (includes coverage report)

## CI/CD

- **test.yml**: Matrix on Ubuntu + macOS, Python 3.10-3.13 (ruff, mypy, pytest)
- **publish.yml**: PyPI publish via OIDC on GitHub release
- **update-homebrew.yml**: Auto-update Homebrew formula after PyPI publish
- **Pre-push hook**: `ln -sf ../../scripts/pre-push .git/hooks/pre-push` (mirrors CI)

## Common Tasks

### Adding a new command
1. Create `src/langfuse_cli/commands/newcmd.py` following existing command pattern
2. Register in `main.py` with `app.add_typer(newcmd.app, name="newcmd")`
3. Add tests in `tests/test_newcmd.py`
4. Add any new API methods to `client.py`

### Adding a new API endpoint
1. Add method to `LangfuseClient` in `client.py`
2. Use `_get()` for single resources, `_paginate()` for lists
3. Raise `LangfuseAPIError` with appropriate exit codes on failure

## Entry Point

Console script: `lf = "langfuse_cli.main:app"` (defined in pyproject.toml)
