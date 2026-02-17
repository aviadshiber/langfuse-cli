"""Tests for the datasets command module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


# Sample test data
SAMPLE_DATASETS = [
    {
        "name": "test-dataset-1",
        "description": "Test dataset for QA",
        "createdAt": "2024-01-15T10:00:00Z",
        "updatedAt": "2024-01-15T12:00:00Z",
    },
    {
        "name": "test-dataset-2",
        "description": "Production evaluation set",
        "createdAt": "2024-01-14T09:00:00Z",
        "updatedAt": "2024-01-14T09:00:00Z",
    },
]

SAMPLE_DATASET_DETAIL = {
    "name": "test-dataset-1",
    "description": "Test dataset for QA",
    "createdAt": "2024-01-15T10:00:00Z",
    "updatedAt": "2024-01-15T12:00:00Z",
    "metadata": {"version": "1.0", "domain": "support"},
}

SAMPLE_DATASET_ITEMS = [
    {
        "id": "item-1",
        "status": "active",
        "createdAt": "2024-01-15T10:30:00Z",
    },
    {
        "id": "item-2",
        "status": "active",
        "createdAt": "2024-01-15T11:00:00Z",
    },
]


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock LangfuseClient."""
    client = MagicMock()
    client.close = MagicMock()
    return client


class TestDatasetsListCommand:
    """Test 'lf datasets list' command."""

    def test_list_datasets_default_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf datasets list' outputs table with dataset data."""
        mock_client.list_datasets.return_value = SAMPLE_DATASETS

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "list"])

        assert result.exit_code == 0
        mock_client.list_datasets.assert_called_once_with(limit=50)
        mock_client.close.assert_called_once()

    def test_list_datasets_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf datasets list --json' outputs JSON array."""
        mock_client.list_datasets.return_value = SAMPLE_DATASETS

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "datasets", "list"])

        assert result.exit_code == 0
        # Verify JSON output contains dataset names
        assert "test-dataset-1" in result.stdout
        assert "test-dataset-2" in result.stdout
        mock_client.close.assert_called_once()

    def test_list_datasets_with_limit(self, mock_client: MagicMock) -> None:
        """Test that 'lf datasets list --limit 10' passes limit to client."""
        mock_client.list_datasets.return_value = []

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "list", "--limit", "10"])

        assert result.exit_code == 0
        mock_client.list_datasets.assert_called_once_with(limit=10)

    def test_list_datasets_api_error_exits_with_code(self, mock_client: MagicMock) -> None:
        """Test that API errors produce correct exit codes."""
        mock_client.list_datasets.side_effect = LangfuseAPIError(
            "API error 500: Internal Server Error",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "list"])

        assert result.exit_code == ERROR
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_list_datasets_not_found_error_exits_with_not_found_code(self, mock_client: MagicMock) -> None:
        """Test that 404 errors exit with NOT_FOUND code."""
        mock_client.list_datasets.side_effect = LangfuseAPIError(
            "Resource not found",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "list"])

        assert result.exit_code == NOT_FOUND
        mock_client.close.assert_called_once()

    def test_list_datasets_empty_results(self, mock_client: MagicMock) -> None:
        """Test that empty results are handled gracefully."""
        mock_client.list_datasets.return_value = []

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "list"])

        assert result.exit_code == 0


class TestDatasetsGetCommand:
    """Test 'lf datasets get' command."""

    def test_get_dataset_success(self, mock_client: MagicMock) -> None:
        """Test that 'lf datasets get <name>' shows dataset detail and items."""
        mock_client.get_dataset.return_value = SAMPLE_DATASET_DETAIL
        mock_client.list_dataset_items.return_value = SAMPLE_DATASET_ITEMS

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "get", "test-dataset-1"])

        assert result.exit_code == 0
        # Verify the dataset name was passed correctly
        mock_client.get_dataset.assert_called_once_with("test-dataset-1")
        mock_client.list_dataset_items.assert_called_once_with("test-dataset-1", limit=50)
        # Verify some of the detail appears in output
        assert "test-dataset-1" in result.stdout
        mock_client.close.assert_called_once()

    def test_get_dataset_json_output(self, mock_client: MagicMock) -> None:
        """Test that 'lf datasets get <name> --json' outputs JSON with dataset and items."""
        mock_client.get_dataset.return_value = SAMPLE_DATASET_DETAIL
        mock_client.list_dataset_items.return_value = SAMPLE_DATASET_ITEMS

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "datasets", "get", "test-dataset-1"])

        assert result.exit_code == 0
        # Verify JSON output contains both dataset and items
        assert "test-dataset-1" in result.stdout
        assert "dataset" in result.stdout
        assert "items" in result.stdout
        mock_client.close.assert_called_once()

    def test_get_dataset_with_custom_limit(self, mock_client: MagicMock) -> None:
        """Test that 'lf datasets get <name> --limit 10' passes limit to items call."""
        mock_client.get_dataset.return_value = SAMPLE_DATASET_DETAIL
        mock_client.list_dataset_items.return_value = []

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "get", "test-dataset-1", "--limit", "10"])

        assert result.exit_code == 0
        mock_client.list_dataset_items.assert_called_once_with("test-dataset-1", limit=10)

    def test_get_dataset_not_found(self, mock_client: MagicMock) -> None:
        """Test that missing dataset returns NOT_FOUND exit code."""
        mock_client.get_dataset.side_effect = LangfuseAPIError(
            "Resource not found: /datasets/missing-dataset",
            status_code=404,
            exit_code=NOT_FOUND,
        )

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "get", "missing-dataset"])

        assert result.exit_code == NOT_FOUND
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_get_dataset_api_error(self, mock_client: MagicMock) -> None:
        """Test that API errors are handled correctly."""
        mock_client.get_dataset.side_effect = LangfuseAPIError(
            "API error 500",
            status_code=500,
            exit_code=ERROR,
        )

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "get", "test-dataset-1"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_get_dataset_empty_items(self, mock_client: MagicMock) -> None:
        """Test that dataset with no items is handled gracefully."""
        mock_client.get_dataset.return_value = SAMPLE_DATASET_DETAIL
        mock_client.list_dataset_items.return_value = []

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "get", "test-dataset-1"])

        assert result.exit_code == 0
        # Should show dataset details even if no items
        assert "test-dataset-1" in result.stdout
        mock_client.close.assert_called_once()


class TestDatasetCommandIntegration:
    """Integration tests for dataset commands."""

    def test_client_always_closed_on_error(self, mock_client: MagicMock) -> None:
        """Test that client is closed even when errors occur."""
        mock_client.list_datasets.side_effect = LangfuseAPIError("Error", exit_code=ERROR)

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["datasets", "list"])

        assert result.exit_code == ERROR
        mock_client.close.assert_called_once()

    def test_help_text_available(self) -> None:
        """Test that help text is available for datasets commands."""
        result = runner.invoke(app, ["datasets", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "get" in result.stdout

    def test_list_help_shows_options(self) -> None:
        """Test that list command help shows options."""
        from tests.conftest import strip_ansi

        result = runner.invoke(app, ["datasets", "list", "--help"])
        assert result.exit_code == 0
        assert "--limit" in strip_ansi(result.stdout)

    def test_get_help_shows_options(self) -> None:
        """Test that get command help shows options."""
        from tests.conftest import strip_ansi

        result = runner.invoke(app, ["datasets", "get", "--help"])
        assert result.exit_code == 0
        assert "--limit" in strip_ansi(result.stdout)
