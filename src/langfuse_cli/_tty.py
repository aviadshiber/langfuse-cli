"""TTY detection and semantic color utilities following gh-ux patterns."""

from __future__ import annotations

import os
import sys


def is_tty() -> bool:
    """Check if stdout is connected to a terminal."""
    if os.getenv("LANGFUSE_FORCE_TTY") == "1":
        return True
    return sys.stdout.isatty()


def should_use_color() -> bool:
    """Determine if color output should be used."""
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("CLICOLOR") == "0":
        return False
    if os.getenv("CLICOLOR_FORCE"):
        return True
    return is_tty()


def _colorize(text: str, code: str) -> str:
    if not should_use_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def success(msg: str) -> str:
    """Green checkmark for success."""
    symbol = "\u2713" if is_tty() else "+"
    return _colorize(f"{symbol} {msg}", "0;32")


def failure(msg: str) -> str:
    """Red X for failure."""
    symbol = "\u2717" if is_tty() else "x"
    return _colorize(f"{symbol} {msg}", "0;31")


def warning(msg: str) -> str:
    """Yellow exclamation for warning."""
    symbol = "!"
    return _colorize(f"{symbol} {msg}", "0;33")


def running(msg: str) -> str:
    """Blue circle for running."""
    symbol = "\u25cb" if is_tty() else "o"
    return _colorize(f"{symbol} {msg}", "0;34")


def pending(msg: str) -> str:
    """Cyan circle for pending."""
    symbol = "\u25cc" if is_tty() else "."
    return _colorize(f"{symbol} {msg}", "0;36")


def muted(msg: str) -> str:
    """Gray dash for muted/cancelled."""
    return _colorize(f"- {msg}", "0;37")
