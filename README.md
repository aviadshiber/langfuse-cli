# langfuse-cli (`lf`)

Observability-first CLI for the [Langfuse](https://langfuse.com) LLM platform, following [gh-ux patterns](https://cli.github.com/manual/).

**Features**: traces, prompts, scores, datasets, experiments, sessions | JSON/table/TSV output | config profiles | system keyring secrets | agent-friendly `--json` mode

## Installation

```bash
# With uv (recommended)
uv tool install langfuse-cli

# With pip
pip install langfuse-cli

# From source
git clone <repo-url> && cd langfuse-cli
uv sync && uv run lf --version
```

## Quick Start

```bash
# Set credentials (or use config file below)
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"  # optional, this is the default

# List recent traces
lf traces list --limit 5 --from 2026-02-01

# List prompts
lf prompts list

# Get JSON output (agent-friendly)
lf --json traces list --limit 5 --from 2026-02-01
```

## Configuration

### Resolution Order

Configuration is resolved in this order (first match wins):

1. **CLI flags** (`--host`, `--profile`)
2. **Environment variables** (`LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`)
3. **Config file** (`~/.config/langfuse/config.toml`)
4. **System keyring** (macOS Keychain / Linux Secret Service)
5. **Defaults** (host: `https://cloud.langfuse.com`)

### Config File

```toml
# ~/.config/langfuse/config.toml

[default]
host = "https://cloud.langfuse.com"
public_key = "pk-lf-..."
# secret_key stored in keyring, NOT in plaintext

[profiles.staging]
host = "https://staging.langfuse.example.com"
public_key = "pk-lf-staging-..."

[defaults]
limit = 50
output = "table"
```

### Secret Storage

Secret keys are stored in the system keyring (service: `langfuse-cli`):

- **macOS**: Keychain (`security add-generic-password -s langfuse-cli -a default/secret_key -w <secret>`)
- **Linux**: Secret Service API (GNOME Keyring / KDE Wallet)
- **Fallback**: Environment variables or config file

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LANGFUSE_HOST` | Langfuse host URL |
| `LANGFUSE_BASEURL` | Alias for `LANGFUSE_HOST` (SDK compatibility) |
| `LANGFUSE_PUBLIC_KEY` | Public API key |
| `LANGFUSE_SECRET_KEY` | Secret API key |
| `LANGFUSE_PROFILE` | Config profile name |
| `LANGFUSE_FORCE_TTY` | Force TTY mode (set to `1`) |
| `NO_COLOR` | Disable color output |

## Global Options

Global options go **before** the subcommand:

```bash
lf --json traces list --limit 5       # correct
lf --quiet scores summary             # correct
```

| Flag | Description |
|------|-------------|
| `--version`, `-v` | Show version and exit |
| `--host URL` | Override Langfuse host URL |
| `--profile NAME` | Use named config profile |
| `--json` | Output as JSON |
| `--fields FIELDS` | Filter JSON to specific fields (comma-separated, implies `--json`) |
| `--jq EXPR` | Filter JSON with jq expression (implies `--json`) |
| `--quiet`, `-q` | Suppress status messages |

## Commands

### Traces

```bash
# List traces (use --from to avoid timeouts on large projects)
lf traces list --limit 10 --from 2026-02-01
lf traces list --user-id user-123 --session-id sess-456
lf traces list --tags production,v2 --name chat-completion

# Get a single trace
lf traces get <trace-id>

# Visualize trace hierarchy as a tree
lf traces tree <trace-id>
```

| Flag | Type | Description |
|------|------|-------------|
| `--limit`, `-l` | INT | Max results (default: 50) |
| `--user-id`, `-u` | TEXT | Filter by user ID |
| `--session-id` | TEXT | Filter by session ID |
| `--tags` | TEXT | Filter by tags (comma-separated) |
| `--name`, `-n` | TEXT | Filter by trace name |
| `--from` | DATETIME | Start time filter (ISO 8601) |
| `--to` | DATETIME | End time filter (ISO 8601) |

### Prompts

```bash
# List all prompts
lf prompts list

# Get a specific prompt
lf prompts get my-prompt
lf prompts get my-prompt --label production
lf prompts get my-prompt --version 3

# Compile a prompt with variables
lf prompts compile my-prompt --var name=Alice --var role=engineer

# Compare two versions
lf prompts diff my-prompt --v1 3 --v2 5
```

### Scores

```bash
# List scores
lf scores list --trace-id abc-123
lf scores list --name quality --from 2026-01-01

# Aggregated statistics
lf scores summary
lf scores summary --name quality --from 2026-01-01
```

### Datasets

```bash
# List datasets
lf datasets list

# Get dataset with items
lf datasets get my-dataset --limit 10
```

### Experiments

```bash
# List runs for a dataset
lf experiments list my-dataset

# Compare two runs
lf experiments compare my-dataset run-baseline run-improved
```

### Sessions

```bash
# List sessions
lf sessions list --limit 20 --from 2026-01-01

# Get session details
lf sessions get session-abc-123
```

## Output Modes

| Context | Format | Status Messages |
|---------|--------|-----------------|
| Terminal (TTY) | Rich aligned columns with colors | Shown |
| Piped (non-TTY) | Tab-separated values | Suppressed |
| `--json` flag | JSON array | Suppressed unless error |
| `--quiet` flag | Normal tables | All suppressed |

```bash
# Rich table (terminal)
lf prompts list

# Tab-separated (piped)
lf traces list --limit 5 --from 2026-02-01 | head

# JSON (agent-friendly)
lf --json traces list --limit 5 --from 2026-02-01

# Filtered JSON fields
lf --fields id,name,userId traces list --limit 5 --from 2026-02-01

# jq expression
lf --jq '.[].name' traces list --limit 5 --from 2026-02-01
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (API failure, auth, general) |
| 2 | Resource not found |
| 3 | Cancelled (Ctrl+C) |

## Architecture

Hybrid SDK + REST approach:

- **REST (httpx)**: Traces, observations, scores, sessions — full filter control, 60s timeout
- **SDK (langfuse)**: Prompts (built-in 300s caching), datasets, experiments — complex operations

## Development

```bash
# Setup
git clone <repo-url> && cd langfuse-cli
uv sync

# Run tests (291 tests, ~97% coverage)
uv run pytest

# Lint & type check
uv run ruff check src/ tests/
uv run mypy src/

# Run locally
uv run lf --version
```

## License

MIT
