"""Security audit tools for detecting plaintext secrets."""

import re
from pathlib import Path
from typing import NamedTuple


class SecretFinding(NamedTuple):
    """Represents a detected secret pattern in a file.

    Attributes:
        file_path: Path to the file containing the secret.
        line_number: Line number where secret was found.
        pattern_type: Type of secret pattern detected.
        severity: Severity level (HIGH, MEDIUM, LOW).
        context: Line content with secret value partially masked.
    """

    file_path: Path
    line_number: int
    pattern_type: str
    severity: str
    context: str


class SecretsAuditor:
    """Scans files for plaintext secrets and API keys."""

    # Secret patterns with severity levels
    PATTERNS = {
        "openai_key": (re.compile(r"sk-[a-zA-Z0-9]{32,}"), "HIGH"),
        "google_api_key": (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "HIGH"),
        "github_token": (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "HIGH"),
        "github_oauth": (re.compile(r"gho_[a-zA-Z0-9]{36}"), "HIGH"),
        "aws_access_key": (re.compile(r"AKIA[0-9A-Z]{16}"), "HIGH"),
        "generic_api_key": (re.compile(r"['\"]?api[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_-]{20,}"), "MEDIUM"),
        "generic_secret": (re.compile(r"['\"]?secret['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_-]{20,}"), "MEDIUM"),
        "generic_token": (re.compile(r"['\"]?token['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_-]{20,}"), "MEDIUM"),
        "password": (re.compile(r"['\"]?password['\"]?\s*[:=]\s*['\"]?[^\s'\"]{8,}"), "MEDIUM"),
        "bearer_token": (re.compile(r"Bearer\s+[a-zA-Z0-9_-]{20,}"), "HIGH"),
        "basic_auth": (re.compile(r"Basic\s+[A-Za-z0-9+/]{20,}={0,2}"), "HIGH"),
    }

    # File patterns to skip
    SKIP_PATTERNS = [
        ".git/",
        "__pycache__/",
        "node_modules/",
        ".venv/",
        "venv/",
        ".pytest_cache/",
        "*.pyc",
        "*.pyo",
        "*.so",
        "*.dylib",
        ".DS_Store",
        "*.egg-info/",
        "dist/",
        "build/",
    ]

    # File extensions to scan
    SCAN_EXTENSIONS = {
        ".py",
        ".env",
        ".yml",
        ".yaml",
        ".json",
        ".toml",
        ".ini",
        ".conf",
        ".config",
        ".sh",
        ".bash",
        ".md",
        ".txt",
    }

    def should_skip(self, path: Path) -> bool:
        """Check if path should be skipped during scan.

        Args:
            path: Path to check.

        Returns:
            True if path should be skipped, False otherwise.
        """
        path_str = str(path)
        for pattern in self.SKIP_PATTERNS:
            if pattern.endswith("/"):
                if pattern[:-1] in path_str.split("/"):
                    return True
            elif pattern.startswith("*."):
                if path_str.endswith(pattern[1:]):
                    return True
            elif pattern in path_str:
                return True
        return False

    def should_scan_file(self, path: Path) -> bool:
        """Check if file should be scanned.

        Args:
            path: Path to check.

        Returns:
            True if file should be scanned, False otherwise.
        """
        if not path.is_file():
            return False
        if self.should_skip(path):
            return False
        if path.suffix in self.SCAN_EXTENSIONS:
            return True
        # Also scan files without extension (like .env, Dockerfile)
        if not path.suffix and not path.name.startswith("."):
            return True
        return False

    def mask_secret(self, text: str, start: int, length: int = 8) -> str:
        """Mask a detected secret in text for safe display.

        Args:
            text: Original text containing secret.
            start: Start position of secret in text.
            length: Number of characters to show before masking.

        Returns:
            Text with secret partially masked.
        """
        if start + length < len(text):
            return text[: start + length] + "***REDACTED***"
        return text[:start] + "***REDACTED***"

    def scan_file(self, file_path: Path) -> list[SecretFinding]:
        """Scan a single file for secret patterns.

        Args:
            file_path: Path to file to scan.

        Returns:
            List of SecretFinding objects for any secrets found.
        """
        findings = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, start=1):
                    for pattern_type, (pattern, severity) in self.PATTERNS.items():
                        match = pattern.search(line)
                        if match:
                            masked_context = self.mask_secret(
                                line.rstrip(), match.start()
                            )
                            findings.append(
                                SecretFinding(
                                    file_path=file_path,
                                    line_number=line_num,
                                    pattern_type=pattern_type,
                                    severity=severity,
                                    context=masked_context,
                                )
                            )
        except (UnicodeDecodeError, PermissionError):
            # Skip files that can't be read
            pass

        return findings

    def scan_directory(
        self, root_path: Path, recursive: bool = True
    ) -> list[SecretFinding]:
        """Scan directory for secret patterns.

        Args:
            root_path: Root directory to scan.
            recursive: If True, scan subdirectories recursively.

        Returns:
            List of all SecretFinding objects found.
        """
        findings = []

        if recursive:
            for item in root_path.rglob("*"):
                if self.should_scan_file(item):
                    findings.extend(self.scan_file(item))
        else:
            for item in root_path.iterdir():
                if self.should_scan_file(item):
                    findings.extend(self.scan_file(item))

        return findings


def audit_secrets_in_path(
    path: Path | str, recursive: bool = True
) -> list[SecretFinding]:
    """Scan path for plaintext secrets.

    Args:
        path: File or directory path to scan.
        recursive: If True and path is a directory, scan recursively.

    Returns:
        List of SecretFinding objects.

    Raises:
        FileNotFoundError: If path doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    auditor = SecretsAuditor()

    if path.is_file():
        return auditor.scan_file(path)
    else:
        return auditor.scan_directory(path, recursive=recursive)
