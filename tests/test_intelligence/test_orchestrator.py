"""Tests for the intelligence orchestrator module."""

from unittest.mock import MagicMock

from nebulus_core.intelligence.core.classifier import (
    ClassificationResult,
    QueryType,
)
from nebulus_core.intelligence.core.orchestrator import (
    IntelligenceOrchestrator,
    IntelligenceResponse,
)
from nebulus_core.intelligence.core.sql_engine import QueryResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SCHEMA: dict = {
    "tables": {
        "vehicles": {
            "columns": [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "nullable": False,
                    "primary_key": True,
                },
                {
                    "name": "make",
                    "type": "TEXT",
                    "nullable": True,
                    "primary_key": False,
                },
            ],
            "row_count": 100,
            "sample_rows": [],
        },
        "sales": {
            "columns": [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "nullable": False,
                    "primary_key": True,
                },
                {
                    "name": "price",
                    "type": "REAL",
                    "nullable": True,
                    "primary_key": False,
                },
            ],
            "row_count": 50,
            "sample_rows": [],
        },
    }
}


def _sql_classification() -> ClassificationResult:
    return ClassificationResult(
        query_type=QueryType.SQL_ONLY,
        reasoning="Needs a count query.",
        needs_sql=True,
        needs_semantic=False,
        needs_knowledge=False,
        suggested_tables=["vehicles"],
        confidence=0.9,
    )


def _semantic_classification() -> ClassificationResult:
    return ClassificationResult(
        query_type=QueryType.SEMANTIC_ONLY,
        reasoning="Similarity search needed.",
        needs_sql=False,
        needs_semantic=True,
        needs_knowledge=False,
        suggested_tables=[],
        confidence=0.85,
    )


def _strategic_classification() -> ClassificationResult:
    return ClassificationResult(
        query_type=QueryType.STRATEGIC,
        reasoning="Business strategy question.",
        needs_sql=False,
        needs_semantic=False,
        needs_knowledge=True,
        suggested_tables=[],
        confidence=0.8,
    )


def _hybrid_classification() -> ClassificationResult:
    return ClassificationResult(
        query_type=QueryType.HYBRID,
        reasoning="Needs SQL and semantic data.",
        needs_sql=True,
        needs_semantic=True,
        needs_knowledge=True,
        suggested_tables=["vehicles"],
        confidence=0.75,
    )


def _make_orchestrator(
    classify_result: ClassificationResult | None = None,
) -> IntelligenceOrchestrator:
    """Build an orchestrator with fully mocked dependencies."""
    classifier = MagicMock()
    sql_engine = MagicMock()
    vector_engine = MagicMock()
    knowledge = MagicMock()
    llm = MagicMock()

    # Default classify returns SQL_ONLY
    if classify_result is None:
        classify_result = _sql_classification()
    classifier.classify.return_value = classify_result
    classifier.classify_simple.return_value = classify_result

    # Default schema
    sql_engine.get_schema.return_value = SAMPLE_SCHEMA

    # Default SQL results
    sql_engine.natural_to_sql.return_value = "SELECT COUNT(*) FROM vehicles"
    sql_engine.execute.return_value = QueryResult(
        columns=["count"],
        rows=[[100]],
        row_count=1,
        sql="SELECT COUNT(*) FROM vehicles",
    )

    # Default vector results
    vector_engine.list_collections.return_value = ["vehicles", "sales"]
    vector_engine.search_similar.return_value = []

    # Default knowledge
    knowledge.export_for_prompt.return_value = "## Domain Knowledge\nTest."

    # Default LLM synthesis
    llm.chat.return_value = "There are 100 vehicles in the database."

    return IntelligenceOrchestrator(
        classifier=classifier,
        sql_engine=sql_engine,
        vector_engine=vector_engine,
        knowledge=knowledge,
        llm=llm,
        model="test-model",
    )


# ---------------------------------------------------------------------------
# Tests -- ask() orchestration flow
# ---------------------------------------------------------------------------


class TestAskOrchestration:
    """Tests for the top-level ask() method."""

    def test_ask_returns_intelligence_response(self) -> None:
        """ask() returns an IntelligenceResponse instance."""
        orch = _make_orchestrator()
        result = orch.ask("How many vehicles?")
        assert isinstance(result, IntelligenceResponse)

    def test_ask_calls_classifier(self) -> None:
        """ask() invokes classifier.classify with the schema."""
        orch = _make_orchestrator()
        orch.ask("How many vehicles?")
        orch.classifier.classify.assert_called_once()
        args = orch.classifier.classify.call_args
        assert args[0][0] == "How many vehicles?"

    def test_ask_simple_classification(self) -> None:
        """ask() uses classify_simple when flag is set."""
        orch = _make_orchestrator()
        orch.ask("How many vehicles?", use_simple_classification=True)
        orch.classifier.classify_simple.assert_called_once_with("How many vehicles?")
        orch.classifier.classify.assert_not_called()

    def test_ask_calls_llm_for_synthesis(self) -> None:
        """ask() sends a synthesis prompt to the LLM."""
        orch = _make_orchestrator()
        orch.ask("How many vehicles?")
        orch.llm.chat.assert_called_once()
        call_kwargs = orch.llm.chat.call_args
        assert call_kwargs.kwargs["model"] == "test-model"
        assert call_kwargs.kwargs["temperature"] == 0.7
        assert call_kwargs.kwargs["max_tokens"] == 1000

    def test_ask_response_fields(self) -> None:
        """Response carries through classification metadata."""
        orch = _make_orchestrator()
        result = orch.ask("How many vehicles?")
        assert result.classification == "sql"
        assert result.confidence == 0.9
        assert result.reasoning == "Needs a count query."

    def test_ask_passes_template_name(self) -> None:
        """template_name propagates to strategic prompt."""
        orch = _make_orchestrator(_strategic_classification())
        orch.ask(
            "What is the ideal inventory?",
            template_name="auto_dealer",
        )
        prompt_text = orch.llm.chat.call_args.kwargs["messages"][0]["content"]
        assert "auto_dealer" in prompt_text


# ---------------------------------------------------------------------------
# Tests -- context gathering for each query type
# ---------------------------------------------------------------------------


class TestContextGathering:
    """Tests for _gather_context routing."""

    def test_sql_context_gathered(self) -> None:
        """SQL context is gathered when needs_sql is True."""
        orch = _make_orchestrator(_sql_classification())
        orch.ask("How many vehicles?")
        orch.sql_engine.natural_to_sql.assert_called_once()
        orch.sql_engine.execute.assert_called_once()

    def test_sql_results_in_response(self) -> None:
        """SQL results appear in the response."""
        orch = _make_orchestrator(_sql_classification())
        result = orch.ask("How many vehicles?")
        assert result.supporting_data is not None
        assert result.sql_used == "SELECT COUNT(*) FROM vehicles"

    def test_semantic_context_gathered(self) -> None:
        """Semantic context is gathered when needs_semantic is True."""
        orch = _make_orchestrator(_semantic_classification())
        orch.ask("Find vehicles like the Corvette")
        orch.vector_engine.list_collections.assert_called_once()
        orch.vector_engine.search_similar.assert_called()

    def test_semantic_prioritises_matching_tables(self) -> None:
        """Tables whose name appears in the question are searched first."""
        orch = _make_orchestrator(_semantic_classification())
        similar_record = MagicMock()
        similar_record.id = "1"
        similar_record.record = {"make": "Chevrolet"}
        orch.vector_engine.search_similar.return_value = [similar_record]

        result = orch.ask("Find vehicles like the Corvette")
        first_call = orch.vector_engine.search_similar.call_args_list[0]
        assert first_call.kwargs["table_name"] == "vehicles"
        assert result.similar_records is not None

    def test_knowledge_context_gathered(self) -> None:
        """Knowledge is gathered when needs_knowledge is True."""
        orch = _make_orchestrator(_strategic_classification())
        orch.ask("What is the ideal inventory?")
        orch.knowledge.export_for_prompt.assert_called_once()

    def test_hybrid_gathers_all(self) -> None:
        """Hybrid classification gathers SQL, semantic, and knowledge."""
        orch = _make_orchestrator(_hybrid_classification())
        orch.ask("What makes our best sales successful?")
        orch.sql_engine.natural_to_sql.assert_called_once()
        orch.vector_engine.list_collections.assert_called_once()
        orch.knowledge.export_for_prompt.assert_called_once()

    def test_no_sql_when_not_needed(self) -> None:
        """SQL engine is not called when needs_sql is False."""
        orch = _make_orchestrator(_semantic_classification())
        orch.ask("Find similar records")
        orch.sql_engine.natural_to_sql.assert_not_called()
        orch.sql_engine.execute.assert_not_called()

    def test_no_semantic_when_not_needed(self) -> None:
        """Vector engine is not called when needs_semantic is False."""
        orch = _make_orchestrator(_sql_classification())
        orch.ask("How many vehicles?")
        orch.vector_engine.list_collections.assert_not_called()
        orch.vector_engine.search_similar.assert_not_called()


# ---------------------------------------------------------------------------
# Tests -- synthesis
# ---------------------------------------------------------------------------


class TestSynthesis:
    """Tests for the _synthesize method."""

    def test_synthesis_prompt_contains_question(self) -> None:
        """The synthesis prompt includes the user's question."""
        orch = _make_orchestrator()
        orch.ask("How many vehicles are over 60 days?")
        prompt = orch.llm.chat.call_args.kwargs["messages"][0]["content"]
        assert "How many vehicles are over 60 days?" in prompt

    def test_strategic_prompt_used_for_strategic_queries(self) -> None:
        """Strategic queries use the STRATEGIC_PROMPT template."""
        orch = _make_orchestrator(_strategic_classification())
        orch.ask("What is the ideal inventory?")
        prompt = orch.llm.chat.call_args.kwargs["messages"][0]["content"]
        assert "business strategist" in prompt.lower()

    def test_non_strategic_uses_synthesis_prompt(self) -> None:
        """Non-strategic queries use the SYNTHESIS_PROMPT template."""
        orch = _make_orchestrator(_sql_classification())
        orch.ask("How many vehicles?")
        prompt = orch.llm.chat.call_args.kwargs["messages"][0]["content"]
        assert "business analyst" in prompt.lower()

    def test_llm_answer_in_response(self) -> None:
        """The LLM's answer appears in the response."""
        orch = _make_orchestrator()
        orch.llm.chat.return_value = "Exactly 42 vehicles."
        result = orch.ask("How many vehicles?")
        assert result.answer == "Exactly 42 vehicles."


# ---------------------------------------------------------------------------
# Tests -- error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error resilience."""

    def test_sql_error_captured(self) -> None:
        """SQL errors are captured and the orchestrator still responds."""
        orch = _make_orchestrator(_sql_classification())
        orch.sql_engine.natural_to_sql.side_effect = RuntimeError("DB locked")
        result = orch.ask("How many vehicles?")
        assert isinstance(result, IntelligenceResponse)
        assert result.sql_used is None

    def test_semantic_error_captured(self) -> None:
        """Semantic search errors are captured gracefully."""
        orch = _make_orchestrator(_semantic_classification())
        orch.vector_engine.list_collections.side_effect = RuntimeError("ChromaDB down")
        result = orch.ask("Find similar vehicles")
        assert isinstance(result, IntelligenceResponse)
        assert result.similar_records is None

    def test_llm_synthesis_error_captured(self) -> None:
        """LLM synthesis errors produce a graceful fallback answer."""
        orch = _make_orchestrator()
        orch.llm.chat.side_effect = ConnectionError("LLM unreachable")
        result = orch.ask("How many vehicles?")
        assert "unable to fully analyze" in result.answer.lower()

    def test_sql_error_noted_in_synthesis_prompt(self) -> None:
        """When SQL fails, the error is noted in the synthesis prompt."""
        orch = _make_orchestrator(_sql_classification())
        orch.sql_engine.natural_to_sql.side_effect = RuntimeError("table missing")
        orch.ask("How many vehicles?")
        prompt = orch.llm.chat.call_args.kwargs["messages"][0]["content"]
        assert "table missing" in prompt


# ---------------------------------------------------------------------------
# Tests -- IntelligenceResponse dataclass
# ---------------------------------------------------------------------------


class TestIntelligenceResponse:
    """Tests for the IntelligenceResponse dataclass."""

    def test_defaults(self) -> None:
        """Default field values are applied correctly."""
        resp = IntelligenceResponse(answer="Hello")
        assert resp.answer == "Hello"
        assert resp.supporting_data is None
        assert resp.reasoning == ""
        assert resp.sql_used is None
        assert resp.similar_records is None
        assert resp.classification is None
        assert resp.confidence == 0.0

    def test_all_fields(self) -> None:
        """All fields can be set explicitly."""
        resp = IntelligenceResponse(
            answer="Test",
            supporting_data=[{"a": 1}],
            reasoning="because",
            sql_used="SELECT 1",
            similar_records=[{"id": "x"}],
            classification="sql",
            confidence=0.95,
        )
        assert resp.supporting_data == [{"a": 1}]
        assert resp.confidence == 0.95
