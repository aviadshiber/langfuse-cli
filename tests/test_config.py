"""Tests for config resolution module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from langfuse_cli.config import (
    DEFAULT_HOST,
    KEYRING_SERVICE,
    LangfuseConfig,
    _get_from_keyring,
    _load_toml,
    _resolve,
    ensure_config_dir,
    resolve_config,
    set_keyring_secret,
)


class TestLangfuseConfig:
    """Test LangfuseConfig dataclass."""

    def test_default_values(self):
        """Test that dataclass has correct defaults."""
        config = LangfuseConfig()
        assert config.host == DEFAULT_HOST
        assert config.public_key == ""
        assert config.secret_key == ""
        assert config.default_limit == 50
        assert config.default_output == "table"

    def test_custom_values(self):
        """Test that custom values can be set."""
        config = LangfuseConfig(
            host="https://custom.example.com",
            public_key="pk-test",
            secret_key="sk-test",
            default_limit=100,
            default_output="json",
        )
        assert config.host == "https://custom.example.com"
        assert config.public_key == "pk-test"
        assert config.secret_key == "sk-test"
        assert config.default_limit == 100
        assert config.default_output == "json"

    def test_immutability(self):
        """Test that config is frozen (immutable)."""
        config = LangfuseConfig()
        with pytest.raises(AttributeError):
            config.host = "https://new-host.com"  # type: ignore[misc]


class TestLoadToml:
    """Test TOML file loading."""

    def test_load_missing_file(self, tmp_path):
        """Test that missing file returns empty dict."""
        missing_file = tmp_path / "missing.toml"
        result = _load_toml(missing_file)
        assert result == {}

    def test_load_valid_toml(self, tmp_path):
        """Test loading valid TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[default]
host = "https://example.com"
public_key = "pk-123"

[profiles.staging]
host = "https://staging.example.com"
"""
        )
        result = _load_toml(config_file)
        assert result["default"]["host"] == "https://example.com"
        assert result["default"]["public_key"] == "pk-123"
        assert result["profiles"]["staging"]["host"] == "https://staging.example.com"

    def test_load_invalid_toml(self, tmp_path, caplog):
        """Test that invalid TOML returns empty dict and logs warning."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("invalid toml content [[[")
        result = _load_toml(config_file)
        assert result == {}
        assert "Failed to parse config file" in caplog.text

    def test_load_empty_file(self, tmp_path):
        """Test loading empty TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        result = _load_toml(config_file)
        assert result == {}


class TestKeyring:
    """Test keyring integration."""

    def test_get_from_keyring_success(self):
        """Test successful keyring retrieval."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "secret-value"

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = _get_from_keyring("test-account")

        assert result == "secret-value"
        mock_keyring.get_password.assert_called_once_with(KEYRING_SERVICE, "test-account")

    def test_get_from_keyring_missing(self):
        """Test keyring retrieval when key not found."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = _get_from_keyring("missing-account")

        assert result is None

    def test_get_from_keyring_unavailable(self, caplog):
        """Test keyring retrieval when keyring not available."""
        import logging

        # Set log level to DEBUG to capture debug messages
        caplog.set_level(logging.DEBUG)

        # Mock keyring.get_password to raise an exception
        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = Exception("Keyring error")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = _get_from_keyring("test-account")

        assert result is None
        assert "Keyring unavailable" in caplog.text

    def test_get_from_keyring_error(self):
        """Test keyring retrieval when error occurs."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = Exception("Keyring error")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = _get_from_keyring("test-account")

        assert result is None

    def test_set_keyring_secret_success(self):
        """Test successful keyring storage."""
        mock_keyring = MagicMock()

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = set_keyring_secret("test-account", "secret-value")

        assert result is True
        mock_keyring.set_password.assert_called_once_with(KEYRING_SERVICE, "test-account", "secret-value")

    def test_set_keyring_secret_unavailable(self, caplog):
        """Test keyring storage when keyring not available."""
        # Mock keyring.set_password to raise an exception
        mock_keyring = MagicMock()
        mock_keyring.set_password.side_effect = Exception("Keyring error")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = set_keyring_secret("test-account", "secret-value")

        assert result is False
        assert "Failed to store secret in keyring" in caplog.text

    def test_set_keyring_secret_error(self, caplog):
        """Test keyring storage when error occurs."""
        mock_keyring = MagicMock()
        mock_keyring.set_password.side_effect = Exception("Keyring error")

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = set_keyring_secret("test-account", "secret-value")

        assert result is False
        assert "Failed to store secret in keyring" in caplog.text


class TestResolve:
    """Test _resolve precedence chain."""

    def test_flag_overrides_all(self, monkeypatch):
        """Test that flag value takes highest precedence."""
        monkeypatch.setenv("TEST_VAR", "env-value")
        result = _resolve(
            flag_value="flag-value",
            env_var="TEST_VAR",
            toml_value="toml-value",
            default="default-value",
        )
        assert result == "flag-value"

    def test_env_overrides_toml_and_default(self, monkeypatch):
        """Test that env var overrides TOML and default."""
        monkeypatch.setenv("TEST_VAR", "env-value")
        result = _resolve(
            flag_value=None,
            env_var="TEST_VAR",
            toml_value="toml-value",
            default="default-value",
        )
        assert result == "env-value"

    def test_toml_overrides_default(self, monkeypatch):
        """Test that TOML value overrides default."""
        monkeypatch.delenv("TEST_VAR", raising=False)
        result = _resolve(
            flag_value=None,
            env_var="TEST_VAR",
            toml_value="toml-value",
            default="default-value",
        )
        assert result == "toml-value"

    def test_keyring_overrides_default(self, monkeypatch):
        """Test that keyring value overrides default."""
        monkeypatch.delenv("TEST_VAR", raising=False)
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "keyring-value"

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = _resolve(
                flag_value=None,
                env_var="TEST_VAR",
                toml_value=None,
                keyring_account="test-account",
                default="default-value",
            )

        assert result == "keyring-value"

    def test_toml_overrides_keyring(self, monkeypatch):
        """Test that TOML value overrides keyring."""
        monkeypatch.delenv("TEST_VAR", raising=False)
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "keyring-value"

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            result = _resolve(
                flag_value=None,
                env_var="TEST_VAR",
                toml_value="toml-value",
                keyring_account="test-account",
                default="default-value",
            )

        assert result == "toml-value"

    def test_default_when_nothing_set(self, monkeypatch):
        """Test that default is returned when nothing else is set."""
        monkeypatch.delenv("TEST_VAR", raising=False)
        result = _resolve(
            flag_value=None,
            env_var="TEST_VAR",
            toml_value=None,
            default="default-value",
        )
        assert result == "default-value"

    def test_empty_string_default(self, monkeypatch):
        """Test that empty string default works."""
        monkeypatch.delenv("TEST_VAR", raising=False)
        result = _resolve(
            flag_value=None,
            env_var="TEST_VAR",
            toml_value=None,
            default="",
        )
        assert result == ""


class TestResolveConfig:
    """Test resolve_config function."""

    def test_all_defaults(self, tmp_path, monkeypatch):
        """Test config resolution with all defaults."""
        # Point to empty temp dir
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        # Clear all env vars
        env_vars = [
            "LANGFUSE_HOST",
            "LANGFUSE_BASEURL",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_PROFILE",
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)
        # Mock keyring to prevent picking up real system keyring values
        monkeypatch.setattr("langfuse_cli.config._get_from_keyring", lambda account: None)

        config = resolve_config()

        assert config.host == DEFAULT_HOST
        assert config.public_key == ""
        assert config.secret_key == ""
        assert config.default_limit == 50
        assert config.default_output == "table"

    def test_env_vars_override_defaults(self, tmp_path, monkeypatch):
        """Test that env vars override defaults."""
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.setenv("LANGFUSE_HOST", "https://env-host.com")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-env")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-env")

        config = resolve_config()

        assert config.host == "https://env-host.com"
        assert config.public_key == "pk-env"
        assert config.secret_key == "sk-env"

    def test_baseurl_env_var(self, tmp_path, monkeypatch):
        """Test LANGFUSE_BASEURL env var for SDK compatibility."""
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.setenv("LANGFUSE_BASEURL", "https://baseurl-host.com")
        monkeypatch.delenv("LANGFUSE_HOST", raising=False)

        config = resolve_config()

        assert config.host == "https://baseurl-host.com"

    def test_host_overrides_baseurl(self, tmp_path, monkeypatch):
        """Test that LANGFUSE_HOST takes precedence over LANGFUSE_BASEURL."""
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.setenv("LANGFUSE_HOST", "https://host.com")
        monkeypatch.setenv("LANGFUSE_BASEURL", "https://baseurl.com")

        config = resolve_config()

        assert config.host == "https://host.com"

    def test_flags_override_env_vars(self, tmp_path, monkeypatch):
        """Test that flag values override env vars."""
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.setenv("LANGFUSE_HOST", "https://env-host.com")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-env")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-env")

        config = resolve_config(
            host="https://flag-host.com",
            public_key="pk-flag",
            secret_key="sk-flag",
        )

        assert config.host == "https://flag-host.com"
        assert config.public_key == "pk-flag"
        assert config.secret_key == "sk-flag"

    def test_toml_config_loading(self, tmp_path, monkeypatch):
        """Test loading from TOML config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[default]
host = "https://toml-host.com"
public_key = "pk-toml"
secret_key = "sk-toml"

[defaults]
limit = 100
output = "json"
"""
        )
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)
        for var in ["LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            monkeypatch.delenv(var, raising=False)

        config = resolve_config()

        assert config.host == "https://toml-host.com"
        assert config.public_key == "pk-toml"
        assert config.secret_key == "sk-toml"
        assert config.default_limit == 100
        assert config.default_output == "json"

    def test_profile_selection_from_env(self, tmp_path, monkeypatch):
        """Test profile selection via LANGFUSE_PROFILE env var."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[default]
host = "https://default-host.com"
public_key = "pk-default"

[profiles.staging]
host = "https://staging-host.com"
public_key = "pk-staging"
secret_key = "sk-staging"
"""
        )
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)
        monkeypatch.setenv("LANGFUSE_PROFILE", "staging")
        for var in ["LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            monkeypatch.delenv(var, raising=False)

        config = resolve_config()

        assert config.host == "https://staging-host.com"
        assert config.public_key == "pk-staging"
        assert config.secret_key == "sk-staging"

    def test_profile_selection_from_flag(self, tmp_path, monkeypatch):
        """Test profile selection via profile parameter."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[default]
host = "https://default-host.com"

[profiles.production]
host = "https://prod-host.com"
public_key = "pk-prod"
"""
        )
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)
        monkeypatch.delenv("LANGFUSE_PROFILE", raising=False)
        monkeypatch.delenv("LANGFUSE_HOST", raising=False)
        for var in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            monkeypatch.delenv(var, raising=False)

        # Mock keyring to prevent picking up real system keyring values
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            config = resolve_config(profile="production")

        assert config.host == "https://prod-host.com"
        assert config.public_key == "pk-prod"

    def test_missing_profile_returns_empty(self, tmp_path, monkeypatch):
        """Test that missing profile section returns defaults."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[default]
host = "https://default-host.com"
"""
        )
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)
        monkeypatch.delenv("LANGFUSE_HOST", raising=False)
        for var in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            monkeypatch.delenv(var, raising=False)

        # Mock keyring to prevent picking up real system keyring values
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            config = resolve_config(profile="nonexistent")

        assert config.host == DEFAULT_HOST
        assert config.public_key == ""

    def test_keyring_integration(self, tmp_path, monkeypatch):
        """Test keyring fallback for secrets."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[default]
host = "https://toml-host.com"
"""
        )
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)
        for var in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            monkeypatch.delenv(var, raising=False)

        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = lambda service, account: {
            "default/public_key": "pk-keyring",
            "default/secret_key": "sk-keyring",
        }.get(account)

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            config = resolve_config()

        assert config.public_key == "pk-keyring"
        assert config.secret_key == "sk-keyring"

    def test_keyring_with_custom_profile(self, tmp_path, monkeypatch):
        """Test keyring with custom profile prefix."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("[profiles.staging]")
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)
        for var in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            monkeypatch.delenv(var, raising=False)

        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = lambda service, account: {
            "staging/public_key": "pk-staging-keyring",
            "staging/secret_key": "sk-staging-keyring",
        }.get(account)

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            config = resolve_config(profile="staging")

        assert config.public_key == "pk-staging-keyring"
        assert config.secret_key == "sk-staging-keyring"

    def test_invalid_toml_returns_defaults(self, tmp_path, monkeypatch):
        """Test that invalid TOML file returns defaults gracefully."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("invalid toml [[[")
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)
        for var in ["LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            monkeypatch.delenv(var, raising=False)
        # Mock keyring to prevent picking up real system keyring values
        monkeypatch.setattr("langfuse_cli.config._get_from_keyring", lambda account: None)

        config = resolve_config()

        assert config.host == DEFAULT_HOST
        assert config.public_key == ""
        assert config.secret_key == ""

    def test_missing_config_file_returns_defaults(self, tmp_path, monkeypatch):
        """Test that missing config file returns defaults gracefully."""
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", tmp_path / "nonexistent.toml")
        for var in ["LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]:
            monkeypatch.delenv(var, raising=False)
        # Mock keyring to prevent picking up real system keyring values
        monkeypatch.setattr("langfuse_cli.config._get_from_keyring", lambda account: None)

        config = resolve_config()

        assert config.host == DEFAULT_HOST
        assert config.public_key == ""
        assert config.secret_key == ""

    def test_precedence_chain_complete(self, tmp_path, monkeypatch):
        """Test complete precedence chain: flag > env > toml > keyring > default."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[default]
host = "https://toml-host.com"
public_key = "pk-toml"
"""
        )
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-env")
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = lambda service, account: {
            "default/public_key": None,  # Already set via env
            "default/secret_key": "sk-keyring",
        }.get(account)

        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            config = resolve_config(host="https://flag-host.com")

        # Flag overrides toml for host
        assert config.host == "https://flag-host.com"
        # Env overrides toml for public_key
        assert config.public_key == "pk-env"
        # Keyring provides secret_key (nothing else set)
        assert config.secret_key == "sk-keyring"

    def test_defaults_limit_and_output(self, tmp_path, monkeypatch):
        """Test that defaults section sets limit and output."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[defaults]
limit = 25
output = "json"
"""
        )
        monkeypatch.setattr("langfuse_cli.config.CONFIG_FILE", config_file)

        config = resolve_config()

        assert config.default_limit == 25
        assert config.default_output == "json"


class TestEnsureConfigDir:
    """Test ensure_config_dir function."""

    def test_creates_directory(self, tmp_path, monkeypatch):
        """Test that config directory is created."""
        config_dir = tmp_path / "langfuse"
        monkeypatch.setattr("langfuse_cli.config.CONFIG_DIR", config_dir)

        result = ensure_config_dir()

        assert result == config_dir
        assert config_dir.exists()
        assert config_dir.is_dir()

    def test_existing_directory(self, tmp_path, monkeypatch):
        """Test that existing directory is not affected."""
        config_dir = tmp_path / "langfuse"
        config_dir.mkdir(parents=True)
        test_file = config_dir / "test.txt"
        test_file.write_text("existing content")

        monkeypatch.setattr("langfuse_cli.config.CONFIG_DIR", config_dir)

        result = ensure_config_dir()

        assert result == config_dir
        assert test_file.exists()
        assert test_file.read_text() == "existing content"

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        """Test that parent directories are created."""
        config_dir = tmp_path / "nested" / "path" / "langfuse"
        monkeypatch.setattr("langfuse_cli.config.CONFIG_DIR", config_dir)

        result = ensure_config_dir()

        assert result == config_dir
        assert config_dir.exists()
