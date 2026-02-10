"""Tests for document parsing MCP tools."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.documents import register


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> MCPConfig:
    return MCPConfig(workspace_path=workspace)


@pytest.fixture
def tools(config: MCPConfig) -> dict:
    """Register document tools and return them by name."""
    mcp = MagicMock()
    registered = {}

    def capture_tool():
        def decorator(func):
            registered[func.__name__] = func
            return func

        return decorator

    mcp.tool.side_effect = capture_tool
    register(mcp, config)
    return registered


class TestReadPdf:
    """read_pdf tool tests."""

    @patch("nebulus_core.mcp.tools.documents.pypdf")
    def test_read_pdf_success(
        self, mock_pypdf: MagicMock, tools: dict, workspace: Path
    ) -> None:
        # Create a dummy file so path validation passes
        pdf_path = workspace / "test.pdf"
        pdf_path.write_bytes(b"dummy")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pypdf.PdfReader.return_value = mock_reader

        result = tools["read_pdf"]("test.pdf")
        assert result == "Page 1 content"

    @patch("nebulus_core.mcp.tools.documents.pypdf")
    def test_read_pdf_multi_page(
        self, mock_pypdf: MagicMock, tools: dict, workspace: Path
    ) -> None:
        pdf_path = workspace / "multi.pdf"
        pdf_path.write_bytes(b"dummy")

        page1 = MagicMock()
        page1.extract_text.return_value = "Page 1"
        page2 = MagicMock()
        page2.extract_text.return_value = "Page 2"
        mock_reader = MagicMock()
        mock_reader.pages = [page1, page2]
        mock_pypdf.PdfReader.return_value = mock_reader

        result = tools["read_pdf"]("multi.pdf")
        assert "Page 1" in result
        assert "Page 2" in result

    def test_read_pdf_missing(self, tools: dict) -> None:
        result = tools["read_pdf"]("nonexistent.pdf")
        assert "Error reading PDF" in result


class TestReadDocx:
    """read_docx tool tests."""

    @patch("nebulus_core.mcp.tools.documents.docx")
    def test_read_docx_success(
        self, mock_docx: MagicMock, tools: dict, workspace: Path
    ) -> None:
        docx_path = workspace / "test.docx"
        docx_path.write_bytes(b"dummy")

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

    def test_read_docx_missing(self, tools: dict) -> None:
        result = tools["read_docx"]("nonexistent.docx")
        assert "Error reading DOCX" in result
