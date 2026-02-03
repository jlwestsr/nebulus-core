"""Mock fixtures for testing against nebulus-core interfaces."""

from pathlib import Path
from unittest.mock import MagicMock


def create_mock_llm_client(
    chat_response: str = "mock LLM response",
) -> MagicMock:
    """Create a mock LLMClient with working chat().

    Args:
        chat_response: Default return value for chat().

    Returns:
        MagicMock with LLMClient interface.
    """
    mock = MagicMock()
    mock.chat.return_value = chat_response
    mock.list_models.return_value = []
    mock.health_check.return_value = True
    return mock


def create_mock_vector_client() -> MagicMock:
    """Create a mock VectorClient with a fake collection.

    Returns:
        MagicMock with VectorClient interface.
    """
    mock = MagicMock()
    collection = MagicMock()
    collection.add = MagicMock()
    collection.query = MagicMock(return_value={"documents": [[]]})
    collection.get = MagicMock(
        return_value={"ids": [], "documents": [], "metadatas": []}
    )
    collection.update = MagicMock()
    mock.get_or_create_collection.return_value = collection
    mock.list_collections.return_value = []
    mock.heartbeat.return_value = True
    return mock


def create_mock_adapter(**overrides) -> MagicMock:
    """Create a mock PlatformAdapter with sensible defaults.

    Args:
        **overrides: Properties to override (e.g. platform_name="edge").

    Returns:
        MagicMock with PlatformAdapter interface.
    """
    defaults = {
        "platform_name": "test",
        "llm_base_url": "http://localhost:5000/v1",
        "chroma_settings": {
            "mode": "http",
            "host": "localhost",
            "port": 8001,
        },
        "default_model": "test-model",
        "data_dir": Path("/tmp/test-data"),
        "services": [],
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(type(mock), key, property(lambda self, v=value: v))
    return mock
