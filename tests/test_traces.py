"""Tests for the traces command module."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


# Sample test data
SAMPLE_TRACES = [
    {
        "id": "trace-1",
        "name": "chat-completion",
        "userId": "user-123",
        "sessionId": "session-456",
        "timestamp": "2024-01-15T10:30:00Z",
        "tags": ["production"],
    },
    {
        "id": "trace-2",
        "name": "search",
        "userId": "user-789",
        "sessionId": None,
        "timestamp": "2024-01-15T11:00:00Z",
        "tags": [],
    },
]

SAMPLE_TRACE_DETAIL = {
    "id": "trace-1",
    "name": "chat-completion",
    "userId": "user-123",
    "sessionId": "session-456",
    "timestamp": "2024-01-15T10:30:00Z",
    "tags": ["production"],
    "input": {"messages": [{"role": "user", "content": "Hello"}]},
    "output": {"response": "Hi there!"},
    "metadata": {"model": "gpt-4"},
}

SAMPLE_OBSERVATIONS = [
    {
        "id": "obs-1",
        "traceId": "trace-1",
        "type": "GENERATION",
        "name": "llm-call",
        "startTime": "2024-01-15T10:30:00Z",
        "endTime": "2024-01-15T10:30:02Z",
    },
    {
        "id": "obs-2",
        "traceId": "trace-1",
        "type": "SPAN",
        "name": "processing",
        "startTime": "2024-01-15T10:30:02Z",
        "endTime": "2024-01-15T10:30:03Z",
    },
]


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock LangfuseClient."""
    client = MagicMock()
    client.close = MagicMock()
    return client


class TestTracesListCommand:
    """Test 'lf traces list' command."""

    def test_list_traces_default_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf traces list' outputs table with trace data."""
        mock_client.list_traces.return_value = SAMPLE_TRACES

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list"])

        assert result.exit_code == 0
        # In TTY mode (which the CliRunner simulates), we get a Rich table
        # Just verify the command ran successfully and client was called
        mock_client.list_traces.assert_called_once_with(
            limit=50,
            user_id=None,
            session_id=None,
            tags=None,
            from_timestamp=None,
            to_timestamp=None,
            name=None,
        )
        mock_client.close.assert_called_once()

    def test_list_traces_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf traces list --json' outputs JSON array."""
        mock_client.list_traces.return_value = SAMPLE_TRACES

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "traces", "list"])

        assert result.exit_code == 0
        # Verify JSON output contains trace IDs
        assert "trace-1" in result.stdout
        assert "trace-2" in result.stdout
        mock_client.close.assert_called_once()

    def test_list_traces_with_limit(self, mock_client: MagicMock) -> None:
        """Test that 'lf traces list --limit 5' passes limit to client."""
        mock_client.list_traces.return_value = []

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list", "--limit", "5"])

        assert result.exit_code == 0
        mock_client.list_traces.assert_called_once()
        call_kwargs = mock_client.list_traces.call_args.kwargs
        assert call_kwargs["limit"] == 5

    def test_list_traces_with_user_id_filter(self, mock_client: MagicMock) -> None:
        """Test that 'lf traces list --user-id foo' passes filter."""
        mock_client.list_traces.return_value = []

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list", "--user-id", "user-123"])

        assert result.exit_code == 0
        mock_client.list_traces.assert_called_once()
        call_kwargs = mock_client.list_traces.call_args.kwargs
        assert call_kwargs["user_id"] == "user-123"

    def test_list_traces_with_session_id_filter(self, mock_client: MagicMock) -> None:
        """Test that session ID filter is passed correctly."""
        mock_client.list_traces.return_value = []

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list", "--session-id", "session-456"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_traces.call_args.kwargs
        assert call_kwargs["session_id"] == "session-456"

    def test_list_traces_with_tags_filter(self, mock_client: MagicMock) -> None:
        """Test that tags filter is parsed from comma-separated string."""
        mock_client.list_traces.return_value = []

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list", "--tags", "production,urgent"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_traces.call_args.kwargs
        assert call_kwargs["tags"] == ["production", "urgent"]

    def test_list_traces_with_name_filter(self, mock_client: MagicMock) -> None:
        """Test that name filter is passed correctly."""
        mock_client.list_traces.return_value = []

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list", "--name", "chat-completion"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_traces.call_args.kwargs
        assert call_kwargs["name"] == "chat-completion"

    def test_list_traces_with_date_filters(self, mock_client: MagicMock) -> None:
        """Test that date filters are passed correctly."""
        mock_client.list_traces.return_value = []

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "traces",
                    "list",
                    "--from",
                    "2024-01-01T00:00:00",
                    "--to",
                    "2024-01-31T23:59:59",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_client.list_traces.call_args.kwargs
        assert isinstance(call_kwargs["from_timestamp"], datetime)
        assert isinstance(call_kwargs["to_timestamp"], datetime)

    def test_list_traces_api_error_exits_with_code(self, mock_client: MagicMock) -> None:
        """Test that API errors produce correct exit codes."""
        mock_client.list_traces.side_effect = LangfuseAPIError(
            "API error 500: Internal Server Error",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list"])

        assert result.exit_code == ERROR
        # Error messages can be in stdout or stderr depending on OutputContext
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_list_traces_not_found_error_exits_with_not_found_code(self, mock_client: MagicMock) -> None:
        """Test that 404 errors exit with NOT_FOUND code."""
        mock_client.list_traces.side_effect = LangfuseAPIError(
            "Resource not found",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list"])

        assert result.exit_code == NOT_FOUND
        mock_client.close.assert_called_once()

    def test_list_traces_empty_results(self, mock_client: MagicMock) -> None:
        """Test that empty results are handled gracefully."""
        mock_client.list_traces.return_value = []

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list"])

        assert result.exit_code == 0
        # Check for "No results found" message in output
        assert "No results found" in result.stdout or result.stdout.strip() == ""


class TestTracesGetCommand:
    """Test 'lf traces get' command."""

    def test_get_trace_success(self, mock_client: MagicMock) -> None:
        """Test that 'lf traces get <id>' shows trace detail."""
        mock_client.get_trace.return_value = SAMPLE_TRACE_DETAIL

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "get", "trace-1"])

        assert result.exit_code == 0
        # Verify the trace ID was passed correctly
        mock_client.get_trace.assert_called_once_with("trace-1")
        # Verify some of the detail appears in output
        assert "trace-1" in result.stdout
        mock_client.close.assert_called_once()

    def test_get_trace_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf traces get <id> --json' outputs JSON."""
        mock_client.get_trace.return_value = SAMPLE_TRACE_DETAIL

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "traces", "get", "trace-1"])

        assert result.exit_code == 0
        # Verify JSON output contains trace data
        assert "trace-1" in result.stdout
        assert "chat-completion" in result.stdout
        mock_client.close.assert_called_once()

    def test_get_trace_not_found(self, mock_client: MagicMock) -> None:
        """Test that missing trace returns NOT_FOUND exit code."""
        mock_client.get_trace.side_effect = LangfuseAPIError(
            "Resource not found: /traces/missing-trace",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "get", "missing-trace"])

        assert result.exit_code == NOT_FOUND
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_get_trace_api_error(self, mock_client: MagicMock) -> None:
        """Test that API errors are handled correctly."""
        mock_client.get_trace.side_effect = LangfuseAPIError(
            "API error 500",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "get", "trace-1"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()


class TestTracesTreeCommand:
    """Test 'lf traces tree' command."""

    def test_tree_trace_success(self, mock_client: MagicMock) -> None:
        """Test that 'lf traces tree <id>' displays trace hierarchy."""
        mock_client.get_trace.return_value = SAMPLE_TRACE_DETAIL
        mock_client.list_observations.return_value = SAMPLE_OBSERVATIONS

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            # Mock the tree renderer to avoid Rich output in tests
            with patch("langfuse_cli.formatters.tree.render_trace_tree") as mock_render:
                result = runner.invoke(app, ["traces", "tree", "trace-1"])

        assert result.exit_code == 0
        mock_client.get_trace.assert_called_once_with("trace-1")
        mock_client.list_observations.assert_called_once_with(trace_id="trace-1", limit=200)
        # Verify tree renderer was called with trace and observations
        mock_render.assert_called_once()
        call_args = mock_render.call_args[0]
        assert call_args[0] == SAMPLE_TRACE_DETAIL
        assert call_args[1] == SAMPLE_OBSERVATIONS
        mock_client.close.assert_called_once()

    def test_tree_trace_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf traces tree <id> --json' outputs JSON instead of tree."""
        mock_client.get_trace.return_value = SAMPLE_TRACE_DETAIL
        mock_client.list_observations.return_value = SAMPLE_OBSERVATIONS

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            # Mock render_trace_tree but it should not be called in JSON mode
            with patch("langfuse_cli.formatters.tree.render_trace_tree") as mock_render:
                result = runner.invoke(app, ["--json", "traces", "tree", "trace-1"])

        assert result.exit_code == 0
        # Tree renderer should NOT be called in JSON mode
        mock_render.assert_not_called()
        # Should output JSON with trace and observations
        assert "trace-1" in result.stdout
        mock_client.close.assert_called_once()

    def test_tree_trace_not_found(self, mock_client: MagicMock) -> None:
        """Test that missing trace returns NOT_FOUND exit code."""
        mock_client.get_trace.side_effect = LangfuseAPIError(
            "Resource not found",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "tree", "missing-trace"])

        assert result.exit_code == NOT_FOUND
        mock_client.close.assert_called_once()

    def test_tree_trace_api_error(self, mock_client: MagicMock) -> None:
        """Test that API errors are handled correctly."""
        mock_client.get_trace.side_effect = LangfuseAPIError(
            "Connection error",
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "tree", "trace-1"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()


class TestTraceCommandIntegration:
    """Integration tests for trace commands."""

    def test_multiple_filters_combined(self, mock_client: MagicMock) -> None:
        """Test that multiple filters can be combined."""
        mock_client.list_traces.return_value = []

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "traces",
                    "list",
                    "--limit",
                    "10",
                    "--user-id",
                    "user-123",
                    "--tags",
                    "production,verified",
                    "--name",
                    "chat",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_client.list_traces.call_args.kwargs
        assert call_kwargs["limit"] == 10
        assert call_kwargs["user_id"] == "user-123"
        assert call_kwargs["tags"] == ["production", "verified"]
        assert call_kwargs["name"] == "chat"

    def test_client_always_closed_on_error(self, mock_client: MagicMock) -> None:
        """Test that client is closed even when errors occur."""
        mock_client.list_traces.side_effect = LangfuseAPIError("Error", exit_code=ERROR)

        with patch("langfuse_cli.commands.traces.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["traces", "list"])

        # Even though there was an error, close should still be called
        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_help_text_available(self) -> None:
        """Test that help text is available for traces commands."""
        result = runner.invoke(app, ["traces", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "get" in result.stdout
        assert "tree" in result.stdout

    def test_list_help_shows_filter_options(self) -> None:
        """Test that list command help shows all filter options."""
        result = runner.invoke(app, ["traces", "list", "--help"])
        assert result.exit_code == 0
        assert "--limit" in result.stdout
        assert "--user-id" in result.stdout
        assert "--session-id" in result.stdout
        assert "--tags" in result.stdout
        assert "--name" in result.stdout
        assert "--from" in result.stdout
        assert "--to" in result.stdout
