"""Audit logging for data access and operations.

Provides compliance-ready logging of all data operations
including uploads, queries, and access events.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class AuditEventType(Enum):
    """Types of audit events."""

    # Data operations
    DATA_UPLOAD = "data_upload"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"

    # Query operations
    QUERY_SQL = "query_sql"
    QUERY_NATURAL = "query_natural"
    QUERY_SEMANTIC = "query_semantic"

    # Access operations
    DATA_VIEW = "data_view"
    SCHEMA_VIEW = "schema_view"

    # Knowledge operations
    KNOWLEDGE_UPDATE = "knowledge_update"
    KNOWLEDGE_VIEW = "knowledge_view"

    # Security events
    PII_DETECTED = "pii_detected"
    ACCESS_DENIED = "access_denied"
    VALIDATION_FAILED = "validation_failed"


@dataclass
class AuditEvent:
    """An audit log entry."""

    event_type: AuditEventType
    timestamp: datetime
    user_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    resource: str | None = None
    action: str | None = None
    details: dict[str, Any] | None = None
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage.

        Returns:
            Dictionary representation of the audit event.
        """
        data = {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "resource": self.resource,
            "action": self.action,
            "details": json.dumps(self.details) if self.details else None,
            "success": self.success,
            "error_message": self.error_message,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEvent":
        """Create from dictionary.

        Args:
            data: Dictionary containing audit event fields.

        Returns:
            A new AuditEvent instance.
        """
        # Handle SQLite integer booleans
        success_val = data.get("success", True)
        if isinstance(success_val, int):
            success_val = bool(success_val)

        return cls(
            event_type=AuditEventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            ip_address=data.get("ip_address"),
            resource=data.get("resource"),
            action=data.get("action"),
            details=json.loads(data["details"]) if data.get("details") else None,
            success=success_val,
            error_message=data.get("error_message"),
        )


class AuditLogger:
    """Audit logging system with SQLite storage."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the audit logger.

        Args:
            db_path: Path to the audit database file.
        """
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure the audit database and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    ip_address TEXT,
                    resource TEXT,
                    action TEXT,
                    details TEXT,
                    success INTEGER DEFAULT 1,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """)
            # Create index for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log(timestamp)
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_event_type
                ON audit_log(event_type)
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user
                ON audit_log(user_id)
                """)
            conn.commit()
        finally:
            conn.close()

    def log(self, event: AuditEvent) -> int:
        """Log an audit event.

        Args:
            event: The audit event to log.

        Returns:
            The ID of the logged event.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            data = event.to_dict()
            cursor = conn.execute(
                """
                INSERT INTO audit_log
                (event_type, timestamp, user_id, session_id, ip_address,
                 resource, action, details, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["event_type"],
                    data["timestamp"],
                    data["user_id"],
                    data["session_id"],
                    data["ip_address"],
                    data["resource"],
                    data["action"],
                    data["details"],
                    1 if data["success"] else 0,
                    data["error_message"],
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0
        finally:
            conn.close()

    def log_upload(
        self,
        table_name: str,
        rows: int,
        columns: list[str],
        pii_detected: bool = False,
        user_id: str | None = None,
        ip_address: str | None = None,
    ) -> int:
        """Log a data upload event.

        Args:
            table_name: Name of the table being uploaded to.
            rows: Number of rows uploaded.
            columns: List of column names.
            pii_detected: Whether PII was detected in the data.
            user_id: Optional user identifier.
            ip_address: Optional IP address of the client.

        Returns:
            The ID of the logged event.
        """
        return self.log(
            AuditEvent(
                event_type=AuditEventType.DATA_UPLOAD,
                timestamp=datetime.now(tz=timezone.utc),
                user_id=user_id,
                ip_address=ip_address,
                resource=table_name,
                action="upload",
                details={
                    "rows": rows,
                    "columns": columns,
                    "pii_detected": pii_detected,
                },
            )
        )

    def log_query(
        self,
        query_type: str,
        query: str,
        table_name: str | None = None,
        rows_returned: int = 0,
        success: bool = True,
        error: str | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
    ) -> int:
        """Log a query event.

        Args:
            query_type: Type of query ("sql", "natural", or "semantic").
            query: The query string (truncated to 1000 chars).
            table_name: Optional name of the table queried.
            rows_returned: Number of rows returned by the query.
            success: Whether the query succeeded.
            error: Optional error message if the query failed.
            user_id: Optional user identifier.
            ip_address: Optional IP address of the client.

        Returns:
            The ID of the logged event.
        """
        event_type = {
            "sql": AuditEventType.QUERY_SQL,
            "natural": AuditEventType.QUERY_NATURAL,
            "semantic": AuditEventType.QUERY_SEMANTIC,
        }.get(query_type, AuditEventType.QUERY_SQL)

        return self.log(
            AuditEvent(
                event_type=event_type,
                timestamp=datetime.now(tz=timezone.utc),
                user_id=user_id,
                ip_address=ip_address,
                resource=table_name,
                action="query",
                details={
                    "query": query[:1000],  # Truncate long queries
                    "rows_returned": rows_returned,
                },
                success=success,
                error_message=error,
            )
        )

    def log_data_access(
        self,
        table_name: str,
        action: str,
        user_id: str | None = None,
        ip_address: str | None = None,
    ) -> int:
        """Log a data access event.

        Args:
            table_name: Name of the table accessed.
            action: Description of the access action.
            user_id: Optional user identifier.
            ip_address: Optional IP address of the client.

        Returns:
            The ID of the logged event.
        """
        return self.log(
            AuditEvent(
                event_type=AuditEventType.DATA_VIEW,
                timestamp=datetime.now(tz=timezone.utc),
                user_id=user_id,
                ip_address=ip_address,
                resource=table_name,
                action=action,
            )
        )

    def log_pii_detection(
        self,
        table_name: str,
        pii_types: list[str],
        records_affected: int,
        user_id: str | None = None,
    ) -> int:
        """Log a PII detection event.

        Args:
            table_name: Name of the table where PII was detected.
            pii_types: List of PII types found (e.g., ["ssn", "email"]).
            records_affected: Number of records containing PII.
            user_id: Optional user identifier.

        Returns:
            The ID of the logged event.
        """
        return self.log(
            AuditEvent(
                event_type=AuditEventType.PII_DETECTED,
                timestamp=datetime.now(tz=timezone.utc),
                user_id=user_id,
                resource=table_name,
                action="pii_scan",
                details={
                    "pii_types": pii_types,
                    "records_affected": records_affected,
                },
            )
        )

    def log_security_event(
        self,
        event_type: AuditEventType,
        resource: str,
        error: str,
        user_id: str | None = None,
        ip_address: str | None = None,
    ) -> int:
        """Log a security event (access denied, validation failed, etc.).

        Args:
            event_type: The type of security event.
            resource: The resource involved in the event.
            error: Error message describing the security event.
            user_id: Optional user identifier.
            ip_address: Optional IP address of the client.

        Returns:
            The ID of the logged event.
        """
        return self.log(
            AuditEvent(
                event_type=event_type,
                timestamp=datetime.now(tz=timezone.utc),
                user_id=user_id,
                ip_address=ip_address,
                resource=resource,
                action="security",
                success=False,
                error_message=error,
            )
        )

    def get_events(
        self,
        event_type: AuditEventType | None = None,
        user_id: str | None = None,
        resource: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit events with filters.

        Args:
            event_type: Filter by event type.
            user_id: Filter by user ID.
            resource: Filter by resource name.
            start_time: Filter events after this time.
            end_time: Filter events before this time.
            limit: Maximum events to return.
            offset: Offset for pagination.

        Returns:
            List of matching AuditEvent objects.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = "SELECT * FROM audit_log WHERE 1=1"
            params: list[Any] = []

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)

            if resource:
                query += " AND resource = ?"
                params.append(resource)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [AuditEvent.from_dict(dict(row)) for row in rows]
        finally:
            conn.close()

    def get_event_counts(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, int]:
        """Get counts of events by type.

        Args:
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            Dictionary mapping event type to count.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            query = """
                SELECT event_type, COUNT(*) as count
                FROM audit_log
                WHERE 1=1
            """
            params: list[Any] = []

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())

            query += " GROUP BY event_type"

            cursor = conn.execute(query, params)
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

    def get_recent_activity(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recent activity summary.

        Args:
            limit: Maximum number of recent events to return.

        Returns:
            List of recent events as dictionaries.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                """
                SELECT event_type, timestamp, user_id, resource, action, success
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def export_logs(
        self,
        output_path: Path,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """Export audit logs to JSON file.

        Args:
            output_path: Path for the output file.
            start_time: Filter events after this time.
            end_time: Filter events before this time.

        Returns:
            Number of events exported.
        """
        events = self.get_events(
            start_time=start_time,
            end_time=end_time,
            limit=100000,  # Large limit for export
        )

        with open(output_path, "w") as f:
            json.dump(
                [e.to_dict() for e in events],
                f,
                indent=2,
                default=str,
            )

        return len(events)

    def purge_old_logs(self, days: int = 90) -> int:
        """Purge audit logs older than specified days.

        Args:
            days: Number of days to retain.

        Returns:
            Number of records deleted.
        """
        cutoff = datetime.now(tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cutoff = cutoff - timedelta(days=days)

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM audit_log WHERE timestamp < ?",
                (cutoff.isoformat(),),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
