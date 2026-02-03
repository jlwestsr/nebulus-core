"""Tests for shared test fixtures."""

from nebulus_core.testing.fixtures import (
    create_mock_adapter,
    create_mock_llm_client,
    create_mock_vector_client,
)


class TestMockLLMClient:
    def test_returns_mock(self):
        mock = create_mock_llm_client()
        assert hasattr(mock, "chat")
        assert hasattr(mock, "list_models")
        assert hasattr(mock, "health_check")

    def test_chat_returns_string(self):
        mock = create_mock_llm_client()
        result = mock.chat(messages=[{"role": "user", "content": "hi"}])
        assert isinstance(result, str)

    def test_custom_chat_response(self):
        mock = create_mock_llm_client(chat_response="custom answer")
        assert mock.chat(messages=[]) == "custom answer"


class TestMockVectorClient:
    def test_returns_mock(self):
        mock = create_mock_vector_client()
        assert hasattr(mock, "get_or_create_collection")
        assert hasattr(mock, "list_collections")

    def test_collection_has_methods(self):
        mock = create_mock_vector_client()
        col = mock.get_or_create_collection("test")
        assert hasattr(col, "add")
        assert hasattr(col, "query")
        assert hasattr(col, "get")


class TestMockAdapter:
    def test_has_required_properties(self):
        mock = create_mock_adapter()
        assert mock.platform_name == "test"
        assert isinstance(mock.llm_base_url, str)
        assert isinstance(mock.chroma_settings, dict)
        assert mock.default_model
        assert mock.data_dir

    def test_custom_overrides(self):
        mock = create_mock_adapter(platform_name="custom", default_model="gpt-4")
        assert mock.platform_name == "custom"
        assert mock.default_model == "gpt-4"
