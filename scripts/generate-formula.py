#!/usr/bin/env python3
"""Generate a Homebrew formula for langfuse-cli with all Python dependency resources.

Usage: python3 scripts/generate-formula.py <version>

Requires: pip install langfuse-cli==<version> (so pip can resolve dependencies)
"""
from __future__ import annotations

import json
import sys
import urllib.request


def get_pypi_sdist(package: str, version: str | None = None) -> tuple[str, str]:
    """Get the sdist URL and sha256 for a package from PyPI."""
    url = f"https://pypi.org/pypi/{package}/{version}/json" if version else f"https://pypi.org/pypi/{package}/json"
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())

    releases = data.get("urls", [])

    for file_info in releases:
        if file_info["filename"].endswith(".tar.gz"):
            return file_info["url"], file_info["digests"]["sha256"]

    # Fallback to .zip sdist
    for file_info in releases:
        if file_info["packagetype"] == "sdist":
            return file_info["url"], file_info["digests"]["sha256"]

    raise ValueError(f"No sdist found for {package}=={version}")


def get_installed_deps(exclude: str) -> list[tuple[str, str]]:
    """Get all installed packages except the main package and pip/setuptools."""
    import importlib.metadata

    # Skip the main package, build tools, and dev-only dependencies
    skip = {
        exclude.lower(), "pip", "setuptools", "wheel", "pkg-resources",
        # Dev dependencies that should not be in the formula
        "pytest", "pytest-cov", "pytest-mock", "respx", "ruff", "mypy",
        "mypy-extensions", "mypy_extensions", "coverage", "iniconfig", "pluggy",
        "pathspec", "librt",
        # Linux-only keyring backends (cryptography needs Rust to build from source)
        "secretstorage", "jeepney", "cryptography", "cffi", "pycparser",
    }
    deps = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"].lower()
        if name not in skip:
            deps.append((dist.metadata["Name"], dist.metadata["Version"]))
    return sorted(set(deps), key=lambda x: x[0].lower())


def generate_formula(version: str) -> str:
    """Generate the complete Homebrew formula."""
    pkg_url, pkg_sha256 = get_pypi_sdist("langfuse-cli", version)

    deps = get_installed_deps("langfuse-cli")
    resource_blocks = []
    for dep_name, dep_version in deps:
        try:
            dep_url, dep_sha256 = get_pypi_sdist(dep_name, dep_version)
            resource_blocks.append(
                f'  resource "{dep_name}" do\n'
                f'    url "{dep_url}"\n'
                f'    sha256 "{dep_sha256}"\n'
                f"  end\n"
            )
        except (ValueError, urllib.error.HTTPError) as e:
            print(f"WARNING: Skipping {dep_name}=={dep_version}: {e}", file=sys.stderr)

    resources = "\n".join(resource_blocks)

    return f'''class LangfuseCli < Formula
  include Language::Python::Virtualenv

  desc "CLI tool for Langfuse LLM observability platform"
  homepage "https://github.com/aviadshiber/langfuse-cli"
  url "{pkg_url}"
  sha256 "{pkg_sha256}"
  license "MIT"

  depends_on "python@3.12"

{resources}
  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{{bin}}/lf --version")
  end
end'''


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <version>", file=sys.stderr)
        sys.exit(1)
    print(generate_formula(sys.argv[1]))
