"""Intelligence orchestrator -- coordinates all engines to answer questions.

The main entry point for all questions to the intelligence system.
Routes queries through classification, context gathering, and LLM synthesis.
"""

from dataclasses import dataclass
from typing import Any

from nebulus_core.intelligence.core.classifier import (
    ClassificationResult,
    QueryType,
    QuestionClassifier,
)
from nebulus_core.intelligence.core.knowledge import KnowledgeManager
from nebulus_core.intelligence.core.sql_engine import SQLEngine
from nebulus_core.intelligence.core.vector_engine import VectorEngine
from nebulus_core.llm.client import LLMClient


@dataclass
class IntelligenceResponse:
    """Complete response from the intelligence system.

    Attributes:
        answer: The synthesized answer text.
        supporting_data: Rows returned by a SQL query, if any.
        reasoning: Explanation of how the question was classified.
        sql_used: The SQL query that was executed, if any.
        similar_records: Records found via semantic search, if any.
        classification: String label for the query type.
        confidence: Classification confidence between 0.0 and 1.0.
    """

    answer: str
    supporting_data: list[dict[str, Any]] | None = None
    reasoning: str = ""
    sql_used: str | None = None
    similar_records: list[dict[str, Any]] | None = None
    classification: str | None = None
    confidence: float = 0.0


class IntelligenceOrchestrator:
    """Main query orchestrator -- coordinates all intelligence engines.

    Accepts a question, classifies it, gathers context from the appropriate
    engines (SQL, vector/semantic, knowledge), and synthesises a final answer
    using the shared ``LLMClient``.

    Args:
        classifier: Question classifier instance.
        sql_engine: SQL engine for database queries.
        vector_engine: Vector engine for semantic search.
        knowledge: Knowledge manager for domain rules.
        llm: Shared LLM client for synthesis requests.
        model: Model identifier passed to every LLM call.
    """

    SYNTHESIS_PROMPT = (
        "You are an AI business analyst. Based on the context below,\n"
        "answer the user's question clearly and actionably.\n\n"
        'Question: "{question}"\n\n'
        "{context}\n\n"
        "Guidelines:\n"
        "- Be specific and data-driven\n"
        "- Provide actionable recommendations when appropriate\n"
        "- Reference the supporting data in your answer\n"
        "- If the data is insufficient, say so clearly\n\n"
        "Answer:"
    )

    STRATEGIC_PROMPT = (
        "You are an AI business strategist for a {vertical}.\n\n"
        'Question: "{question}"\n\n'
        "{domain_knowledge}\n\n"
        "{data_context}\n\n"
        "Based on the domain knowledge and data above, provide strategic "
        "recommendations.\n"
        "Be specific, actionable, and reference both the business rules "
        "and the actual data.\n\n"
        "Strategic Analysis:"
    )

    def __init__(
        self,
        classifier: QuestionClassifier,
        sql_engine: SQLEngine,
        vector_engine: VectorEngine,
        knowledge: KnowledgeManager,
        llm: LLMClient,
        model: str,
    ) -> None:
        self.classifier = classifier
        self.sql_engine = sql_engine
        self.vector_engine = vector_engine
        self.knowledge = knowledge
        self.llm = llm
        self.model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        use_simple_classification: bool = False,
        template_name: str = "generic",
    ) -> IntelligenceResponse:
        """Answer any question about the data.

        This is the main entry point that:

        1. Classifies the question type.
        2. Gathers context from the appropriate engines.
        3. Injects domain knowledge if needed.
        4. Synthesises a final answer via the LLM.

        Args:
            question: The user's natural-language question.
            use_simple_classification: Use rule-based classification
                (faster, no LLM call).
            template_name: Vertical template name used in strategic
                prompts.

        Returns:
            IntelligenceResponse with the answer and supporting data.
        """
        schema = self.sql_engine.get_schema()

        if use_simple_classification:
            classification = self.classifier.classify_simple(question)
        else:
            classification = self.classifier.classify(question, schema)

        context = self._gather_context(question, classification, schema)

        return self._synthesize(question, context, classification, template_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gather_context(
        self,
        question: str,
        classification: ClassificationResult,
        schema: dict,
    ) -> dict[str, Any]:
        """Gather relevant context from the appropriate engines.

        Args:
            question: The user's question.
            classification: Result from the classifier.
            schema: Database schema dict.

        Returns:
            Dict with keys for sql_results, sql_query, similar_records,
            knowledge, and tables.
        """
        table_names = list(schema.get("tables", {}).keys())

        context: dict[str, Any] = {
            "sql_results": None,
            "sql_query": None,
            "similar_records": None,
            "knowledge": None,
            "tables": table_names,
        }

        if classification.needs_sql:
            try:
                sql = self.sql_engine.natural_to_sql(question)
                result = self.sql_engine.execute(sql)
                context["sql_query"] = sql
                context["sql_results"] = [
                    dict(zip(result.columns, row)) for row in result.rows[:50]
                ]
            except Exception as exc:
                context["sql_error"] = str(exc)

        if classification.needs_semantic:
            try:
                collections = self.vector_engine.list_collections()
                tables_with_vectors = [t for t in table_names if t in collections]

                question_lower = question.lower()
                prioritized: list[str] = []
                others: list[str] = []

                for table in tables_with_vectors:
                    table_singular = table.rstrip("s")
                    if table in question_lower or table_singular in question_lower:
                        prioritized.append(table)
                    else:
                        others.append(table)

                for table in prioritized + others:
                    similar = self.vector_engine.search_similar(
                        table_name=table,
                        query=question,
                        n_results=10,
                    )
                    if similar:
                        context["similar_records"] = [
                            {
                                "table": table,
                                "id": r.id,
                                "record": r.record,
                            }
                            for r in similar
                        ]
                        break
            except Exception as exc:
                context["semantic_error"] = str(exc)

        if classification.needs_knowledge:
            context["knowledge"] = self.knowledge.export_for_prompt()

        return context

    def _synthesize(
        self,
        question: str,
        context: dict[str, Any],
        classification: ClassificationResult,
        template_name: str = "generic",
    ) -> IntelligenceResponse:
        """Synthesize a final answer from gathered context.

        Args:
            question: The user's question.
            context: Context dict from ``_gather_context``.
            classification: Classification result.
            template_name: Vertical template name for strategic prompts.

        Returns:
            IntelligenceResponse with the synthesised answer.
        """
        context_parts: list[str] = []

        if context.get("sql_results"):
            data_preview = context["sql_results"][:10]
            context_parts.append(f"## Data Results\n```json\n{data_preview}\n```")
            if context.get("sql_query"):
                context_parts.append(f"SQL Used: `{context['sql_query']}`")

        if context.get("similar_records"):
            context_parts.append(
                f"## Similar Records Found\n" f"{context['similar_records'][:5]}"
            )

        if context.get("knowledge"):
            context_parts.append(f"## Domain Knowledge\n{context['knowledge']}")

        if context.get("sql_error"):
            context_parts.append(f"Note: SQL query failed - {context['sql_error']}")

        context_text = "\n\n".join(context_parts) if context_parts else "No data found."

        if classification.query_type == QueryType.STRATEGIC:
            prompt = self.STRATEGIC_PROMPT.format(
                vertical=template_name,
                question=question,
                domain_knowledge=context.get("knowledge", "No domain knowledge."),
                data_context=context_text,
            )
        else:
            prompt = self.SYNTHESIS_PROMPT.format(
                question=question,
                context=context_text,
            )

        try:
            answer = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.7,
                max_tokens=1000,
            )
        except Exception as exc:
            answer = f"I was unable to fully analyze your question: {exc}"

        return IntelligenceResponse(
            answer=answer,
            supporting_data=context.get("sql_results"),
            reasoning=classification.reasoning,
            sql_used=context.get("sql_query"),
            similar_records=context.get("similar_records"),
            classification=classification.query_type.value,
            confidence=classification.confidence,
        )
