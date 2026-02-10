"""Document parsing tools — read PDF and DOCX files."""

import docx
import pypdf
from mcp.server.fastmcp import FastMCP

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.filesystem import _validate_path


def register(mcp: FastMCP, config: MCPConfig) -> None:
    """Register document tools on the MCP server.

    Args:
        mcp: FastMCP server instance.
        config: MCP configuration.
    """

    @mcp.tool()
    def read_pdf(path: str) -> str:
        """Read text content from a PDF file."""
        try:
            target_path = _validate_path(path, config)
            reader = pypdf.PdfReader(target_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            return f"Error reading PDF: {str(e)}"

    @mcp.tool()
    def read_docx(path: str) -> str:
        """Read text content from a DOCX file."""
        try:
            target_path = _validate_path(path, config)
            doc = docx.Document(target_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text.strip()
        except Exception as e:
            return f"Error reading DOCX: {str(e)}"
