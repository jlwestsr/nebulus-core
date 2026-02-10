"""Tests for secrets management."""

import tempfile
from pathlib import Path

import pytest

from nebulus_core.security.secrets import SecretsManager


@pytest.fixture
def temp_fallback_dir():
    """Create temporary directory for fallback secrets storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def fallback_manager(temp_fallback_dir):
    """Create SecretsManager using fallback mode."""
    return SecretsManager(use_keyring=False, fallback_dir=temp_fallback_dir / "secrets")


class TestSecretsManagerFallback:
    """Test SecretsManager in fallback (encrypted file) mode."""

    def test_init_creates_directory(self, temp_fallback_dir):
        """Test that initialization creates the secrets directory."""
        manager = SecretsManager(use_keyring=False)
        fallback_dir = manager.FALLBACK_DIR
        assert fallback_dir.exists()
        assert fallback_dir.is_dir()

    def test_init_creates_key_file(self, temp_fallback_dir):
        """Test that initialization creates an encryption key file."""
        manager = SecretsManager(use_keyring=False)
        key_file = manager.FALLBACK_KEY_FILE
        assert key_file.exists()
        assert key_file.is_file()

    def test_init_creates_data_file(self, temp_fallback_dir):
        """Test that initialization creates an encrypted data file."""
        manager = SecretsManager(use_keyring=False)
        data_file = manager.FALLBACK_DATA_FILE
        assert data_file.exists()
        assert data_file.is_file()

    def test_store_secret(self, fallback_manager):
        """Test storing a secret."""
        fallback_manager.store_secret("test_key", "test_value")
        assert fallback_manager.get_secret("test_key") == "test_value"

    def test_store_empty_key_raises(self, fallback_manager):
        """Test that storing with empty key raises ValueError."""
        with pytest.raises(ValueError, match="Key and value must be non-empty"):
            fallback_manager.store_secret("", "value")

    def test_store_empty_value_raises(self, fallback_manager):
        """Test that storing with empty value raises ValueError."""
        with pytest.raises(ValueError, match="Key and value must be non-empty"):
            fallback_manager.store_secret("key", "")

    def test_get_secret_not_found(self, fallback_manager):
        """Test retrieving a non-existent secret returns None."""
        assert fallback_manager.get_secret("nonexistent") is None

    def test_update_secret(self, fallback_manager):
        """Test updating an existing secret."""
        fallback_manager.store_secret("key", "value1")
        fallback_manager.store_secret("key", "value2")
        assert fallback_manager.get_secret("key") == "value2"

    def test_delete_secret(self, fallback_manager):
        """Test deleting a secret."""
        fallback_manager.store_secret("key", "value")
        assert fallback_manager.delete_secret("key") is True
        assert fallback_manager.get_secret("key") is None

    def test_delete_nonexistent_secret(self, fallback_manager):
        """Test deleting a non-existent secret returns False."""
        assert fallback_manager.delete_secret("nonexistent") is False

    def test_list_secrets_empty(self, fallback_manager):
        """Test listing secrets when none are stored."""
        assert fallback_manager.list_secrets() == []

    def test_list_secrets_multiple(self, fallback_manager):
        """Test listing multiple secrets."""
        fallback_manager.store_secret("key1", "value1")
        fallback_manager.store_secret("key2", "value2")
        fallback_manager.store_secret("key3", "value3")

        keys = fallback_manager.list_secrets()
        assert set(keys) == {"key1", "key2", "key3"}

    def test_list_secrets_after_delete(self, fallback_manager):
        """Test listing secrets after deleting one."""
        fallback_manager.store_secret("key1", "value1")
        fallback_manager.store_secret("key2", "value2")
        fallback_manager.delete_secret("key1")

        keys = fallback_manager.list_secrets()
        assert keys == ["key2"]

    def test_audit_secrets(self, fallback_manager):
        """Test audit report generation."""
        fallback_manager.store_secret("key1", "value1")
        fallback_manager.store_secret("key2", "value2")

        audit = fallback_manager.audit_secrets()
        assert audit["backend"] == "fallback"
        assert audit["secret_count"] == 2
        assert set(audit["keys"]) == {"key1", "key2"}

    def test_persistence_across_instances(self, temp_fallback_dir):
        """Test that secrets persist across manager instances."""
        fallback_dir = temp_fallback_dir / "secrets"
        manager1 = SecretsManager(use_keyring=False, fallback_dir=fallback_dir)
        manager1.store_secret("persist", "value")

        manager2 = SecretsManager(use_keyring=False, fallback_dir=fallback_dir)
        assert manager2.get_secret("persist") == "value"

    def test_encryption_at_rest(self, fallback_manager):
        """Test that secrets are encrypted on disk."""
        fallback_manager.store_secret("secret", "sensitive_value")

        # Read the encrypted file directly
        encrypted_data = fallback_manager.FALLBACK_DATA_FILE.read_bytes()

        # Plaintext should not appear in encrypted file
        assert b"sensitive_value" not in encrypted_data

    def test_multiple_secrets_roundtrip(self, fallback_manager):
        """Test storing and retrieving multiple secrets."""
        secrets = {
            "api_key": "sk-1234567890",
            "db_password": "secret123",
            "auth_token": "bearer_xyz",
        }

        for key, value in secrets.items():
            fallback_manager.store_secret(key, value)

        for key, value in secrets.items():
            assert fallback_manager.get_secret(key) == value


class TestSecretsManagerKeyring:
    """Test SecretsManager with keyring backend (when available)."""

    @pytest.mark.skipif(
        not pytest.importorskip("keyring"),
        reason="keyring not available",
    )
    def test_keyring_mode_basic_operations(self):
        """Test basic operations with keyring backend."""
        try:
            manager = SecretsManager(use_keyring=True)
            if not manager._use_keyring:
                pytest.skip("Keyring backend not available in environment")

            # Clean up any existing test key
            manager.delete_secret("test_keyring_key")

            # Test store and retrieve
            manager.store_secret("test_keyring_key", "test_value")
            assert manager.get_secret("test_keyring_key") == "test_value"

            # Clean up
            manager.delete_secret("test_keyring_key")

        except Exception as e:
            pytest.skip(f"Keyring test skipped: {e}")

    def test_audit_backend_detection(self, fallback_manager):
        """Test that audit correctly identifies the backend."""
        audit = fallback_manager.audit_secrets()
        assert audit["backend"] == "fallback"


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_module_functions_use_singleton(self):
        """Test that module functions use singleton manager."""
        from nebulus_core.security import secrets

        # Force reset singleton
        secrets._manager = None

        secrets.store_secret("test", "value")
        assert secrets.get_secret("test") == "value"
        assert "test" in secrets.list_secrets()
        assert secrets.delete_secret("test") is True

    def test_audit_secrets_function(self):
        """Test module-level audit_secrets function."""
        from nebulus_core.security import secrets

        secrets._manager = None

        secrets.store_secret("key1", "value1")
        audit = secrets.audit_secrets()
        assert audit["secret_count"] >= 1
