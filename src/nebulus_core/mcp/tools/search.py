"""Search tools — web search (DDG/Google) and code search (grep)."""

import os
import subprocess

from mcp.server.fastmcp import FastMCP

from nebulus_core.mcp.config import MCPConfig


def _search_google_api(query: str, max_results: int, config: MCPConfig) -> list[str]:
    """Search using Google Custom Search API.

    Args:
        query: Search query string.
        max_results: Maximum results to return.
        config: MCP configuration with Google API credentials.

    Returns:
        List of formatted result strings.

    Raises:
        ValueError: If API credentials are missing.
        ImportError: If google-api-python-client is not installed.
    """
    api_key = config.google_api_key or os.environ.get("GOOGLE_API_KEY")
    cse_id = config.google_cse_id or os.environ.get("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        raise ValueError(
            "Error: Google Search requires GOOGLE_API_KEY and GOOGLE_CSE_ID "
            "environment variables."
        )

    try:
        from googleapiclient.discovery import build

        service = build("customsearch", "v1", developerKey=api_key)
        result = service.cse().list(q=query, cx=cse_id, num=max_results).execute()

        items = result.get("items", [])
        return [
            f"Title: {item.get('title')}\n"
            f"Link: {item.get('link')}\n"
            f"Snippet: {item.get('snippet')}\n"
            for item in items
        ]
    except ImportError:
        raise ImportError("Error: google-api-python-client not installed.")


def _search_ddg(query: str, max_results: int) -> list[str]:
    """Search using DuckDuckGo.

    Args:
        query: Search query string.
        max_results: Maximum results to return.

    Returns:
        List of formatted result strings.
    """
    from duckduckgo_search import DDGS

    results = DDGS().text(query, max_results=max_results)
    return [
        f"Title: {result['title']}\n"
        f"Link: {result['href']}\n"
        f"Snippet: {result['body']}\n"
        for result in results
    ]


def _search_google_fallback(query: str, max_results: int) -> list[str]:
    """Search using Google scraper fallback.

    Args:
        query: Search query string.
        max_results: Maximum results to return.

    Returns:
        List of formatted result strings.
    """
    try:
        from googlesearch import search

        g_results = search(query, num_results=max_results, advanced=True)
        return [
            f"Title: {res.title}\n" f"Link: {res.url}\n" f"Snippet: {res.description}\n"
            for res in g_results
        ]
    except Exception:
        return []


def register(mcp: FastMCP, config: MCPConfig) -> None:
    """Register search tools on the MCP server.

    Args:
        mcp: FastMCP server instance.
        config: MCP configuration.
    """

    @mcp.tool()
    def search_web(query: str, max_results: int = 5, engine: str = "duckduckgo") -> str:
        """Search the web using DuckDuckGo or Google.

        Args:
            query: Search query.
            max_results: Number of results to return (default: 5).
            engine: 'duckduckgo' (default) or 'google'.
        """
        try:
            formatted_results: list[str] = []

            if engine.lower() == "google":
                try:
                    formatted_results = _search_google_api(query, max_results, config)
                except (ValueError, ImportError) as e:
                    return str(e)
            else:
                formatted_results = _search_ddg(query, max_results)

            if not formatted_results:
                formatted_results = _search_google_fallback(query, max_results)

            if not formatted_results:
                return "No results found."

            return "\n---\n".join(formatted_results)
        except Exception as e:
            return f"Error performing search: {str(e)}"

    @mcp.tool()
    def search_code(query: str, path: str = ".") -> str:
        """Search for a text pattern in the codebase using grep.

        Args:
            query: The regex pattern to search for.
            path: The path to search within (defaults to workspace root).
        """
        try:
            from nebulus_core.mcp.tools.filesystem import _validate_path

            target_path = _validate_path(path, config)

            cmd = [
                "grep",
                "-r",
                "-n",
                "-I",
                "-H",
                "--exclude-dir={.git,__pycache__,node_modules,venv,.env}",
                query,
                target_path,
            ]

            result = subprocess.run(
                cmd,
                cwd=str(config.workspace_path),
                capture_output=True,
                text=True,
                timeout=config.command_timeout,
            )

            if result.returncode == 0:
                return result.stdout.strip()
            elif result.returncode == 1:
                return "No matches found."
            else:
                return (
                    f"Error executing grep (exit {result.returncode}): "
                    f"\n{result.stderr}"
                )

        except subprocess.TimeoutExpired:
            return f"Error: Search timed out after {config.command_timeout} seconds."
        except Exception as e:
            return f"Error executing search: {str(e)}"
