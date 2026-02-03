"""CSV ingestion with schema inference and primary key detection.

Provides the DataIngestor class for importing CSV data into SQLite,
with automatic schema inference, primary key detection, optional
PII scanning, and vector embedding support.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from nebulus_core.intelligence.core.pii import PIIDetector, PIIReport
from nebulus_core.intelligence.core.security import (
    quote_identifier,
    validate_table_name,
)

if TYPE_CHECKING:
    from nebulus_core.intelligence.core.vector_engine import VectorEngine
    from nebulus_core.intelligence.templates.base import VerticalTemplate


# ------------------------------------------------------------------
# Fallback primary-key hints (used when no template is provided)
# ------------------------------------------------------------------
_GENERIC_PK_HINTS: list[str] = ["id", "ID", "Id", "key", "KEY"]


@dataclass
class IngestResult:
    """Result of CSV ingestion."""

    table_name: str
    rows_imported: int
    columns: list[str]
    column_types: dict[str, str]
    primary_key: str | None = None
    warnings: list[str] = field(default_factory=list)
    records_embedded: int = 0
    pii_detected: bool = False
    pii_columns: list[str] = field(default_factory=list)
    pii_report: PIIReport | None = None


class DataIngestor:
    """CSV ingestion with schema inference and primary key detection.

    The ingestor parses CSV content, cleans column names, infers SQL
    types, detects a primary key (using the optional VerticalTemplate),
    stores rows in SQLite, and optionally embeds records via
    VectorEngine for semantic search.
    """

    def __init__(
        self,
        db_path: Path,
        pii_detector: PIIDetector,
        vector_engine: VectorEngine | None = None,
        template: VerticalTemplate | None = None,
    ) -> None:
        """Initialize the data ingestor.

        Args:
            db_path: Path to the SQLite database file.
            pii_detector: PIIDetector instance for scanning records.
            vector_engine: Optional VectorEngine for embedding records.
            template: Optional VerticalTemplate for primary-key hints.
        """
        self.db_path = db_path
        self.pii_detector = pii_detector
        self.vector_engine = vector_engine
        self.template = template
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure the database file and parent directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_csv(  # noqa: C901
        self,
        csv_content: bytes | str,
        table_name: str,
        primary_key_hint: str | None = None,
        scan_pii: bool = True,
    ) -> IngestResult:
        """Ingest CSV content into the SQLite database.

        Args:
            csv_content: CSV file content as bytes or string.
            table_name: Name for the database table.
            primary_key_hint: Optional column name to use as primary key.
            scan_pii: Whether to scan ingested data for PII.

        Returns:
            IngestResult with import statistics and detected schema.

        Raises:
            ValueError: If the CSV cannot be parsed or is empty.
        """
        warnings: list[str] = []

        # Parse CSV
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode("utf-8")

        try:
            df = pd.read_csv(StringIO(csv_content))
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {e}")

        if df.empty:
            raise ValueError("CSV file is empty")

        # Clean column names
        original_columns = list(df.columns)
        df.columns = [self._clean_column_name(c) for c in df.columns]
        cleaned_columns = list(df.columns)

        for orig, clean in zip(original_columns, cleaned_columns):
            if orig != clean:
                warnings.append(f"Column '{orig}' renamed to '{clean}'")

        # Detect primary key
        primary_key = self._detect_primary_key(df, primary_key_hint)
        if primary_key and df[primary_key].duplicated().any():
            warnings.append(
                f"Primary key '{primary_key}' has duplicates - "
                "may cause issues with joins"
            )

        # Infer column types
        column_types = self._infer_types(df)

        # Import to SQLite
        conn = sqlite3.connect(self.db_path)
        try:
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            rows_imported = len(df)
        finally:
            conn.close()

        # Embed records for semantic search
        records_embedded = 0
        if self.vector_engine:
            try:
                records = df.to_dict(orient="records")
                id_field = primary_key or "id"
                if id_field not in df.columns:
                    for i, record in enumerate(records):
                        record["_row_id"] = str(i)
                    id_field = "_row_id"

                records_embedded = self.vector_engine.embed_records(
                    table_name=table_name,
                    records=records,
                    id_field=id_field,
                )
            except Exception as e:
                warnings.append(f"Embedding failed: {e}")

        # Scan for PII
        pii_detected = False
        pii_columns: list[str] = []
        pii_report: PIIReport | None = None

        if scan_pii:
            try:
                records = df.to_dict(orient="records")
                pii_report = self.pii_detector.scan_records(records)

                if pii_report.has_pii:
                    pii_detected = True
                    pii_columns = list(pii_report.pii_columns)
                    warnings.append(
                        f"PII DETECTED: {pii_report.records_with_pii} records "
                        f"contain sensitive data in columns: "
                        f"{', '.join(pii_columns)}"
                    )
                    for pii_warning in pii_report.warnings:
                        warnings.append(f"PII: {pii_warning}")
            except Exception as e:
                warnings.append(f"PII scan failed: {e}")

        return IngestResult(
            table_name=table_name,
            rows_imported=rows_imported,
            columns=cleaned_columns,
            column_types=column_types,
            primary_key=primary_key,
            warnings=warnings,
            records_embedded=records_embedded,
            pii_detected=pii_detected,
            pii_columns=pii_columns,
            pii_report=pii_report,
        )

    def list_tables(self) -> list[str]:
        """List all tables in the database.

        Returns:
            Sorted list of table name strings.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_table_schema(self, table_name: str) -> dict:
        """Get schema information for a table.

        Args:
            table_name: Name of the table to inspect.

        Returns:
            Dict with ``table_name``, ``columns``, ``types``, and
            ``row_count`` keys.

        Raises:
            ValidationError: If the table name is invalid.
        """
        validate_table_name(table_name)
        quoted_name = quote_identifier(table_name)

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(f"PRAGMA table_info({quoted_name})")
            columns: list[str] = []
            types: dict[str, str] = {}
            for row in cursor.fetchall():
                col_name = row[1]
                col_type = row[2]
                columns.append(col_name)
                types[col_name] = col_type

            cursor = conn.execute(f"SELECT COUNT(*) FROM {quoted_name}")
            row_count = cursor.fetchone()[0]

            return {
                "table_name": table_name,
                "columns": columns,
                "types": types,
                "row_count": row_count,
            }
        finally:
            conn.close()

    def preview_table(self, table_name: str, limit: int = 10) -> list[dict]:
        """Get a preview of rows from a table.

        Args:
            table_name: Name of the table to preview.
            limit: Maximum number of rows to return (clamped 1..1000).

        Returns:
            List of row dicts.

        Raises:
            ValidationError: If the table name is invalid.
        """
        validate_table_name(table_name)
        quoted_name = quote_identifier(table_name)
        limit = max(1, min(limit, 1000))

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                f"SELECT * FROM {quoted_name} LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_table(self, table_name: str) -> bool:
        """Delete a table from the database and its vector embeddings.

        Args:
            table_name: Name of the table to delete.

        Returns:
            True if deleted, False if the table did not exist.

        Raises:
            ValidationError: If the table name is invalid.
        """
        validate_table_name(table_name)
        quoted_name = quote_identifier(table_name)

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master " "WHERE type='table' AND name=?",
                (table_name,),
            )
            if not cursor.fetchone():
                return False

            conn.execute(f"DROP TABLE {quoted_name}")
            conn.commit()

            if self.vector_engine:
                self.vector_engine.delete_collection(table_name)

            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clean_column_name(self, name: str) -> str:
        """Clean a column name for SQL compatibility.

        Args:
            name: Raw column name from CSV header.

        Returns:
            Lowercased, underscore-separated identifier.
        """
        clean = "".join(c if c.isalnum() else "_" for c in str(name))
        clean = clean.strip("_")
        clean = clean.lower()
        return clean or "column"

    def _detect_primary_key(
        self,
        df: pd.DataFrame,
        hint: str | None = None,
    ) -> str | None:
        """Detect the primary key column.

        Uses the user-supplied *hint* first, then falls back to the
        template's ``get_primary_key_hints()`` method, and finally to
        the generic hints list.

        Args:
            df: DataFrame to analyze.
            hint: Optional column name hint from user.

        Returns:
            Column name if a primary key is detected, ``None`` otherwise.
        """
        columns = list(df.columns)

        # User-supplied hint takes priority
        if hint:
            hint_clean = self._clean_column_name(hint)
            if hint_clean in columns:
                return hint_clean
            if hint in columns:
                return hint

        # Template-driven hints
        if self.template is not None:
            pk_hints = self.template.get_primary_key_hints()
        else:
            pk_hints = _GENERIC_PK_HINTS

        for pk_hint in pk_hints:
            clean_hint = self._clean_column_name(pk_hint)
            if clean_hint in columns:
                return clean_hint

        return None

    def _infer_types(self, df: pd.DataFrame) -> dict[str, str]:
        """Infer SQL-friendly type names for each column.

        Args:
            df: DataFrame whose dtypes will be inspected.

        Returns:
            Dict mapping column name to SQL type string.
        """
        type_map: dict[str, str] = {}

        for col in df.columns:
            dtype = df[col].dtype

            if pd.api.types.is_integer_dtype(dtype):
                type_map[col] = "INTEGER"
            elif pd.api.types.is_float_dtype(dtype):
                type_map[col] = "REAL"
            elif pd.api.types.is_bool_dtype(dtype):
                type_map[col] = "BOOLEAN"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                type_map[col] = "DATETIME"
            else:
                type_map[col] = "TEXT"

        return type_map
