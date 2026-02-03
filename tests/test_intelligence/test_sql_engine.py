"""Tests for the SQL engine module."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nebulus_core.intelligence.core.sql_engine import (
    QueryResult,
    SQLEngine,
    UnsafeQueryError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_db(tmp_path: Path) -> Path:
    """Create a temporary SQLite database with sample data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE vehicles ("
        "  id INTEGER PRIMARY KEY,"
        "  make TEXT NOT NULL,"
        "  model TEXT NOT NULL,"
        "  year INTEGER NOT NULL,"
        "  price REAL NOT NULL"
        ")"
    )
    conn.executemany(
        "INSERT INTO vehicles (make, model, year, price) VALUES (?, ?, ?, ?)",
        [
            ("Toyota", "Camry", 2022, 28000.0),
            ("Honda", "Civic", 2023, 25000.0),
            ("Ford", "F-150", 2021, 35000.0),
            ("Toyota", "Corolla", 2023, 22000.0),
        ],
    )
    conn.execute(
        "CREATE TABLE sales ("
        "  id INTEGER PRIMARY KEY,"
        "  vehicle_id INTEGER NOT NULL,"
        "  sale_price REAL NOT NULL,"
        "  sale_date TEXT NOT NULL"
        ")"
    )
    conn.executemany(
        "INSERT INTO sales (vehicle_id, sale_price, sale_date) " "VALUES (?, ?, ?)",
        [
            (1, 27500.0, "2023-06-15"),
            (2, 24500.0, "2023-07-20"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def mock_llm() -> MagicMock:
    """Create a mock LLMClient."""
    return MagicMock()


@pytest.fixture()
def engine(sample_db: Path, mock_llm: MagicMock) -> SQLEngine:
    """Create an SQLEngine instance backed by the sample database."""
    return SQLEngine(db_path=sample_db, llm=mock_llm, model="test-model")


# ---------------------------------------------------------------------------
# Tests -- schema introspection
# ---------------------------------------------------------------------------


class TestGetSchema:
    """Tests for get_schema() and get_schema_for_prompt()."""

    def test_get_schema_returns_all_tables(self, engine: SQLEngine) -> None:
        """Schema includes both tables from the sample DB."""
        schema = engine.get_schema()

        assert "vehicles" in schema["tables"]
        assert "sales" in schema["tables"]

    def test_get_schema_column_metadata(self, engine: SQLEngine) -> None:
        """Column metadata contains name, type, nullable, and pk info."""
        schema = engine.get_schema()
        cols = schema["tables"]["vehicles"]["columns"]
        names = [c["name"] for c in cols]

        assert "id" in names
        assert "make" in names
        assert "price" in names

        id_col = next(c for c in cols if c["name"] == "id")
        assert id_col["primary_key"] is True

    def test_get_schema_row_count(self, engine: SQLEngine) -> None:
        """Row counts are accurate."""
        schema = engine.get_schema()

        assert schema["tables"]["vehicles"]["row_count"] == 4
        assert schema["tables"]["sales"]["row_count"] == 2

    def test_get_schema_for_prompt_readable(self, engine: SQLEngine) -> None:
        """Prompt schema contains human-readable table descriptions."""
        text = engine.get_schema_for_prompt()

        assert "Table: vehicles" in text
        assert "Table: sales" in text
        assert "make: TEXT" in text
        assert "PRIMARY KEY" in text


# ---------------------------------------------------------------------------
# Tests -- natural_to_sql
# ---------------------------------------------------------------------------


class TestNaturalToSQL:
    """Tests for the LLM-powered natural_to_sql() method."""

    def test_natural_to_sql_basic(self, engine: SQLEngine) -> None:
        """LLM response is forwarded as a SQL string."""
        engine.llm.chat.return_value = "SELECT COUNT(*) FROM vehicles"

        sql = engine.natural_to_sql("How many vehicles?")

        assert sql == "SELECT COUNT(*) FROM vehicles"

    def test_natural_to_sql_strips_markdown(self, engine: SQLEngine) -> None:
        """Markdown code fences are removed from the LLM response."""
        engine.llm.chat.return_value = "```sql\nSELECT * FROM vehicles;\n```"

        sql = engine.natural_to_sql("Show all vehicles")

        assert sql == "SELECT * FROM vehicles"

    def test_natural_to_sql_strips_plain_code_block(self, engine: SQLEngine) -> None:
        """Plain (non-sql) code fences are handled correctly."""
        engine.llm.chat.return_value = "```\nSELECT make FROM vehicles;\n```"

        sql = engine.natural_to_sql("List all makes")

        assert sql == "SELECT make FROM vehicles"

    def test_natural_to_sql_removes_trailing_semicolon(self, engine: SQLEngine) -> None:
        """Trailing semicolons are stripped for consistency."""
        engine.llm.chat.return_value = "SELECT 1;"

        sql = engine.natural_to_sql("Return one")

        assert sql == "SELECT 1"

    def test_natural_to_sql_llm_params(self, engine: SQLEngine) -> None:
        """LLM is called with the expected parameters."""
        engine.llm.chat.return_value = "SELECT 1"

        engine.natural_to_sql("test question")

        engine.llm.chat.assert_called_once()
        kwargs = engine.llm.chat.call_args.kwargs
        assert kwargs["model"] == "test-model"
        assert kwargs["temperature"] == 0.1
        assert kwargs["max_tokens"] == 1000
        messages = kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "test question" in messages[0]["content"]

    def test_natural_to_sql_uses_provided_schema(self, engine: SQLEngine) -> None:
        """When a schema dict is passed, the method still works."""
        engine.llm.chat.return_value = "SELECT 1"
        custom_schema: dict = {"tables": {"custom": {"columns": []}}}

        sql = engine.natural_to_sql("anything", schema=custom_schema)

        assert sql == "SELECT 1"


# ---------------------------------------------------------------------------
# Tests -- execute
# ---------------------------------------------------------------------------


class TestExecute:
    """Tests for the execute() method."""

    def test_execute_select(self, engine: SQLEngine) -> None:
        """A simple SELECT returns the correct rows."""
        result = engine.execute("SELECT make, model FROM vehicles ORDER BY id")

        assert result.columns == ["make", "model"]
        assert result.row_count == 4
        assert result.rows[0] == ["Toyota", "Camry"]

    def test_execute_count(self, engine: SQLEngine) -> None:
        """Aggregate queries return expected results."""
        result = engine.execute("SELECT COUNT(*) AS total FROM vehicles")

        assert result.columns == ["total"]
        assert result.rows == [[4]]
        assert result.row_count == 1

    def test_execute_with_params(self, engine: SQLEngine) -> None:
        """Parameterised queries work correctly."""
        result = engine.execute(
            "SELECT model FROM vehicles WHERE make = ?",
            params=("Toyota",),
        )

        assert result.row_count == 2
        models = [r[0] for r in result.rows]
        assert "Camry" in models
        assert "Corolla" in models

    def test_execute_stores_sql(self, engine: SQLEngine) -> None:
        """QueryResult includes the SQL that was executed."""
        result = engine.execute("SELECT 1 AS one")

        assert result.sql == "SELECT 1 AS one"

    def test_execute_join(self, engine: SQLEngine) -> None:
        """Joins across tables work correctly."""
        sql = (
            "SELECT v.make, v.model, s.sale_price "
            "FROM vehicles v "
            "JOIN sales s ON v.id = s.vehicle_id "
            "ORDER BY s.sale_price"
        )
        result = engine.execute(sql)

        assert result.row_count == 2
        assert result.rows[0][0] == "Honda"


# ---------------------------------------------------------------------------
# Tests -- SQL safety / validation
# ---------------------------------------------------------------------------


class TestSQLSafety:
    """Tests for SQL safety validation during execute()."""

    def test_reject_drop_table(self, engine: SQLEngine) -> None:
        """DROP TABLE is rejected when safe=True."""
        with pytest.raises(UnsafeQueryError):
            engine.execute("DROP TABLE vehicles")

    def test_reject_delete(self, engine: SQLEngine) -> None:
        """DELETE is rejected when safe=True."""
        with pytest.raises(UnsafeQueryError):
            engine.execute("DELETE FROM vehicles WHERE id = 1")

    def test_reject_insert(self, engine: SQLEngine) -> None:
        """INSERT is rejected when safe=True."""
        with pytest.raises(UnsafeQueryError):
            engine.execute(
                "INSERT INTO vehicles (make, model, year, price) "
                "VALUES ('BMW', 'X5', 2023, 60000)"
            )

    def test_reject_update(self, engine: SQLEngine) -> None:
        """UPDATE is rejected when safe=True."""
        with pytest.raises(UnsafeQueryError):
            engine.execute("UPDATE vehicles SET price = 0 WHERE id = 1")

    def test_reject_multiple_statements(self, engine: SQLEngine) -> None:
        """Multiple semicolon-separated statements are rejected."""
        with pytest.raises(UnsafeQueryError):
            engine.execute("SELECT 1; DROP TABLE vehicles")

    def test_reject_comment_injection(self, engine: SQLEngine) -> None:
        """SQL comments are rejected."""
        with pytest.raises(UnsafeQueryError):
            engine.execute("SELECT 1 -- malicious comment")

    def test_safe_false_allows_write(self, engine: SQLEngine) -> None:
        """When safe=False, write statements are permitted."""
        result = engine.execute(
            "INSERT INTO vehicles (make, model, year, price) "
            "VALUES ('BMW', 'X5', 2023, 60000)",
            safe=False,
        )
        # INSERT returns no columns
        assert result.columns == []


# ---------------------------------------------------------------------------
# Tests -- ask (end-to-end)
# ---------------------------------------------------------------------------


class TestAsk:
    """Tests for the high-level ask() helper."""

    def test_ask_returns_query_result(self, engine: SQLEngine) -> None:
        """ask() generates SQL via LLM and executes it."""
        engine.llm.chat.return_value = "SELECT COUNT(*) AS total FROM vehicles"

        result = engine.ask("How many vehicles?")

        assert isinstance(result, QueryResult)
        assert result.rows == [[4]]
        assert result.sql == "SELECT COUNT(*) AS total FROM vehicles"


# ---------------------------------------------------------------------------
# Tests -- explain_results
# ---------------------------------------------------------------------------


class TestExplainResults:
    """Tests for the explain_results() method."""

    def test_explain_results_calls_llm(self, engine: SQLEngine) -> None:
        """explain_results() sends the right data to the LLM."""
        engine.llm.chat.return_value = "There are 4 vehicles total."
        qr = QueryResult(
            columns=["total"],
            rows=[[4]],
            row_count=1,
            sql="SELECT COUNT(*) AS total FROM vehicles",
        )

        explanation = engine.explain_results(
            question="How many vehicles?",
            sql=qr.sql,
            results=qr,
        )

        assert explanation == "There are 4 vehicles total."
        engine.llm.chat.assert_called_once()
        kwargs = engine.llm.chat.call_args.kwargs
        assert kwargs["model"] == "test-model"
        prompt_content = kwargs["messages"][0]["content"]
        assert "How many vehicles?" in prompt_content

    def test_explain_empty_results(self, engine: SQLEngine) -> None:
        """explain_results() handles zero-row results gracefully."""
        engine.llm.chat.return_value = "No matching records found."
        qr = QueryResult(
            columns=["make"],
            rows=[],
            row_count=0,
            sql="SELECT make FROM vehicles WHERE year > 2025",
        )

        explanation = engine.explain_results(
            question="Future vehicles?",
            sql=qr.sql,
            results=qr,
        )

        assert explanation == "No matching records found."
        prompt_content = engine.llm.chat.call_args.kwargs["messages"][0]["content"]
        assert "No rows returned." in prompt_content

    def test_explain_limits_rows_to_ten(self, engine: SQLEngine) -> None:
        """Only the first 10 rows are included in the prompt."""
        engine.llm.chat.return_value = "Summary."
        many_rows = [[i] for i in range(25)]
        qr = QueryResult(
            columns=["id"],
            rows=many_rows,
            row_count=25,
            sql="SELECT id FROM big_table",
        )

        engine.explain_results(
            question="Show everything",
            sql=qr.sql,
            results=qr,
        )

        prompt_content = engine.llm.chat.call_args.kwargs["messages"][0]["content"]
        # The prompt should include total_rows: 25 but only 10 row entries
        assert '"total_rows": 25' in prompt_content
        # The JSON rows list should contain exactly 10 entries (indices 0-9)
        import json

        # Parse the JSON portion out of the prompt to verify row count
        json_start = prompt_content.index("{")
        json_end = prompt_content.rindex("}") + 1
        parsed = json.loads(prompt_content[json_start:json_end])
        assert len(parsed["rows"]) == 10
        assert parsed["rows"][-1] == [9]


# ---------------------------------------------------------------------------
# Tests -- _extract_sql helper
# ---------------------------------------------------------------------------


class TestExtractSQL:
    """Tests for the _extract_sql() private helper."""

    def test_plain_sql(self, engine: SQLEngine) -> None:
        """Plain SQL is returned as-is (minus trailing semicolon)."""
        assert engine._extract_sql("SELECT 1;") == "SELECT 1"

    def test_markdown_sql_block(self, engine: SQLEngine) -> None:
        """SQL inside ```sql ... ``` is extracted."""
        raw = "```sql\nSELECT * FROM t\n```"
        assert engine._extract_sql(raw) == "SELECT * FROM t"

    def test_markdown_plain_block(self, engine: SQLEngine) -> None:
        """SQL inside plain ``` ... ``` is extracted."""
        raw = "```\nSELECT 1\n```"
        assert engine._extract_sql(raw) == "SELECT 1"

    def test_whitespace_stripped(self, engine: SQLEngine) -> None:
        """Leading/trailing whitespace is removed."""
        assert engine._extract_sql("  SELECT 1  ") == "SELECT 1"


# ---------------------------------------------------------------------------
# Tests -- QueryResult dataclass
# ---------------------------------------------------------------------------


class TestQueryResult:
    """Tests for the QueryResult dataclass."""

    def test_creation(self) -> None:
        """QueryResult stores all fields correctly."""
        qr = QueryResult(
            columns=["a", "b"],
            rows=[[1, 2]],
            row_count=1,
            sql="SELECT a, b FROM t",
        )

        assert qr.columns == ["a", "b"]
        assert qr.rows == [[1, 2]]
        assert qr.row_count == 1
        assert qr.sql == "SELECT a, b FROM t"
