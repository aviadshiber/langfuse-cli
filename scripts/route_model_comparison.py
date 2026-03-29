#!/usr/bin/env python3
"""
ROUTE Model Comparison: Gemini-3-Flash vs GPT-4.1
==================================================

Self-contained analysis script that compares two LLM models used for the ROUTE
generation step in the DeeperDive pipeline. Collects data via the `lf` CLI,
runs statistical tests, and outputs a formatted report.

Usage:
    python3 route_model_comparison.py

Requirements:
    - `lf` CLI installed and configured (langfuse-cli)
    - `jq` installed (used by lf --jq)
    - Python 3.10+ with scipy installed:
        pip install scipy   (or: uv pip install scipy)

Configuration:
    Adjust the constants in the CONFIG section below to match your environment.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ============================================================================
# CONFIG - Adjust these to match your environment
# ============================================================================

# Trace names as they appear in Langfuse (one per model variant)
GEMINI_TRACE_NAME = "deeperdive-gemeni-3-flash"
GPT4_TRACE_NAME = "deeperdive-gpt-4.1-2025-04-14"

# Date range for today's data (ISO 8601)
DATE_FROM = "2026-02-16T00:00:00Z"
DATE_TO = "2026-02-17T00:00:00Z"

# The observation name for the ROUTE generation step within each trace
ROUTE_OBSERVATION_NAME = "ROUTE"

# How many traces to fetch per model (fetch more than needed, then equalize)
MAX_TRACES_PER_MODEL = 100

# Maximum parallel workers for fetching trace details
MAX_WORKERS = 8

# Labels for the report
MODEL_A_LABEL = "Gemini-3-Flash"
MODEL_B_LABEL = "GPT-4.1"

# Minimum sample size recommendation (see power analysis notes below)
# With the observed effect size (latency: 4.66s vs 2.03s, Cohen's d ~ 1.5),
# a two-sided Mann-Whitney U test at alpha=0.05, power=0.80 needs ~10 per group.
# For more robust estimates (p90/p95 percentiles, chi-squared on routing
# distributions), we recommend at least 25 per group.
# With 43 Gemini and 28 GPT-4.1 traces available, we target min(28, 43) = 28.
MIN_RECOMMENDED_SAMPLE = 25

# ============================================================================
# END CONFIG
# ============================================================================


@dataclass
class RouteObservation:
    """Parsed ROUTE generation observation from a trace."""

    trace_id: str
    trace_name: str
    model: str
    start_time: str
    end_time: str
    completion_start_time: str | None
    latency_seconds: float | None  # endTime - startTime
    ttft_seconds: float | None     # completionStartTime - startTime
    input_tokens: int
    output_tokens: int
    total_tokens: int
    throughput_tokens_per_sec: float | None  # output_tokens / (endTime - completionStartTime)
    routing_decision: str          # semantic_search, popularity_based, reject, or unknown
    tool_call_args: dict[str, Any] # Full tool_call arguments
    tags_count: int                # Number of tags in tool_call
    description_length: int        # Character length of description
    lookback_window: str | None    # lookback_window value if present
    raw_output: Any                # Full output for inspection


@dataclass
class ComparisonReport:
    """Container for the full comparison report data."""

    model_a_label: str
    model_b_label: str
    model_a_obs: list[RouteObservation] = field(default_factory=list)
    model_b_obs: list[RouteObservation] = field(default_factory=list)


# ============================================================================
# CLI HELPERS
# ============================================================================


def run_lf(*args: str, timeout: int = 120) -> str:
    """Run an lf CLI command and return stdout.

    Raises SystemExit on failure with a clear error message.
    """
    cmd = ["lf", "--json", *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            print(f"[ERROR] lf command failed (exit {result.returncode}): {' '.join(cmd)}", file=sys.stderr)
            if stderr:
                print(f"        stderr: {stderr}", file=sys.stderr)
            return "[]"  # Return empty array so caller can handle gracefully
        return result.stdout
    except subprocess.TimeoutExpired:
        print(f"[ERROR] lf command timed out after {timeout}s: {' '.join(cmd)}", file=sys.stderr)
        return "[]"
    except FileNotFoundError:
        print("[FATAL] 'lf' CLI not found in PATH. Install with: pip install langfuse-cli", file=sys.stderr)
        sys.exit(1)


def fetch_trace_ids(trace_name: str) -> list[str]:
    """Fetch trace IDs for a given trace name within the date range."""
    raw = run_lf(
        "traces", "list",
        "--name", trace_name,
        "--limit", str(MAX_TRACES_PER_MODEL),
        "--from", DATE_FROM,
        "--to", DATE_TO,
    )
    traces = json.loads(raw)
    if not traces:
        print(f"[WARN] No traces found for name='{trace_name}' in [{DATE_FROM}, {DATE_TO})", file=sys.stderr)
        return []
    return [t["id"] for t in traces]


def fetch_trace_tree(trace_id: str) -> dict[str, Any] | None:
    """Fetch a single trace with its observations via 'lf traces tree'."""
    raw = run_lf("traces", "tree", trace_id, timeout=30)
    try:
        data = json.loads(raw)
        # traces tree --json returns [{"trace": {...}, "observations": [...]}]
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        if isinstance(data, dict) and "trace" in data:
            return data
        # Fallback: might be wrapped differently
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        print(f"[WARN] Failed to parse JSON for trace {trace_id}", file=sys.stderr)
        return None


# ============================================================================
# PARSING
# ============================================================================


def parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp string into a datetime object."""
    if not ts:
        return None
    # Handle various ISO formats from Langfuse
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f+00:00", "%Y-%m-%dT%H:%M:%S+00:00"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    # Last resort: strip timezone and parse
    try:
        clean = ts.replace("Z", "").split("+")[0]
        return datetime.fromisoformat(clean)
    except ValueError:
        return None


def extract_route_observation(trace_data: dict[str, Any]) -> RouteObservation | None:
    """Extract the ROUTE generation observation from a trace tree.

    The trace tree JSON from 'lf --json traces tree <id>' has structure:
        {"trace": {...}, "observations": [{...}, ...]}

    We look for the observation named ROUTE (or matching the ROUTE_OBSERVATION_NAME
    config) with type=GENERATION.
    """
    trace = trace_data.get("trace", trace_data)
    observations = trace_data.get("observations", [])

    trace_id = trace.get("id", "unknown")
    trace_name = trace.get("name", "unknown")

    # Find the ROUTE observation
    route_obs = None
    for obs in observations:
        obs_name = obs.get("name", "")
        obs_type = obs.get("type", "")
        if obs_name == ROUTE_OBSERVATION_NAME and obs_type == "GENERATION":
            route_obs = obs
            break

    if route_obs is None:
        # Try case-insensitive or partial match
        for obs in observations:
            obs_name = (obs.get("name") or "").lower()
            obs_type = obs.get("type", "")
            if "route" in obs_name and obs_type == "GENERATION":
                route_obs = obs
                break

    if route_obs is None:
        return None

    # Parse timestamps
    start_dt = parse_iso(route_obs.get("startTime"))
    end_dt = parse_iso(route_obs.get("endTime"))
    completion_start_dt = parse_iso(route_obs.get("completionStartTime"))

    # Calculate latency
    latency = None
    if start_dt and end_dt:
        latency = (end_dt - start_dt).total_seconds()

    # Calculate TTFT (Time to First Token)
    ttft = None
    if start_dt and completion_start_dt:
        ttft = (completion_start_dt - start_dt).total_seconds()

    # Token usage - Langfuse v2 uses usageDetails, v1 uses usage
    usage = route_obs.get("usageDetails") or route_obs.get("usage") or {}
    input_tokens = usage.get("input", 0) or usage.get("promptTokens", 0) or usage.get("inputTokens", 0) or 0
    output_tokens = usage.get("output", 0) or usage.get("completionTokens", 0) or usage.get("outputTokens", 0) or 0
    total_tokens = usage.get("total", 0) or usage.get("totalTokens", 0) or (input_tokens + output_tokens)

    # Throughput: output tokens per second of generation time
    # Generation time = endTime - completionStartTime (time spent generating tokens)
    throughput = None
    if completion_start_dt and end_dt and output_tokens > 0:
        gen_time = (end_dt - completion_start_dt).total_seconds()
        if gen_time > 0:
            throughput = output_tokens / gen_time

    # Parse output for routing decision and arguments
    output = route_obs.get("output", {})
    routing_decision, tool_call_args, tags_count, desc_length, lookback = _parse_route_output(output)

    model = route_obs.get("model") or route_obs.get("providedModelName") or "unknown"

    return RouteObservation(
        trace_id=trace_id,
        trace_name=trace_name,
        model=model,
        start_time=route_obs.get("startTime", ""),
        end_time=route_obs.get("endTime", ""),
        completion_start_time=route_obs.get("completionStartTime"),
        latency_seconds=latency,
        ttft_seconds=ttft,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        throughput_tokens_per_sec=throughput,
        routing_decision=routing_decision,
        tool_call_args=tool_call_args,
        tags_count=tags_count,
        description_length=desc_length,
        lookback_window=lookback,
        raw_output=output,
    )


def _parse_route_output(output: Any) -> tuple[str, dict[str, Any], int, int, str | None]:
    """Parse the ROUTE observation output to extract routing decision and arguments.

    The ROUTE output typically contains tool_calls with the routing decision.
    Expected structure varies but commonly:
        - {"tool_calls": [{"function": {"name": "semantic_search", "arguments": {...}}}]}
        - Or: [{"function": {"name": "semantic_search", "arguments": {...}}}]
        - Or: {"name": "semantic_search", "arguments": {...}}

    Returns:
        (routing_decision, tool_call_args, tags_count, description_length, lookback_window)
    """
    if output is None:
        return "unknown", {}, 0, 0, None

    # Normalize: handle string output (some models return stringified JSON)
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return "unknown", {}, 0, 0, None

    tool_calls = []

    # Extract tool_calls from various structures
    if isinstance(output, dict):
        if "tool_calls" in output:
            tool_calls = output["tool_calls"]
        elif "choices" in output:
            # OpenAI-style response
            for choice in output.get("choices", []):
                msg = choice.get("message", {})
                tool_calls.extend(msg.get("tool_calls", []))
        elif "name" in output and "arguments" in output:
            tool_calls = [{"function": output}]
        elif "function" in output:
            tool_calls = [output]
    elif isinstance(output, list):
        tool_calls = output

    if not tool_calls:
        # Try to find any hint of routing in the raw output
        output_str = json.dumps(output) if not isinstance(output, str) else output
        for decision in ("semantic_search", "popularity_based", "reject"):
            if decision in output_str.lower():
                return decision, {}, 0, 0, None
        return "unknown", {}, 0, 0, None

    # Parse the first tool call
    tc = tool_calls[0]
    func = tc.get("function", tc)
    routing_decision = func.get("name", "unknown")

    # Parse arguments
    args = func.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            args = {}

    # Extract richness metrics
    tags = args.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tags_count = len(tags) if isinstance(tags, list) else 0

    description = args.get("description", "")
    desc_length = len(description) if isinstance(description, str) else 0

    lookback = args.get("lookback_window") or args.get("lookbackWindow")
    if lookback is not None:
        lookback = str(lookback)

    return routing_decision, args, tags_count, desc_length, lookback


# ============================================================================
# DATA COLLECTION
# ============================================================================


def collect_observations(trace_name: str, label: str) -> list[RouteObservation]:
    """Collect all ROUTE observations for a given trace name."""
    print(f"\n--- Collecting data for {label} (trace name: {trace_name}) ---", file=sys.stderr)

    # Step 1: Get trace IDs
    trace_ids = fetch_trace_ids(trace_name)
    print(f"    Found {len(trace_ids)} traces", file=sys.stderr)

    if not trace_ids:
        return []

    # Step 2: Fetch trace trees in parallel
    observations: list[RouteObservation] = []
    errors = 0

    print(f"    Fetching trace details ({MAX_WORKERS} workers)...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_trace_tree, tid): tid for tid in trace_ids}
        for i, future in enumerate(as_completed(futures), 1):
            tid = futures[future]
            try:
                tree_data = future.result()
                if tree_data:
                    obs = extract_route_observation(tree_data)
                    if obs:
                        observations.append(obs)
                    else:
                        print(f"    [SKIP] No ROUTE observation in trace {tid}", file=sys.stderr)
                else:
                    errors += 1
            except Exception as e:
                print(f"    [ERROR] Failed to process trace {tid}: {e}", file=sys.stderr)
                errors += 1

            # Progress indicator
            if i % 10 == 0:
                print(f"    Processed {i}/{len(trace_ids)} traces...", file=sys.stderr)

    print(f"    Collected {len(observations)} ROUTE observations ({errors} errors)", file=sys.stderr)
    return observations


# ============================================================================
# STATISTICAL ANALYSIS
# ============================================================================


def percentile(values: list[float], p: float) -> float:
    """Calculate the p-th percentile of a list of values."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_v):
        return sorted_v[-1]
    return sorted_v[f] + (k - f) * (sorted_v[c] - sorted_v[f])


def mean(values: list[float]) -> float:
    """Calculate mean."""
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    """Calculate sample standard deviation."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5


def ci_95(values: list[float]) -> tuple[float, float]:
    """Calculate 95% confidence interval for the mean (t-distribution approximation).

    For sample sizes >= 25, t ~ 1.96; for smaller samples we use a rough lookup.
    """
    n = len(values)
    if n < 2:
        m = mean(values)
        return (m, m)
    m = mean(values)
    se = stdev(values) / (n ** 0.5)
    # Rough t-values for 95% CI (two-tailed)
    t_table = {2: 12.71, 3: 4.30, 4: 3.18, 5: 2.78, 6: 2.57, 7: 2.45, 8: 2.37,
               9: 2.31, 10: 2.26, 15: 2.14, 20: 2.09, 25: 2.06, 30: 2.04, 50: 2.01}
    t_val = 1.96  # default for large n
    for threshold in sorted(t_table.keys()):
        if n <= threshold:
            t_val = t_table[threshold]
            break
    return (m - t_val * se, m + t_val * se)


def mann_whitney_u(a: list[float], b: list[float]) -> tuple[float, float]:
    """Run Mann-Whitney U test. Returns (U statistic, p-value).

    Requires scipy. Falls back to a message if not installed.
    """
    try:
        from scipy.stats import mannwhitneyu
        stat, p = mannwhitneyu(a, b, alternative="two-sided")
        return stat, p
    except ImportError:
        print("[WARN] scipy not installed. Skipping Mann-Whitney U test.", file=sys.stderr)
        print("       Install with: pip install scipy", file=sys.stderr)
        return float("nan"), float("nan")


def chi_squared_test(counts_a: dict[str, int], counts_b: dict[str, int]) -> tuple[float, float, int]:
    """Run chi-squared test on two routing decision distributions.

    Returns (chi2 statistic, p-value, degrees_of_freedom).
    Requires scipy.
    """
    try:
        from scipy.stats import chi2_contingency
        import numpy as np
    except ImportError:
        print("[WARN] scipy/numpy not installed. Skipping chi-squared test.", file=sys.stderr)
        return float("nan"), float("nan"), 0

    # Build contingency table with all categories present in either
    all_categories = sorted(set(list(counts_a.keys()) + list(counts_b.keys())))
    if len(all_categories) < 2:
        return float("nan"), float("nan"), 0

    observed = np.array([
        [counts_a.get(cat, 0) for cat in all_categories],
        [counts_b.get(cat, 0) for cat in all_categories],
    ])

    # Remove columns with all zeros
    col_sums = observed.sum(axis=0)
    nonzero_cols = col_sums > 0
    observed = observed[:, nonzero_cols]

    if observed.shape[1] < 2:
        return float("nan"), float("nan"), 0

    try:
        chi2, p, dof, expected = chi2_contingency(observed)
        return chi2, p, dof
    except ValueError:
        return float("nan"), float("nan"), 0


def cohens_d(a: list[float], b: list[float]) -> float:
    """Calculate Cohen's d effect size."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    m_a, m_b = mean(a), mean(b)
    s_a, s_b = stdev(a), stdev(b)
    # Pooled standard deviation
    n_a, n_b = len(a), len(b)
    s_pooled = (((n_a - 1) * s_a**2 + (n_b - 1) * s_b**2) / (n_a + n_b - 2)) ** 0.5
    if s_pooled == 0:
        return float("nan")
    return (m_a - m_b) / s_pooled


# ============================================================================
# REPORT GENERATION
# ============================================================================


def format_float(v: float | None, decimals: int = 3) -> str:
    """Format a float for display, handling None and NaN."""
    if v is None:
        return "N/A"
    if v != v:  # NaN check
        return "N/A"
    return f"{v:.{decimals}f}"


def format_ci(ci: tuple[float, float], decimals: int = 3) -> str:
    """Format a confidence interval."""
    return f"[{ci[0]:.{decimals}f}, {ci[1]:.{decimals}f}]"


def generate_report(report: ComparisonReport) -> str:
    """Generate the full comparison report as a formatted string."""
    lines: list[str] = []
    W = 80  # report width

    def section(title: str) -> None:
        lines.append("")
        lines.append("=" * W)
        lines.append(f"  {title}")
        lines.append("=" * W)

    def subsection(title: str) -> None:
        lines.append("")
        lines.append(f"  --- {title} ---")

    def row(label: str, val_a: str, val_b: str, note: str = "") -> None:
        note_str = f"  {note}" if note else ""
        lines.append(f"  {label:<30s}  {val_a:>14s}  {val_b:>14s}{note_str}")

    a_obs = report.model_a_obs
    b_obs = report.model_b_obs
    a_label = report.model_a_label
    b_label = report.model_b_label

    # ── Header ──
    lines.append("")
    lines.append("*" * W)
    lines.append("  ROUTE MODEL COMPARISON REPORT")
    lines.append(f"  {a_label} vs {b_label}")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Date range: {DATE_FROM} to {DATE_TO}")
    lines.append("*" * W)

    # ── Sample Summary ──
    section("1. SAMPLE SUMMARY")
    lines.append("")
    row("Metric", a_label, b_label)
    lines.append("  " + "-" * 62)
    row("Total traces found", str(len(a_obs)), str(len(b_obs)))

    # Check sample size adequacy
    min_n = min(len(a_obs), len(b_obs))
    lines.append("")
    if min_n < MIN_RECOMMENDED_SAMPLE:
        lines.append(f"  [!] WARNING: Minimum sample size ({min_n}) is below the recommended")
        lines.append(f"      threshold of {MIN_RECOMMENDED_SAMPLE} for reliable statistical tests.")
        lines.append(f"      Results should be interpreted with caution.")
    else:
        lines.append(f"  [OK] Sample sizes meet the minimum recommendation of {MIN_RECOMMENDED_SAMPLE}.")

    # Power analysis explanation
    lines.append("")
    lines.append("  Power Analysis Notes:")
    lines.append("  - For Mann-Whitney U (alpha=0.05, power=0.80, large effect d>0.8): n>=10/group")
    lines.append("  - For chi-squared (3 categories, alpha=0.05, power=0.80, medium w=0.3): n>=25/group")
    lines.append("  - For reliable percentile estimation (p90/p95): n>=25/group recommended")

    # ── Latency ──
    section("2. LATENCY (seconds)")

    a_lat = [o.latency_seconds for o in a_obs if o.latency_seconds is not None]
    b_lat = [o.latency_seconds for o in b_obs if o.latency_seconds is not None]

    if a_lat and b_lat:
        subsection("Descriptive Statistics")
        row("Metric", a_label, b_label)
        lines.append("  " + "-" * 62)
        row("N (valid)", str(len(a_lat)), str(len(b_lat)))
        row("Mean", format_float(mean(a_lat)), format_float(mean(b_lat)))
        row("Std Dev", format_float(stdev(a_lat)), format_float(stdev(b_lat)))
        row("95% CI (mean)", format_ci(ci_95(a_lat)), format_ci(ci_95(b_lat)))
        row("Min", format_float(min(a_lat)), format_float(min(b_lat)))
        row("P50 (median)", format_float(percentile(a_lat, 50)), format_float(percentile(b_lat, 50)))
        row("P90", format_float(percentile(a_lat, 90)), format_float(percentile(b_lat, 90)))
        row("P95", format_float(percentile(a_lat, 95)), format_float(percentile(b_lat, 95)))
        row("Max", format_float(max(a_lat)), format_float(max(b_lat)))

        subsection("Statistical Test: Mann-Whitney U")
        u_stat, p_val = mann_whitney_u(a_lat, b_lat)
        d = cohens_d(a_lat, b_lat)
        lines.append(f"  U statistic:  {format_float(u_stat, 1)}")
        lines.append(f"  p-value:      {format_float(p_val, 6)}")
        lines.append(f"  Cohen's d:    {format_float(d, 3)}")
        if p_val == p_val:  # not NaN
            sig = "YES (p < 0.05)" if p_val < 0.05 else "NO (p >= 0.05)"
            lines.append(f"  Significant:  {sig}")
            effect = "small" if abs(d) < 0.5 else "medium" if abs(d) < 0.8 else "large"
            lines.append(f"  Effect size:  {effect}")
            faster = a_label if mean(a_lat) < mean(b_lat) else b_label
            pct_diff = abs(mean(a_lat) - mean(b_lat)) / max(mean(a_lat), mean(b_lat)) * 100
            lines.append(f"  Faster model: {faster} (by {pct_diff:.1f}%)")
    else:
        lines.append("  [!] Insufficient latency data for comparison.")

    # ── TTFT ──
    section("3. TIME TO FIRST TOKEN - TTFT (seconds)")

    a_ttft = [o.ttft_seconds for o in a_obs if o.ttft_seconds is not None]
    b_ttft = [o.ttft_seconds for o in b_obs if o.ttft_seconds is not None]

    if a_ttft and b_ttft:
        subsection("Descriptive Statistics")
        row("Metric", a_label, b_label)
        lines.append("  " + "-" * 62)
        row("N (valid)", str(len(a_ttft)), str(len(b_ttft)))
        row("Mean", format_float(mean(a_ttft)), format_float(mean(b_ttft)))
        row("95% CI (mean)", format_ci(ci_95(a_ttft)), format_ci(ci_95(b_ttft)))
        row("P50 (median)", format_float(percentile(a_ttft, 50)), format_float(percentile(b_ttft, 50)))
        row("P90", format_float(percentile(a_ttft, 90)), format_float(percentile(b_ttft, 90)))
        row("P95", format_float(percentile(a_ttft, 95)), format_float(percentile(b_ttft, 95)))

        u_stat, p_val = mann_whitney_u(a_ttft, b_ttft)
        subsection("Statistical Test: Mann-Whitney U")
        lines.append(f"  U statistic:  {format_float(u_stat, 1)}")
        lines.append(f"  p-value:      {format_float(p_val, 6)}")
        if p_val == p_val:
            sig = "YES (p < 0.05)" if p_val < 0.05 else "NO (p >= 0.05)"
            lines.append(f"  Significant:  {sig}")
    else:
        lines.append("")
        n_a = len(a_ttft)
        n_b = len(b_ttft)
        lines.append(f"  TTFT data available: {a_label}={n_a}, {b_label}={n_b}")
        if n_a == 0 and n_b == 0:
            lines.append("  [!] No completionStartTime recorded for either model.")
            lines.append("      TTFT requires streaming responses with completionStartTime set.")
        else:
            lines.append("  [!] Insufficient TTFT data for one or both models.")

    # ── Token Usage ──
    section("4. TOKEN USAGE")

    subsection("Input Tokens")
    a_in = [o.input_tokens for o in a_obs if o.input_tokens > 0]
    b_in = [o.input_tokens for o in b_obs if o.input_tokens > 0]
    if a_in and b_in:
        row("Metric", a_label, b_label)
        lines.append("  " + "-" * 62)
        row("N (valid)", str(len(a_in)), str(len(b_in)))
        row("Mean", format_float(mean(a_in), 0), format_float(mean(b_in), 0))
        row("Std Dev", format_float(stdev(a_in), 0), format_float(stdev(b_in), 0))
        row("Min", str(min(a_in)), str(min(b_in)))
        row("Max", str(max(a_in)), str(max(b_in)))
    else:
        lines.append("  [!] Insufficient input token data.")

    subsection("Output Tokens")
    a_out = [o.output_tokens for o in a_obs if o.output_tokens > 0]
    b_out = [o.output_tokens for o in b_obs if o.output_tokens > 0]
    if a_out and b_out:
        row("Metric", a_label, b_label)
        lines.append("  " + "-" * 62)
        row("N (valid)", str(len(a_out)), str(len(b_out)))
        row("Mean", format_float(mean(a_out), 0), format_float(mean(b_out), 0))
        row("Std Dev", format_float(stdev(a_out), 0), format_float(stdev(b_out), 0))
        row("Min", str(min(a_out)), str(min(b_out)))
        row("Max", str(max(a_out)), str(max(b_out)))
        u_stat, p_val = mann_whitney_u([float(x) for x in a_out], [float(x) for x in b_out])
        lines.append(f"  Mann-Whitney U: U={format_float(u_stat, 1)}, p={format_float(p_val, 6)}")
        if p_val == p_val and p_val < 0.05:
            lines.append("  [*] Output token counts differ significantly between models.")
    else:
        lines.append("  [!] Insufficient output token data.")

    subsection("Total Tokens")
    a_total = [o.total_tokens for o in a_obs if o.total_tokens > 0]
    b_total = [o.total_tokens for o in b_obs if o.total_tokens > 0]
    if a_total and b_total:
        row("Metric", a_label, b_label)
        lines.append("  " + "-" * 62)
        row("Mean", format_float(mean(a_total), 0), format_float(mean(b_total), 0))
        row("Min", str(min(a_total)), str(min(b_total)))
        row("Max", str(max(a_total)), str(max(b_total)))

    # ── Throughput ──
    section("5. THROUGHPUT (output tokens/sec)")

    a_tp = [o.throughput_tokens_per_sec for o in a_obs if o.throughput_tokens_per_sec is not None and o.throughput_tokens_per_sec > 0]
    b_tp = [o.throughput_tokens_per_sec for o in b_obs if o.throughput_tokens_per_sec is not None and o.throughput_tokens_per_sec > 0]

    if a_tp and b_tp:
        row("Metric", a_label, b_label)
        lines.append("  " + "-" * 62)
        row("N (valid)", str(len(a_tp)), str(len(b_tp)))
        row("Mean", format_float(mean(a_tp), 1), format_float(mean(b_tp), 1))
        row("95% CI (mean)", format_ci(ci_95(a_tp), 1), format_ci(ci_95(b_tp), 1))
        row("P50 (median)", format_float(percentile(a_tp, 50), 1), format_float(percentile(b_tp, 50), 1))
        row("P90", format_float(percentile(a_tp, 90), 1), format_float(percentile(b_tp, 90), 1))
        row("Min", format_float(min(a_tp), 1), format_float(min(b_tp), 1))
        row("Max", format_float(max(a_tp), 1), format_float(max(b_tp), 1))

        u_stat, p_val = mann_whitney_u(a_tp, b_tp)
        lines.append(f"  Mann-Whitney U: U={format_float(u_stat, 1)}, p={format_float(p_val, 6)}")
    else:
        lines.append("")
        lines.append("  [!] Throughput requires completionStartTime to calculate generation window.")
        lines.append(f"      Data available: {a_label}={len(a_tp)}, {b_label}={len(b_tp)}")

    # ── Routing Decision Quality ──
    section("6. ROUTING DECISION DISTRIBUTION")

    a_decisions = Counter(o.routing_decision for o in a_obs)
    b_decisions = Counter(o.routing_decision for o in b_obs)
    all_decisions = sorted(set(list(a_decisions.keys()) + list(b_decisions.keys())))

    lines.append("")
    row("Decision", a_label, b_label)
    lines.append("  " + "-" * 62)
    for decision in all_decisions:
        ca = a_decisions.get(decision, 0)
        cb = b_decisions.get(decision, 0)
        pct_a = f"{ca} ({ca / len(a_obs) * 100:.1f}%)" if a_obs else "0"
        pct_b = f"{cb} ({cb / len(b_obs) * 100:.1f}%)" if b_obs else "0"
        row(decision, pct_a, pct_b)

    # Chi-squared test
    if len(all_decisions) >= 2 and len(a_obs) >= 5 and len(b_obs) >= 5:
        subsection("Statistical Test: Chi-Squared")
        chi2, p_val, dof = chi_squared_test(a_decisions, b_decisions)
        lines.append(f"  Chi-squared:   {format_float(chi2, 3)}")
        lines.append(f"  p-value:       {format_float(p_val, 6)}")
        lines.append(f"  df:            {dof}")
        if p_val == p_val:
            sig = "YES (p < 0.05)" if p_val < 0.05 else "NO (p >= 0.05)"
            lines.append(f"  Significant:   {sig}")
            if p_val < 0.05:
                lines.append("  [*] Routing distributions differ significantly between models.")
            else:
                lines.append("  [OK] No significant difference in routing distributions.")
    else:
        lines.append("")
        lines.append("  [!] Not enough categories or samples for chi-squared test.")

    # ── Argument Richness ──
    section("7. ARGUMENT RICHNESS")

    subsection("Tags Count (per generation)")
    a_tags = [o.tags_count for o in a_obs]
    b_tags = [o.tags_count for o in b_obs]
    if a_tags and b_tags:
        row("Metric", a_label, b_label)
        lines.append("  " + "-" * 62)
        row("Mean tags", format_float(mean(a_tags), 1), format_float(mean(b_tags), 1))
        row("Min tags", str(min(a_tags)), str(min(b_tags)))
        row("Max tags", str(max(a_tags)), str(max(b_tags)))
        row("Zero-tag rate", f"{sum(1 for t in a_tags if t == 0)}/{len(a_tags)}", f"{sum(1 for t in b_tags if t == 0)}/{len(b_tags)}")

        # Distribution of tag counts
        a_tag_dist = Counter(a_tags)
        b_tag_dist = Counter(b_tags)
        all_tag_counts = sorted(set(list(a_tag_dist.keys()) + list(b_tag_dist.keys())))
        if len(all_tag_counts) <= 10:
            lines.append("")
            lines.append("  Tag count distribution:")
            for tc in all_tag_counts:
                row(f"  {tc} tags", str(a_tag_dist.get(tc, 0)), str(b_tag_dist.get(tc, 0)))

    subsection("Description Length (characters)")
    a_desc = [o.description_length for o in a_obs]
    b_desc = [o.description_length for o in b_obs]
    if a_desc and b_desc:
        row("Metric", a_label, b_label)
        lines.append("  " + "-" * 62)
        row("Mean length", format_float(mean(a_desc), 0), format_float(mean(b_desc), 0))
        row("Min", str(min(a_desc)), str(min(b_desc)))
        row("Max", str(max(a_desc)), str(max(b_desc)))
        row("Zero-length rate", f"{sum(1 for d in a_desc if d == 0)}/{len(a_desc)}", f"{sum(1 for d in b_desc if d == 0)}/{len(b_desc)}")

        u_stat, p_val = mann_whitney_u([float(x) for x in a_desc], [float(x) for x in b_desc])
        lines.append(f"  Mann-Whitney U: U={format_float(u_stat, 1)}, p={format_float(p_val, 6)}")

    subsection("Lookback Window Choices")
    a_lb = Counter(o.lookback_window for o in a_obs)
    b_lb = Counter(o.lookback_window for o in b_obs)
    all_lb = sorted(set(list(a_lb.keys()) + list(b_lb.keys())), key=lambda x: str(x))
    if all_lb:
        row("Window", a_label, b_label)
        lines.append("  " + "-" * 62)
        for lb in all_lb:
            display = str(lb) if lb is not None else "(none)"
            ca = a_lb.get(lb, 0)
            cb = b_lb.get(lb, 0)
            row(display, str(ca), str(cb))

    # ── Model Metadata ──
    section("8. MODEL METADATA")

    a_models = Counter(o.model for o in a_obs)
    b_models = Counter(o.model for o in b_obs)
    lines.append("")
    lines.append(f"  {a_label} model(s): {dict(a_models)}")
    lines.append(f"  {b_label} model(s): {dict(b_models)}")

    # ── Raw Data Dump (sample) ──
    section("9. SAMPLE RAW DATA (first 3 per model)")
    for label, obs_list in [(a_label, a_obs), (b_label, b_obs)]:
        lines.append(f"\n  {label}:")
        for obs in obs_list[:3]:
            lines.append(f"    Trace: {obs.trace_id}")
            lines.append(f"    Model: {obs.model}")
            lines.append(f"    Latency: {format_float(obs.latency_seconds)}s")
            lines.append(f"    TTFT: {format_float(obs.ttft_seconds)}s")
            lines.append(f"    Tokens: in={obs.input_tokens}, out={obs.output_tokens}, total={obs.total_tokens}")
            lines.append(f"    Decision: {obs.routing_decision}")
            lines.append(f"    Tags ({obs.tags_count}): {obs.tool_call_args.get('tags', [])}")
            lines.append(f"    Description ({obs.description_length} chars): {str(obs.tool_call_args.get('description', ''))[:100]}...")
            lines.append(f"    Lookback: {obs.lookback_window}")
            lines.append("")

    # ── Summary ──
    section("10. EXECUTIVE SUMMARY")
    lines.append("")

    if a_lat and b_lat:
        faster = a_label if mean(a_lat) < mean(b_lat) else b_label
        slower = b_label if faster == a_label else a_label
        pct = abs(mean(a_lat) - mean(b_lat)) / max(mean(a_lat), mean(b_lat)) * 100
        ratio = max(mean(a_lat), mean(b_lat)) / min(mean(a_lat), mean(b_lat))
        lines.append(f"  LATENCY: {faster} is {pct:.0f}% faster ({ratio:.1f}x) than {slower}")
        lines.append(f"           Mean: {faster}={format_float(min(mean(a_lat), mean(b_lat)))}s "
                     f"vs {slower}={format_float(max(mean(a_lat), mean(b_lat)))}s")

    if a_out and b_out:
        more = a_label if mean(a_out) > mean(b_out) else b_label
        ratio = max(mean(a_out), mean(b_out)) / max(min(mean(a_out), mean(b_out)), 1)
        lines.append(f"  TOKENS:  {more} generates {ratio:.1f}x more output tokens")

    if a_tp and b_tp:
        faster_tp = a_label if mean(a_tp) > mean(b_tp) else b_label
        lines.append(f"  THROUGHPUT: {faster_tp} has higher throughput "
                     f"({format_float(max(mean(a_tp), mean(b_tp)), 1)} vs "
                     f"{format_float(min(mean(a_tp), mean(b_tp)), 1)} tok/s)")

    # Routing agreement
    if a_decisions and b_decisions:
        lines.append(f"  ROUTING: {a_label} routes: {dict(a_decisions)}")
        lines.append(f"           {b_label} routes: {dict(b_decisions)}")

    lines.append("")
    lines.append("  RECOMMENDATION:")
    lines.append("  Review the latency vs output quality tradeoff. Higher output tokens")
    lines.append("  may indicate more verbose (potentially less focused) routing arguments,")
    lines.append("  or richer context. Check if the routing decisions lead to equivalent")
    lines.append("  downstream results by examining full trace outcomes.")

    lines.append("")
    lines.append("*" * W)
    lines.append("  END OF REPORT")
    lines.append("*" * W)
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# MAIN
# ============================================================================


def main() -> None:
    """Main entry point: collect data, analyze, and output report."""
    start_time = time.time()

    print("=" * 60, file=sys.stderr)
    print("ROUTE Model Comparison Analysis", file=sys.stderr)
    print(f"Date range: {DATE_FROM} to {DATE_TO}", file=sys.stderr)
    print(f"Models: {MODEL_A_LABEL} vs {MODEL_B_LABEL}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Collect data for both models
    gemini_obs = collect_observations(GEMINI_TRACE_NAME, MODEL_A_LABEL)
    gpt4_obs = collect_observations(GPT4_TRACE_NAME, MODEL_B_LABEL)

    if not gemini_obs and not gpt4_obs:
        print("\n[FATAL] No data collected for either model. Check:", file=sys.stderr)
        print("  1. lf CLI is configured (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)", file=sys.stderr)
        print("  2. Trace names are correct in CONFIG section", file=sys.stderr)
        print("  3. Date range contains data", file=sys.stderr)
        sys.exit(1)

    # Equalize sample sizes for fair comparison
    min_n = min(len(gemini_obs), len(gpt4_obs))
    if min_n == 0:
        print(f"\n[WARN] One model has no data. Proceeding with unequal samples.", file=sys.stderr)
        print(f"       {MODEL_A_LABEL}: {len(gemini_obs)}, {MODEL_B_LABEL}: {len(gpt4_obs)}", file=sys.stderr)
    else:
        # Sort by start_time and take the most recent `min_n` from each
        gemini_obs.sort(key=lambda o: o.start_time, reverse=True)
        gpt4_obs.sort(key=lambda o: o.start_time, reverse=True)
        gemini_obs = gemini_obs[:min_n]
        gpt4_obs = gpt4_obs[:min_n]
        print(f"\n--- Equalized to {min_n} samples per model ---", file=sys.stderr)

    # Build report
    report = ComparisonReport(
        model_a_label=MODEL_A_LABEL,
        model_b_label=MODEL_B_LABEL,
        model_a_obs=gemini_obs,
        model_b_obs=gpt4_obs,
    )

    # Generate and output report
    report_text = generate_report(report)
    print(report_text)

    elapsed = time.time() - start_time
    print(f"[Analysis completed in {elapsed:.1f}s]", file=sys.stderr)

    # Also dump raw JSON data to stderr for debugging (optional)
    raw_data = {
        "config": {
            "gemini_trace_name": GEMINI_TRACE_NAME,
            "gpt4_trace_name": GPT4_TRACE_NAME,
            "date_from": DATE_FROM,
            "date_to": DATE_TO,
            "sample_size": min_n if min_n > 0 else max(len(gemini_obs), len(gpt4_obs)),
        },
        "gemini_observations": [
            {
                "trace_id": o.trace_id,
                "model": o.model,
                "latency": o.latency_seconds,
                "ttft": o.ttft_seconds,
                "input_tokens": o.input_tokens,
                "output_tokens": o.output_tokens,
                "throughput": o.throughput_tokens_per_sec,
                "routing_decision": o.routing_decision,
                "tags_count": o.tags_count,
                "description_length": o.description_length,
                "lookback_window": o.lookback_window,
            }
            for o in gemini_obs
        ],
        "gpt4_observations": [
            {
                "trace_id": o.trace_id,
                "model": o.model,
                "latency": o.latency_seconds,
                "ttft": o.ttft_seconds,
                "input_tokens": o.input_tokens,
                "output_tokens": o.output_tokens,
                "throughput": o.throughput_tokens_per_sec,
                "routing_decision": o.routing_decision,
                "tags_count": o.tags_count,
                "description_length": o.description_length,
                "lookback_window": o.lookback_window,
            }
            for o in gpt4_obs
        ],
    }
    # Write raw JSON to a file for later analysis
    raw_path = f"/tmp/route_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(raw_path, "w") as f:
            json.dump(raw_data, f, indent=2, default=str)
        print(f"[Raw data saved to {raw_path}]", file=sys.stderr)
    except OSError as e:
        print(f"[WARN] Could not save raw data: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
