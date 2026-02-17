"""Tests for the LangfuseClient hybrid client."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from langfuse_cli._exit_codes import ERROR, NOT_FOUND
from langfuse_cli.client import LangfuseAPIError, LangfuseClient, _clean_params, _iso_with_tz, _prompt_to_dict
from langfuse_cli.config import LangfuseConfig


@pytest.fixture
def test_config() -> LangfuseConfig:
    """Create a test configuration."""
    return LangfuseConfig(
        host="https://test.langfuse.com",
        public_key="pk-test",
        secret_key="sk-test",
    )


@pytest.fixture
def client(test_config: LangfuseConfig) -> LangfuseClient:
    """Create a test client."""
    return LangfuseClient(test_config)


class TestLangfuseClient:
    """Test LangfuseClient initialization and basic functionality."""

    def test_init_creates_httpx_client(self, test_config: LangfuseConfig) -> None:
        """Test that __init__ creates httpx client with correct base_url and auth."""
        client = LangfuseClient(test_config)
        assert str(client._http.base_url) == "https://test.langfuse.com/api/public/"
        # Auth is a BasicAuth object, check the credentials
        assert isinstance(client._http.auth, httpx.BasicAuth)
        # Access internal _auth_header to verify credentials
        auth_header = client._http.auth._auth_header
        # BasicAuth creates header in format "Basic <base64(username:password)>"
        import base64

        expected = f"Basic {base64.b64encode(b'pk-test:sk-test').decode()}"
        assert auth_header == expected
        assert client._http.timeout == httpx.Timeout(60.0)
        from langfuse_cli import __version__

        assert client._http.headers["User-Agent"] == f"langfuse-cli/{__version__}"

    def test_close_closes_httpx_client(self, client: LangfuseClient) -> None:
        """Test that close() closes the httpx client."""
        client.close()
        assert client._http.is_closed

    def test_close_flushes_sdk_if_initialized(self, client: LangfuseClient) -> None:
        """Test that close() flushes SDK if it was initialized."""
        from unittest.mock import MagicMock

        mock_sdk = MagicMock()
        client._sdk = mock_sdk
        client.close()
        mock_sdk.flush.assert_called_once()


class TestGetMethod:
    """Test the _get() method."""

    @respx.mock
    def test_get_success(self, client: LangfuseClient) -> None:
        """Test that _get() makes GET requests and returns JSON."""
        mock_route = respx.get("https://test.langfuse.com/api/public/traces/trace-1").mock(
            return_value=httpx.Response(
                200,
                json={"id": "trace-1", "name": "test-trace"},
            )
        )

        result = client._get("/traces/trace-1")

        assert result == {"id": "trace-1", "name": "test-trace"}
        assert mock_route.called

    @respx.mock
    def test_get_with_params(self, client: LangfuseClient) -> None:
        """Test that _get() passes query parameters correctly."""
        mock_route = respx.get("https://test.langfuse.com/api/public/traces").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        client._get("/traces", params={"userId": "user-123", "limit": 10})

        assert mock_route.called
        request = mock_route.calls.last.request
        assert "userId=user-123" in str(request.url)
        assert "limit=10" in str(request.url)

    @respx.mock
    def test_get_404_raises_not_found_error(self, client: LangfuseClient) -> None:
        """Test that _get() raises LangfuseAPIError with exit_code=NOT_FOUND for 404 responses."""
        respx.get("https://test.langfuse.com/api/public/traces/missing").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        with pytest.raises(LangfuseAPIError) as exc_info:
            client._get("/traces/missing")

        assert exc_info.value.status_code == 404
        assert exc_info.value.exit_code == NOT_FOUND
        assert "Resource not found" in str(exc_info.value)

    @respx.mock
    def test_get_other_http_error_raises_api_error(self, client: LangfuseClient) -> None:
        """Test that _get() raises LangfuseAPIError with exit_code=ERROR for other HTTP errors."""
        respx.get("https://test.langfuse.com/api/public/traces").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(LangfuseAPIError) as exc_info:
            client._get("/traces")

        assert exc_info.value.status_code == 500
        assert exc_info.value.exit_code == ERROR
        assert "API error 500" in str(exc_info.value)

    @respx.mock
    def test_get_connection_error_raises_api_error(self, client: LangfuseClient) -> None:
        """Test that _get() raises LangfuseAPIError for connection errors."""
        respx.get("https://test.langfuse.com/api/public/traces").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with pytest.raises(LangfuseAPIError) as exc_info:
            client._get("/traces")

        assert exc_info.value.exit_code == ERROR
        assert "Connection error" in str(exc_info.value)


class TestPaginateMethod:
    """Test the _paginate() method."""

    @respx.mock
    def test_paginate_yields_items_across_pages(self, client: LangfuseClient) -> None:
        """Test that _paginate() yields items across multiple pages."""
        # Use side_effect to return different responses for consecutive calls
        respx.get("https://test.langfuse.com/api/public/traces").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "data": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
                        "meta": {"totalItems": 5},
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "data": [{"id": "4"}, {"id": "5"}],
                        "meta": {"totalItems": 5},
                    },
                ),
            ]
        )

        items = list(client._paginate("/traces", {}, limit=5))

        assert len(items) == 5
        assert [item["id"] for item in items] == ["1", "2", "3", "4", "5"]

    @respx.mock
    def test_paginate_stops_when_no_more_items(self, client: LangfuseClient) -> None:
        """Test that _paginate() stops when no more items."""
        # Page 1: 2 items
        respx.get("https://test.langfuse.com/api/public/traces", params={"page": 1, "limit": 50}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}, {"id": "2"}],
                    "meta": {"totalItems": 2},
                },
            )
        )

        items = list(client._paginate("/traces", {}, limit=100))

        assert len(items) == 2
        assert [item["id"] for item in items] == ["1", "2"]

    @respx.mock
    def test_paginate_respects_limit(self, client: LangfuseClient) -> None:
        """Test that _paginate() respects the limit parameter."""
        # Page 1: 50 items (full page)
        page1_data = [{"id": str(i)} for i in range(50)]
        # Page 2: Only 5 more items to reach limit of 55
        page2_data = [{"id": str(i)} for i in range(50, 55)]

        respx.get("https://test.langfuse.com/api/public/traces").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "data": page1_data,
                        "meta": {"totalItems": 200},
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "data": page2_data,
                        "meta": {"totalItems": 200},
                    },
                ),
            ]
        )

        items = list(client._paginate("/traces", {}, limit=55))

        assert len(items) == 55

    @respx.mock
    def test_paginate_handles_empty_first_page(self, client: LangfuseClient) -> None:
        """Test that _paginate() handles empty first page gracefully."""
        respx.get("https://test.langfuse.com/api/public/traces").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "meta": {"totalItems": 0}},
            )
        )

        items = list(client._paginate("/traces", {}, limit=10))

        assert items == []


class TestTracesMethods:
    """Test trace-related methods."""

    @respx.mock
    def test_list_traces_no_filters(self, client: LangfuseClient) -> None:
        """Test list_traces() with no filters."""
        respx.get("https://test.langfuse.com/api/public/traces").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}, {"id": "2"}],
                    "meta": {"totalItems": 2},
                },
            )
        )

        traces = client.list_traces(limit=50)

        assert len(traces) == 2

    @respx.mock
    def test_list_traces_with_filters(self, client: LangfuseClient) -> None:
        """Test list_traces() passes correct filter params to the API."""
        mock_route = respx.get("https://test.langfuse.com/api/public/traces").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "meta": {"totalItems": 0}},
            )
        )

        from_ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        to_ts = datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc)

        client.list_traces(
            limit=10,
            user_id="user-123",
            session_id="session-456",
            tags=["production", "urgent"],
            from_timestamp=from_ts,
            to_timestamp=to_ts,
            name="chat-completion",
        )

        assert mock_route.called
        request = mock_route.calls.last.request
        url_str = str(request.url)
        assert "userId=user-123" in url_str
        assert "sessionId=session-456" in url_str
        assert "name=chat-completion" in url_str
        assert "fromTimestamp=2024-01-01T00%3A00%3A00%2B00%3A00" in url_str
        assert "toTimestamp=2024-01-31T23%3A59%3A59%2B00%3A00" in url_str

    @respx.mock
    def test_get_trace(self, client: LangfuseClient) -> None:
        """Test get_trace() calls correct endpoint."""
        mock_route = respx.get("https://test.langfuse.com/api/public/traces/trace-123").mock(
            return_value=httpx.Response(
                200,
                json={"id": "trace-123", "name": "test"},
            )
        )

        trace = client.get_trace("trace-123")

        assert trace["id"] == "trace-123"
        assert mock_route.called


class TestScoresMethods:
    """Test score-related methods."""

    @respx.mock
    def test_list_scores_passes_filters(self, client: LangfuseClient) -> None:
        """Test list_scores() passes correct filter params."""
        mock_route = respx.get("https://test.langfuse.com/api/public/scores").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "meta": {"totalItems": 0}},
            )
        )

        from_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)

        client.list_scores(
            limit=20,
            trace_id="trace-123",
            name="accuracy",
            from_timestamp=from_ts,
        )

        assert mock_route.called
        request = mock_route.calls.last.request
        url_str = str(request.url)
        assert "traceId=trace-123" in url_str
        assert "name=accuracy" in url_str
        assert "fromTimestamp=2024-01-01T00%3A00%3A00%2B00%3A00" in url_str


class TestSessionsMethods:
    """Test session-related methods."""

    @respx.mock
    def test_list_sessions_passes_filters(self, client: LangfuseClient) -> None:
        """Test list_sessions() passes correct filter params."""
        mock_route = respx.get("https://test.langfuse.com/api/public/sessions").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "meta": {"totalItems": 0}},
            )
        )

        from_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        to_ts = datetime(2024, 1, 31, tzinfo=timezone.utc)

        client.list_sessions(
            limit=15,
            from_timestamp=from_ts,
            to_timestamp=to_ts,
        )

        assert mock_route.called
        request = mock_route.calls.last.request
        url_str = str(request.url)
        assert "fromTimestamp=2024-01-01T00%3A00%3A00%2B00%3A00" in url_str
        assert "toTimestamp=2024-01-31T00%3A00%3A00%2B00%3A00" in url_str

    @respx.mock
    def test_get_session(self, client: LangfuseClient) -> None:
        """Test get_session() calls correct endpoint."""
        mock_route = respx.get("https://test.langfuse.com/api/public/sessions/session-123").mock(
            return_value=httpx.Response(
                200,
                json={"id": "session-123"},
            )
        )

        session = client.get_session("session-123")

        assert session["id"] == "session-123"
        assert mock_route.called


class TestObservationsMethods:
    """Test observation-related methods."""

    @respx.mock
    def test_list_observations_passes_filters(self, client: LangfuseClient) -> None:
        """Test list_observations() passes correct filter params."""
        mock_route = respx.get("https://test.langfuse.com/api/public/observations").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "meta": {"totalItems": 0}},
            )
        )

        client.list_observations(
            limit=30,
            trace_id="trace-123",
            observation_type="GENERATION",
            name="llm-call",
        )

        assert mock_route.called
        request = mock_route.calls.last.request
        url_str = str(request.url)
        assert "traceId=trace-123" in url_str
        assert "type=GENERATION" in url_str
        assert "name=llm-call" in url_str


class TestDatasetMethods:
    """Test dataset-related methods."""

    @respx.mock
    def test_list_datasets(self, client: LangfuseClient) -> None:
        """Test list_datasets() calls correct endpoint."""
        mock_route = respx.get("https://test.langfuse.com/api/public/v2/datasets").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "1"}], "meta": {}},
            )
        )

        datasets = client.list_datasets(limit=50)

        assert len(datasets) == 1
        assert mock_route.called

    @respx.mock
    def test_get_dataset(self, client: LangfuseClient) -> None:
        """Test get_dataset() calls correct endpoint."""
        mock_route = respx.get("https://test.langfuse.com/api/public/v2/datasets/my-dataset").mock(
            return_value=httpx.Response(
                200,
                json={"name": "my-dataset"},
            )
        )

        dataset = client.get_dataset("my-dataset")

        assert dataset["name"] == "my-dataset"
        assert mock_route.called

    @respx.mock
    def test_list_dataset_items(self, client: LangfuseClient) -> None:
        """Test list_dataset_items() passes dataset name."""
        mock_route = respx.get("https://test.langfuse.com/api/public/dataset-items").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "meta": {"totalItems": 0}},
            )
        )

        client.list_dataset_items("my-dataset", limit=100)

        assert mock_route.called
        request = mock_route.calls.last.request
        assert "datasetName=my-dataset" in str(request.url)


class TestUtilityFunctions:
    """Test utility functions."""

    def test_clean_params_removes_none_values(self) -> None:
        """Test _clean_params removes None values."""
        params = {
            "userId": "user-123",
            "sessionId": None,
            "limit": 10,
            "name": None,
        }
        cleaned = _clean_params(params)
        assert cleaned == {"userId": "user-123", "limit": 10}

    def test_clean_params_handles_none_input(self) -> None:
        """Test _clean_params handles None input."""
        assert _clean_params(None) == {}

    def test_clean_params_handles_empty_dict(self) -> None:
        """Test _clean_params handles empty dict."""
        assert _clean_params({}) == {}

    def test_prompt_to_dict_extracts_attributes(self) -> None:
        """Test _prompt_to_dict extracts prompt attributes."""

        class MockPrompt:
            name = "test-prompt"
            version = 1
            labels: ClassVar[list[str]] = ["production"]
            tags: ClassVar[list[str]] = ["verified"]
            type = "chat"

        prompt = MockPrompt()
        result = _prompt_to_dict(prompt)

        assert result == {
            "name": "test-prompt",
            "version": 1,
            "labels": ["production"],
            "tags": ["verified"],
            "type": "chat",
        }

    def test_prompt_to_dict_uses_dict_method_fallback(self) -> None:
        """Test _prompt_to_dict uses dict() method as fallback."""

        class MockPrompt:
            def dict(self) -> dict[str, Any]:
                return {"name": "test", "version": 2}

        prompt = MockPrompt()
        result = _prompt_to_dict(prompt)

        assert result == {"name": "test", "version": 2}

    def test_prompt_to_dict_handles_unknown_object(self) -> None:
        """Test _prompt_to_dict handles unknown object types."""

        class UnknownPrompt:
            pass

        prompt = UnknownPrompt()
        result = _prompt_to_dict(prompt)

        assert "raw" in result
        assert isinstance(result["raw"], str)


class TestIsoWithTz:
    """Test _iso_with_tz() utility function."""

    def test_naive_datetime_gets_utc(self) -> None:
        """Test that naive datetimes get UTC timezone added."""
        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = _iso_with_tz(dt)
        assert "+00:00" in result
        assert result == "2026-01-15T10:30:00+00:00"

    def test_aware_datetime_preserved(self) -> None:
        """Test that timezone-aware datetimes keep their timezone."""
        dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _iso_with_tz(dt)
        assert result == "2026-01-15T10:30:00+00:00"


class TestSDKProperty:
    """Test the SDK lazy initialization property."""

    def test_sdk_lazy_init_caches(self, test_config: LangfuseConfig) -> None:
        """Test that SDK is initialized once and cached."""
        client = LangfuseClient(test_config)
        mock_langfuse = MagicMock()

        with patch("langfuse.Langfuse", return_value=mock_langfuse) as mock_cls:
            sdk1 = client.sdk
            sdk2 = client.sdk

        assert sdk1 is sdk2
        mock_cls.assert_called_once_with(
            public_key="pk-test",
            secret_key="sk-test",
            host="https://test.langfuse.com",
        )

    def test_sdk_passes_config(self, test_config: LangfuseConfig) -> None:
        """Test that SDK receives correct configuration."""
        client = LangfuseClient(test_config)

        with patch("langfuse.Langfuse") as mock_cls:
            _ = client.sdk

        mock_cls.assert_called_once_with(
            public_key="pk-test",
            secret_key="sk-test",
            host="https://test.langfuse.com",
        )


class TestListPrompts:
    """Test list_prompts() SDK method."""

    def test_list_prompts_calls_sdk(self, client: LangfuseClient) -> None:
        """Test that list_prompts() calls SDK and converts results."""
        mock_prompt = MagicMock()
        mock_prompt.name = "test-prompt"
        mock_prompt.version = 1
        mock_prompt.labels = ["production"]
        mock_prompt.tags = ["verified"]
        mock_prompt.type = "text"

        mock_sdk = MagicMock()
        mock_sdk.api.prompts.list.return_value.data = [mock_prompt]
        client._sdk = mock_sdk

        result = client.list_prompts()

        assert len(result) == 1
        assert result[0]["name"] == "test-prompt"
        assert result[0]["version"] == 1
        mock_sdk.api.prompts.list.assert_called_once()

    def test_list_prompts_empty(self, client: LangfuseClient) -> None:
        """Test that list_prompts() handles empty results."""
        mock_sdk = MagicMock()
        mock_sdk.api.prompts.list.return_value.data = []
        client._sdk = mock_sdk

        result = client.list_prompts()

        assert result == []


class TestGetPrompt:
    """Test get_prompt() SDK method."""

    def test_get_prompt_name_only(self, client: LangfuseClient) -> None:
        """Test get_prompt() with just a name."""
        mock_sdk = MagicMock()
        client._sdk = mock_sdk

        client.get_prompt("my-prompt")

        mock_sdk.get_prompt.assert_called_once_with("my-prompt")

    def test_get_prompt_with_version(self, client: LangfuseClient) -> None:
        """Test get_prompt() passes version kwarg."""
        mock_sdk = MagicMock()
        client._sdk = mock_sdk

        client.get_prompt("my-prompt", version=3)

        mock_sdk.get_prompt.assert_called_once_with("my-prompt", version=3)

    def test_get_prompt_with_label(self, client: LangfuseClient) -> None:
        """Test get_prompt() passes label kwarg."""
        mock_sdk = MagicMock()
        client._sdk = mock_sdk

        client.get_prompt("my-prompt", label="production")

        mock_sdk.get_prompt.assert_called_once_with("my-prompt", label="production")


class TestCompilePrompt:
    """Test compile_prompt() SDK method."""

    def test_compile_prompt(self, client: LangfuseClient) -> None:
        """Test that compile_prompt() gets prompt and compiles with variables."""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "Hello Alice!"

        mock_sdk = MagicMock()
        mock_sdk.get_prompt.return_value = mock_prompt
        client._sdk = mock_sdk

        result = client.compile_prompt("greeting", {"name": "Alice"})

        assert result == "Hello Alice!"
        mock_sdk.get_prompt.assert_called_once_with("greeting")
        mock_prompt.compile.assert_called_once_with(name="Alice")


class TestDatasetRunMethods:
    """Test dataset run REST methods."""

    @respx.mock
    def test_list_dataset_runs(self, client: LangfuseClient) -> None:
        """Test list_dataset_runs() returns run list."""
        mock_route = respx.get("https://test.langfuse.com/api/public/datasets/my-dataset/runs").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"name": "run-1"}, {"name": "run-2"}]},
            )
        )

        runs = client.list_dataset_runs("my-dataset")

        assert len(runs) == 2
        assert runs[0]["name"] == "run-1"
        assert mock_route.called

    @respx.mock
    def test_list_dataset_runs_empty(self, client: LangfuseClient) -> None:
        """Test list_dataset_runs() handles empty results."""
        respx.get("https://test.langfuse.com/api/public/datasets/empty-dataset/runs").mock(
            return_value=httpx.Response(
                200,
                json={"data": []},
            )
        )

        runs = client.list_dataset_runs("empty-dataset")

        assert runs == []

    @respx.mock
    def test_get_dataset_run(self, client: LangfuseClient) -> None:
        """Test get_dataset_run() returns run data."""
        mock_route = respx.get(
            "https://test.langfuse.com/api/public/datasets/my-dataset/runs/run-1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"name": "run-1", "description": "baseline"},
            )
        )

        run = client.get_dataset_run("my-dataset", "run-1")

        assert run["name"] == "run-1"
        assert run["description"] == "baseline"
        assert mock_route.called

    @respx.mock
    def test_get_dataset_run_404(self, client: LangfuseClient) -> None:
        """Test get_dataset_run() raises on 404."""
        respx.get(
            "https://test.langfuse.com/api/public/datasets/my-dataset/runs/missing"
        ).mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        with pytest.raises(LangfuseAPIError) as exc_info:
            client.get_dataset_run("my-dataset", "missing")

        assert exc_info.value.status_code == 404
        assert exc_info.value.exit_code == NOT_FOUND


class TestPaginateMidPageBreak:
    """Test pagination edge case: limit breaks mid-page."""

    @respx.mock
    def test_paginate_breaks_mid_page(self, client: LangfuseClient) -> None:
        """Test that _paginate() stops at limit even mid-page."""
        page_data = [{"id": str(i)} for i in range(50)]

        respx.get("https://test.langfuse.com/api/public/traces").mock(
            return_value=httpx.Response(
                200,
                json={"data": page_data, "meta": {"totalItems": 200}},
            )
        )

        items = list(client._paginate("/traces", {}, limit=3))

        assert len(items) == 3
        assert [item["id"] for item in items] == ["0", "1", "2"]


class TestScoresTimestampFilter:
    """Test scores to_timestamp filter specifically."""

    @respx.mock
    def test_list_scores_with_to_timestamp(self, client: LangfuseClient) -> None:
        """Test list_scores() passes to_timestamp filter."""
        mock_route = respx.get("https://test.langfuse.com/api/public/scores").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "meta": {"totalItems": 0}},
            )
        )

        to_ts = datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        client.list_scores(limit=10, to_timestamp=to_ts)

        assert mock_route.called
        request = mock_route.calls.last.request
        url_str = str(request.url)
        assert "toTimestamp=2024-01-31T23%3A59%3A59%2B00%3A00" in url_str
