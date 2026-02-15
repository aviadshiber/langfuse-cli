"""Tests for the experiments command module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


# Sample test data
SAMPLE_RUNS = [
    {
        "name": "run-v1",
        "description": "Baseline model",
        "createdAt": "2024-01-15T10:00:00Z",
        "updatedAt": "2024-01-15T12:00:00Z",
    },
    {
        "name": "run-v2",
        "description": "Improved prompt",
        "createdAt": "2024-01-16T10:00:00Z",
        "updatedAt": "2024-01-16T12:00:00Z",
    },
]

SAMPLE_RUN_DATA = {
    "name": "run-v1",
    "description": "Baseline model",
    "createdAt": "2024-01-15T10:00:00Z",
    "updatedAt": "2024-01-15T12:00:00Z",
    "metadata": {"model": "gpt-4", "temperature": 0.7},
}

SAMPLE_RUN_DATA_2 = {
    "name": "run-v2",
    "description": "Improved prompt",
    "createdAt": "2024-01-16T10:00:00Z",
    "updatedAt": "2024-01-16T12:00:00Z",
    "metadata": {"model": "gpt-4", "temperature": 0.5},
}


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock LangfuseClient."""
    client = MagicMock()
    client.close = MagicMock()
    return client


class TestExperimentsListCommand:
    """Test 'lf experiments list' command."""

    def test_list_experiments_default_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf experiments list <dataset>' outputs table with run data."""
        mock_client.list_dataset_runs.return_value = SAMPLE_RUNS

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["experiments", "list", "test-dataset"])

        assert result.exit_code == 0
        mock_client.list_dataset_runs.assert_called_once_with("test-dataset")
        mock_client.close.assert_called_once()

    def test_list_experiments_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf experiments list <dataset> --json' outputs JSON array."""
        mock_client.list_dataset_runs.return_value = SAMPLE_RUNS

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "experiments", "list", "test-dataset"])

        assert result.exit_code == 0
        # Verify JSON output contains run names
        assert "run-v1" in result.stdout
        assert "run-v2" in result.stdout
        mock_client.close.assert_called_once()

    def test_list_experiments_api_error_exits_with_code(self, mock_client: MagicMock) -> None:
        """Test that API errors produce correct exit codes."""
        mock_client.list_dataset_runs.side_effect = LangfuseAPIError(
            "API error 500: Internal Server Error",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["experiments", "list", "test-dataset"])

        assert result.exit_code == ERROR
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_list_experiments_not_found_error_exits_with_not_found_code(self, mock_client: MagicMock) -> None:
        """Test that 404 errors exit with NOT_FOUND code."""
        mock_client.list_dataset_runs.side_effect = LangfuseAPIError(
            "Resource not found",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["experiments", "list", "missing-dataset"])

        assert result.exit_code == NOT_FOUND
        mock_client.close.assert_called_once()

    def test_list_experiments_empty_results(self, mock_client: MagicMock) -> None:
        """Test that empty results are handled gracefully."""
        mock_client.list_dataset_runs.return_value = []

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["experiments", "list", "test-dataset"])

        assert result.exit_code == 0


class TestExperimentsCompareCommand:
    """Test 'lf experiments compare' command."""

    def test_compare_experiments_success(self, mock_client: MagicMock) -> None:
        """Test that 'lf experiments compare <dataset> <run1> <run2>' shows comparison table."""
        mock_client.get_dataset_run.side_effect = [SAMPLE_RUN_DATA, SAMPLE_RUN_DATA_2]

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            # Mock Rich Console to avoid terminal output in tests
            with patch("rich.console.Console") as mock_console_class:
                mock_console = MagicMock()
                mock_console_class.return_value = mock_console
                result = runner.invoke(app, ["experiments", "compare", "test-dataset", "run-v1", "run-v2"])

        assert result.exit_code == 0
        # Verify both runs were fetched
        assert mock_client.get_dataset_run.call_count == 2
        mock_client.get_dataset_run.assert_any_call("test-dataset", "run-v1")
        mock_client.get_dataset_run.assert_any_call("test-dataset", "run-v2")
        # Verify Rich table was printed
        mock_console.print.assert_called_once()
        mock_client.close.assert_called_once()

    def test_compare_experiments_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf experiments compare <dataset> <run1> <run2> --json' outputs JSON comparison."""
        mock_client.get_dataset_run.side_effect = [SAMPLE_RUN_DATA, SAMPLE_RUN_DATA_2]

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "experiments", "compare", "test-dataset", "run-v1", "run-v2"])

        assert result.exit_code == 0
        # Verify JSON output contains both runs
        assert "run-v1" in result.stdout
        assert "run-v2" in result.stdout
        assert "dataset" in result.stdout
        mock_client.close.assert_called_once()

    def test_compare_experiments_first_run_not_found(self, mock_client: MagicMock) -> None:
        """Test that missing first run returns NOT_FOUND exit code."""
        mock_client.get_dataset_run.side_effect = LangfuseAPIError(
            "Resource not found: /datasets/test-dataset/runs/missing-run",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["experiments", "compare", "test-dataset", "missing-run", "run-v2"])

        assert result.exit_code == NOT_FOUND
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_compare_experiments_second_run_not_found(self, mock_client: MagicMock) -> None:
        """Test that missing second run returns NOT_FOUND exit code."""
        def side_effect(dataset: str, run_name: str) -> dict[str, Any]:
            if run_name == "run-v1":
                return SAMPLE_RUN_DATA
            raise LangfuseAPIError(
                "Resource not found: /datasets/test-dataset/runs/missing-run",
                status_code=404,
                exit_code=NOT_FOUND,
            )

        mock_client.get_dataset_run.side_effect = side_effect

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["experiments", "compare", "test-dataset", "run-v1", "missing-run"])

        assert result.exit_code == NOT_FOUND
        mock_client.close.assert_called_once()

    def test_compare_experiments_api_error(self, mock_client: MagicMock) -> None:
        """Test that API errors are handled correctly."""
        mock_client.get_dataset_run.side_effect = LangfuseAPIError(
            "API error 500",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["experiments", "compare", "test-dataset", "run-v1", "run-v2"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()


class TestExperimentCommandIntegration:
    """Integration tests for experiment commands."""

    def test_client_always_closed_on_error(self, mock_client: MagicMock) -> None:
        """Test that client is closed even when errors occur."""
        mock_client.list_dataset_runs.side_effect = LangfuseAPIError("Error", exit_code=ERROR)

        with patch("langfuse_cli.commands.experiments.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["experiments", "list", "test-dataset"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_help_text_available(self) -> None:
        """Test that help text is available for experiments commands."""
        result = runner.invoke(app, ["experiments", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "compare" in result.stdout

    def test_list_help_text(self) -> None:
        """Test that list command help is available."""
        result = runner.invoke(app, ["experiments", "list", "--help"])
        assert result.exit_code == 0
        assert "dataset" in result.stdout.lower()

    def test_compare_help_text(self) -> None:
        """Test that compare command help is available."""
        result = runner.invoke(app, ["experiments", "compare", "--help"])
        assert result.exit_code == 0
        assert "dataset" in result.stdout.lower()
        assert "run" in result.stdout.lower()
