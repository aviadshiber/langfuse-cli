"""Hybrid Langfuse client facade: SDK for prompts/datasets, httpx for traces/scores/sessions."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import httpx

from langfuse_cli import __version__
from langfuse_cli._exit_codes import ERROR, HTTP_NOT_FOUND, NOT_FOUND
from langfuse_cli.config import LangfuseConfig

logger = logging.getLogger(__name__)


class LangfuseAPIError(Exception):
    """Raised when a Langfuse API call fails."""

    def __init__(self, message: str, status_code: int = 0, exit_code: int = ERROR) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.exit_code = exit_code


class LangfuseClient:
    """Facade wrapping both Langfuse SDK and direct REST calls.

    - REST (httpx): traces, observations, scores, sessions — full filter control
    - SDK: prompts (caching), datasets, experiments — complex operations
    """

    def __init__(self, config: LangfuseConfig) -> None:
        self._config = config
        self._http = httpx.Client(
            base_url=f"{config.host}/api/public",
            auth=(config.public_key, config.secret_key),
            timeout=60.0,
            headers={"User-Agent": f"langfuse-cli/{__version__}"},
        )
        self._sdk: Any = None  # Lazy-init Langfuse SDK

    @property
    def sdk(self) -> Any:
        """Lazily initialize the Langfuse SDK."""
        if self._sdk is None:
            try:
                from langfuse import Langfuse

                self._sdk = Langfuse(
                    public_key=self._config.public_key,
                    secret_key=self._config.secret_key,
                    host=self._config.host,
                )
            except ImportError:
                raise LangfuseAPIError(
                    "Langfuse SDK not installed. Install with: pip install langfuse",
                    exit_code=ERROR,
                ) from None
            except Exception as e:
                raise LangfuseAPIError(
                    f"Failed to initialize Langfuse SDK: {e}",
                    exit_code=ERROR,
                ) from e
        return self._sdk

    def close(self) -> None:
        """Close HTTP client and flush SDK."""
        self._http.close()
        if self._sdk is not None:
            self._sdk.flush()

    # ── REST helpers ──────────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to the Langfuse API."""
        try:
            resp = self._http.get(path, params=_clean_params(params))
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTP_NOT_FOUND:
                raise LangfuseAPIError(
                    f"Resource not found: {path}",
                    status_code=404,
                    exit_code=NOT_FOUND,
                ) from e
            raise LangfuseAPIError(
                f"API error {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise LangfuseAPIError(f"Connection error: {e}") from e

    def _paginate(self, path: str, params: dict[str, Any], limit: int) -> Iterator[dict[str, Any]]:
        """Paginate through results, yielding individual items."""
        page = 1
        yielded = 0
        while yielded < limit:
            page_params = {**params, "page": page, "limit": min(limit - yielded, 50)}
            data = self._get(path, page_params)
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                if yielded >= limit:
                    break
                yield item
                yielded += 1
            # Check if there are more pages
            meta = data.get("meta", {})
            total = meta.get("totalItems", 0)
            if yielded >= total:
                break
            page += 1

    # ── Traces (REST) ─────────────────────────────────────────────────────

    def list_traces(
        self,
        *,
        limit: int = 50,
        user_id: str | None = None,
        session_id: str | None = None,
        tags: list[str] | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        """List traces with optional filters."""
        params: dict[str, Any] = {}
        if user_id:
            params["userId"] = user_id
        if session_id:
            params["sessionId"] = session_id
        if tags:
            params["tags"] = tags
        if from_timestamp:
            params["fromTimestamp"] = _iso_with_tz(from_timestamp)
        if to_timestamp:
            params["toTimestamp"] = _iso_with_tz(to_timestamp)
        if name:
            params["name"] = name
        return list(self._paginate("/traces", params, limit))

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        """Get a single trace by ID."""
        return self._get(f"/traces/{trace_id}")

    # ── Observations (REST) ───────────────────────────────────────────────

    def list_observations(
        self,
        *,
        limit: int = 50,
        trace_id: str | None = None,
        observation_type: str | None = None,
        name: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """List observations with optional filters."""
        params: dict[str, Any] = {}
        if trace_id:
            params["traceId"] = trace_id
        if observation_type:
            params["type"] = observation_type
        if name:
            params["name"] = name
        if from_timestamp:
            params["fromTimestamp"] = _iso_with_tz(from_timestamp)
        if to_timestamp:
            params["toTimestamp"] = _iso_with_tz(to_timestamp)
        return list(self._paginate("/observations", params, limit))

    # ── Sessions (REST) ───────────────────────────────────────────────────

    def list_sessions(
        self,
        *,
        limit: int = 50,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """List sessions with optional filters."""
        params: dict[str, Any] = {}
        if from_timestamp:
            params["fromTimestamp"] = _iso_with_tz(from_timestamp)
        if to_timestamp:
            params["toTimestamp"] = _iso_with_tz(to_timestamp)
        return list(self._paginate("/sessions", params, limit))

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Get a single session by ID."""
        return self._get(f"/sessions/{session_id}")

    # ── Scores (REST) ─────────────────────────────────────────────────────

    def list_scores(
        self,
        *,
        limit: int = 50,
        trace_id: str | None = None,
        name: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """List scores with optional filters."""
        params: dict[str, Any] = {}
        if trace_id:
            params["traceId"] = trace_id
        if name:
            params["name"] = name
        if from_timestamp:
            params["fromTimestamp"] = _iso_with_tz(from_timestamp)
        if to_timestamp:
            params["toTimestamp"] = _iso_with_tz(to_timestamp)
        return list(self._paginate("/scores", params, limit))

    # ── Prompts (SDK) ─────────────────────────────────────────────────────

    def list_prompts(self) -> list[dict[str, Any]]:
        """List all prompts via SDK."""
        result = self.sdk.api.prompts.list()
        return [_prompt_to_dict(p) for p in result.data]

    def get_prompt(
        self,
        name: str,
        *,
        version: int | None = None,
        label: str | None = None,
    ) -> Any:
        """Get a specific prompt (benefits from SDK caching)."""
        kwargs: dict[str, Any] = {}
        if version is not None:
            kwargs["version"] = version
        if label is not None:
            kwargs["label"] = label
        return self.sdk.get_prompt(name, **kwargs)

    def compile_prompt(self, name: str, variables: dict[str, str], **kwargs: Any) -> Any:
        """Get and compile a prompt with variables."""
        prompt = self.get_prompt(name, **kwargs)
        return prompt.compile(**variables)

    # ── Datasets (SDK) ────────────────────────────────────────────────────

    def list_datasets(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """List datasets."""
        data = self._get("/v2/datasets", {"limit": limit})
        result: list[dict[str, Any]] = data.get("data", [])
        return result

    def get_dataset(self, name: str) -> dict[str, Any]:
        """Get a dataset by name."""
        return self._get(f"/v2/datasets/{name}")

    def list_dataset_items(self, dataset_name: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """List items in a dataset."""
        return list(self._paginate("/dataset-items", {"datasetName": dataset_name}, limit))

    def list_dataset_runs(self, dataset_name: str) -> list[dict[str, Any]]:
        """List runs for a dataset."""
        data = self._get(f"/datasets/{dataset_name}/runs")
        result: list[dict[str, Any]] = data.get("data", [])
        return result

    def get_dataset_run(self, dataset_name: str, run_name: str) -> dict[str, Any]:
        """Get a specific dataset run."""
        return self._get(f"/datasets/{dataset_name}/runs/{run_name}")


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Remove None values from params dict."""
    if params is None:
        return {}
    return {k: v for k, v in params.items() if v is not None}


def _iso_with_tz(dt: datetime) -> str:
    """Format datetime as ISO 8601 with timezone (Langfuse API requires it)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _prompt_to_dict(prompt: Any) -> dict[str, Any]:
    """Convert SDK prompt object to dict."""
    try:
        return {
            "name": prompt.name,
            "version": prompt.version,
            "labels": getattr(prompt, "labels", []),
            "tags": getattr(prompt, "tags", []),
            "type": getattr(prompt, "type", "text"),
        }
    except AttributeError:
        if hasattr(prompt, "dict"):
            result: dict[str, Any] = prompt.dict()
            return result
        return {"raw": str(prompt)}
