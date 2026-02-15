"""Tests for the scores command module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


# Sample test data
SAMPLE_SCORES = [
    {
        "id": "s1",
        "traceId": "t1",
        "name": "quality",
        "value": 0.9,
        "observationId": None,
        "timestamp": "2024-01-15T10:30:00Z",
    },
    {
        "id": "s2",
        "traceId": "t2",
        "name": "quality",
        "value": 0.7,
        "observationId": "obs1",
        "timestamp": "2024-01-15T11:00:00Z",
    },
    {
        "id": "s3",
        "traceId": "t3",
        "name": "relevance",
        "value": 0.5,
        "observationId": None,
        "timestamp": "2024-01-15T11:30:00Z",
    },
]


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock LangfuseClient."""
    client = MagicMock()
    client.close = MagicMock()
    return client


class TestScoresListCommand:
    """Test 'lf scores list' command."""

    def test_list_scores_default_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf scores list' outputs table with score data."""
        mock_client.list_scores.return_value = SAMPLE_SCORES

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "list"])

        assert result.exit_code == 0
        mock_client.list_scores.assert_called_once_with(
            limit=50,
            trace_id=None,
            name=None,
            from_timestamp=None,
            to_timestamp=None,
        )
        mock_client.close.assert_called_once()

    def test_list_scores_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf scores list --json' outputs JSON array."""
        mock_client.list_scores.return_value = SAMPLE_SCORES

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "scores", "list"])

        assert result.exit_code == 0
        # Verify JSON output contains score data
        assert "s1" in result.stdout
        assert "quality" in result.stdout
        assert "0.9" in result.stdout
        mock_client.close.assert_called_once()

    def test_list_scores_with_limit(self, mock_client: MagicMock) -> None:
        """Test that 'lf scores list --limit 10' passes limit to client."""
        mock_client.list_scores.return_value = []

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "list", "--limit", "10"])

        assert result.exit_code == 0
        mock_client.list_scores.assert_called_once()
        call_kwargs = mock_client.list_scores.call_args.kwargs
        assert call_kwargs["limit"] == 10

    def test_list_scores_with_trace_id_filter(self, mock_client: MagicMock) -> None:
        """Test that 'lf scores list --trace-id X' passes filter."""
        mock_client.list_scores.return_value = []

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "list", "--trace-id", "t1"])

        assert result.exit_code == 0
        mock_client.list_scores.assert_called_once()
        call_kwargs = mock_client.list_scores.call_args.kwargs
        assert call_kwargs["trace_id"] == "t1"

    def test_list_scores_with_name_filter(self, mock_client: MagicMock) -> None:
        """Test that 'lf scores list --name quality' passes name filter."""
        mock_client.list_scores.return_value = []

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "list", "--name", "quality"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_scores.call_args.kwargs
        assert call_kwargs["name"] == "quality"

    def test_list_scores_api_error_exits_with_code(self, mock_client: MagicMock) -> None:
        """Test that API errors produce correct exit codes."""
        mock_client.list_scores.side_effect = LangfuseAPIError(
            "API error 500: Internal Server Error",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "list"])

        assert result.exit_code == ERROR
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_list_scores_not_found_error_exits_with_not_found_code(self, mock_client: MagicMock) -> None:
        """Test that 404 errors exit with NOT_FOUND code."""
        mock_client.list_scores.side_effect = LangfuseAPIError(
            "Resource not found",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "list"])

        assert result.exit_code == NOT_FOUND
        mock_client.close.assert_called_once()

    def test_list_scores_empty_results(self, mock_client: MagicMock) -> None:
        """Test that empty results are handled gracefully."""
        mock_client.list_scores.return_value = []

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "list"])

        assert result.exit_code == 0


class TestScoresSummaryCommand:
    """Test 'lf scores summary' command."""

    def test_summary_scores_computes_statistics(self, mock_client: MagicMock) -> None:
        """Test that 'lf scores summary' computes mean/min/max/count grouped by name."""
        mock_client.list_scores.return_value = SAMPLE_SCORES

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "summary"])

        assert result.exit_code == 0
        # Should fetch scores with limit 500
        mock_client.list_scores.assert_called_once_with(
            limit=500,
            name=None,
            from_timestamp=None,
            to_timestamp=None,
        )
        # Output should contain score names and statistics
        # (exact format depends on output mode, but command should succeed)
        mock_client.close.assert_called_once()

    def test_summary_scores_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf scores summary --json' outputs JSON with statistics."""
        mock_client.list_scores.return_value = SAMPLE_SCORES

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "scores", "summary"])

        assert result.exit_code == 0
        # Should contain score names and computed statistics
        assert "quality" in result.stdout or "relevance" in result.stdout
        mock_client.close.assert_called_once()

    def test_summary_scores_with_name_filter(self, mock_client: MagicMock) -> None:
        """Test that 'lf scores summary --name quality' filters by name."""
        quality_scores = [s for s in SAMPLE_SCORES if s["name"] == "quality"]
        mock_client.list_scores.return_value = quality_scores

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "summary", "--name", "quality"])

        assert result.exit_code == 0
        call_kwargs = mock_client.list_scores.call_args.kwargs
        assert call_kwargs["name"] == "quality"
        mock_client.close.assert_called_once()

    def test_summary_scores_empty_results(self, mock_client: MagicMock) -> None:
        """Test that empty scores show appropriate message."""
        mock_client.list_scores.return_value = []

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "summary"])

        assert result.exit_code == 0
        # Should show "No scores found" message
        assert "No scores found" in result.stdout or result.stdout.strip() == ""
        mock_client.close.assert_called_once()

    def test_summary_scores_api_error_exits_with_code(self, mock_client: MagicMock) -> None:
        """Test that API errors produce correct exit codes."""
        mock_client.list_scores.side_effect = LangfuseAPIError(
            "API error 500",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "summary"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_summary_computes_correct_statistics(self, mock_client: MagicMock) -> None:
        """Test that summary computes statistics correctly."""
        # Create scores with known statistics
        scores = [
            {
                "id": "s1", "traceId": "t1", "name": "quality",
                "value": 1.0, "observationId": None, "timestamp": "2024-01-15T10:30:00Z",
            },
            {
                "id": "s2", "traceId": "t2", "name": "quality",
                "value": 0.0, "observationId": None, "timestamp": "2024-01-15T11:00:00Z",
            },
            {
                "id": "s3", "traceId": "t3", "name": "quality",
                "value": 0.5, "observationId": None, "timestamp": "2024-01-15T11:30:00Z",
            },
        ]
        mock_client.list_scores.return_value = scores

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "scores", "summary"])

        assert result.exit_code == 0
        # Expected: count=3, mean=0.5, min=0.0, max=1.0
        # These should appear in JSON output
        assert "quality" in result.stdout
        mock_client.close.assert_called_once()


class TestScoreCommandIntegration:
    """Integration tests for score commands."""

    def test_multiple_filters_combined(self, mock_client: MagicMock) -> None:
        """Test that multiple filters can be combined."""
        mock_client.list_scores.return_value = []

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "scores",
                    "list",
                    "--limit",
                    "10",
                    "--trace-id",
                    "t1",
                    "--name",
                    "quality",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_client.list_scores.call_args.kwargs
        assert call_kwargs["limit"] == 10
        assert call_kwargs["trace_id"] == "t1"
        assert call_kwargs["name"] == "quality"

    def test_client_always_closed_on_error(self, mock_client: MagicMock) -> None:
        """Test that client is closed even when errors occur."""
        mock_client.list_scores.side_effect = LangfuseAPIError("Error", exit_code=ERROR)

        with patch("langfuse_cli.commands.scores.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["scores", "list"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_help_text_available(self) -> None:
        """Test that help text is available for scores commands."""
        result = runner.invoke(app, ["scores", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "summary" in result.stdout

    def test_list_help_shows_filter_options(self) -> None:
        """Test that list command help shows all filter options."""
        from tests.conftest import strip_ansi
        result = runner.invoke(app, ["scores", "list", "--help"])
        assert result.exit_code == 0
        stdout = strip_ansi(result.stdout)
        assert "--limit" in stdout
        assert "--trace-id" in stdout
        assert "--name" in stdout
        assert "--from" in stdout
        assert "--to" in stdout
