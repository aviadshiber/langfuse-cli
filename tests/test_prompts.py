"""Tests for the prompts command module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError
from langfuse_cli.main import app

runner = CliRunner()


# list command tests


@patch("langfuse_cli.commands.prompts._get_client")
def test_list_prompts_success(mock_get_client: MagicMock) -> None:
    """Test listing prompts successfully."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_output.is_json_mode = False
    mock_get_client.return_value = (mock_client, mock_output)

    sample_prompts = [
        {
            "name": "test-prompt",
            "version": 1,
            "type": "text",
            "labels": ["production"],
            "tags": ["tag1"],
        },
        {
            "name": "chat-prompt",
            "version": 2,
            "type": "chat",
            "labels": [],
            "tags": ["tag2", "tag3"],
        },
    ]
    mock_client.list_prompts.return_value = sample_prompts

    result = runner.invoke(app, ["prompts", "list"])

    assert result.exit_code == 0
    mock_client.list_prompts.assert_called_once()
    mock_output.render_table.assert_called_once_with(
        sample_prompts,
        columns=["name", "version", "type", "labels", "tags"],
    )
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_list_prompts_json(mock_get_client: MagicMock) -> None:
    """Test listing prompts in JSON mode."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_output.is_json_mode = True
    mock_get_client.return_value = (mock_client, mock_output)

    sample_prompts = [{"name": "test-prompt", "version": 1, "type": "text", "labels": [], "tags": []}]
    mock_client.list_prompts.return_value = sample_prompts

    result = runner.invoke(app, ["prompts", "list"])

    assert result.exit_code == 0
    mock_output.render_table.assert_called_once_with(
        sample_prompts,
        columns=["name", "version", "type", "labels", "tags"],
    )
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_list_prompts_api_error(mock_get_client: MagicMock) -> None:
    """Test list prompts with API error."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_client.list_prompts.side_effect = LangfuseAPIError("API error", exit_code=ERROR)

    result = runner.invoke(app, ["prompts", "list"])

    assert result.exit_code == ERROR
    mock_output.error.assert_called_once()
    assert "error:" in mock_output.error.call_args[0][0]
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_list_prompts_calls_close(mock_get_client: MagicMock) -> None:
    """Test that client.close() is always called."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_client.list_prompts.return_value = []

    runner.invoke(app, ["prompts", "list"])

    mock_client.close.assert_called_once()


# get command tests


@patch("langfuse_cli.commands.prompts._get_client")
def test_get_prompt_text_type(mock_get_client: MagicMock) -> None:
    """Test getting a text-type prompt."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_output.is_json_mode = False
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt = MagicMock()
    mock_prompt.name = "test-prompt"
    mock_prompt.version = 1
    mock_prompt.type = "text"
    mock_prompt.labels = ["production"]
    mock_prompt.config = {"temperature": 0.7}
    mock_prompt.prompt = "This is the prompt text"
    mock_client.get_prompt.return_value = mock_prompt

    result = runner.invoke(app, ["prompts", "get", "test-prompt"])

    assert result.exit_code == 0
    mock_client.get_prompt.assert_called_once_with("test-prompt", version=None, label=None)
    mock_output.render_detail.assert_called_once()
    call_args = mock_output.render_detail.call_args
    assert call_args[0][0]["name"] == "test-prompt"
    assert call_args[0][0]["prompt"] == "This is the prompt text"
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_get_prompt_chat_type(mock_get_client: MagicMock) -> None:
    """Test getting a chat-type prompt with messages."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_output.is_json_mode = False
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt = MagicMock()
    mock_prompt.name = "chat-prompt"
    mock_prompt.version = 2
    mock_prompt.type = "chat"
    mock_prompt.labels = []
    mock_prompt.config = {}
    mock_prompt.messages = [{"role": "user", "content": "Hello"}]
    # No prompt attribute for chat type
    delattr(mock_prompt, "prompt")
    mock_client.get_prompt.return_value = mock_prompt

    result = runner.invoke(app, ["prompts", "get", "chat-prompt"])

    assert result.exit_code == 0
    call_args = mock_output.render_detail.call_args
    assert call_args[0][0]["messages"] == [{"role": "user", "content": "Hello"}]
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_get_prompt_with_version(mock_get_client: MagicMock) -> None:
    """Test getting a prompt with specific version."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt = MagicMock()
    mock_prompt.name = "test-prompt"
    mock_prompt.version = 5
    mock_prompt.type = "text"
    mock_prompt.labels = []
    mock_prompt.config = {}
    mock_prompt.prompt = "Version 5 text"
    mock_client.get_prompt.return_value = mock_prompt

    result = runner.invoke(app, ["prompts", "get", "test-prompt", "--version", "5"])

    assert result.exit_code == 0
    mock_client.get_prompt.assert_called_once_with("test-prompt", version=5, label=None)
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_get_prompt_with_label(mock_get_client: MagicMock) -> None:
    """Test getting a prompt with specific label."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt = MagicMock()
    mock_prompt.name = "test-prompt"
    mock_prompt.version = 3
    mock_prompt.type = "text"
    mock_prompt.labels = ["production"]
    mock_prompt.config = {}
    mock_prompt.prompt = "Production prompt"
    mock_client.get_prompt.return_value = mock_prompt

    result = runner.invoke(app, ["prompts", "get", "test-prompt", "--label", "production"])

    assert result.exit_code == 0
    mock_client.get_prompt.assert_called_once_with("test-prompt", version=None, label="production")
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_get_prompt_api_error(mock_get_client: MagicMock) -> None:
    """Test get prompt with API error (not found)."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_client.get_prompt.side_effect = LangfuseAPIError("Prompt not found", status_code=404, exit_code=NOT_FOUND)

    result = runner.invoke(app, ["prompts", "get", "nonexistent"])

    assert result.exit_code == NOT_FOUND
    mock_output.error.assert_called_once()
    assert "error:" in mock_output.error.call_args[0][0]
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_get_prompt_generic_error(mock_get_client: MagicMock) -> None:
    """Test get prompt with generic exception."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_client.get_prompt.side_effect = ValueError("Unexpected error")

    result = runner.invoke(app, ["prompts", "get", "test-prompt"])

    assert result.exit_code == 1
    mock_output.error.assert_called_once()
    assert "error:" in mock_output.error.call_args[0][0]
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_get_prompt_calls_close(mock_get_client: MagicMock) -> None:
    """Test that client.close() is always called."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt = MagicMock()
    mock_prompt.name = "test-prompt"
    mock_prompt.version = 1
    mock_prompt.type = "text"
    mock_prompt.labels = []
    mock_prompt.config = {}
    mock_prompt.prompt = "Text"
    mock_client.get_prompt.return_value = mock_prompt

    runner.invoke(app, ["prompts", "get", "test-prompt"])

    mock_client.close.assert_called_once()


# compile command tests


@patch("langfuse_cli.commands.prompts._get_client")
def test_compile_prompt_basic(mock_get_client: MagicMock) -> None:
    """Test compiling a prompt with basic variable."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    compiled_result = {"prompt": "Hello, World!"}
    mock_client.compile_prompt.return_value = compiled_result

    result = runner.invoke(app, ["prompts", "compile", "test-prompt", "--var", "name=World"])

    assert result.exit_code == 0
    mock_client.compile_prompt.assert_called_once_with("test-prompt", {"name": "World"})
    mock_output.render_json.assert_called_once_with(compiled_result)
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_compile_prompt_multiple_vars(mock_get_client: MagicMock) -> None:
    """Test compiling a prompt with multiple variables."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    compiled_result = {"prompt": "Hello, Alice! You are 30 years old."}
    mock_client.compile_prompt.return_value = compiled_result

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


@patch("langfuse_cli.commands.prompts._get_client")
def test_compile_prompt_with_version(mock_get_client: MagicMock) -> None:
    """Test compiling a prompt with specific version."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    compiled_result = {"prompt": "Version 2 compiled"}
    mock_client.compile_prompt.return_value = compiled_result

    result = runner.invoke(
        app,
        ["prompts", "compile", "test-prompt", "--var", "x=y", "--version", "2"],
    )

    assert result.exit_code == 0
    mock_client.compile_prompt.assert_called_once_with("test-prompt", {"x": "y"}, version=2)
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_compile_prompt_with_label(mock_get_client: MagicMock) -> None:
    """Test compiling a prompt with specific label."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    compiled_result = {"prompt": "Production compiled"}
    mock_client.compile_prompt.return_value = compiled_result

    result = runner.invoke(
        app,
        ["prompts", "compile", "test-prompt", "--var", "x=y", "--label", "production"],
    )

    assert result.exit_code == 0
    mock_client.compile_prompt.assert_called_once_with("test-prompt", {"x": "y"}, label="production")
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_compile_prompt_invalid_var(mock_get_client: MagicMock) -> None:
    """Test compiling a prompt with invalid variable format."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    result = runner.invoke(app, ["prompts", "compile", "test-prompt", "--var", "invalidformat"])

    assert result.exit_code == 1
    mock_output.error.assert_called_once()
    assert "invalid variable format" in mock_output.error.call_args[0][0]
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_compile_prompt_api_error(mock_get_client: MagicMock) -> None:
    """Test compile prompt with API error."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_client.compile_prompt.side_effect = LangfuseAPIError("Compilation failed", exit_code=ERROR)

    result = runner.invoke(app, ["prompts", "compile", "test-prompt", "--var", "x=y"])

    assert result.exit_code == ERROR
    mock_output.error.assert_called_once()
    assert "error:" in mock_output.error.call_args[0][0]
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_compile_prompt_calls_close(mock_get_client: MagicMock) -> None:
    """Test that client.close() is always called."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_client.compile_prompt.return_value = {"prompt": "Result"}

    runner.invoke(app, ["prompts", "compile", "test-prompt", "--var", "x=y"])

    mock_client.close.assert_called_once()


# diff command tests


@patch("langfuse_cli.commands.prompts._get_client")
def test_diff_prompts_json_mode(mock_get_client: MagicMock) -> None:
    """Test diffing prompts in JSON mode."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_output.is_json_mode = True
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt1 = MagicMock()
    mock_prompt1.prompt = "Version 1 text"
    delattr(mock_prompt1, "messages")

    mock_prompt2 = MagicMock()
    mock_prompt2.prompt = "Version 2 text"
    delattr(mock_prompt2, "messages")

    mock_client.get_prompt.side_effect = [mock_prompt1, mock_prompt2]

    result = runner.invoke(app, ["prompts", "diff", "test-prompt", "--v1", "1", "--v2", "2"])

    assert result.exit_code == 0
    assert mock_client.get_prompt.call_count == 2
    mock_output.render_json.assert_called_once()
    json_data = mock_output.render_json.call_args[0][0]
    assert json_data["name"] == "test-prompt"
    assert json_data["v1"]["version"] == 1
    assert json_data["v1"]["content"] == "Version 1 text"
    assert json_data["v2"]["version"] == 2
    assert json_data["v2"]["content"] == "Version 2 text"
    mock_client.close.assert_called_once()


@patch("langfuse_cli.formatters.diff.render_diff")
@patch("langfuse_cli.commands.prompts._get_client")
def test_diff_prompts_text_mode(mock_get_client: MagicMock, mock_render_diff: MagicMock) -> None:
    """Test diffing prompts in text mode."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_output.is_json_mode = False
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt1 = MagicMock()
    mock_prompt1.prompt = "Original text"
    delattr(mock_prompt1, "messages")

    mock_prompt2 = MagicMock()
    mock_prompt2.prompt = "Modified text"
    delattr(mock_prompt2, "messages")

    mock_client.get_prompt.side_effect = [mock_prompt1, mock_prompt2]

    result = runner.invoke(app, ["prompts", "diff", "test-prompt", "--v1", "3", "--v2", "4"])

    assert result.exit_code == 0
    mock_render_diff.assert_called_once_with(
        "Original text",
        "Modified text",
        labels=("v3", "v4"),
    )
    mock_client.close.assert_called_once()


@patch("langfuse_cli.formatters.diff.render_diff")
@patch("langfuse_cli.commands.prompts._get_client")
def test_diff_prompts_messages_type(mock_get_client: MagicMock, mock_render_diff: MagicMock) -> None:
    """Test diffing prompts with messages (chat type)."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_output.is_json_mode = False
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt1 = MagicMock()
    mock_prompt1.messages = [{"role": "user", "content": "Hello"}]
    delattr(mock_prompt1, "prompt")

    mock_prompt2 = MagicMock()
    mock_prompt2.messages = [{"role": "user", "content": "Hi there"}]
    delattr(mock_prompt2, "prompt")

    mock_client.get_prompt.side_effect = [mock_prompt1, mock_prompt2]

    result = runner.invoke(app, ["prompts", "diff", "chat-prompt", "--v1", "1", "--v2", "2"])

    assert result.exit_code == 0
    # Should fall back to str(messages)
    call_args = mock_render_diff.call_args
    assert "[{'role': 'user', 'content': 'Hello'}]" in call_args[0][0]
    assert "[{'role': 'user', 'content': 'Hi there'}]" in call_args[0][1]
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_diff_prompts_api_error(mock_get_client: MagicMock) -> None:
    """Test diff prompts with API error."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_get_client.return_value = (mock_client, mock_output)

    mock_client.get_prompt.side_effect = LangfuseAPIError("Version not found", exit_code=NOT_FOUND)

    result = runner.invoke(app, ["prompts", "diff", "test-prompt", "--v1", "1", "--v2", "999"])

    assert result.exit_code == NOT_FOUND
    mock_output.error.assert_called_once()
    assert "error:" in mock_output.error.call_args[0][0]
    mock_client.close.assert_called_once()


@patch("langfuse_cli.commands.prompts._get_client")
def test_diff_prompts_calls_close(mock_get_client: MagicMock) -> None:
    """Test that client.close() is always called."""
    mock_client = MagicMock()
    mock_output = MagicMock()
    mock_output.is_json_mode = True
    mock_get_client.return_value = (mock_client, mock_output)

    mock_prompt1 = MagicMock()
    mock_prompt1.prompt = "Text 1"
    delattr(mock_prompt1, "messages")

    mock_prompt2 = MagicMock()
    mock_prompt2.prompt = "Text 2"
    delattr(mock_prompt2, "messages")

    mock_client.get_prompt.side_effect = [mock_prompt1, mock_prompt2]

    runner.invoke(app, ["prompts", "diff", "test-prompt", "--v1", "1", "--v2", "2"])

    mock_client.close.assert_called_once()
