# Contributing to langfuse-cli

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Getting Started

```bash
# Fork and clone the repository
git clone https://github.com/<your-username>/langfuse-cli.git
cd langfuse-cli

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linter
uv run ruff check src/ tests/

# Run type checker
uv run mypy src/
```

## Making Changes

1. **Create a branch** from `master`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Write your code** following existing patterns:
   - CLI commands go in `src/langfuse_cli/commands/`
   - Formatters go in `src/langfuse_cli/formatters/`
   - Follow [gh-ux patterns](https://cli.github.com/manual/) for CLI design

3. **Add tests** for any new functionality:
   - Tests live in `tests/`
   - Use `pytest` with `respx` for HTTP mocking
   - Aim for high coverage (current: 96%+)

4. **Ensure all checks pass**:
   ```bash
   uv run ruff check src/ tests/
   uv run mypy src/
   uv run pytest
   ```

## Pull Request Guidelines

- Keep PRs focused on a single change
- Write a clear description of what and why
- Reference any related issues
- All CI checks must pass
- A maintainer review is required before merge

## Code Style

- Formatter and linter: [Ruff](https://docs.astral.sh/ruff/)
- Max line length: 120 characters
- Type annotations required for all public functions (`mypy --strict`)
- Use `from __future__ import annotations` in all files

## Reporting Issues

- **Bugs**: Use the [bug report template](https://github.com/aviadshiber/langfuse-cli/issues/new?template=bug-report.md)
- **Features**: Use the [feature request template](https://github.com/aviadshiber/langfuse-cli/issues/new?template=feature-request.md)
- **Security**: See [SECURITY.md](.github/SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
