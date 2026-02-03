"""Tests for the insights module."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nebulus_core.intelligence.core.insights import (
    Insight,
    InsightGenerator,
    InsightPriority,
    InsightReport,
    InsightType,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database with test data."""
    db_path = tmp_path / "test.db"

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE inventory (
            vin TEXT PRIMARY KEY,
            make TEXT,
            model TEXT,
            year INTEGER,
            price REAL,
            days_on_lot INTEGER,
            category TEXT
        )
        """)

    # Insert test data with varied days_on_lot
    test_data = [
        ("VIN001", "Honda", "Accord", 2020, 25000, 15, "sedan"),
        ("VIN002", "Toyota", "Camry", 2021, 28000, 25, "sedan"),
        ("VIN003", "Ford", "F-150", 2019, 35000, 45, "truck"),
        ("VIN004", "Chevy", "Tahoe", 2020, 45000, 65, "suv"),
        ("VIN005", "BMW", "X5", 2021, 55000, 95, "suv"),
        ("VIN006", "Audi", "A4", 2020, 40000, 100, "sedan"),
        ("VIN007", "Honda", "CR-V", 2021, 30000, 10, "suv"),
        ("VIN008", "Toyota", "RAV4", 2020, 32000, 20, "suv"),
        ("VIN009", "Ford", "Escape", 2021, 28000, 30, "suv"),
        ("VIN010", "Chevy", "Malibu", 2020, 22000, 55, "sedan"),
    ]

    conn.executemany(
        "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?)",
        test_data,
    )
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    """Create a path for a non-existent database."""
    return tmp_path / "empty.db"


@pytest.fixture
def generator(temp_db: Path) -> InsightGenerator:
    """Create an InsightGenerator instance."""
    return InsightGenerator(temp_db)


class TestInsight:
    """Tests for Insight dataclass."""

    def test_create_insight(self) -> None:
        """Test creating an insight."""
        insight = Insight(
            insight_type=InsightType.RISK,
            priority=InsightPriority.HIGH,
            title="Test insight",
            description="This is a test insight",
            data_points={"value": 100},
            recommendations=["Do something"],
        )

        assert insight.insight_type == InsightType.RISK
        assert insight.priority == InsightPriority.HIGH
        assert insight.title == "Test insight"

    def test_to_dict(self) -> None:
        """Test converting insight to dictionary."""
        insight = Insight(
            insight_type=InsightType.OPPORTUNITY,
            priority=InsightPriority.MEDIUM,
            title="Opportunity found",
            description="A great opportunity",
        )

        data = insight.to_dict()

        assert data["insight_type"] == "opportunity"
        assert data["priority"] == "medium"
        assert "generated_at" in data


class TestInsightReport:
    """Tests for InsightReport dataclass."""

    def test_create_report(self) -> None:
        """Test creating an insight report."""
        report = InsightReport(
            generated_at=datetime.now(tz=timezone.utc),
            tables_analyzed=["table1", "table2"],
            insights=[
                Insight(
                    insight_type=InsightType.RISK,
                    priority=InsightPriority.HIGH,
                    title="Risk 1",
                    description="High risk",
                ),
                Insight(
                    insight_type=InsightType.OPPORTUNITY,
                    priority=InsightPriority.LOW,
                    title="Opportunity 1",
                    description="Low priority opportunity",
                ),
            ],
        )

        assert len(report.insights) == 2
        assert len(report.tables_analyzed) == 2

    def test_to_dict(self) -> None:
        """Test converting report to dictionary."""
        report = InsightReport(
            generated_at=datetime.now(tz=timezone.utc),
            tables_analyzed=["inventory"],
            insights=[],
            summary="No insights",
        )

        data = report.to_dict()

        assert "generated_at" in data
        assert data["tables_analyzed"] == ["inventory"]
        assert data["insight_count"] == 0

    def test_count_by_priority(self) -> None:
        """Test counting insights by priority."""
        report = InsightReport(
            generated_at=datetime.now(tz=timezone.utc),
            tables_analyzed=[],
            insights=[
                Insight(
                    insight_type=InsightType.RISK,
                    priority=InsightPriority.HIGH,
                    title="High 1",
                    description="",
                ),
                Insight(
                    insight_type=InsightType.RISK,
                    priority=InsightPriority.HIGH,
                    title="High 2",
                    description="",
                ),
                Insight(
                    insight_type=InsightType.OPPORTUNITY,
                    priority=InsightPriority.LOW,
                    title="Low 1",
                    description="",
                ),
            ],
        )

        counts = report._count_by_priority()

        assert counts["high"] == 2
        assert counts["low"] == 1


class TestInsightGenerator:
    """Tests for InsightGenerator class."""

    def test_generate_insights(self, generator: InsightGenerator) -> None:
        """Test generating insights from data."""
        report = generator.generate_insights()

        assert len(report.tables_analyzed) > 0
        assert "inventory" in report.tables_analyzed

    def test_generate_insights_no_db(self, empty_db: Path) -> None:
        """Test generating insights with no database."""
        gen = InsightGenerator(empty_db)
        report = gen.generate_insights()

        assert "No database found" in report.summary

    def test_inventory_aging_insights(self, generator: InsightGenerator) -> None:
        """Test that inventory aging insights are generated."""
        report = generator.generate_insights()

        # Should find aging-related insights (we have vehicles > 90 days)
        aging_insights = [
            i for i in report.insights if i.category == "inventory_health"
        ]

        # With test data (2 vehicles > 90 days = 20%), should have
        # high priority
        assert len(aging_insights) > 0

    def test_get_high_priority_insights(self, generator: InsightGenerator) -> None:
        """Test getting high-priority insights only."""
        high_priority = generator.get_high_priority_insights()

        for insight in high_priority:
            assert insight.priority in (
                InsightPriority.HIGH,
                InsightPriority.CRITICAL,
            )

    def test_get_insights_by_category(self, generator: InsightGenerator) -> None:
        """Test filtering insights by category."""
        insights = generator.get_insights_by_category("inventory_health")

        for insight in insights:
            assert insight.category == "inventory_health"

    def test_report_summary(self, generator: InsightGenerator) -> None:
        """Test that report includes summary."""
        report = generator.generate_insights()

        assert report.summary != ""

    def test_specific_tables(self, generator: InsightGenerator) -> None:
        """Test analyzing specific tables."""
        report = generator.generate_insights(tables=["inventory"])

        assert report.tables_analyzed == ["inventory"]


class TestInsightTypes:
    """Tests for different insight types."""

    def test_all_types_valid(self) -> None:
        """Test that all insight types are valid."""
        for itype in InsightType:
            insight = Insight(
                insight_type=itype,
                priority=InsightPriority.MEDIUM,
                title="Test",
                description="Test",
            )
            assert insight.insight_type == itype

    def test_all_priorities_valid(self) -> None:
        """Test that all priorities are valid."""
        for priority in InsightPriority:
            insight = Insight(
                insight_type=InsightType.TREND,
                priority=priority,
                title="Test",
                description="Test",
            )
            assert insight.priority == priority
