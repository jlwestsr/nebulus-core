"""Tests for the audit logging module."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nebulus_core.intelligence.core.audit import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary audit database path."""
    return tmp_path / "audit.db"


@pytest.fixture
def logger(temp_db: Path) -> AuditLogger:
    """Create an AuditLogger instance."""
    return AuditLogger(temp_db)


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""

    def test_create_event(self) -> None:
        """Test creating an audit event."""
        event = AuditEvent(
            event_type=AuditEventType.DATA_UPLOAD,
            timestamp=datetime.now(tz=timezone.utc),
            user_id="user123",
            resource="test_table",
            action="upload",
        )

        assert event.event_type == AuditEventType.DATA_UPLOAD
        assert event.user_id == "user123"
        assert event.success is True

    def test_to_dict(self) -> None:
        """Test converting event to dictionary."""
        event = AuditEvent(
            event_type=AuditEventType.QUERY_SQL,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user_id="user123",
            resource="sales",
            details={"query": "SELECT * FROM sales"},
        )

        data = event.to_dict()

        assert data["event_type"] == "query_sql"
        assert data["user_id"] == "user123"
        assert "SELECT" in data["details"]

    def test_from_dict(self) -> None:
        """Test creating event from dictionary."""
        data = {
            "event_type": "data_upload",
            "timestamp": "2024-01-15T10:30:00",
            "user_id": "user123",
            "resource": "test_table",
            "action": "upload",
            "details": None,
            "success": True,
            "error_message": None,
        }

        event = AuditEvent.from_dict(data)

        assert event.event_type == AuditEventType.DATA_UPLOAD
        assert event.user_id == "user123"


class TestAuditLogger:
    """Tests for AuditLogger class."""

    def test_log_event(self, logger: AuditLogger) -> None:
        """Test logging a basic event."""
        event = AuditEvent(
            event_type=AuditEventType.DATA_UPLOAD,
            timestamp=datetime.now(tz=timezone.utc),
            user_id="user123",
            resource="test_table",
        )

        event_id = logger.log(event)

        assert event_id > 0

    def test_log_upload(self, logger: AuditLogger) -> None:
        """Test logging an upload event."""
        event_id = logger.log_upload(
            table_name="inventory",
            rows=100,
            columns=["vin", "make", "model"],
            pii_detected=False,
            user_id="admin",
        )

        assert event_id > 0

        # Verify event was logged
        events = logger.get_events(event_type=AuditEventType.DATA_UPLOAD)
        assert len(events) == 1
        assert events[0].resource == "inventory"

    def test_log_query(self, logger: AuditLogger) -> None:
        """Test logging a query event."""
        event_id = logger.log_query(
            query_type="sql",
            query="SELECT * FROM sales WHERE year = 2024",
            table_name="sales",
            rows_returned=50,
            user_id="analyst",
        )

        assert event_id > 0

        events = logger.get_events(event_type=AuditEventType.QUERY_SQL)
        assert len(events) == 1
        assert events[0].details["rows_returned"] == 50

    def test_log_pii_detection(self, logger: AuditLogger) -> None:
        """Test logging a PII detection event."""
        event_id = logger.log_pii_detection(
            table_name="customers",
            pii_types=["ssn", "email"],
            records_affected=25,
        )

        assert event_id > 0

        events = logger.get_events(event_type=AuditEventType.PII_DETECTED)
        assert len(events) == 1
        assert events[0].details["records_affected"] == 25

    def test_log_security_event(self, logger: AuditLogger) -> None:
        """Test logging a security event."""
        event_id = logger.log_security_event(
            event_type=AuditEventType.ACCESS_DENIED,
            resource="admin_panel",
            error="Unauthorized access attempt",
            user_id="unknown",
            ip_address="192.168.1.100",
        )

        assert event_id > 0

        events = logger.get_events(event_type=AuditEventType.ACCESS_DENIED)
        assert len(events) == 1
        assert events[0].success is False

    def test_get_events_filtered(self, logger: AuditLogger) -> None:
        """Test filtering events by criteria."""
        # Log multiple events
        logger.log_upload("table1", 10, ["col1"], user_id="user1")
        logger.log_upload("table2", 20, ["col1"], user_id="user2")
        logger.log_query("sql", "SELECT 1", user_id="user1")

        # Filter by user
        events = logger.get_events(user_id="user1")
        assert len(events) == 2

        # Filter by event type
        events = logger.get_events(event_type=AuditEventType.DATA_UPLOAD)
        assert len(events) == 2

        # Filter by resource
        events = logger.get_events(resource="table1")
        assert len(events) == 1

    def test_get_events_with_time_filter(self, logger: AuditLogger) -> None:
        """Test filtering events by time."""
        # Log an event
        logger.log_upload("test_table", 10, ["col1"])

        # Query with time filter
        now = datetime.now(tz=timezone.utc)
        events = logger.get_events(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert len(events) == 1

        # Query outside time range
        events = logger.get_events(
            start_time=now + timedelta(days=1),
        )
        assert len(events) == 0

    def test_get_event_counts(self, logger: AuditLogger) -> None:
        """Test getting event counts by type."""
        logger.log_upload("table1", 10, ["col1"])
        logger.log_upload("table2", 20, ["col1"])
        logger.log_query("sql", "SELECT 1")
        logger.log_query("natural", "how many rows?")

        counts = logger.get_event_counts()

        assert counts.get("data_upload") == 2
        assert counts.get("query_sql") == 1
        assert counts.get("query_natural") == 1

    def test_get_recent_activity(self, logger: AuditLogger) -> None:
        """Test getting recent activity."""
        logger.log_upload("table1", 10, ["col1"])
        logger.log_query("sql", "SELECT 1")

        activity = logger.get_recent_activity(limit=5)

        assert len(activity) == 2
        # Most recent should be first
        assert activity[0]["event_type"] == "query_sql"

    def test_export_logs(
        self, logger: AuditLogger, temp_db: Path
    ) -> None:
        """Test exporting logs to file."""
        logger.log_upload("table1", 10, ["col1"])
        logger.log_query("sql", "SELECT 1")

        export_path = temp_db.parent / "export.json"
        count = logger.export_logs(export_path)

        assert count == 2
        assert export_path.exists()

    def test_purge_old_logs(self, logger: AuditLogger) -> None:
        """Test purging old logs."""
        # Log an event
        logger.log_upload("test_table", 10, ["col1"])

        # Check that purge with days=90 doesn't delete recent logs
        deleted = logger.purge_old_logs(days=90)
        assert deleted == 0

        # Verify event still exists
        events = logger.get_events()
        assert len(events) == 1

    def test_pagination(self, logger: AuditLogger) -> None:
        """Test pagination of events."""
        # Log multiple events
        for i in range(15):
            logger.log_upload(f"table{i}", i, ["col1"])

        # Get first page
        page1 = logger.get_events(limit=10, offset=0)
        assert len(page1) == 10

        # Get second page
        page2 = logger.get_events(limit=10, offset=10)
        assert len(page2) == 5


class TestAuditEventTypes:
    """Tests for different audit event types."""

    def test_all_event_types_loggable(self, logger: AuditLogger) -> None:
        """Test that all event types can be logged."""
        for event_type in AuditEventType:
            event = AuditEvent(
                event_type=event_type,
                timestamp=datetime.now(tz=timezone.utc),
                resource="test",
            )
            event_id = logger.log(event)
            assert event_id > 0
