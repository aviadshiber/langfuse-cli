"""Configuration resolution: flags -> env -> config file -> keyring -> defaults."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_HOST = "https://cloud.langfuse.com"
CONFIG_DIR = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "langfuse"
CONFIG_FILE = CONFIG_DIR / "config.toml"
KEYRING_SERVICE = "langfuse-cli"


@dataclass(frozen=True)
class LangfuseConfig:
    """Resolved Langfuse configuration."""

    host: str = DEFAULT_HOST
    public_key: str = ""
    secret_key: str = ""
    default_limit: int = 50
    default_output: str = "table"


def _load_toml(path: Path) -> dict[str, Any]:
    """Load TOML config file, return empty dict if missing."""
    if not path.exists():
        return {}
    try:
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore[no-redef]
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        logger.warning("Failed to parse config file: %s", path)
        return {}


def _get_from_keyring(account: str) -> str | None:
    """Retrieve a secret from the system keyring, return None if unavailable."""
    try:
        import keyring

        value: str | None = keyring.get_password(KEYRING_SERVICE, account)
        return value
    except Exception:
        logger.debug("Keyring unavailable for account: %s", account)
        return None


def set_keyring_secret(account: str, secret: str) -> bool:
    """Store a secret in the system keyring. Returns True on success."""
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, account, secret)
        return True
    except Exception:
        logger.warning("Failed to store secret in keyring for account: %s", account)
        return False


def _resolve(
    flag_value: str | None,
    env_var: str,
    toml_value: str | None,
    keyring_account: str | None = None,
    default: str = "",
) -> str:
    """Resolve a config value using the precedence chain."""
    if flag_value:
        return flag_value
    env = os.getenv(env_var)
    if env:
        return env
    if toml_value:
        return toml_value
    if keyring_account:
        keyring_val = _get_from_keyring(keyring_account)
        if keyring_val:
            return keyring_val
    return default


def resolve_config(
    *,
    host: str | None = None,
    public_key: str | None = None,
    secret_key: str | None = None,
    profile: str | None = None,
) -> LangfuseConfig:
    """Resolve configuration from all sources using gh-ux precedence.

    Resolution order: flags -> env vars -> config file -> keyring -> defaults.
    """
    toml_data = _load_toml(CONFIG_FILE)

    # Determine which profile section to read
    profile_name = profile or os.getenv("LANGFUSE_PROFILE", "default")
    if profile_name == "default":
        profile_data = toml_data.get("default", {})
    else:
        profile_data = toml_data.get("profiles", {}).get(profile_name, {})

    defaults_data = toml_data.get("defaults", {})

    # Build the keyring account prefix for profile-scoped secrets
    keyring_prefix = f"{profile_name}/"

    resolved_host = _resolve(
        host,
        "LANGFUSE_HOST",
        profile_data.get("host"),
        default=DEFAULT_HOST,
    )
    # Also check LANGFUSE_BASEURL for compatibility with SDK
    if resolved_host == DEFAULT_HOST:
        base_url = os.getenv("LANGFUSE_BASEURL")
        if base_url:
            resolved_host = base_url

    resolved_public = _resolve(
        public_key,
        "LANGFUSE_PUBLIC_KEY",
        profile_data.get("public_key"),
        keyring_account=f"{keyring_prefix}public_key",
    )

    resolved_secret = _resolve(
        secret_key,
        "LANGFUSE_SECRET_KEY",
        profile_data.get("secret_key"),
        keyring_account=f"{keyring_prefix}secret_key",
    )

    return LangfuseConfig(
        host=resolved_host,
        public_key=resolved_public,
        secret_key=resolved_secret,
        default_limit=int(defaults_data.get("limit", 50)),
        default_output=str(defaults_data.get("output", "table")),
    )


def ensure_config_dir() -> Path:
    """Create the config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR
