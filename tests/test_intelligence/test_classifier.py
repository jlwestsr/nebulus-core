"""Tests for the question classifier module."""

import json

from unittest.mock import MagicMock

from nebulus_core.intelligence.core.classifier import (
    ClassificationResult,
    QueryType,
    QuestionClassifier,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_classifier() -> QuestionClassifier:
    """Create a QuestionClassifier with a mocked LLMClient."""
    mock_llm = MagicMock()
    return QuestionClassifier(llm=mock_llm, model="test-model")


SAMPLE_SCHEMA: dict = {
    "vehicles": {
        "columns": ["id", "make", "model", "year", "days_on_lot"],
        "types": {
            "id": "INTEGER",
            "make": "TEXT",
            "model": "TEXT",
            "year": "INTEGER",
            "days_on_lot": "INTEGER",
        },
    },
    "sales": {
        "columns": ["id", "vehicle_id", "price", "date"],
        "types": {
            "id": "INTEGER",
            "vehicle_id": "INTEGER",
            "price": "REAL",
            "date": "TEXT",
        },
    },
}


# ---------------------------------------------------------------------------
# Tests — LLM-based classify()
# ---------------------------------------------------------------------------


class TestClassifyLLM:
    """Tests for the LLM-based classify() method."""

    def test_classify_sql_only(self) -> None:
        """LLM returns a valid SQL_ONLY classification."""
        clf = _make_classifier()
        clf.llm.chat.return_value = json.dumps(
            {
                "query_type": "sql",
                "reasoning": "Simple count query",
                "needs_sql": True,
                "needs_semantic": False,
                "needs_knowledge": False,
                "suggested_tables": ["vehicles"],
                "confidence": 0.95,
            }
        )

        result = clf.classify("How many vehicles on the lot?", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.SQL_ONLY
        assert result.needs_sql is True
        assert result.needs_semantic is False
        assert result.suggested_tables == ["vehicles"]
        assert result.confidence == 0.95

    def test_classify_strategic(self) -> None:
        """LLM returns a strategic classification."""
        clf = _make_classifier()
        clf.llm.chat.return_value = json.dumps(
            {
                "query_type": "strategic",
                "reasoning": "Requires business reasoning",
                "needs_sql": True,
                "needs_semantic": True,
                "needs_knowledge": True,
                "suggested_tables": ["vehicles", "sales"],
                "confidence": 0.88,
            }
        )

        result = clf.classify("What is the ideal inventory mix?", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.STRATEGIC
        assert result.needs_knowledge is True

    def test_classify_semantic(self) -> None:
        """LLM returns a semantic classification."""
        clf = _make_classifier()
        clf.llm.chat.return_value = json.dumps(
            {
                "query_type": "semantic",
                "reasoning": "Similarity search needed",
                "needs_sql": False,
                "needs_semantic": True,
                "needs_knowledge": False,
                "suggested_tables": [],
                "confidence": 0.9,
            }
        )

        result = clf.classify("Find vehicles similar to this one", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.SEMANTIC_ONLY
        assert result.needs_semantic is True
        assert result.needs_sql is False

    def test_classify_hybrid(self) -> None:
        """LLM returns a hybrid classification."""
        clf = _make_classifier()
        clf.llm.chat.return_value = json.dumps(
            {
                "query_type": "hybrid",
                "reasoning": "Needs SQL data and semantic patterns",
                "needs_sql": True,
                "needs_semantic": True,
                "needs_knowledge": True,
                "suggested_tables": ["vehicles", "sales"],
                "confidence": 0.85,
            }
        )

        result = clf.classify("What makes our best sales successful?", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.HYBRID
        assert result.needs_sql is True
        assert result.needs_semantic is True

    def test_classify_json_in_markdown_code_block(self) -> None:
        """LLM wraps JSON in a markdown code block."""
        clf = _make_classifier()
        raw = (
            "Here is my analysis:\n```json\n"
            + json.dumps(
                {
                    "query_type": "sql",
                    "reasoning": "Count query",
                    "needs_sql": True,
                    "needs_semantic": False,
                    "needs_knowledge": False,
                    "suggested_tables": ["vehicles"],
                    "confidence": 0.92,
                }
            )
            + "\n```"
        )
        clf.llm.chat.return_value = raw

        result = clf.classify("How many cars?", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.SQL_ONLY
        assert result.confidence == 0.92

    def test_classify_json_in_plain_code_block(self) -> None:
        """LLM wraps JSON in a plain (non-json) code block."""
        clf = _make_classifier()
        raw = (
            "```\n"
            + json.dumps(
                {
                    "query_type": "semantic",
                    "reasoning": "Similarity",
                    "needs_sql": False,
                    "needs_semantic": True,
                    "needs_knowledge": False,
                    "suggested_tables": [],
                    "confidence": 0.8,
                }
            )
            + "\n```"
        )
        clf.llm.chat.return_value = raw

        result = clf.classify("Find similar sales", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.SEMANTIC_ONLY

    def test_classify_llm_chat_params(self) -> None:
        """Verify the LLM is called with the expected parameters."""
        clf = _make_classifier()
        clf.llm.chat.return_value = json.dumps(
            {
                "query_type": "sql",
                "reasoning": "test",
                "needs_sql": True,
                "needs_semantic": False,
                "needs_knowledge": False,
                "suggested_tables": [],
                "confidence": 0.9,
            }
        )

        clf.classify("test question", SAMPLE_SCHEMA)

        clf.llm.chat.assert_called_once()
        call_kwargs = clf.llm.chat.call_args
        assert call_kwargs.kwargs["model"] == "test-model"
        assert call_kwargs.kwargs["temperature"] == 0.1
        assert call_kwargs.kwargs["max_tokens"] == 500
        messages = call_kwargs.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "test question" in messages[0]["content"]


# ---------------------------------------------------------------------------
# Tests — error handling
# ---------------------------------------------------------------------------


class TestClassifyErrorHandling:
    """Tests for error and fallback handling in classify()."""

    def test_classify_llm_exception_defaults_to_sql(self) -> None:
        """When the LLM raises an exception, default to SQL_ONLY."""
        clf = _make_classifier()
        clf.llm.chat.side_effect = RuntimeError("connection refused")

        result = clf.classify("How many cars?", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.SQL_ONLY
        assert "Classification failed" in result.reasoning
        assert result.confidence == 0.5

    def test_classify_malformed_json_fallback_strategic(self) -> None:
        """Malformed JSON with strategic keywords falls back correctly."""
        clf = _make_classifier()
        clf.llm.chat.return_value = "This is a strategic question about ideal mix"

        result = clf.classify("What is the ideal mix?", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.STRATEGIC
        assert result.needs_knowledge is True
        assert result.confidence == 0.6

    def test_classify_malformed_json_fallback_semantic(self) -> None:
        """Malformed JSON with semantic keywords falls back correctly."""
        clf = _make_classifier()
        clf.llm.chat.return_value = "This requires semantic similarity search"

        result = clf.classify("Find similar ones", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.SEMANTIC_ONLY

    def test_classify_malformed_json_fallback_hybrid(self) -> None:
        """Malformed JSON with hybrid keyword falls back correctly."""
        clf = _make_classifier()
        clf.llm.chat.return_value = "This is a hybrid question"

        result = clf.classify("Complex question", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.HYBRID

    def test_classify_malformed_json_fallback_sql(self) -> None:
        """Malformed JSON with no keywords defaults to SQL."""
        clf = _make_classifier()
        clf.llm.chat.return_value = "I cannot classify this properly"

        result = clf.classify("Some question", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.SQL_ONLY
        assert result.reasoning == "Parsed from text response"

    def test_classify_unknown_query_type_defaults_to_sql(self) -> None:
        """An unrecognized query_type string defaults to SQL_ONLY."""
        clf = _make_classifier()
        clf.llm.chat.return_value = json.dumps(
            {
                "query_type": "unknown_type",
                "reasoning": "test",
                "needs_sql": True,
                "needs_semantic": False,
                "needs_knowledge": False,
                "suggested_tables": [],
                "confidence": 0.5,
            }
        )

        result = clf.classify("A question", SAMPLE_SCHEMA)

        assert result.query_type == QueryType.SQL_ONLY


# ---------------------------------------------------------------------------
# Tests — rule-based classify_simple()
# ---------------------------------------------------------------------------


class TestClassifySimple:
    """Tests for the rule-based classify_simple() method."""

    def test_simple_strategic_ideal(self) -> None:
        """'ideal' keyword triggers STRATEGIC."""
        clf = _make_classifier()
        result = clf.classify_simple("What is the ideal inventory?")

        assert result.query_type == QueryType.STRATEGIC
        assert result.needs_sql is True
        assert result.needs_semantic is True
        assert result.needs_knowledge is True
        assert result.confidence == 0.7

    def test_simple_strategic_best(self) -> None:
        """'best' keyword triggers STRATEGIC."""
        clf = _make_classifier()
        result = clf.classify_simple("What is the best strategy?")

        assert result.query_type == QueryType.STRATEGIC

    def test_simple_strategic_recommend(self) -> None:
        """'recommend' keyword triggers STRATEGIC."""
        clf = _make_classifier()
        result = clf.classify_simple("What do you recommend?")

        assert result.query_type == QueryType.STRATEGIC

    def test_simple_semantic_similar(self) -> None:
        """'similar' keyword triggers SEMANTIC_ONLY."""
        clf = _make_classifier()
        result = clf.classify_simple("Find vehicles similar to this one")

        assert result.query_type == QueryType.SEMANTIC_ONLY
        assert result.needs_sql is False
        assert result.needs_semantic is True

    def test_simple_semantic_pattern(self) -> None:
        """'pattern' keyword triggers SEMANTIC_ONLY."""
        clf = _make_classifier()
        result = clf.classify_simple("Is there a pattern in sales?")

        assert result.query_type == QueryType.SEMANTIC_ONLY

    def test_simple_default_sql(self) -> None:
        """No special keywords defaults to SQL_ONLY."""
        clf = _make_classifier()
        result = clf.classify_simple("How many cars do we have?")

        assert result.query_type == QueryType.SQL_ONLY
        assert result.needs_sql is True
        assert result.needs_semantic is False
        assert result.needs_knowledge is False

    def test_simple_case_insensitive(self) -> None:
        """Keyword matching is case-insensitive."""
        clf = _make_classifier()
        result = clf.classify_simple("WHAT IS THE IDEAL MIX?")

        assert result.query_type == QueryType.STRATEGIC


# ---------------------------------------------------------------------------
# Tests — _format_schema()
# ---------------------------------------------------------------------------


class TestFormatSchema:
    """Tests for the schema formatting helper."""

    def test_format_schema_with_data(self) -> None:
        """Schema with tables formats correctly."""
        clf = _make_classifier()
        text = clf._format_schema(SAMPLE_SCHEMA)

        assert "vehicles" in text
        assert "sales" in text
        assert "id (INTEGER)" in text
        assert "make (TEXT)" in text

    def test_format_schema_empty(self) -> None:
        """Empty schema returns fallback message."""
        clf = _make_classifier()
        text = clf._format_schema({})

        assert text == "No tables available"

    def test_format_schema_missing_types(self) -> None:
        """Columns without explicit types default to TEXT."""
        clf = _make_classifier()
        schema = {
            "test_table": {
                "columns": ["col_a", "col_b"],
                "types": {},
            },
        }
        text = clf._format_schema(schema)

        assert "col_a (TEXT)" in text
        assert "col_b (TEXT)" in text


# ---------------------------------------------------------------------------
# Tests — dataclass / enum basics
# ---------------------------------------------------------------------------


class TestDataModels:
    """Tests for QueryType and ClassificationResult."""

    def test_query_type_values(self) -> None:
        """QueryType enum has the expected members and values."""
        assert QueryType.SQL_ONLY.value == "sql"
        assert QueryType.SEMANTIC_ONLY.value == "semantic"
        assert QueryType.STRATEGIC.value == "strategic"
        assert QueryType.HYBRID.value == "hybrid"

    def test_classification_result_creation(self) -> None:
        """ClassificationResult can be created with expected fields."""
        result = ClassificationResult(
            query_type=QueryType.SQL_ONLY,
            reasoning="test",
            needs_sql=True,
            needs_semantic=False,
            needs_knowledge=False,
            suggested_tables=["vehicles"],
            confidence=0.9,
        )

        assert result.query_type == QueryType.SQL_ONLY
        assert result.suggested_tables == ["vehicles"]
        assert result.confidence == 0.9
