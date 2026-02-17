"""Tests for the observations command module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


# Sample test data
SAMPLE_OBSERVATIONS = [
    {
        "id": "obs-1",
        "traceId": "trace-1",
        "type": "GENERATION",
        "name": "llm-call",
        "startTime": "2024-01-15T10:30:00Z",
        "model": "gpt-4",
        "usage": {"totalTokens": 150},
    },
    {
        "id": "obs-2",
        "traceId": "trace-1",
        "type": "SPAN",
        "name": "processing",
        "startTime": "2024-01-15T10:30:02Z",
        "model": None,
        "usage": None,
    },
    {
        "id": "obs-3",
        "traceId": "trace-2",
        "type": "EVENT",
        "name": "user-feedback",
        "startTime": "2024-01-15T10:30:05Z",
        "model": None,
        "usage": None,
    },
]


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock LangfuseClient."""
    client = MagicMock()
    client.close = MagicMock()
    return client


class TestObservationsListCommand:
    """Test 'lf observations list' command."""

    def test_list_observations_default_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf observations list' outputs table with observation data."""
        mock_client.list_observations.return_value = SAMPLE_OBSERVATIONS

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list"])

        assert result.exit_code == 0
        mock_client.list_observations.assert_called_once_with(
            limit=50,
            trace_id=None,
            observation_type=None,
            name=None,
        )
        mock_client.close.assert_called_once()

    def test_list_observations_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf --json observations list' outputs JSON array."""
        mock_client.list_observations.return_value = SAMPLE_OBSERVATIONS

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "observations", "list"])

        assert result.exit_code == 0
        assert "obs-1" in result.stdout
        assert "GENERATION" in result.stdout
        assert "gpt-4" in result.stdout
        mock_client.close.assert_called_once()

    def test_list_observations_with_limit(self, mock_client: MagicMock) -> None:
        """Test that 'lf observations list --limit 10' passes limit to client."""
        mock_client.list_observations.return_value = []

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list", "--limit", "10"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_observations.call_args.kwargs
        assert call_kwargs["limit"] == 10

    def test_list_observations_with_trace_id(self, mock_client: MagicMock) -> None:
        """Test that 'lf observations list --trace-id X' passes filter."""
        mock_client.list_observations.return_value = []

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list", "--trace-id", "trace-123"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_observations.call_args.kwargs
        assert call_kwargs["trace_id"] == "trace-123"

    def test_list_observations_with_type_filter(self, mock_client: MagicMock) -> None:
        """Test that 'lf observations list --type GENERATION' passes type filter."""
        mock_client.list_observations.return_value = []

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list", "--type", "GENERATION"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_observations.call_args.kwargs
        assert call_kwargs["observation_type"] == "GENERATION"

    def test_list_observations_with_name_filter(self, mock_client: MagicMock) -> None:
        """Test that 'lf observations list --name llm-call' passes name filter."""
        mock_client.list_observations.return_value = []

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list", "--name", "llm-call"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_observations.call_args.kwargs
        assert call_kwargs["name"] == "llm-call"

    def test_list_observations_api_error_exits_with_code(self, mock_client: MagicMock) -> None:
        """Test that API errors produce correct exit codes."""
        mock_client.list_observations.side_effect = LangfuseAPIError(
            "API error 500: Internal Server Error",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list"])

        assert result.exit_code == ERROR
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_list_observations_not_found_error(self, mock_client: MagicMock) -> None:
        """Test that 404 errors exit with NOT_FOUND code."""
        mock_client.list_observations.side_effect = LangfuseAPIError(
            "Resource not found",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list"])

        assert result.exit_code == NOT_FOUND
        mock_client.close.assert_called_once()

    def test_list_observations_empty_results(self, mock_client: MagicMock) -> None:
        """Test that empty results are handled gracefully."""
        mock_client.list_observations.return_value = []

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list"])

        assert result.exit_code == 0


class TestObservationsIntegration:
    """Integration tests for observation commands."""

    def test_multiple_filters_combined(self, mock_client: MagicMock) -> None:
        """Test that multiple filters can be combined."""
        mock_client.list_observations.return_value = []

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "observations",
                    "list",
                    "--trace-id",
                    "trace-1",
                    "--type",
                    "GENERATION",
                    "--name",
                    "llm-call",
                    "--limit",
                    "10",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_client.list_observations.call_args.kwargs
        assert call_kwargs["trace_id"] == "trace-1"
        assert call_kwargs["observation_type"] == "GENERATION"
        assert call_kwargs["name"] == "llm-call"
        assert call_kwargs["limit"] == 10

    def test_client_always_closed_on_error(self, mock_client: MagicMock) -> None:
        """Test that client is closed even when errors occur."""
        mock_client.list_observations.side_effect = LangfuseAPIError("Error", exit_code=ERROR)

        with patch("langfuse_cli.commands.observations.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["observations", "list"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_help_text_available(self) -> None:
        """Test that help text is available for observations commands."""
        result = runner.invoke(app, ["observations", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout

    def test_list_help_shows_filter_options(self) -> None:
        """Test that list command help shows all filter options."""
        from tests.conftest import strip_ansi

        result = runner.invoke(app, ["observations", "list", "--help"])
        assert result.exit_code == 0
        stdout = strip_ansi(result.stdout)
        assert "--limit" in stdout
        assert "--trace-id" in stdout
        assert "--type" in stdout
        assert "--name" in stdout
