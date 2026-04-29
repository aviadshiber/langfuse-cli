"""Shared command infrastructure."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import typer

from langfuse_cli.client import LangfuseAPIError, LangfuseClient

if TYPE_CHECKING:
    from langfuse_cli.output import OutputContext


@contextmanager
def command_context(
    operation: str = "",
    *,
    catch_all: bool = False,
) -> Generator[tuple[LangfuseClient, OutputContext], None, None]:
    """Shared context for all commands: client lifecycle + error handling.

    Args:
        operation: Human-readable label for error messages (e.g. "listing traces").
        catch_all: Also catch generic Exception (for SDK commands that may raise non-API errors).
    """
    from langfuse_cli.main import state

    client = LangfuseClient(state.config)
    output = state.output
    try:
        yield client, output
    except LangfuseAPIError as e:
        prefix = f"{operation}: " if operation else ""
        output.error(f"error: {prefix}{e}")
        raise typer.Exit(e.exit_code) from None
    except Exception as e:
        if not catch_all:
            raise
        prefix = f"{operation}: " if operation else ""
        output.error(f"error: {prefix}{e}")
        raise typer.Exit(1) from None
    finally:
        client.close()
