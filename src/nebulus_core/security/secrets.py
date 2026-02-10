"""Unified secrets management with keyring backend and encrypted fallback."""

import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

try:
    import keyring
    import keyring.errors

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False


class SecretsManager:
    """Unified interface for storing and retrieving secrets.

    Uses platform keystores (macOS Keychain, Linux Secret Service) via keyring
    when available. Falls back to Fernet-encrypted file store for environments
    without keyring support.

    All secrets are decrypted only in-memory and never written to disk in plaintext.
    """

    SERVICE_NAME = "nebulus"
    FALLBACK_DIR = Path.home() / ".nebulus" / "secrets"
    FALLBACK_KEY_FILE = FALLBACK_DIR / ".key"
    FALLBACK_DATA_FILE = FALLBACK_DIR / "secrets.enc"

    def __init__(self, use_keyring: bool | None = None) -> None:
        """Initialize the secrets manager.

        Args:
            use_keyring: Force keyring on (True) or fallback mode (False).
                If None (default), auto-detect keyring availability.
        """
        if use_keyring is None:
            self._use_keyring = KEYRING_AVAILABLE and self._test_keyring()
        else:
            self._use_keyring = use_keyring and KEYRING_AVAILABLE

        if not self._use_keyring:
            self._init_fallback()

    def _test_keyring(self) -> bool:
        """Test if keyring backend is accessible.

        Returns:
            True if keyring is functional, False otherwise.
        """
        try:
            # Try to access keyring - this will fail if no backend is available
            keyring.get_password(self.SERVICE_NAME, "__test__")
            return True
        except keyring.errors.NoKeyringError:
            return False
        except Exception:
            # Any other error means keyring exists but failed for other reasons
            return True

    def _init_fallback(self) -> None:
        """Initialize encrypted file fallback store."""
        self.FALLBACK_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Generate or load encryption key
        if not self.FALLBACK_KEY_FILE.exists():
            key = Fernet.generate_key()
            self.FALLBACK_KEY_FILE.write_bytes(key)
            self.FALLBACK_KEY_FILE.chmod(0o600)
        else:
            key = self.FALLBACK_KEY_FILE.read_bytes()

        self._cipher = Fernet(key)

        # Initialize empty data file if needed
        if not self.FALLBACK_DATA_FILE.exists():
            self._write_fallback_data({})

    def _read_fallback_data(self) -> dict[str, str]:
        """Read and decrypt fallback data file.

        Returns:
            Dictionary of key-value pairs.
        """
        if not self.FALLBACK_DATA_FILE.exists():
            return {}

        encrypted = self.FALLBACK_DATA_FILE.read_bytes()
        decrypted = self._cipher.decrypt(encrypted)
        return json.loads(decrypted.decode("utf-8"))

    def _write_fallback_data(self, data: dict[str, str]) -> None:
        """Encrypt and write fallback data file.

        Args:
            data: Dictionary of key-value pairs to encrypt and store.
        """
        json_data = json.dumps(data).encode("utf-8")
        encrypted = self._cipher.encrypt(json_data)
        self.FALLBACK_DATA_FILE.write_bytes(encrypted)
        self.FALLBACK_DATA_FILE.chmod(0o600)

    def store_secret(self, key: str, value: str) -> None:
        """Store a secret.

        Args:
            key: Secret identifier.
            value: Secret value (will be encrypted).

        Raises:
            ValueError: If key or value is empty.
        """
        if not key or not value:
            raise ValueError("Key and value must be non-empty strings")

        if self._use_keyring:
            keyring.set_password(self.SERVICE_NAME, key, value)
        else:
            data = self._read_fallback_data()
            data[key] = value
            self._write_fallback_data(data)

    def get_secret(self, key: str) -> str | None:
        """Retrieve a secret.

        Args:
            key: Secret identifier.

        Returns:
            Secret value, or None if not found.
        """
        if self._use_keyring:
            return keyring.get_password(self.SERVICE_NAME, key)
        else:
            data = self._read_fallback_data()
            return data.get(key)

    def delete_secret(self, key: str) -> bool:
        """Delete a secret.

        Args:
            key: Secret identifier.

        Returns:
            True if secret was deleted, False if it didn't exist.
        """
        if self._use_keyring:
            try:
                keyring.delete_password(self.SERVICE_NAME, key)
                return True
            except keyring.errors.PasswordDeleteError:
                return False
        else:
            data = self._read_fallback_data()
            if key in data:
                del data[key]
                self._write_fallback_data(data)
                return True
            return False

    def list_secrets(self) -> list[str]:
        """List all stored secret keys.

        Returns:
            List of secret identifiers (keys only, not values).
        """
        if self._use_keyring:
            # Keyring doesn't provide enumeration - must track separately
            # Store a metadata key with list of all keys
            metadata = keyring.get_password(self.SERVICE_NAME, "__metadata__")
            if metadata:
                return json.loads(metadata)
            return []
        else:
            data = self._read_fallback_data()
            return list(data.keys())

    def audit_secrets(self) -> dict[str, Any]:
        """Generate audit report of secrets storage.

        Returns:
            Dictionary with audit information:
            - backend: "keyring" or "fallback"
            - secret_count: Number of stored secrets
            - keys: List of secret keys
        """
        backend = "keyring" if self._use_keyring else "fallback"
        keys = self.list_secrets()

        return {
            "backend": backend,
            "secret_count": len(keys),
            "keys": keys,
        }


# Singleton instance for module-level functions
_manager: SecretsManager | None = None


def _get_manager() -> SecretsManager:
    """Get or create the global secrets manager instance.

    Returns:
        The global SecretsManager instance.
    """
    global _manager
    if _manager is None:
        _manager = SecretsManager()
    return _manager


def store_secret(key: str, value: str) -> None:
    """Store a secret using the global manager.

    Args:
        key: Secret identifier.
        value: Secret value (will be encrypted).
    """
    _get_manager().store_secret(key, value)


def get_secret(key: str) -> str | None:
    """Retrieve a secret using the global manager.

    Args:
        key: Secret identifier.

    Returns:
        Secret value, or None if not found.
    """
    return _get_manager().get_secret(key)


def delete_secret(key: str) -> bool:
    """Delete a secret using the global manager.

    Args:
        key: Secret identifier.

    Returns:
        True if secret was deleted, False if it didn't exist.
    """
    return _get_manager().delete_secret(key)


def list_secrets() -> list[str]:
    """List all stored secret keys using the global manager.

    Returns:
        List of secret identifiers.
    """
    return _get_manager().list_secrets()


def audit_secrets() -> dict[str, Any]:
    """Generate audit report using the global manager.

    Returns:
        Audit information dictionary.
    """
    return _get_manager().audit_secrets()
