"""Argument parsers for command flags."""

from __future__ import annotations

import typer


def parse_metadata(items: list[str] | None) -> list[tuple[str, str]] | None:
    """Parse repeatable --metadata KEY=VALUE flags into (key, value) tuples.

    Splits on the first '=' so values may contain '='. Keys are stripped of
    surrounding whitespace. Raises typer.BadParameter on missing '=', empty
    key (after stripping), or empty value.
    """
    if not items:
        return None
    pairs: list[tuple[str, str]] = []
    for raw in items:
        key, sep, value = raw.partition("=")
        key = key.strip()
        if not sep or not key or not value:
            raise typer.BadParameter(
                f"--metadata expects KEY=VALUE with non-empty key and value (got {raw!r})",
                param_hint="--metadata",
            )
        pairs.append((key, value))
    return pairs
