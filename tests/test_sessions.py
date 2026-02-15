"""Tests for the sessions command module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


# Sample test data
SAMPLE_SESSIONS = [
    {
        "id": "sess-1",
        "createdAt": "2024-01-15T10:00:00Z",
        "projectId": "proj-1",
    },
    {
        "id": "sess-2",
        "createdAt": "2024-01-15T11:00:00Z",
        "projectId": "proj-1",
    },
]

SAMPLE_SESSION_DETAIL = {
    "id": "sess-1",
    "createdAt": "2024-01-15T10:00:00Z",
    "projectId": "proj-1",
    "traces": ["trace-1", "trace-2"],
}


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock LangfuseClient."""
    client = MagicMock()
    client.close = MagicMock()
    return client


class TestSessionsListCommand:
    """Test 'lf sessions list' command."""

    def test_list_sessions_default_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf sessions list' outputs table with session data."""
        mock_client.list_sessions.return_value = SAMPLE_SESSIONS

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "list"])

        assert result.exit_code == 0
        mock_client.list_sessions.assert_called_once_with(
            limit=50,
            from_timestamp=None,
            to_timestamp=None,
        )
        mock_client.close.assert_called_once()

    def test_list_sessions_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf sessions list --json' outputs JSON array."""
        mock_client.list_sessions.return_value = SAMPLE_SESSIONS

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "sessions", "list"])

        assert result.exit_code == 0
        # Verify JSON output contains session data
        assert "sess-1" in result.stdout
        assert "sess-2" in result.stdout
        mock_client.close.assert_called_once()

    def test_list_sessions_with_limit(self, mock_client: MagicMock) -> None:
        """Test that 'lf sessions list --limit 10' passes limit to client."""
        mock_client.list_sessions.return_value = []

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "list", "--limit", "10"])

        assert result.exit_code == 0
        mock_client.list_sessions.assert_called_once()
        call_kwargs = mock_client.list_sessions.call_args.kwargs
        assert call_kwargs["limit"] == 10

    def test_list_sessions_api_error_exits_with_code(self, mock_client: MagicMock) -> None:
        """Test that API errors produce correct exit codes."""
        mock_client.list_sessions.side_effect = LangfuseAPIError(
            "API error 500: Internal Server Error",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "list"])

        assert result.exit_code == ERROR
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_list_sessions_not_found_error_exits_with_not_found_code(self, mock_client: MagicMock) -> None:
        """Test that 404 errors exit with NOT_FOUND code."""
        mock_client.list_sessions.side_effect = LangfuseAPIError(
            "Resource not found",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "list"])

        assert result.exit_code == NOT_FOUND
        mock_client.close.assert_called_once()

    def test_list_sessions_empty_results(self, mock_client: MagicMock) -> None:
        """Test that empty results are handled gracefully."""
        mock_client.list_sessions.return_value = []

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "list"])

        assert result.exit_code == 0


class TestSessionsGetCommand:
    """Test 'lf sessions get' command."""

    def test_get_session_success(self, mock_client: MagicMock) -> None:
        """Test that 'lf sessions get <id>' shows session detail."""
        mock_client.get_session.return_value = SAMPLE_SESSION_DETAIL

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "get", "sess-1"])

        assert result.exit_code == 0
        # Verify the session ID was passed correctly
        mock_client.get_session.assert_called_once_with("sess-1")
        # Verify some of the detail appears in output
        assert "sess-1" in result.stdout
        mock_client.close.assert_called_once()

    def test_get_session_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf sessions get <id> --json' outputs JSON."""
        mock_client.get_session.return_value = SAMPLE_SESSION_DETAIL

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "sessions", "get", "sess-1"])

        assert result.exit_code == 0
        # Verify JSON output contains session data
        assert "sess-1" in result.stdout
        assert "proj-1" in result.stdout
        mock_client.close.assert_called_once()

    def test_get_session_not_found(self, mock_client: MagicMock) -> None:
        """Test that missing session returns NOT_FOUND exit code."""
        mock_client.get_session.side_effect = LangfuseAPIError(
            "Resource not found: /sessions/missing-session",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "get", "missing-session"])

        assert result.exit_code == NOT_FOUND
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_get_session_api_error(self, mock_client: MagicMock) -> None:
        """Test that API errors are handled correctly."""
        mock_client.get_session.side_effect = LangfuseAPIError(
            "API error 500",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "get", "sess-1"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()


class TestSessionCommandIntegration:
    """Integration tests for session commands."""

    def test_client_always_closed_on_error(self, mock_client: MagicMock) -> None:
        """Test that client is closed even when errors occur."""
        mock_client.list_sessions.side_effect = LangfuseAPIError("Error", exit_code=ERROR)

        with patch("langfuse_cli.commands.sessions.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["sessions", "list"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_help_text_available(self) -> None:
        """Test that help text is available for sessions commands."""
        result = runner.invoke(app, ["sessions", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "get" in result.stdout

    def test_list_help_shows_filter_options(self) -> None:
        """Test that list command help shows all filter options."""
        from tests.conftest import strip_ansi
        result = runner.invoke(app, ["sessions", "list", "--help"])
        assert result.exit_code == 0
        stdout = strip_ansi(result.stdout)
        assert "--limit" in stdout
        assert "--from" in stdout
        assert "--to" in stdout
