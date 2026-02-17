"""Tests for the prompts command module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock LangfuseClient."""
    client = MagicMock()
    client.close = MagicMock()
    return client


# list command tests


class TestListPrompts:
    """Test 'lf prompts list' command."""

    def test_list_prompts_success(self, mock_client: MagicMock) -> None:
        """Test listing prompts successfully."""
        sample_prompts = [
            {"name": "test-prompt", "version": 1, "type": "text", "labels": ["production"], "tags": ["tag1"]},
            {"name": "chat-prompt", "version": 2, "type": "chat", "labels": [], "tags": ["tag2", "tag3"]},
        ]
        mock_client.list_prompts.return_value = sample_prompts

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "list"])

        assert result.exit_code == 0
        mock_client.list_prompts.assert_called_once()
        mock_client.close.assert_called_once()

    def test_list_prompts_json(self, mock_client: MagicMock) -> None:
        """Test listing prompts in JSON mode."""
        sample_prompts = [{"name": "test-prompt", "version": 1, "type": "text", "labels": [], "tags": []}]
        mock_client.list_prompts.return_value = sample_prompts

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "prompts", "list"])

        assert result.exit_code == 0
        assert "test-prompt" in result.stdout
        mock_client.close.assert_called_once()

    def test_list_prompts_api_error(self, mock_client: MagicMock) -> None:
        """Test list prompts with API error."""
        mock_client.list_prompts.side_effect = LangfuseAPIError("API error", exit_code=ERROR)

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "list"])

        assert result.exit_code == ERROR
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_list_prompts_calls_close(self, mock_client: MagicMock) -> None:
        """Test that client.close() is always called."""
        mock_client.list_prompts.return_value = []

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            runner.invoke(app, ["prompts", "list"])

        mock_client.close.assert_called_once()


# get command tests


class TestGetPrompt:
    """Test 'lf prompts get' command."""

    def test_get_prompt_text_type(self, mock_client: MagicMock) -> None:
        """Test getting a text-type prompt."""
        mock_prompt = MagicMock()
        mock_prompt.name = "test-prompt"
        mock_prompt.version = 1
        mock_prompt.type = "text"
        mock_prompt.labels = ["production"]
        mock_prompt.config = {"temperature": 0.7}
        mock_prompt.prompt = "This is the prompt text"
        mock_client.get_prompt.return_value = mock_prompt

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "get", "test-prompt"])

        assert result.exit_code == 0
        mock_client.get_prompt.assert_called_once_with("test-prompt", version=None, label=None)
        assert "test-prompt" in result.stdout
        mock_client.close.assert_called_once()

    def test_get_prompt_chat_type(self, mock_client: MagicMock) -> None:
        """Test getting a chat-type prompt with messages."""
        mock_prompt = MagicMock()
        mock_prompt.name = "chat-prompt"
        mock_prompt.version = 2
        mock_prompt.type = "chat"
        mock_prompt.labels = []
        mock_prompt.config = {}
        mock_prompt.messages = [{"role": "user", "content": "Hello"}]
        delattr(mock_prompt, "prompt")
        mock_client.get_prompt.return_value = mock_prompt

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "get", "chat-prompt"])

        assert result.exit_code == 0
        mock_client.close.assert_called_once()

    def test_get_prompt_with_version(self, mock_client: MagicMock) -> None:
        """Test getting a prompt with specific version."""
        mock_prompt = MagicMock()
        mock_prompt.name = "test-prompt"
        mock_prompt.version = 5
        mock_prompt.type = "text"
        mock_prompt.labels = []
        mock_prompt.config = {}
        mock_prompt.prompt = "Version 5 text"
        mock_client.get_prompt.return_value = mock_prompt

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "get", "test-prompt", "--version", "5"])

        assert result.exit_code == 0
        mock_client.get_prompt.assert_called_once_with("test-prompt", version=5, label=None)
        mock_client.close.assert_called_once()

    def test_get_prompt_with_label(self, mock_client: MagicMock) -> None:
        """Test getting a prompt with specific label."""
        mock_prompt = MagicMock()
        mock_prompt.name = "test-prompt"
        mock_prompt.version = 3
        mock_prompt.type = "text"
        mock_prompt.labels = ["production"]
        mock_prompt.config = {}
        mock_prompt.prompt = "Production prompt"
        mock_client.get_prompt.return_value = mock_prompt

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "get", "test-prompt", "--label", "production"])

        assert result.exit_code == 0
        mock_client.get_prompt.assert_called_once_with("test-prompt", version=None, label="production")
        mock_client.close.assert_called_once()

    def test_get_prompt_api_error(self, mock_client: MagicMock) -> None:
        """Test get prompt with API error (not found)."""
        mock_client.get_prompt.side_effect = LangfuseAPIError("Prompt not found", status_code=404, exit_code=NOT_FOUND)

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "get", "nonexistent"])

        assert result.exit_code == NOT_FOUND
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_get_prompt_generic_error(self, mock_client: MagicMock) -> None:
        """Test get prompt with generic exception (catch_all=True)."""
        mock_client.get_prompt.side_effect = ValueError("Unexpected error")

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "get", "test-prompt"])

        assert result.exit_code == 1
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_get_prompt_calls_close(self, mock_client: MagicMock) -> None:
        """Test that client.close() is always called."""
        mock_prompt = MagicMock()
        mock_prompt.name = "test-prompt"
        mock_prompt.version = 1
        mock_prompt.type = "text"
        mock_prompt.labels = []
        mock_prompt.config = {}
        mock_prompt.prompt = "Text"
        mock_client.get_prompt.return_value = mock_prompt

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            runner.invoke(app, ["prompts", "get", "test-prompt"])

        mock_client.close.assert_called_once()


# compile command tests


class TestCompilePrompt:
    """Test 'lf prompts compile' command."""

    def test_compile_prompt_basic(self, mock_client: MagicMock) -> None:
        """Test compiling a prompt with basic variable."""
        compiled_result = {"prompt": "Hello, World!"}
        mock_client.compile_prompt.return_value = compiled_result

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "compile", "test-prompt", "--var", "name=World"])

        assert result.exit_code == 0
        mock_client.compile_prompt.assert_called_once_with("test-prompt", {"name": "World"})
        mock_client.close.assert_called_once()

    def test_compile_prompt_multiple_vars(self, mock_client: MagicMock) -> None:
        """Test compiling a prompt with multiple variables."""
        compiled_result = {"prompt": "Hello, Alice! You are 30 years old."}
        mock_client.compile_prompt.return_value = compiled_result

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(
                app,
                ["prompts", "compile", "test-prompt", "--var", "name=Alice", "--var", "age=30"],
            )

        assert result.exit_code == 0
        mock_client.compile_prompt.assert_called_once_with(
            "test-prompt",
            {"name": "Alice", "age": "30"},
        )
        mock_client.close.assert_called_once()

    def test_compile_prompt_with_version(self, mock_client: MagicMock) -> None:
        """Test compiling a prompt with specific version."""
        compiled_result = {"prompt": "Version 2 compiled"}
        mock_client.compile_prompt.return_value = compiled_result

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(
                app,
                ["prompts", "compile", "test-prompt", "--var", "x=y", "--version", "2"],
            )

        assert result.exit_code == 0
        mock_client.compile_prompt.assert_called_once_with("test-prompt", {"x": "y"}, version=2)
        mock_client.close.assert_called_once()

    def test_compile_prompt_with_label(self, mock_client: MagicMock) -> None:
        """Test compiling a prompt with specific label."""
        compiled_result = {"prompt": "Production compiled"}
        mock_client.compile_prompt.return_value = compiled_result

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(
                app,
                ["prompts", "compile", "test-prompt", "--var", "x=y", "--label", "production"],
            )

        assert result.exit_code == 0
        mock_client.compile_prompt.assert_called_once_with("test-prompt", {"x": "y"}, label="production")
        mock_client.close.assert_called_once()

    def test_compile_prompt_invalid_var(self, mock_client: MagicMock) -> None:
        """Test compiling a prompt with invalid variable format."""
        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "compile", "test-prompt", "--var", "invalidformat"])

        assert result.exit_code == 1
        error_output = result.stdout + result.stderr
        assert "invalid variable format" in error_output
        mock_client.close.assert_called_once()

    def test_compile_prompt_api_error(self, mock_client: MagicMock) -> None:
        """Test compile prompt with API error."""
        mock_client.compile_prompt.side_effect = LangfuseAPIError("Compilation failed", exit_code=ERROR)

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "compile", "test-prompt", "--var", "x=y"])

        assert result.exit_code == ERROR
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_compile_prompt_calls_close(self, mock_client: MagicMock) -> None:
        """Test that client.close() is always called."""
        mock_client.compile_prompt.return_value = {"prompt": "Result"}

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            runner.invoke(app, ["prompts", "compile", "test-prompt", "--var", "x=y"])

        mock_client.close.assert_called_once()


# diff command tests


class TestDiffPrompts:
    """Test 'lf prompts diff' command."""

    def test_diff_prompts_json_mode(self, mock_client: MagicMock) -> None:
        """Test diffing prompts in JSON mode."""
        mock_prompt1 = MagicMock()
        mock_prompt1.prompt = "Version 1 text"
        delattr(mock_prompt1, "messages")

        mock_prompt2 = MagicMock()
        mock_prompt2.prompt = "Version 2 text"
        delattr(mock_prompt2, "messages")

        mock_client.get_prompt.side_effect = [mock_prompt1, mock_prompt2]

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["--json", "prompts", "diff", "test-prompt", "--v1", "1", "--v2", "2"])

        assert result.exit_code == 0
        assert mock_client.get_prompt.call_count == 2
        assert "test-prompt" in result.stdout
        assert "Version 1 text" in result.stdout
        assert "Version 2 text" in result.stdout
        mock_client.close.assert_called_once()

    @patch("langfuse_cli.formatters.diff.render_diff")
    def test_diff_prompts_text_mode(self, mock_render_diff: MagicMock, mock_client: MagicMock) -> None:
        """Test diffing prompts in text mode."""
        mock_prompt1 = MagicMock()
        mock_prompt1.prompt = "Original text"
        delattr(mock_prompt1, "messages")

        mock_prompt2 = MagicMock()
        mock_prompt2.prompt = "Modified text"
        delattr(mock_prompt2, "messages")

        mock_client.get_prompt.side_effect = [mock_prompt1, mock_prompt2]

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "diff", "test-prompt", "--v1", "3", "--v2", "4"])

        assert result.exit_code == 0
        mock_render_diff.assert_called_once_with(
            "Original text",
            "Modified text",
            labels=("v3", "v4"),
        )
        mock_client.close.assert_called_once()

    @patch("langfuse_cli.formatters.diff.render_diff")
    def test_diff_prompts_messages_type(self, mock_render_diff: MagicMock, mock_client: MagicMock) -> None:
        """Test diffing prompts with messages (chat type)."""
        mock_prompt1 = MagicMock()
        mock_prompt1.messages = [{"role": "user", "content": "Hello"}]
        delattr(mock_prompt1, "prompt")

        mock_prompt2 = MagicMock()
        mock_prompt2.messages = [{"role": "user", "content": "Hi there"}]
        delattr(mock_prompt2, "prompt")

        mock_client.get_prompt.side_effect = [mock_prompt1, mock_prompt2]

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "diff", "chat-prompt", "--v1", "1", "--v2", "2"])

        assert result.exit_code == 0
        call_args = mock_render_diff.call_args
        assert "[{'role': 'user', 'content': 'Hello'}]" in call_args[0][0]
        assert "[{'role': 'user', 'content': 'Hi there'}]" in call_args[0][1]
        mock_client.close.assert_called_once()

    def test_diff_prompts_api_error(self, mock_client: MagicMock) -> None:
        """Test diff prompts with API error."""
        mock_client.get_prompt.side_effect = LangfuseAPIError("Version not found", exit_code=NOT_FOUND)

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            result = runner.invoke(app, ["prompts", "diff", "test-prompt", "--v1", "1", "--v2", "999"])

        assert result.exit_code == NOT_FOUND
        error_output = result.stdout + result.stderr
        assert "error:" in error_output
        mock_client.close.assert_called_once()

    def test_diff_prompts_calls_close(self, mock_client: MagicMock) -> None:
        """Test that client.close() is always called."""
        mock_prompt1 = MagicMock()
        mock_prompt1.prompt = "Text 1"
        delattr(mock_prompt1, "messages")

        mock_prompt2 = MagicMock()
        mock_prompt2.prompt = "Text 2"
        delattr(mock_prompt2, "messages")

        mock_client.get_prompt.side_effect = [mock_prompt1, mock_prompt2]

        with patch("langfuse_cli.commands.LangfuseClient", return_value=mock_client):
            runner.invoke(app, ["--json", "prompts", "diff", "test-prompt", "--v1", "1", "--v2", "2"])

        mock_client.close.assert_called_once()
