"""Tests for encryption utilities."""

import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import InvalidToken

from nebulus_core.security.encryption import EncryptionManager
from nebulus_core.security.secrets import SecretsManager


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def encryption_manager(temp_dir):
    """Create EncryptionManager with isolated secrets storage."""
    secrets_mgr = SecretsManager(use_keyring=False, fallback_dir=temp_dir / "secrets")
    return EncryptionManager(secrets_manager=secrets_mgr)


class TestEncryptionManager:
    """Test EncryptionManager functionality."""

    def test_init_creates_master_key(self, encryption_manager):
        """Test that initialization creates master encryption key."""
        master_key = encryption_manager._secrets.get_secret(
            encryption_manager.MASTER_KEY_NAME
        )
        assert master_key is not None
        assert len(master_key) > 0

    def test_encrypt_decrypt_string(self, encryption_manager):
        """Test encrypting and decrypting a string."""
        plaintext = "sensitive data"
        ciphertext = encryption_manager.encrypt_value(plaintext)

        assert isinstance(ciphertext, bytes)
        assert ciphertext != plaintext.encode("utf-8")

        decrypted = encryption_manager.decrypt_value(ciphertext)
        assert decrypted.decode("utf-8") == plaintext

    def test_encrypt_decrypt_bytes(self, encryption_manager):
        """Test encrypting and decrypting bytes."""
        plaintext = b"binary data \x00\x01\x02"
        ciphertext = encryption_manager.encrypt_value(plaintext)

        assert isinstance(ciphertext, bytes)
        assert ciphertext != plaintext

        decrypted = encryption_manager.decrypt_value(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext(self, encryption_manager):
        """Test that encrypting same plaintext produces different ciphertext."""
        plaintext = "test data"
        ciphertext1 = encryption_manager.encrypt_value(plaintext)
        ciphertext2 = encryption_manager.encrypt_value(plaintext)

        # Fernet includes timestamp and random IV, so ciphertexts differ
        assert ciphertext1 != ciphertext2

        # But both decrypt to same plaintext
        assert encryption_manager.decrypt_value(ciphertext1) == plaintext.encode("utf-8")
        assert encryption_manager.decrypt_value(ciphertext2) == plaintext.encode("utf-8")

    def test_decrypt_invalid_token_raises(self, encryption_manager):
        """Test that decrypting invalid data raises InvalidToken."""
        with pytest.raises(InvalidToken):
            encryption_manager.decrypt_value(b"invalid_encrypted_data")

    def test_encrypt_file(self, encryption_manager, temp_dir):
        """Test encrypting a file."""
        input_file = temp_dir / "plaintext.txt"
        output_file = temp_dir / "encrypted.bin"

        input_file.write_text("This is sensitive data")

        encryption_manager.encrypt_file(input_file, output_file)

        assert output_file.exists()
        # Plaintext should not appear in encrypted file
        assert b"sensitive data" not in output_file.read_bytes()

    def test_decrypt_file(self, encryption_manager, temp_dir):
        """Test decrypting a file."""
        plaintext_file = temp_dir / "plaintext.txt"
        encrypted_file = temp_dir / "encrypted.bin"
        decrypted_file = temp_dir / "decrypted.txt"

        original_data = "Secret information"
        plaintext_file.write_text(original_data)

        encryption_manager.encrypt_file(plaintext_file, encrypted_file)
        encryption_manager.decrypt_file(encrypted_file, decrypted_file)

        assert decrypted_file.read_text() == original_data

    def test_encrypt_file_not_found_raises(self, encryption_manager, temp_dir):
        """Test that encrypting non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            encryption_manager.encrypt_file(
                temp_dir / "nonexistent.txt", temp_dir / "output.bin"
            )

    def test_decrypt_file_not_found_raises(self, encryption_manager, temp_dir):
        """Test that decrypting non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            encryption_manager.decrypt_file(
                temp_dir / "nonexistent.bin", temp_dir / "output.txt"
            )

    def test_file_roundtrip_with_binary_data(self, encryption_manager, temp_dir):
        """Test file encryption/decryption with binary data."""
        input_file = temp_dir / "binary.dat"
        encrypted_file = temp_dir / "encrypted.bin"
        output_file = temp_dir / "decrypted.dat"

        binary_data = bytes(range(256))  # All possible byte values
        input_file.write_bytes(binary_data)

        encryption_manager.encrypt_file(input_file, encrypted_file)
        encryption_manager.decrypt_file(encrypted_file, output_file)

        assert output_file.read_bytes() == binary_data

    def test_encrypted_file_has_secure_permissions(self, encryption_manager, temp_dir):
        """Test that encrypted files are created with secure permissions."""
        input_file = temp_dir / "input.txt"
        encrypted_file = temp_dir / "encrypted.bin"

        input_file.write_text("data")
        encryption_manager.encrypt_file(input_file, encrypted_file)

        # Check that file has 0o600 permissions (owner read/write only)
        mode = encrypted_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_master_key_persistence(self):
        """Test that master key persists across manager instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            fallback_dir = tmpdir / "secrets"

            secrets1 = SecretsManager(use_keyring=False, fallback_dir=fallback_dir)
            manager1 = EncryptionManager(secrets_manager=secrets1)

            plaintext = "test data"
            ciphertext = manager1.encrypt_value(plaintext)

            # Create new manager instance
            secrets2 = SecretsManager(use_keyring=False, fallback_dir=fallback_dir)
            manager2 = EncryptionManager(secrets_manager=secrets2)

            # Should decrypt successfully with same master key
            decrypted = manager2.decrypt_value(ciphertext)
            assert decrypted.decode("utf-8") == plaintext


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_encrypt_decrypt_value(self):
        """Test module-level encrypt/decrypt functions."""
        from nebulus_core.security import encryption

        # Force reset singleton
        encryption._manager = None

        plaintext = "test data"
        ciphertext = encryption.encrypt_value(plaintext)
        decrypted = encryption.decrypt_value(ciphertext)

        assert decrypted.decode("utf-8") == plaintext

    def test_encrypt_decrypt_file(self):
        """Test module-level file encryption functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            from nebulus_core.security import encryption

            encryption._manager = None

            input_file = tmpdir / "input.txt"
            encrypted_file = tmpdir / "encrypted.bin"
            output_file = tmpdir / "output.txt"

            input_file.write_text("secret")

            encryption.encrypt_file(input_file, encrypted_file)
            encryption.decrypt_file(encrypted_file, output_file)

            assert output_file.read_text() == "secret"
