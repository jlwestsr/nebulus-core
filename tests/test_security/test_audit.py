"""Tests for secrets auditing."""

import tempfile
from pathlib import Path

import pytest

from nebulus_core.security.audit import SecretsAuditor, audit_secrets_in_path


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestSecretsAuditor:
    """Test SecretsAuditor functionality."""

    def test_should_skip_git_directory(self):
        """Test that .git directories are skipped."""
        auditor = SecretsAuditor()
        assert auditor.should_skip(Path("/repo/.git/config"))
        assert auditor.should_skip(Path("/repo/.git/objects/abc"))

    def test_should_skip_pycache(self):
        """Test that __pycache__ directories are skipped."""
        auditor = SecretsAuditor()
        assert auditor.should_skip(Path("/repo/__pycache__/module.pyc"))

    def test_should_skip_node_modules(self):
        """Test that node_modules directories are skipped."""
        auditor = SecretsAuditor()
        assert auditor.should_skip(Path("/repo/node_modules/package"))

    def test_should_skip_venv(self):
        """Test that venv directories are skipped."""
        auditor = SecretsAuditor()
        assert auditor.should_skip(Path("/repo/venv/lib/python"))
        assert auditor.should_skip(Path("/repo/.venv/bin/python"))

    def test_should_not_skip_normal_files(self):
        """Test that normal files are not skipped."""
        auditor = SecretsAuditor()
        assert not auditor.should_skip(Path("/repo/src/main.py"))
        assert not auditor.should_skip(Path("/repo/.env"))

    def test_should_scan_python_files(self):
        """Test that Python files are scanned."""
        auditor = SecretsAuditor()
        py_file = Path("/tmp/test.py")
        # Mock file existence
        assert ".py" in SecretsAuditor.SCAN_EXTENSIONS

    def test_should_scan_env_files(self):
        """Test that .env files are scanned."""
        auditor = SecretsAuditor()
        assert ".env" in SecretsAuditor.SCAN_EXTENSIONS

    def test_should_scan_config_files(self):
        """Test that config files are scanned."""
        auditor = SecretsAuditor()
        extensions = SecretsAuditor.SCAN_EXTENSIONS
        assert ".yml" in extensions
        assert ".yaml" in extensions
        assert ".json" in extensions
        assert ".toml" in extensions

    def test_mask_secret_short_text(self):
        """Test masking a short secret."""
        auditor = SecretsAuditor()
        text = "api_key=sk-1234567890"
        masked = auditor.mask_secret(text, 8, length=8)
        assert "sk-12345***REDACTED***" in masked
        assert "67890" not in masked

    def test_mask_secret_long_text(self):
        """Test masking a secret in long text."""
        auditor = SecretsAuditor()
        text = "This is a line with api_key=sk-verylongsecretkey and more text"
        start = text.index("sk-")
        masked = auditor.mask_secret(text, start, length=8)
        assert "sk-veryl***REDACTED***" in masked
        assert "secretkey" not in masked

    def test_scan_file_detects_openai_key(self, temp_dir):
        """Test detecting OpenAI API key."""
        test_file = temp_dir / "config.py"
        test_file.write_text("OPENAI_API_KEY = 'sk-1234567890abcdefghijklmnopqrstuvwx'")

        auditor = SecretsAuditor()
        findings = auditor.scan_file(test_file)

        assert len(findings) >= 1
        openai_findings = [f for f in findings if f.pattern_type == "openai_key"]
        assert len(openai_findings) == 1
        assert openai_findings[0].severity == "HIGH"
        assert openai_findings[0].line_number == 1

    def test_scan_file_detects_google_api_key(self, temp_dir):
        """Test detecting Google API key."""
        test_file = temp_dir / "config.yaml"
        test_file.write_text("google_api_key: AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz012345678")

        auditor = SecretsAuditor()
        findings = auditor.scan_file(test_file)

        assert len(findings) >= 1
        google_findings = [f for f in findings if f.pattern_type == "google_api_key"]
        assert len(google_findings) == 1
        assert google_findings[0].severity == "HIGH"

    def test_scan_file_detects_github_token(self, temp_dir):
        """Test detecting GitHub token."""
        test_file = temp_dir / ".env"
        test_file.write_text("GITHUB_TOKEN=ghp_123456789012345678901234567890123456")

        auditor = SecretsAuditor()
        findings = auditor.scan_file(test_file)

        assert len(findings) >= 1
        github_findings = [f for f in findings if f.pattern_type == "github_token"]
        assert len(github_findings) == 1
        assert github_findings[0].severity == "HIGH"

    def test_scan_file_detects_generic_api_key(self, temp_dir):
        """Test detecting generic API key pattern."""
        test_file = temp_dir / "settings.py"
        test_file.write_text("api_key = 'abcdefghijklmnopqrstuvwxyz12345'")

        auditor = SecretsAuditor()
        findings = auditor.scan_file(test_file)

        assert len(findings) >= 1
        assert any(f.pattern_type == "generic_api_key" for f in findings)

    def test_scan_file_detects_password(self, temp_dir):
        """Test detecting password."""
        test_file = temp_dir / "config.ini"
        test_file.write_text("password=supersecret123")

        auditor = SecretsAuditor()
        findings = auditor.scan_file(test_file)

        assert len(findings) >= 1
        assert any(f.pattern_type == "password" for f in findings)

    def test_scan_file_multiple_secrets(self, temp_dir):
        """Test detecting multiple secrets in one file."""
        test_file = temp_dir / "app.py"
        test_file.write_text("""
OPENAI_KEY = 'sk-1234567890abcdefghijklmnopqrstuvwx'
API_TOKEN = 'abcdefghijklmnopqrstuvwxyz'
PASSWORD = 'secret123'
        """)

        auditor = SecretsAuditor()
        findings = auditor.scan_file(test_file)

        assert len(findings) >= 3

    def test_scan_file_no_secrets(self, temp_dir):
        """Test file with no secrets."""
        test_file = temp_dir / "clean.py"
        test_file.write_text("""
def hello():
    print("Hello, World!")
    return 42
        """)

        auditor = SecretsAuditor()
        findings = auditor.scan_file(test_file)

        assert len(findings) == 0

    def test_scan_file_handles_binary_gracefully(self, temp_dir):
        """Test that scanning binary files doesn't crash."""
        test_file = temp_dir / "binary.dat"
        test_file.write_bytes(bytes(range(256)))

        auditor = SecretsAuditor()
        # Should not raise exception
        findings = auditor.scan_file(test_file)
        # Binary files are likely to produce false positives or be skipped
        assert isinstance(findings, list)

    def test_scan_directory_recursive(self, temp_dir):
        """Test scanning directory recursively."""
        # Create nested structure
        (temp_dir / "subdir").mkdir()
        (temp_dir / "config.py").write_text("OPENAI_KEY = 'sk-1234567890abcdefghijklmnopqrstuvwx'")
        (temp_dir / "subdir" / "secrets.env").write_text(
            "GITHUB_TOKEN=ghp_123456789012345678901234567890123456"
        )

        auditor = SecretsAuditor()
        findings = auditor.scan_directory(temp_dir, recursive=True)

        # Should find at least 2 secrets (may find more due to generic patterns)
        assert len(findings) >= 2
        # Should find secrets in both files
        files = {f.file_path for f in findings}
        assert len(files) >= 2

    def test_scan_directory_non_recursive(self, temp_dir):
        """Test scanning directory non-recursively."""
        # Create nested structure
        (temp_dir / "subdir").mkdir()
        (temp_dir / "config.py").write_text("OPENAI_KEY = 'sk-1234567890abcdefghijklmnopqrstuvwx'")
        (temp_dir / "subdir" / "secrets.env").write_text(
            "GITHUB_TOKEN=ghp_123456789012345678901234567890123456"
        )

        auditor = SecretsAuditor()
        findings = auditor.scan_directory(temp_dir, recursive=False)

        # Should only find secrets in root directory
        assert len(findings) >= 1
        files = {f.file_path for f in findings}
        # All findings should be from root directory
        assert all(f.parent == temp_dir for f in files)

    def test_scan_directory_skips_excluded_dirs(self, temp_dir):
        """Test that scanning skips excluded directories."""
        (temp_dir / ".git").mkdir()
        (temp_dir / "__pycache__").mkdir()
        (temp_dir / ".git" / "config").write_text("secret = sk-12345678901234567890")
        (temp_dir / "__pycache__" / "module.pyc").write_bytes(b"sk-fake")

        auditor = SecretsAuditor()
        findings = auditor.scan_directory(temp_dir, recursive=True)

        # Should not find anything in excluded directories
        assert len(findings) == 0


class TestAuditSecretsInPath:
    """Test the audit_secrets_in_path convenience function."""

    def test_audit_file(self, temp_dir):
        """Test auditing a single file."""
        test_file = temp_dir / "config.py"
        test_file.write_text("API_KEY = 'sk-1234567890abcdefghijklmnopqrstuvwx'")

        findings = audit_secrets_in_path(test_file)

        assert len(findings) >= 1
        assert findings[0].file_path == test_file

    def test_audit_directory(self, temp_dir):
        """Test auditing a directory."""
        (temp_dir / "file1.py").write_text("OPENAI_KEY1 = 'sk-1234567890abcdefghijklmnopqrstuvwx'")
        (temp_dir / "file2.py").write_text("OPENAI_KEY2 = 'sk-abcdefghijklmnopqrstuvwxyz123456'")

        findings = audit_secrets_in_path(temp_dir)

        # Should find at least the two OpenAI keys
        assert len(findings) >= 2
        # Check that we found OpenAI keys from both files
        openai_findings = [f for f in findings if f.pattern_type == "openai_key"]
        assert len(openai_findings) >= 2

    def test_audit_nonexistent_path_raises(self):
        """Test that auditing non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            audit_secrets_in_path("/nonexistent/path")

    def test_audit_string_path(self, temp_dir):
        """Test that function accepts string paths."""
        test_file = temp_dir / "config.py"
        test_file.write_text("OPENAI_KEY = 'sk-1234567890abcdefghijklmnopqrstuvwx'")

        findings = audit_secrets_in_path(str(test_file))

        assert len(findings) >= 1
        openai_findings = [f for f in findings if f.pattern_type == "openai_key"]
        assert len(openai_findings) == 1

    def test_findings_have_correct_structure(self, temp_dir):
        """Test that findings have all required fields."""
        test_file = temp_dir / "test.py"
        test_file.write_text("OPENAI_KEY = 'sk-1234567890abcdefghijklmnopqrstuvwx'")

        findings = audit_secrets_in_path(test_file)

        assert len(findings) > 0
        # Find an OpenAI key finding to check structure
        openai_finding = next((f for f in findings if f.pattern_type == "openai_key"), findings[0])
        assert hasattr(openai_finding, "file_path")
        assert hasattr(openai_finding, "line_number")
        assert hasattr(openai_finding, "pattern_type")
        assert hasattr(openai_finding, "severity")
        assert hasattr(openai_finding, "context")
        assert openai_finding.line_number > 0
        assert openai_finding.severity in ["HIGH", "MEDIUM", "LOW"]
