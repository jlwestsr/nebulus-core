"""Question classification for routing to appropriate engines.

Analyzes questions to determine the best approach for answering them,
using either LLM-based classification or simple rule-based heuristics.
"""

import json
from dataclasses import dataclass
from enum import Enum

from nebulus_core.llm.client import LLMClient


class QueryType(Enum):
    """Types of queries the system can handle."""

    SQL_ONLY = "sql"  # "How many cars over 60 days?"
    SEMANTIC_ONLY = "semantic"  # "Find sales like this one"
    STRATEGIC = "strategic"  # "What's ideal inventory?"
    HYBRID = "hybrid"  # Needs multiple sources


@dataclass
class ClassificationResult:
    """Result of question classification.

    Attributes:
        query_type: The determined type of query.
        reasoning: Explanation for the classification decision.
        needs_sql: Whether the query requires SQL database access.
        needs_semantic: Whether the query requires semantic/vector search.
        needs_knowledge: Whether the query requires knowledge graph access.
        suggested_tables: Database tables relevant to the query.
        confidence: Confidence score between 0.0 and 1.0.
    """

    query_type: QueryType
    reasoning: str
    needs_sql: bool
    needs_semantic: bool
    needs_knowledge: bool
    suggested_tables: list[str]
    confidence: float


class QuestionClassifier:
    """Classify questions to determine how to answer them.

    Uses an LLM to analyze questions and route them to the appropriate
    engine (SQL, semantic search, strategic reasoning, or hybrid).
    Falls back to rule-based classification when the LLM is unavailable.

    Args:
        llm: An LLMClient instance for making inference requests.
        model: The model identifier to use for classification.
    """

    CLASSIFICATION_PROMPT = (
        "You are a query classifier for a business "
        "intelligence system.\n\n"
        "Analyze this question and determine how to answer it.\n\n"
        'Question: "{question}"\n\n'
        "Available database tables and columns:\n"
        "{schema}\n\n"
        "Question Types:\n"
        "1. SQL_ONLY - Can be answered with a database query "
        "(counts, sums, filters, joins, aggregations)\n"
        '   Examples: "How many vehicles?", '
        '"Average sale price last month?"\n\n'
        "2. SEMANTIC_ONLY - Needs similarity or pattern matching, "
        "not exact queries\n"
        '   Examples: "Find sales similar to this one", '
        '"What vehicles are like the Corvette?"\n\n'
        "3. STRATEGIC - Requires reasoning about what's "
        '"best" or "ideal" using business knowledge\n'
        '   Examples: "What\'s our ideal inventory?", '
        '"Which salespeople should we hire more like?"\n\n'
        "4. HYBRID - Needs data from multiple approaches "
        "combined\n"
        '   Examples: "What makes our best sales successful?" '
        "(needs SQL + patterns + knowledge)\n\n"
        "Respond with JSON only:\n"
        "{{\n"
        '    "query_type": "sql" | "semantic" | '
        '"strategic" | "hybrid",\n'
        '    "reasoning": "Brief explanation of '
        'why this classification",\n'
        '    "needs_sql": true | false,\n'
        '    "needs_semantic": true | false,\n'
        '    "needs_knowledge": true | false,\n'
        '    "suggested_tables": ["table1", "table2"],\n'
        '    "confidence": 0.0 to 1.0\n'
        "}}"
    )

    def __init__(self, llm: LLMClient, model: str) -> None:
        """Initialize the classifier.

        Args:
            llm: An LLMClient instance for making inference requests.
            model: The model identifier to use for classification.
        """
        self.llm = llm
        self.model = model

    def classify(
        self,
        question: str,
        schema: dict,
    ) -> ClassificationResult:
        """Classify a question to determine how to answer it.

        Uses the LLM to analyze the question against the provided database
        schema and determine the best query strategy.

        Args:
            question: The user's question.
            schema: Database schema information mapping table names to
                column/type metadata.

        Returns:
            ClassificationResult with query type and routing flags.
        """
        schema_text = self._format_schema(schema)

        prompt = self.CLASSIFICATION_PROMPT.format(
            question=question,
            schema=schema_text,
        )

        try:
            content = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.1,
                max_tokens=500,
            )
            return self._parse_response(content)
        except Exception as e:
            return ClassificationResult(
                query_type=QueryType.SQL_ONLY,
                reasoning=f"Classification failed ({e}), defaulting to SQL",
                needs_sql=True,
                needs_semantic=False,
                needs_knowledge=False,
                suggested_tables=[],
                confidence=0.5,
            )

    def _format_schema(self, schema: dict) -> str:
        """Format schema dict into a human-readable string for the prompt.

        Args:
            schema: Mapping of table names to dicts with 'columns' and
                'types' keys.

        Returns:
            Formatted string describing the database schema.
        """
        if not schema:
            return "No tables available"

        lines = []
        for table_name, info in schema.items():
            columns = info.get("columns", [])
            types = info.get("types", {})

            col_strs = []
            for col in columns:
                col_type = types.get(col, "TEXT")
                col_strs.append(f"{col} ({col_type})")

            lines.append(f"- {table_name}: {', '.join(col_strs)}")

        return "\n".join(lines)

    def _parse_response(self, response: str) -> ClassificationResult:
        """Parse the LLM response into a ClassificationResult.

        Handles JSON responses, markdown-wrapped JSON, and falls back
        to keyword-based parsing if JSON extraction fails.

        Args:
            response: Raw text response from the LLM.

        Returns:
            Parsed ClassificationResult.
        """
        try:
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response.strip())

            type_map = {
                "sql": QueryType.SQL_ONLY,
                "semantic": QueryType.SEMANTIC_ONLY,
                "strategic": QueryType.STRATEGIC,
                "hybrid": QueryType.HYBRID,
            }

            query_type = type_map.get(
                data.get("query_type", "sql").lower(),
                QueryType.SQL_ONLY,
            )

            return ClassificationResult(
                query_type=query_type,
                reasoning=data.get("reasoning", ""),
                needs_sql=data.get("needs_sql", True),
                needs_semantic=data.get("needs_semantic", False),
                needs_knowledge=data.get("needs_knowledge", False),
                suggested_tables=data.get("suggested_tables", []),
                confidence=data.get("confidence", 0.8),
            )

        except (json.JSONDecodeError, KeyError, IndexError):
            # If parsing fails, make best guess from text
            response_lower = response.lower()

            if "strategic" in response_lower or "ideal" in response_lower:
                query_type = QueryType.STRATEGIC
                needs_knowledge = True
            elif "semantic" in response_lower or "similar" in response_lower:
                query_type = QueryType.SEMANTIC_ONLY
                needs_knowledge = False
            elif "hybrid" in response_lower:
                query_type = QueryType.HYBRID
                needs_knowledge = True
            else:
                query_type = QueryType.SQL_ONLY
                needs_knowledge = False

            return ClassificationResult(
                query_type=query_type,
                reasoning="Parsed from text response",
                needs_sql=query_type in (QueryType.SQL_ONLY, QueryType.HYBRID),
                needs_semantic=query_type
                in (QueryType.SEMANTIC_ONLY, QueryType.HYBRID),
                needs_knowledge=needs_knowledge,
                suggested_tables=[],
                confidence=0.6,
            )

    def classify_simple(self, question: str) -> ClassificationResult:
        """Simple rule-based classification without LLM call.

        Useful for quick classification or when the LLM is unavailable.
        Matches keywords in the question to determine query type.

        Args:
            question: The user's question.

        Returns:
            ClassificationResult based on keyword matching.
        """
        question_lower = question.lower()

        strategic_keywords = [
            "ideal",
            "best",
            "optimal",
            "should we",
            "recommend",
            "strategy",
            "what makes",
            "why do",
            "perfect",
        ]

        semantic_keywords = [
            "similar",
            "like this",
            "find like",
            "pattern",
            "common",
        ]

        if any(kw in question_lower for kw in strategic_keywords):
            return ClassificationResult(
                query_type=QueryType.STRATEGIC,
                reasoning="Contains strategic keywords",
                needs_sql=True,
                needs_semantic=True,
                needs_knowledge=True,
                suggested_tables=[],
                confidence=0.7,
            )

        if any(kw in question_lower for kw in semantic_keywords):
            return ClassificationResult(
                query_type=QueryType.SEMANTIC_ONLY,
                reasoning="Contains similarity keywords",
                needs_sql=False,
                needs_semantic=True,
                needs_knowledge=False,
                suggested_tables=[],
                confidence=0.7,
            )

        return ClassificationResult(
            query_type=QueryType.SQL_ONLY,
            reasoning="Appears to be a data query",
            needs_sql=True,
            needs_semantic=False,
            needs_knowledge=False,
            suggested_tables=[],
            confidence=0.7,
        )
