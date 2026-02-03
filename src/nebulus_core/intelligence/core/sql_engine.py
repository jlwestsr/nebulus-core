"""SQLite wrapper with natural-language-to-SQL conversion.

Uses the shared LLMClient for text-to-SQL generation and result
explanation, replacing the former async httpx Brain API calls.
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nebulus_core.intelligence.core.security import (
    ValidationError,
    quote_identifier,
    validate_sql_query,
)
from nebulus_core.llm.client import LLMClient


@dataclass
class QueryResult:
    """Result of a SQL query.

    Attributes:
        columns: Column names returned by the query.
        rows: Row data as a list of lists.
        row_count: Number of rows returned.
        sql: The SQL query that was executed.
    """

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    sql: str


class UnsafeQueryError(Exception):
    """Raised when a query is deemed unsafe to execute."""


class SQLEngine:
    """Execute SQL queries against a SQLite database with a natural-language interface.

    Args:
        db_path: Path to the SQLite database file.
        llm: An initialised LLMClient instance.
        model: Model identifier to use for LLM requests.
    """

    def __init__(self, db_path: Path, llm: LLMClient, model: str) -> None:
        self.db_path = db_path
        self.llm = llm
        self.model = model

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    def get_schema(self) -> dict[str, Any]:
        """Retrieve the database schema.

        Returns:
            A dict with a ``tables`` key mapping table names to their
            column metadata, row counts, and sample rows.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            schema: dict[str, Any] = {"tables": {}}

            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                quoted_table = quote_identifier(table)

                cursor = conn.execute(f"PRAGMA table_info({quoted_table})")
                columns = []
                for row in cursor.fetchall():
                    columns.append(
                        {
                            "name": row[1],
                            "type": row[2],
                            "nullable": not row[3],
                            "primary_key": bool(row[5]),
                        }
                    )

                cursor = conn.execute(f"SELECT * FROM {quoted_table} LIMIT 3")
                sample_rows = cursor.fetchall()

                cursor = conn.execute(f"SELECT COUNT(*) FROM {quoted_table}")
                row_count = cursor.fetchone()[0]

                schema["tables"][table] = {
                    "columns": columns,
                    "row_count": row_count,
                    "sample_rows": sample_rows,
                }

            return schema
        finally:
            conn.close()

    def get_schema_for_prompt(self) -> str:
        """Format the database schema as a human-readable string for LLM prompts.

        Returns:
            Multi-line string describing every table with its columns.
        """
        schema = self.get_schema()
        lines: list[str] = ["Database Schema:", ""]

        for table_name, table_info in schema["tables"].items():
            lines.append(f"Table: {table_name} ({table_info['row_count']} rows)")
            for col in table_info["columns"]:
                pk = " (PRIMARY KEY)" if col["primary_key"] else ""
                lines.append(f"  - {col['name']}: {col['type']}{pk}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Natural language -> SQL
    # ------------------------------------------------------------------

    def natural_to_sql(
        self,
        question: str,
        schema: dict[str, Any] | None = None,
    ) -> str:
        """Convert a natural-language question to a SQL query via the LLM.

        Args:
            question: Natural-language question from the user.
            schema: Optional pre-fetched schema dict. Fetched automatically
                when not provided.

        Returns:
            A SQL query string.
        """
        if schema is None:
            schema = self.get_schema()

        schema_str = self.get_schema_for_prompt()

        prompt = (
            "You are a SQL expert. Convert the following natural language "
            "question to a SQLite query.\n\n"
            f"{schema_str}\n"
            f"Question: {question}\n\n"
            "Rules:\n"
            "1. Return ONLY the SQL query, no explanation\n"
            "2. Use SQLite syntax\n"
            "3. Only use SELECT statements (no INSERT, UPDATE, DELETE)\n"
            "4. Use table and column names exactly as shown in the schema\n"
            "5. If the question cannot be answered with the available data, "
            "return: SELECT 'Cannot answer: <reason>' AS error\n\n"
            "SQL Query:"
        )

        content = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.1,
            max_tokens=1000,
        )

        return self._extract_sql(content)

    # ------------------------------------------------------------------
    # SQL extraction helper
    # ------------------------------------------------------------------

    def _extract_sql(self, content: str) -> str:
        """Extract a SQL query from raw LLM output.

        Handles responses wrapped in markdown code blocks as well as
        plain SQL text.

        Args:
            content: Raw LLM response string.

        Returns:
            Cleaned SQL query string.
        """
        content = content.strip()

        if content.startswith("```"):
            lines = content.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        content = content.strip()

        if content.endswith(";"):
            content = content[:-1]

        return content

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        safe: bool = True,
        params: tuple[Any, ...] | None = None,
    ) -> QueryResult:
        """Execute a SQL query against the database.

        Args:
            sql: SQL query to execute.
            safe: When ``True``, only SELECT statements are permitted.
            params: Optional positional parameters for the query.

        Returns:
            A ``QueryResult`` containing columns, rows, and metadata.

        Raises:
            UnsafeQueryError: If *safe* is ``True`` and the query fails
                validation.
        """
        sql = sql.strip()

        if safe:
            try:
                validate_sql_query(sql, allow_write=False)
            except ValidationError as exc:
                raise UnsafeQueryError(str(exc)) from exc

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(sql, params or ())

            columns = [desc[0] for desc in cursor.description or []]
            rows = [list(row) for row in cursor.fetchall()]

            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                sql=sql,
            )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def ask(self, question: str) -> QueryResult:
        """Answer a natural-language question by generating and executing SQL.

        Args:
            question: Natural-language question from the user.

        Returns:
            A ``QueryResult`` with the answer data.
        """
        sql = self.natural_to_sql(question)
        return self.execute(sql)

    def explain_results(
        self,
        question: str,
        sql: str,
        results: QueryResult,
    ) -> str:
        """Generate a natural-language explanation of query results.

        Args:
            question: The original natural-language question.
            sql: The SQL query that was executed.
            results: The ``QueryResult`` returned by ``execute()``.

        Returns:
            A concise, human-readable explanation of the results.
        """
        if results.row_count == 0:
            results_str = "No rows returned."
        else:
            rows_to_show = results.rows[:10]
            results_str = json.dumps(
                {
                    "columns": results.columns,
                    "rows": rows_to_show,
                    "total_rows": results.row_count,
                },
                indent=2,
            )

        prompt = (
            "Given the following question, SQL query, and results, "
            "provide a clear, concise answer.\n\n"
            f"Question: {question}\n\n"
            f"SQL Query: {sql}\n\n"
            f"Results:\n{results_str}\n\n"
            "Answer the question directly based on the results. "
            "Be specific with numbers and data. "
            "Keep the answer to 2-3 sentences."
        )

        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.7,
            max_tokens=1000,
        )
