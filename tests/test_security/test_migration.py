"""Tests for secrets migration."""

import tempfile
from pathlib import Path

import pytest

from nebulus_core.security.migration import SecretsMigrator, migrate_secrets
from nebulus_core.security.secrets import SecretsManager


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def migrator(temp_dir):
    """Create SecretsMigrator with isolated secrets storage."""
    secrets_mgr = SecretsManager(use_keyring=False, fallback_dir=temp_dir / "secrets")
    return SecretsMigrator(secrets_manager=secrets_mgr)


class TestSecretsMigrator:
    """Test SecretsMigrator functionality."""

    def test_is_secret_key_api_key(self):
        """Test identifying API key patterns."""
        migrator = SecretsMigrator()
        assert migrator.is_secret_key("API_KEY")
        assert migrator.is_secret_key("api_key")
        assert migrator.is_secret_key("OPENAI_API_KEY")
        assert migrator.is_secret_key("google_api_key")

    def test_is_secret_key_token(self):
        """Test identifying token patterns."""
        migrator = SecretsMigrator()
        assert migrator.is_secret_key("AUTH_TOKEN")
        assert migrator.is_secret_key("access_token")
        assert migrator.is_secret_key("GITHUB_TOKEN")

    def test_is_secret_key_password(self):
        """Test identifying password patterns."""
        migrator = SecretsMigrator()
        assert migrator.is_secret_key("PASSWORD")
        assert migrator.is_secret_key("DB_PASSWORD")
        assert migrator.is_secret_key("admin_password")

    def test_is_secret_key_secret(self):
        """Test identifying secret patterns."""
        migrator = SecretsMigrator()
        assert migrator.is_secret_key("SECRET")
        assert migrator.is_secret_key("CLIENT_SECRET")
        assert migrator.is_secret_key("app_secret")

    def test_is_not_secret_key_normal(self):
        """Test that normal keys are not identified as secrets."""
        migrator = SecretsMigrator()
        assert not migrator.is_secret_key("DEBUG")
        assert not migrator.is_secret_key("PORT")
        assert not migrator.is_secret_key("DATABASE_URL")
        assert not migrator.is_secret_key("LOG_LEVEL")

    def test_extract_from_env_file_simple(self, temp_dir, migrator):
        """Test extracting secrets from simple .env file."""
        env_file = temp_dir / ".env"
        env_file.write_text("""
API_KEY=sk-1234567890
SECRET_TOKEN=abc123xyz
DEBUG=true
PORT=8000
        """)

        secrets = migrator.extract_from_env_file(env_file)

        assert "api_key" in secrets
        assert secrets["api_key"] == "sk-1234567890"
        assert "secret_token" in secrets
        assert secrets["secret_token"] == "abc123xyz"
        assert "debug" not in secrets
        assert "port" not in secrets

    def test_extract_from_env_file_with_quotes(self, temp_dir, migrator):
        """Test extracting secrets with quoted values."""
        env_file = temp_dir / ".env"
        env_file.write_text("""
API_KEY="value-with-quotes"
SECRET='single-quotes'
TOKEN=no-quotes
        """)

        secrets = migrator.extract_from_env_file(env_file)

        assert "api_key" in secrets
        assert "secret" in secrets
        assert "token" in secrets

    def test_extract_from_env_file_empty_values(self, temp_dir, migrator):
        """Test that empty values are not extracted."""
        env_file = temp_dir / ".env"
        env_file.write_text("""
API_KEY=
SECRET=
TOKEN=value
        """)

        secrets = migrator.extract_from_env_file(env_file)

        assert "api_key" not in secrets
        assert "secret" not in secrets
        assert "token" in secrets

    def test_extract_from_yaml_file(self, temp_dir, migrator):
        """Test extracting secrets from YAML file."""
        yaml_file = temp_dir / "config.yml"
        yaml_file.write_text("""
api_key: sk-1234567890
secret: abc123
port: 8000
debug: true
        """)

        secrets = migrator.extract_from_yaml_file(yaml_file)

        assert "api_key" in secrets
        assert secrets["api_key"] == "sk-1234567890"
        assert "secret" in secrets
        assert "port" not in secrets
        assert "debug" not in secrets

    def test_extract_from_nonexistent_file(self, temp_dir, migrator):
        """Test extracting from non-existent file returns empty dict."""
        secrets = migrator.extract_from_env_file(temp_dir / "nonexistent.env")
        assert secrets == {}

        secrets = migrator.extract_from_yaml_file(temp_dir / "nonexistent.yml")
        assert secrets == {}

    def test_migrate_from_env_file(self, temp_dir, migrator):
        """Test migrating secrets from .env file."""
        env_file = temp_dir / ".env"
        env_file.write_text("""
OPENAI_API_KEY=sk-1234567890abcdefghijklmnop
DATABASE_PASSWORD=secret123
DEBUG=true
        """)

        migrated, errors = migrator.migrate_from_file(env_file)

        assert migrated == 2
        assert len(errors) == 0

        # Verify secrets were stored
        assert migrator._secrets.get_secret("openai_api_key") == "sk-1234567890abcdefghijklmnop"
        assert migrator._secrets.get_secret("database_password") == "secret123"
        assert migrator._secrets.get_secret("debug") is None

    def test_migrate_from_yaml_file(self, temp_dir, migrator):
        """Test migrating secrets from YAML file."""
        yaml_file = temp_dir / "config.yaml"
        yaml_file.write_text("""
api_key: test-key-123
secret: test-secret
port: 8000
        """)

        migrated, errors = migrator.migrate_from_file(yaml_file)

        assert migrated == 2
        assert len(errors) == 0

    def test_migrate_from_directory(self, temp_dir, migrator):
        """Test migrating secrets from directory."""
        (temp_dir / ".env").write_text("API_KEY=key1")
        (temp_dir / "config.yml").write_text("secret: secret1")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / ".env.local").write_text("TOKEN=token1")

        result = migrator.migrate_from_directory(temp_dir, recursive=True)

        assert result.secrets_found == 3
        assert result.secrets_migrated == 3
        assert len(result.source_files) == 3
        assert len(result.errors) == 0

    def test_migrate_from_directory_non_recursive(self, temp_dir, migrator):
        """Test migrating from directory non-recursively."""
        (temp_dir / ".env").write_text("API_KEY=key1")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / ".env").write_text("TOKEN=token1")

        result = migrator.migrate_from_directory(temp_dir, recursive=False)

        assert result.secrets_found == 1
        assert result.secrets_migrated == 1

    def test_migrate_from_directory_skips_excluded(self, temp_dir, migrator):
        """Test that migration skips excluded directories."""
        (temp_dir / ".git").mkdir()
        (temp_dir / "node_modules").mkdir()
        (temp_dir / ".git" / ".env").write_text("SECRET=git-secret")
        (temp_dir / "node_modules" / ".env").write_text("SECRET=node-secret")
        (temp_dir / ".env").write_text("API_KEY=real-key")

        result = migrator.migrate_from_directory(temp_dir, recursive=True)

        # Should only find the root .env file
        assert result.secrets_found == 1
        assert result.secrets_migrated == 1

    def test_migrate_from_directory_no_secrets(self, temp_dir, migrator):
        """Test migrating from directory with no secrets."""
        (temp_dir / "app.py").write_text("print('hello')")
        (temp_dir / "README.md").write_text("# Project")

        result = migrator.migrate_from_directory(temp_dir, recursive=True)

        assert result.secrets_found == 0
        assert result.secrets_migrated == 0
        assert len(result.source_files) == 0

    def test_migrate_handles_duplicate_keys(self, temp_dir, migrator):
        """Test that migrating duplicate keys updates the value."""
        (temp_dir / "file1.env").write_text("API_KEY=value1")
        (temp_dir / "file2.env").write_text("API_KEY=value2")

        result = migrator.migrate_from_directory(temp_dir, recursive=True)

        # Both should be migrated (second overwrites first)
        assert result.secrets_migrated == 2
        # Final value should be from second file
        assert migrator._secrets.get_secret("api_key") == "value2"


class TestMigrateSecretsFunction:
    """Test the migrate_secrets convenience function."""

    def test_migrate_file(self):
        """Test migrating a single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            env_file = tmpdir / ".env"
            env_file.write_text("API_KEY=test123")

            result = migrate_secrets(env_file)

            assert result.secrets_migrated == 1
            assert len(result.source_files) == 1

    def test_migrate_directory(self):
        """Test migrating a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / ".env").write_text("API_KEY=key1")
            (tmpdir / "config.yml").write_text("secret: secret1")

            result = migrate_secrets(tmpdir)

            assert result.secrets_migrated == 2

    def test_migrate_string_path(self):
        """Test that function accepts string paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / ".env").write_text("API_KEY=test")

            result = migrate_secrets(str(tmpdir))

            assert result.secrets_migrated == 1

    def test_migrate_nonexistent_path_raises(self):
        """Test that migrating non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            migrate_secrets("/nonexistent/path")

    def test_migrate_result_structure(self):
        """Test that MigrationResult has correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            (tmpdir / ".env").write_text("API_KEY=test")

            result = migrate_secrets(tmpdir)

            assert hasattr(result, "secrets_found")
            assert hasattr(result, "secrets_migrated")
            assert hasattr(result, "errors")
            assert hasattr(result, "source_files")
            assert isinstance(result.errors, list)
            assert isinstance(result.source_files, list)
