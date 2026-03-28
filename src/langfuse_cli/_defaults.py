"""Default values for CLI options and API parameters."""

from __future__ import annotations

# User-facing defaults (exposed as CLI option defaults)
DEFAULT_LIMIT = 50  # list commands: traces, observations, sessions, scores, datasets
DEFAULT_HISTORY_LIMIT = 20  # prompts history: number of versions to show

# Internal fetch limits (not user-configurable, used by aggregation/rendering)
SUMMARY_FETCH_LIMIT = 500  # scores summary: fetch enough data for meaningful statistics
TREE_OBSERVATION_LIMIT = 200  # trace tree: fetch enough spans to render the full tree
