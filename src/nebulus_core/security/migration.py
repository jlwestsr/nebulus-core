"""Migration tools for moving plaintext secrets to encrypted storage."""

import re
from pathlib import Path
from typing import NamedTuple

from nebulus_core.security.secrets import SecretsManager


class MigrationResult(NamedTuple):
    """Result of a secrets migration operation.

    Attributes:
        secrets_found: Number of secrets found in source files.
        secrets_migrated: Number of secrets successfully migrated.
        errors: List of error messages encountered during migration.
        source_files: List of source files that were processed.
    """

    secrets_found: int
    secrets_migrated: int
    errors: list[str]
    source_files: list[Path]


class SecretsMigrator:
    """Migrates plaintext secrets from config files to encrypted storage."""

    # Patterns for extracting key-value pairs from common config formats
    # Must have at least one non-quote, non-newline character for the value
    # Use [ \t]* instead of \s* to avoid matching newlines
    ENV_PATTERN = re.compile(
        r'^([A-Z_][A-Z0-9_]*)[ \t]*=[ \t]*["\']?([^"\'\n]+)["\']?[ \t]*$', re.MULTILINE
    )
    YAML_PATTERN = re.compile(r'^(\w+):[ \t]*["\']?([^"\'\n]+)["\']?[ \t]*$', re.MULTILINE)

    # Keys that likely contain secrets (case-insensitive matching)
    SECRET_KEY_PATTERNS = [
        r".*api[_-]?key.*",
        r".*secret.*",
        r".*token.*",
        r".*password.*",
        r".*auth.*",
        r".*credential.*",
        r".*access[_-]?key.*",
        r".*private[_-]?key.*",
    ]

    def __init__(self, secrets_manager: SecretsManager | None = None) -> None:
        """Initialize the migrator.

        Args:
            secrets_manager: Optional SecretsManager instance. If None, creates new one.
        """
        self._secrets = secrets_manager or SecretsManager()
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.SECRET_KEY_PATTERNS
        ]

    def is_secret_key(self, key: str) -> bool:
        """Check if a key name suggests it contains a secret.

        Args:
            key: Key name to check.

        Returns:
            True if key likely contains a secret, False otherwise.
        """
        return any(pattern.match(key) for pattern in self._compiled_patterns)

    def extract_from_env_file(self, file_path: Path) -> dict[str, str]:
        """Extract key-value pairs from a .env file.

        Args:
            file_path: Path to .env file.

        Returns:
            Dictionary of key-value pairs that appear to be secrets.
        """
        if not file_path.exists():
            return {}

        content = file_path.read_text(encoding="utf-8")
        matches = self.ENV_PATTERN.findall(content)

        secrets = {}
        for key, value in matches:
            value = value.strip()
            if self.is_secret_key(key) and value:
                secrets[key.lower()] = value

        return secrets

    def extract_from_yaml_file(self, file_path: Path) -> dict[str, str]:
        """Extract key-value pairs from a YAML file.

        Args:
            file_path: Path to YAML file.

        Returns:
            Dictionary of key-value pairs that appear to be secrets.
        """
        if not file_path.exists():
            return {}

        content = file_path.read_text(encoding="utf-8")
        matches = self.YAML_PATTERN.findall(content)

        secrets = {}
        for key, value in matches:
            value = value.strip()
            if self.is_secret_key(key) and value:
                secrets[key.lower()] = value

        return secrets

    def migrate_from_file(self, file_path: Path) -> tuple[int, list[str]]:
        """Migrate secrets from a config file to encrypted storage.

        Args:
            file_path: Path to config file (.env, .yml, .yaml, etc.).

        Returns:
            Tuple of (number_migrated, list_of_errors).
        """
        file_path = Path(file_path)
        errors = []
        secrets = {}

        # Extract secrets based on file type
        if file_path.suffix in [".env"] or file_path.name == ".env":
            secrets = self.extract_from_env_file(file_path)
        elif file_path.suffix in [".yml", ".yaml"]:
            secrets = self.extract_from_yaml_file(file_path)
        else:
            # Try both patterns
            secrets.update(self.extract_from_env_file(file_path))
            secrets.update(self.extract_from_yaml_file(file_path))

        # Store each secret
        migrated = 0
        for key, value in secrets.items():
            try:
                self._secrets.store_secret(key, value)
                migrated += 1
            except Exception as e:
                errors.append(f"Failed to store {key}: {str(e)}")

        return migrated, errors

    def migrate_from_directory(
        self, root_path: Path, recursive: bool = True
    ) -> MigrationResult:
        """Migrate secrets from all config files in a directory.

        Args:
            root_path: Root directory to scan.
            recursive: If True, scan subdirectories recursively.

        Returns:
            MigrationResult with migration statistics.
        """
        root_path = Path(root_path)
        total_found = 0
        total_migrated = 0
        all_errors = []
        source_files = []
        processed_files = set()  # Track processed files to avoid duplicates

        # File patterns to scan
        patterns = ["**/.env*", "**/*.env", "**/*.yml", "**/*.yaml"]
        if not recursive:
            patterns = [p.replace("**/", "") for p in patterns]

        # Skip patterns
        skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}

        for pattern in patterns:
            for file_path in root_path.glob(pattern):
                # Skip files in excluded directories
                if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                    continue

                # Skip if already processed
                if file_path in processed_files:
                    continue

                if file_path.is_file():
                    processed_files.add(file_path)
                    try:
                        migrated, errors = self.migrate_from_file(file_path)
                        if migrated > 0:
                            total_found += migrated
                            total_migrated += migrated
                            source_files.append(file_path)
                        all_errors.extend(errors)
                    except Exception as e:
                        all_errors.append(f"Error processing {file_path}: {str(e)}")

        return MigrationResult(
            secrets_found=total_found,
            secrets_migrated=total_migrated,
            errors=all_errors,
            source_files=source_files,
        )


def migrate_secrets(
    path: Path | str, recursive: bool = True, secrets_manager: SecretsManager | None = None
) -> MigrationResult:
    """Migrate secrets from config files to encrypted storage.

    Args:
        path: File or directory path to process.
        recursive: If True and path is a directory, scan recursively.
        secrets_manager: Optional SecretsManager instance.

    Returns:
        MigrationResult with migration statistics.

    Raises:
        FileNotFoundError: If path doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    migrator = SecretsMigrator(secrets_manager)

    if path.is_file():
        migrated, errors = migrator.migrate_from_file(path)
        return MigrationResult(
            secrets_found=migrated,
            secrets_migrated=migrated,
            errors=errors,
            source_files=[path] if migrated > 0 else [],
        )
    else:
        return migrator.migrate_from_directory(path, recursive=recursive)
