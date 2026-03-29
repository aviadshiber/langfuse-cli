"""Tests for the hello command module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


SAMPLE_HELLO_RESPONSE = {
    "message": "Hello, World!",
}


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock LangfuseClient."""
    client = MagicMock()
    client.close = MagicMock()
    return client


class TestHelloCommand:
    """Test 'lf hello' command."""

    def test_hello_default_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf hello' outputs the hello message."""
        mock_client.get_hello.return_value = SAMPLE_HELLO_RESPONSE

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["hello"])

        assert result.exit_code == 0
        mock_client.get_hello.assert_called_once()
        mock_client.close.assert_called_once()

    def test_hello_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf --json hello' outputs JSON."""
        mock_client.get_hello.return_value = SAMPLE_HELLO_RESPONSE

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "hello"])

        assert result.exit_code == 0
        assert "Hello, World!" in result.stdout
        mock_client.close.assert_called_once()

    def test_hello_custom_message(self, mock_client: MagicMock) -> None:
        """Test that 'lf hello' handles a custom message from the server."""
        mock_client.get_hello.return_value = {"message": "Greetings from Langfuse!"}

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["hello"])

        assert result.exit_code == 0
        mock_client.get_hello.assert_called_once()

    def test_hello_api_error(self, mock_client: MagicMock) -> None:
        """Test that API errors are handled correctly."""
        mock_client.get_hello.side_effect = LangfuseAPIError(
            "API error 500: Internal Server Error",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["hello"])

        assert result.exit_code == ERROR
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_hello_connection_error(self, mock_client: MagicMock) -> None:
        """Test that connection errors are handled correctly."""
        mock_client.get_hello.side_effect = LangfuseAPIError(
            "Connection error: Could not connect to server",
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["hello"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_hello_fallback_message(self, mock_client: MagicMock) -> None:
        """Test that a missing 'message' key falls back to default."""
        mock_client.get_hello.return_value = {"status": "ok"}

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["hello"])

        assert result.exit_code == 0
        mock_client.get_hello.assert_called_once()

    def test_hello_help_text(self) -> None:
        """Test that help text is available for hello command."""
        result = runner.invoke(app, ["hello", "--help"])
        assert result.exit_code == 0
        assert "hello" in result.stdout.lower()
