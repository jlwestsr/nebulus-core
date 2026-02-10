"""Comprehensive tests for document parsing MCP tools."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.documents import register


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory."""
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> MCPConfig:
    """Create MCPConfig pointing to the temp workspace."""
    return MCPConfig(workspace_path=workspace)


@pytest.fixture
def tools(config: MCPConfig) -> dict:
    """Register document tools and return them by name."""
    mcp = MagicMock()
    registered: dict = {}

    def capture_tool():
        def decorator(func):
            registered[func.__name__] = func
            return func

        return decorator

    mcp.tool.side_effect = capture_tool
    register(mcp, config)
    return registered


# ---------------------------------------------------------------------------
# read_pdf
# ---------------------------------------------------------------------------
class TestReadPdf:
    """read_pdf tool tests."""

    @patch("nebulus_core.mcp.tools.documents.pypdf")
    def test_single_page(
        self, mock_pypdf: MagicMock, tools: dict, workspace: Path
    ) -> None:
        (workspace / "test.pdf").write_bytes(b"dummy")
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pypdf.PdfReader.return_value = mock_reader

        result = tools["read_pdf"]("test.pdf")
        assert result == "Page 1 content"

    @patch("nebulus_core.mcp.tools.documents.pypdf")
    def test_multi_page(
        self, mock_pypdf: MagicMock, tools: dict, workspace: Path
    ) -> None:
        (workspace / "multi.pdf").write_bytes(b"dummy")
        page1 = MagicMock()
        page1.extract_text.return_value = "First"
        page2 = MagicMock()
        page2.extract_text.return_value = "Second"
        page3 = MagicMock()
        page3.extract_text.return_value = "Third"
        mock_reader = MagicMock()
        mock_reader.pages = [page1, page2, page3]
        mock_pypdf.PdfReader.return_value = mock_reader

        result = tools["read_pdf"]("multi.pdf")
        assert "First" in result
        assert "Second" in result
        assert "Third" in result

    @patch("nebulus_core.mcp.tools.documents.pypdf")
    def test_empty_pdf(
        self, mock_pypdf: MagicMock, tools: dict, workspace: Path
    ) -> None:
        """A PDF with no pages returns empty string."""
        (workspace / "empty.pdf").write_bytes(b"dummy")
        mock_reader = MagicMock()
        mock_reader.pages = []
        mock_pypdf.PdfReader.return_value = mock_reader

        result = tools["read_pdf"]("empty.pdf")
        assert result == ""

    @patch("nebulus_core.mcp.tools.documents.pypdf")
    def test_blank_page(
        self, mock_pypdf: MagicMock, tools: dict, workspace: Path
    ) -> None:
        """PDF with a page that has no text."""
        (workspace / "blank.pdf").write_bytes(b"dummy")
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pypdf.PdfReader.return_value = mock_reader

        result = tools["read_pdf"]("blank.pdf")
        assert result == ""

    def test_missing_file(self, tools: dict) -> None:
        result = tools["read_pdf"]("nonexistent.pdf")
        assert "Error reading PDF" in result

    def test_traversal_blocked(self, tools: dict) -> None:
        result = tools["read_pdf"]("../../etc/secret.pdf")
        assert "Error reading PDF" in result

    @patch("nebulus_core.mcp.tools.documents.pypdf")
    def test_pdf_reader_exception(
        self, mock_pypdf: MagicMock, tools: dict, workspace: Path
    ) -> None:
        """PdfReader raises on corrupt file."""
        (workspace / "corrupt.pdf").write_bytes(b"not-a-pdf")
        mock_pypdf.PdfReader.side_effect = Exception("Invalid PDF")
        result = tools["read_pdf"]("corrupt.pdf")
        assert "Error reading PDF" in result


# ---------------------------------------------------------------------------
# read_docx
# ---------------------------------------------------------------------------
class TestReadDocx:
    """read_docx tool tests."""

    @patch("nebulus_core.mcp.tools.documents.docx")
    def test_multi_paragraph(
        self, mock_docx: MagicMock, tools: dict, workspace: Path
    ) -> None:
        (workspace / "test.docx").write_bytes(b"dummy")
        para1 = MagicMock()
        para1.text = "Paragraph 1"
        para2 = MagicMock()
        para2.text = "Paragraph 2"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2]
        mock_docx.Document.return_value = mock_doc

        result = tools["read_docx"]("test.docx")
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result
        assert "\n" in result

    @patch("nebulus_core.mcp.tools.documents.docx")
    def test_empty_docx(
        self, mock_docx: MagicMock, tools: dict, workspace: Path
    ) -> None:
        """DOCX with no paragraphs returns empty string."""
        (workspace / "empty.docx").write_bytes(b"dummy")
        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_docx.Document.return_value = mock_doc

        result = tools["read_docx"]("empty.docx")
        assert result == ""

    @patch("nebulus_core.mcp.tools.documents.docx")
    def test_single_paragraph(
        self, mock_docx: MagicMock, tools: dict, workspace: Path
    ) -> None:
        (workspace / "single.docx").write_bytes(b"dummy")
        para = MagicMock()
        para.text = "Only paragraph"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [para]
        mock_docx.Document.return_value = mock_doc

        result = tools["read_docx"]("single.docx")
        assert result == "Only paragraph"

    @patch("nebulus_core.mcp.tools.documents.docx")
    def test_blank_paragraphs(
        self, mock_docx: MagicMock, tools: dict, workspace: Path
    ) -> None:
        """DOCX with empty paragraphs."""
        (workspace / "blank_p.docx").write_bytes(b"dummy")
        para1 = MagicMock()
        para1.text = ""
        para2 = MagicMock()
        para2.text = "Content"
        para3 = MagicMock()
        para3.text = ""
        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2, para3]
        mock_docx.Document.return_value = mock_doc

        result = tools["read_docx"]("blank_p.docx")
        assert "Content" in result

    def test_missing_file(self, tools: dict) -> None:
        result = tools["read_docx"]("nonexistent.docx")
        assert "Error reading DOCX" in result

    def test_traversal_blocked(self, tools: dict) -> None:
        result = tools["read_docx"]("../../etc/secret.docx")
        assert "Error reading DOCX" in result

    @patch("nebulus_core.mcp.tools.documents.docx")
    def test_docx_reader_exception(
        self, mock_docx: MagicMock, tools: dict, workspace: Path
    ) -> None:
        """Document constructor raises on corrupt file."""
        (workspace / "corrupt.docx").write_bytes(b"not-a-docx")
        mock_docx.Document.side_effect = Exception("Bad DOCX")
        result = tools["read_docx"]("corrupt.docx")
        assert "Error reading DOCX" in result


# ---------------------------------------------------------------------------
# register function
# ---------------------------------------------------------------------------
class TestRegister:
    """Verify register adds expected tools."""

    def test_registers_two_tools(self, tools: dict) -> None:
        expected = {"read_pdf", "read_docx"}
        assert set(tools.keys()) == expected
