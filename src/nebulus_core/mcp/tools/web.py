"""Web scraping tool — fetch and parse webpage content."""

import re

import httpx
from mcp.server.fastmcp import FastMCP
from selectolax.parser import HTMLParser

from nebulus_core.mcp.config import MCPConfig

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)


def register(mcp: FastMCP, config: MCPConfig) -> None:
    """Register web tools on the MCP server.

    Args:
        mcp: FastMCP server instance.
        config: MCP configuration.
    """

    @mcp.tool()
    async def scrape_url(url: str) -> str:
        """Scrape and parse the textual content of a webpage."""
        if not (url.startswith("http://") or url.startswith("https://")):
            return "Error: Invalid URL. Must start with http:// or https://"

        try:
            headers = {"User-Agent": _USER_AGENT}
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                tree = HTMLParser(response.text)

                for tag in tree.css("script, style"):
                    tag.decompose()

                if tree.body:
                    text = tree.body.text(separator="\n", strip=True)
                else:
                    text = tree.text(separator="\n", strip=True)

                lines = (line.strip() for line in text.splitlines())
                cleaned_lines = (re.sub(r"\s+", " ", line) for line in lines)
                text = "\n".join(line for line in cleaned_lines if line)

                return text

        except httpx.RequestError as e:
            return f"Error scraping URL: {str(e)}"
        except httpx.HTTPStatusError as e:
            return f"HTTP error {e.response.status_code} while scraping URL."
        except Exception as e:
            return f"Unexpected error: {str(e)}"
