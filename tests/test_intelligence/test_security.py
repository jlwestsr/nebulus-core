"""Tests for the security module."""

import pytest

from nebulus_core.intelligence.core.security import (
    ValidationError,
    quote_identifier,
    sanitize_table_name,
    validate_column_name,
    validate_limit,
    validate_sql_query,
    validate_table_name,
)


class TestValidateTableName:
    """Tests for validate_table_name function."""

    def test_valid_table_names(self):
        assert validate_table_name("users") == "users"
        assert validate_table_name("user_data") == "user_data"
        assert validate_table_name("Table1") == "Table1"
        assert validate_table_name("_private") == "_private"

    def test_empty_table_name(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_table_name("")

    def test_table_name_too_long(self):
        with pytest.raises(ValidationError, match="too long"):
            validate_table_name("a" * 200)

    def test_invalid_characters(self):
        with pytest.raises(ValidationError, match="Invalid table name"):
            validate_table_name("users; DROP TABLE")
        with pytest.raises(ValidationError, match="Invalid table name"):
            validate_table_name("table with spaces")

    def test_reserved_keywords(self):
        with pytest.raises(ValidationError, match="reserved SQL keyword"):
            validate_table_name("select")
        with pytest.raises(ValidationError, match="reserved SQL keyword"):
            validate_table_name("DROP")


class TestValidateColumnName:
    """Tests for validate_column_name function."""

    def test_valid_column_names(self):
        assert validate_column_name("id") == "id"
        assert validate_column_name("user_name") == "user_name"

    def test_empty_column_name(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_column_name("")

    def test_invalid_column_characters(self):
        with pytest.raises(ValidationError, match="Invalid column name"):
            validate_column_name("column; DROP")


class TestSanitizeTableName:
    """Tests for sanitize_table_name function."""

    def test_basic_sanitization(self):
        assert sanitize_table_name("users") == "users"
        assert sanitize_table_name("User Data") == "user_data"
        assert sanitize_table_name("table-name") == "table_name"

    def test_empty_input(self):
        assert sanitize_table_name("") == "table_data"

    def test_numeric_start(self):
        assert sanitize_table_name("123table") == "t_123table"

    def test_reserved_keyword(self):
        assert sanitize_table_name("select") == "select_table"

    def test_special_characters(self):
        assert sanitize_table_name("my@table!") == "my_table"


class TestQuoteIdentifier:
    """Tests for quote_identifier function."""

    def test_basic_quoting(self):
        assert quote_identifier("users") == '"users"'

    def test_double_quote_escaping(self):
        assert quote_identifier('user"name') == '"user""name"'


class TestValidateSqlQuery:
    """Tests for validate_sql_query function."""

    def test_valid_select_queries(self):
        assert validate_sql_query("SELECT * FROM users") == "SELECT * FROM users"

    def test_empty_query(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_sql_query("")

    def test_non_select_blocked(self):
        with pytest.raises(ValidationError, match="Only SELECT"):
            validate_sql_query("INSERT INTO users VALUES (1)")

    def test_dangerous_keywords_blocked(self):
        with pytest.raises(ValidationError, match="forbidden keyword"):
            validate_sql_query("SELECT * FROM users; DROP TABLE users")

    def test_comment_injection_blocked(self):
        with pytest.raises(ValidationError, match="comments"):
            validate_sql_query("SELECT * FROM users -- WHERE id = 1")

    def test_multiple_statements_blocked(self):
        with pytest.raises(ValidationError, match="Multiple SQL"):
            validate_sql_query("SELECT 1; SELECT 2")

    def test_allow_write_mode(self):
        validate_sql_query("INSERT INTO users VALUES (1)", allow_write=True)
        validate_sql_query("UPDATE users SET name = 'x'", allow_write=True)


class TestValidateLimit:
    """Tests for validate_limit function."""

    def test_valid_limits(self):
        assert validate_limit(10) == 10
        assert validate_limit(None) == 10000

    def test_limit_capped(self):
        assert validate_limit(50000) == 10000
        assert validate_limit(100, max_limit=50) == 50

    def test_negative_limit(self):
        with pytest.raises(ValidationError, match="non-negative"):
            validate_limit(-1)
