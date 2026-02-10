"""At-rest encryption utilities using Fernet symmetric encryption."""

from pathlib import Path
from typing import Union

from cryptography.fernet import Fernet

from nebulus_core.security.secrets import SecretsManager


class EncryptionManager:
    """Manages encryption and decryption operations.

    Uses a master key stored in the platform keystore (via SecretsManager).
    Data keys are derived from the master key for actual encryption operations.
    """

    MASTER_KEY_NAME = "nebulus_master_encryption_key"

    def __init__(self, secrets_manager: SecretsManager | None = None) -> None:
        """Initialize the encryption manager.

        Args:
            secrets_manager: Optional SecretsManager instance. If None, creates new one.
        """
        self._secrets = secrets_manager or SecretsManager()
        self._ensure_master_key()

    def _ensure_master_key(self) -> None:
        """Ensure master encryption key exists, generating if needed."""
        if self._secrets.get_secret(self.MASTER_KEY_NAME) is None:
            # Generate and store new master key
            master_key = Fernet.generate_key().decode("utf-8")
            self._secrets.store_secret(self.MASTER_KEY_NAME, master_key)

    def _get_cipher(self) -> Fernet:
        """Get Fernet cipher initialized with master key.

        Returns:
            Initialized Fernet cipher.

        Raises:
            RuntimeError: If master key is not available.
        """
        master_key = self._secrets.get_secret(self.MASTER_KEY_NAME)
        if master_key is None:
            raise RuntimeError("Master encryption key not found")
        return Fernet(master_key.encode("utf-8"))

    def encrypt_value(self, plaintext: Union[str, bytes]) -> bytes:
        """Encrypt a value.

        Args:
            plaintext: String or bytes to encrypt.

        Returns:
            Encrypted bytes.
        """
        cipher = self._get_cipher()
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")
        return cipher.encrypt(plaintext)

    def decrypt_value(self, ciphertext: bytes) -> bytes:
        """Decrypt a value.

        Args:
            ciphertext: Encrypted bytes.

        Returns:
            Decrypted bytes.

        Raises:
            cryptography.fernet.InvalidToken: If decryption fails.
        """
        cipher = self._get_cipher()
        return cipher.decrypt(ciphertext)

    def encrypt_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> None:
        """Encrypt a file.

        Args:
            input_path: Path to plaintext file.
            output_path: Path to write encrypted file.

        Raises:
            FileNotFoundError: If input file doesn't exist.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        plaintext = input_path.read_bytes()
        ciphertext = self.encrypt_value(plaintext)
        output_path.write_bytes(ciphertext)
        output_path.chmod(0o600)

    def decrypt_file(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> None:
        """Decrypt a file.

        Args:
            input_path: Path to encrypted file.
            output_path: Path to write decrypted file.

        Raises:
            FileNotFoundError: If input file doesn't exist.
            cryptography.fernet.InvalidToken: If decryption fails.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        ciphertext = input_path.read_bytes()
        plaintext = self.decrypt_value(ciphertext)
        output_path.write_bytes(plaintext)
        output_path.chmod(0o600)


# Singleton instance for module-level functions
_manager: EncryptionManager | None = None


def _get_manager() -> EncryptionManager:
    """Get or create the global encryption manager instance.

    Returns:
        The global EncryptionManager instance.
    """
    global _manager
    if _manager is None:
        _manager = EncryptionManager()
    return _manager


def encrypt_value(plaintext: Union[str, bytes]) -> bytes:
    """Encrypt a value using the global manager.

    Args:
        plaintext: String or bytes to encrypt.

    Returns:
        Encrypted bytes.
    """
    return _get_manager().encrypt_value(plaintext)


def decrypt_value(ciphertext: bytes) -> bytes:
    """Decrypt a value using the global manager.

    Args:
        ciphertext: Encrypted bytes.

    Returns:
        Decrypted bytes.
    """
    return _get_manager().decrypt_value(ciphertext)


def encrypt_file(input_path: Union[str, Path], output_path: Union[str, Path]) -> None:
    """Encrypt a file using the global manager.

    Args:
        input_path: Path to plaintext file.
        output_path: Path to write encrypted file.
    """
    _get_manager().encrypt_file(input_path, output_path)


def decrypt_file(input_path: Union[str, Path], output_path: Union[str, Path]) -> None:
    """Decrypt a file using the global manager.

    Args:
        input_path: Path to encrypted file.
        output_path: Path to write decrypted file.
    """
    _get_manager().decrypt_file(input_path, output_path)
