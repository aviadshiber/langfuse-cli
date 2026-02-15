#!/usr/bin/env python3
"""Generate a Homebrew formula for langfuse-cli.

Usage: python3 scripts/generate-formula.py <version>
"""
from __future__ import annotations

import json
import sys
import urllib.request


def get_pypi_sha256(package: str, version: str) -> str:
    """Get the sdist sha256 for a package from PyPI."""
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())

    for file_info in data.get("urls", []):
        if file_info["filename"].endswith(".tar.gz"):
            return file_info["digests"]["sha256"]

    for file_info in data.get("urls", []):
        if file_info["packagetype"] == "sdist":
            return file_info["digests"]["sha256"]

    raise ValueError(f"No sdist found for {package}=={version}")


def generate_formula(version: str) -> str:
    """Generate the Homebrew formula."""
    sha256 = get_pypi_sha256("langfuse-cli", version)

    return f'''class LangfuseCli < Formula
  include Language::Python::Virtualenv

  desc "CLI tool for Langfuse LLM observability platform"
  homepage "https://github.com/aviadshiber/langfuse-cli"
  url "https://files.pythonhosted.org/packages/source/l/langfuse-cli/langfuse_cli-{version}.tar.gz"
  sha256 "{sha256}"
  license "MIT"

  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install buildpath
    bin.install_symlink Dir[libexec/"bin/lf"]
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
