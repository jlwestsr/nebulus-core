"""Security utilities for input validation and sanitization."""

import re


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


# Pattern for valid SQL identifiers (table names, column names)
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Maximum lengths
MAX_TABLE_NAME_LENGTH = 128
MAX_COLUMN_NAME_LENGTH = 128
MAX_SQL_LENGTH = 10000

# Reserved SQL keywords that cannot be used as table names
RESERVED_KEYWORDS = {
    "select",
    "insert",
    "update",
    "delete",
    "drop",
    "create",
    "alter",
    "table",
    "index",
    "where",
    "from",
    "join",
    "union",
    "order",
    "group",
    "having",
    "limit",
    "offset",
    "and",
    "or",
    "not",
    "null",
    "true",
    "false",
    "as",
    "on",
    "in",
    "is",
    "like",
    "between",
    "exists",
    "case",
    "when",
    "then",
    "else",
    "end",
    "begin",
    "commit",
    "rollback",
    "transaction",
    "pragma",
    "attach",
    "detach",
    "vacuum",
    "analyze",
    "explain",
}


def validate_table_name(name: str) -> str:
    """Validate and sanitize a table name.

    Args:
        name: The table name to validate.

    Returns:
        The validated table name.

    Raises:
        ValidationError: If the table name is invalid.
    """
    if not name:
        raise ValidationError("Table name cannot be empty")

    if len(name) > MAX_TABLE_NAME_LENGTH:
        raise ValidationError(
            f"Table name too long (max {MAX_TABLE_NAME_LENGTH} characters)"
        )

    if not IDENTIFIER_PATTERN.match(name):
        raise ValidationError(
            f"Invalid table name '{name}'. "
            "Must start with letter or underscore, "
            "contain only alphanumeric characters and underscores."
        )

    if name.lower() in RESERVED_KEYWORDS:
        raise ValidationError(f"Table name '{name}' is a reserved SQL keyword")

    return name


def validate_column_name(name: str) -> str:
    """Validate and sanitize a column name.

    Args:
        name: The column name to validate.

    Returns:
        The validated column name.

    Raises:
        ValidationError: If the column name is invalid.
    """
    if not name:
        raise ValidationError("Column name cannot be empty")

    if len(name) > MAX_COLUMN_NAME_LENGTH:
        raise ValidationError(
            f"Column name too long (max {MAX_COLUMN_NAME_LENGTH} characters)"
        )

    if not IDENTIFIER_PATTERN.match(name):
        raise ValidationError(
            f"Invalid column name '{name}'. "
            "Must start with letter or underscore, "
            "contain only alphanumeric characters and underscores."
        )

    return name


def sanitize_table_name(name: str) -> str:
    """Sanitize a table name, converting invalid characters.

    Unlike validate_table_name, this doesn't raise an error but
    attempts to fix the name.

    Args:
        name: The table name to sanitize.

    Returns:
        A sanitized, valid table name.
    """
    if not name:
        return "table_data"

    # Convert to lowercase and replace invalid chars with underscore
    clean = "".join(c if c.isalnum() else "_" for c in name.lower())

    # Remove leading/trailing underscores
    clean = clean.strip("_")

    # Ensure it doesn't start with a number
    if clean and clean[0].isdigit():
        clean = "t_" + clean

    # Ensure not empty after cleaning
    if not clean:
        clean = "table_data"

    # Truncate if too long
    if len(clean) > MAX_TABLE_NAME_LENGTH:
        clean = clean[:MAX_TABLE_NAME_LENGTH]

    # Check if it's a reserved keyword
    if clean.lower() in RESERVED_KEYWORDS:
        clean = clean + "_table"

    return clean


def quote_identifier(name: str) -> str:
    """Quote an identifier for safe use in SQL.

    Uses double quotes (ANSI SQL standard) to escape the identifier.

    Args:
        name: The identifier to quote.

    Returns:
        Quoted identifier string.
    """
    # Escape any double quotes in the name by doubling them
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def validate_sql_query(sql: str, allow_write: bool = False) -> str:
    """Validate a SQL query for safety.

    Args:
        sql: The SQL query to validate.
        allow_write: If True, allow INSERT/UPDATE/DELETE.

    Returns:
        The validated SQL query.

    Raises:
        ValidationError: If the query is unsafe.
    """
    if not sql:
        raise ValidationError("SQL query cannot be empty")

    if len(sql) > MAX_SQL_LENGTH:
        raise ValidationError(f"SQL query too long (max {MAX_SQL_LENGTH} characters)")

    sql_upper = sql.upper().strip()

    # Check for basic query type
    if not allow_write:
        if not sql_upper.startswith("SELECT"):
            raise ValidationError("Only SELECT statements are allowed")

        # Check for dangerous patterns
        dangerous_keywords = [
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "REPLACE",
            "ATTACH",
            "DETACH",
        ]
        for keyword in dangerous_keywords:
            # Check for keyword not preceded/followed by alphanumeric
            if re.search(rf"\b{keyword}\b", sql_upper):
                raise ValidationError(f"Query contains forbidden keyword: {keyword}")

    # Check for comment injection
    if "--" in sql or "/*" in sql:
        raise ValidationError("SQL comments are not allowed")

    # Check for multiple statements (basic check)
    if ";" in sql.rstrip(";"):
        raise ValidationError("Multiple SQL statements are not allowed")

    return sql


def validate_limit(limit: int | None, max_limit: int = 10000) -> int:
    """Validate a LIMIT value.

    Args:
        limit: The limit value (or None).
        max_limit: Maximum allowed limit.

    Returns:
        Validated limit value.
    """
    if limit is None:
        return max_limit

    if not isinstance(limit, int) or limit < 0:
        raise ValidationError("Limit must be a non-negative integer")

    return min(limit, max_limit)
