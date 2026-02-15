"""Tests for _tty module."""

from __future__ import annotations

import pytest

from langfuse_cli import _tty


class TestIsTty:
    """Test is_tty function."""

    def test_is_tty_force_env(self, monkeypatch):
        """Test that LANGFUSE_FORCE_TTY=1 returns True."""
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        # Also mock isatty to ensure env var takes precedence
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert _tty.is_tty() is True

    def test_is_tty_no_force_env(self, monkeypatch):
        """Test that without LANGFUSE_FORCE_TTY, falls through to isatty()."""
        # Make sure env var is not set
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        # Mock isatty to return a known value
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert _tty.is_tty() is True

    def test_is_tty_isatty_true(self, monkeypatch):
        """Test that is_tty returns True when isatty() returns True."""
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert _tty.is_tty() is True

    def test_is_tty_isatty_false(self, monkeypatch):
        """Test that is_tty returns False when isatty() returns False."""
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert _tty.is_tty() is False


class TestShouldUseColor:
    """Test should_use_color function."""

    def test_no_color_env_disables(self, monkeypatch):
        """Test that NO_COLOR environment variable disables color."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert _tty.should_use_color() is False

    def test_clicolor_zero_disables(self, monkeypatch):
        """Test that CLICOLOR=0 disables color."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("CLICOLOR", "0")
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert _tty.should_use_color() is False

    def test_clicolor_force_enables(self, monkeypatch):
        """Test that CLICOLOR_FORCE enables color."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert _tty.should_use_color() is True

    def test_falls_through_to_tty(self, monkeypatch):
        """Test that without env vars, returns is_tty() result."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert _tty.should_use_color() is True

    def test_falls_through_to_tty_false(self, monkeypatch):
        """Test that without env vars and non-TTY, returns False."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert _tty.should_use_color() is False

    def test_no_color_overrides_clicolor_force(self, monkeypatch):
        """Test that NO_COLOR takes precedence over CLICOLOR_FORCE."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        assert _tty.should_use_color() is False


class TestSuccess:
    """Test success semantic color function."""

    def test_success_tty(self, monkeypatch):
        """Test success with TTY shows checkmark symbol."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        result = _tty.success("test message")
        assert "\u2713" in result  # checkmark
        assert "test message" in result
        assert "\033[0;32m" in result  # green color code

    def test_success_non_tty(self, monkeypatch):
        """Test success without TTY shows plus symbol."""
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        result = _tty.success("test message")
        assert "+" in result
        assert "\u2713" not in result  # no checkmark
        assert "test message" in result

    def test_success_no_color(self, monkeypatch):
        """Test success without color has no ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        result = _tty.success("test message")
        assert "\033[" not in result  # no ANSI codes
        assert "test message" in result


class TestFailure:
    """Test failure semantic color function."""

    def test_failure_tty(self, monkeypatch):
        """Test failure with TTY shows X symbol."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        result = _tty.failure("error occurred")
        assert "\u2717" in result  # X symbol
        assert "error occurred" in result
        assert "\033[0;31m" in result  # red color code

    def test_failure_non_tty(self, monkeypatch):
        """Test failure without TTY shows x symbol."""
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        result = _tty.failure("error occurred")
        assert "x" in result
        assert "\u2717" not in result  # no X symbol
        assert "error occurred" in result

    def test_failure_no_color(self, monkeypatch):
        """Test failure without color has no ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        result = _tty.failure("error occurred")
        assert "\033[" not in result  # no ANSI codes
        assert "error occurred" in result


class TestWarning:
    """Test warning semantic color function."""

    def test_warning_tty(self, monkeypatch):
        """Test warning with TTY shows exclamation symbol."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        result = _tty.warning("be careful")
        assert "!" in result  # exclamation
        assert "be careful" in result
        assert "\033[0;33m" in result  # yellow color code

    def test_warning_non_tty(self, monkeypatch):
        """Test warning without TTY shows same exclamation symbol."""
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        result = _tty.warning("be careful")
        assert "!" in result
        assert "be careful" in result

    def test_warning_no_color(self, monkeypatch):
        """Test warning without color has no ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        result = _tty.warning("be careful")
        assert "\033[" not in result  # no ANSI codes
        assert "be careful" in result


class TestRunning:
    """Test running semantic color function."""

    def test_running_tty(self, monkeypatch):
        """Test running with TTY shows circle symbol."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        result = _tty.running("processing")
        assert "\u25cb" in result  # circle
        assert "processing" in result
        assert "\033[0;34m" in result  # blue color code

    def test_running_non_tty(self, monkeypatch):
        """Test running without TTY shows o symbol."""
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        result = _tty.running("processing")
        assert "o" in result
        assert "\u25cb" not in result  # no circle
        assert "processing" in result

    def test_running_no_color(self, monkeypatch):
        """Test running without color has no ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        result = _tty.running("processing")
        assert "\033[" not in result  # no ANSI codes
        assert "processing" in result


class TestPending:
    """Test pending semantic color function."""

    def test_pending_tty(self, monkeypatch):
        """Test pending with TTY shows dotted circle symbol."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        result = _tty.pending("waiting")
        assert "\u25cc" in result  # dotted circle
        assert "waiting" in result
        assert "\033[0;36m" in result  # cyan color code

    def test_pending_non_tty(self, monkeypatch):
        """Test pending without TTY shows dot symbol."""
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        result = _tty.pending("waiting")
        assert "." in result
        assert "\u25cc" not in result  # no dotted circle
        assert "waiting" in result

    def test_pending_no_color(self, monkeypatch):
        """Test pending without color has no ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        result = _tty.pending("waiting")
        assert "\033[" not in result  # no ANSI codes
        assert "waiting" in result


class TestMuted:
    """Test muted semantic color function."""

    def test_muted_tty(self, monkeypatch):
        """Test muted with TTY shows dash and gray color."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        result = _tty.muted("cancelled")
        assert "-" in result  # dash
        assert "cancelled" in result
        assert "\033[0;37m" in result  # gray color code

    def test_muted_non_tty(self, monkeypatch):
        """Test muted without TTY shows same dash."""
        monkeypatch.delenv("LANGFUSE_FORCE_TTY", raising=False)
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        result = _tty.muted("cancelled")
        assert "-" in result
        assert "cancelled" in result

    def test_muted_no_color(self, monkeypatch):
        """Test muted without color has no ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        result = _tty.muted("cancelled")
        assert "\033[" not in result  # no ANSI codes
        assert "cancelled" in result


class TestColorize:
    """Test _colorize internal function."""

    def test_colorize_with_color(self, monkeypatch):
        """Test that _colorize adds ANSI codes when color is enabled."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("CLICOLOR", raising=False)
        monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
        monkeypatch.setenv("LANGFUSE_FORCE_TTY", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        result = _tty._colorize("test", "0;32")
        assert result == "\033[0;32mtest\033[0m"

    def test_colorize_without_color(self, monkeypatch):
        """Test that _colorize returns plain text when color is disabled."""
        monkeypatch.setenv("NO_COLOR", "1")
        result = _tty._colorize("test", "0;32")
        assert result == "test"
        assert "\033[" not in result
