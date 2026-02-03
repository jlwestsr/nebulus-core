"""OpenAI-compatible HTTP client for LLM inference.

Talks to whichever endpoint the platform adapter provides —
TabbyAPI on Linux, MLX server on macOS, or any OpenAI-compatible API.
"""

from typing import Any

import httpx


class LLMClient:
    """HTTP client for OpenAI-compatible LLM endpoints.

    Args:
        base_url: Base URL of the inference server (e.g. http://localhost:5000/v1).
        timeout: Request timeout in seconds.
    """

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model identifier. If None, uses server default.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            The assistant's response content.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
        }
        if model:
            payload["model"] = model
        if max_tokens:
            payload["max_tokens"] = max_tokens

        resp = self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def list_models(self) -> list[dict[str, Any]]:
        """List available models on the inference server.

        Returns:
            List of model info dicts with at least 'id' and 'owned_by'.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        resp = self.client.get(f"{self.base_url}/models")
        resp.raise_for_status()
        return resp.json().get("data", [])

    def health_check(self) -> bool:
        """Check if the inference server is reachable.

        Returns:
            True if the server responds, False otherwise.
        """
        try:
            resp = self.client.get(f"{self.base_url}/models")
            return resp.status_code < 400
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
