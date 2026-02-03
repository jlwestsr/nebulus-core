"""Tests for the scoring module."""

import sqlite3
from pathlib import Path

import pytest

from nebulus_core.intelligence.core.knowledge import KnowledgeManager
from nebulus_core.intelligence.core.scoring import SaleScorer, ScoredRecord
from nebulus_core.intelligence.templates import load_template


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database with test data."""
    db_path = tmp_path / "test.db"

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE sales (
            vin TEXT PRIMARY KEY,
            sale_price INTEGER,
            gross_profit INTEGER,
            days_to_sale INTEGER,
            trade_in_vin TEXT,
            financing_type TEXT,
            warranty_sold INTEGER,
            buyer_distance_miles INTEGER
        )
    """)

    # Insert test data
    test_data = [
        # Perfect sale - all factors
        (
            "VIN001",
            30000,
            5000,
            15,
            "TRADE001",
            "dealer",
            1,
            10,
        ),
        # Partial - no trade-in, no warranty
        (
            "VIN002",
            25000,
            4000,
            20,
            None,
            "dealer",
            0,
            20,
        ),
        # Minimal - only quick turn
        (
            "VIN003",
            20000,
            2000,
            25,
            None,
            "cash",
            0,
            50,
        ),
        # No factors met
        (
            "VIN004",
            35000,
            3000,
            45,
            None,
            "outside",
            0,
            100,
        ),
    ]

    conn.executemany(
        """
        INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        test_data,
    )
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def knowledge_manager(tmp_path: Path) -> KnowledgeManager:
    """Create a KnowledgeManager with dealership config."""
    knowledge_path = tmp_path / "knowledge.json"
    template = load_template("dealership")
    return KnowledgeManager(knowledge_path, template.config)


@pytest.fixture
def scorer(temp_db: Path, knowledge_manager: KnowledgeManager) -> SaleScorer:
    """Create a SaleScorer instance."""
    return SaleScorer(temp_db, knowledge_manager, category="perfect_sale")


class TestSaleScorer:
    """Tests for SaleScorer class."""

    def test_score_record_perfect(self, scorer: SaleScorer) -> None:
        """Test scoring a perfect sale record."""
        record = {
            "vin": "VIN001",
            "sale_price": 30000,
            "gross_profit": 5000,
            "days_to_sale": 15,
            "trade_in_vin": "TRADE001",
            "financing_type": "dealer",
            "warranty_sold": 1,
            "buyer_distance_miles": 10,
        }

        result = scorer.score_record(record)

        assert isinstance(result, ScoredRecord)
        assert result.percentage > 50  # Should be high
        assert result.factor_scores["trade_in"] > 0
        assert result.factor_scores["dealer_financing"] > 0
        assert result.factor_scores["warranty_sold"] > 0
        assert result.factor_scores["quick_turn"] > 0

    def test_score_record_minimal(self, scorer: SaleScorer) -> None:
        """Test scoring a minimal sale record."""
        record = {
            "vin": "VIN004",
            "sale_price": 35000,
            "gross_profit": 3000,
            "days_to_sale": 45,
            "trade_in_vin": None,
            "financing_type": "outside",
            "warranty_sold": 0,
            "buyer_distance_miles": 100,
        }

        result = scorer.score_record(record)

        assert result.percentage < 50  # Should be low
        assert result.factor_scores["trade_in"] == 0
        assert result.factor_scores["dealer_financing"] == 0
        assert result.factor_scores["warranty_sold"] == 0

    def test_score_table(self, scorer: SaleScorer) -> None:
        """Test scoring all records in a table."""
        results = scorer.score_table("sales")

        assert len(results) == 4
        # Should be sorted by score descending
        assert results[0].percentage >= results[-1].percentage

    def test_score_table_with_limit(self, scorer: SaleScorer) -> None:
        """Test scoring with a limit."""
        results = scorer.score_table("sales", limit=2)

        assert len(results) == 2

    def test_score_distribution(self, scorer: SaleScorer) -> None:
        """Test getting score distribution."""
        dist = scorer.get_score_distribution("sales")

        assert "count" in dist
        assert dist["count"] == 4
        assert "min" in dist
        assert "max" in dist
        assert "avg" in dist
        assert "distribution" in dist

    def test_factor_performance(self, scorer: SaleScorer) -> None:
        """Test getting factor performance analysis."""
        perf = scorer.get_factor_performance("sales")

        assert "trade_in" in perf
        assert "dealer_financing" in perf

        # Check structure
        for factor_name, stats in perf.items():
            assert "weight" in stats
            assert "achieved" in stats
            assert "total" in stats
            assert "rate" in stats

    def test_score_query(self, scorer: SaleScorer, temp_db: Path) -> None:
        """Test scoring records from a custom query."""
        sql = "SELECT * FROM sales WHERE sale_price > 25000"
        results = scorer.score_query(sql)

        assert len(results) == 2  # VIN001 and VIN004

    def test_factor_evaluation_is_not_null(self, scorer: SaleScorer) -> None:
        """Test IS NOT NULL calculation pattern."""
        record = {"trade_in_vin": "TRADE001"}
        result = scorer.score_record(record)

        assert result.factor_scores["trade_in"] > 0

    def test_factor_evaluation_equals(self, scorer: SaleScorer) -> None:
        """Test = comparison calculation pattern."""
        record = {"financing_type": "dealer"}
        result = scorer.score_record(record)

        assert result.factor_scores["dealer_financing"] > 0

    def test_factor_evaluation_boolean(self, scorer: SaleScorer) -> None:
        """Test boolean comparison calculation pattern."""
        record = {"warranty_sold": True}
        result = scorer.score_record(record)

        assert result.factor_scores["warranty_sold"] > 0

    def test_factor_evaluation_less_than_equal(self, scorer: SaleScorer) -> None:
        """Test <= comparison calculation pattern."""
        record = {"days_to_sale": 25}
        result = scorer.score_record(record)

        assert result.factor_scores["quick_turn"] > 0

    def test_factor_evaluation_ratio(self, scorer: SaleScorer) -> None:
        """Test ratio comparison calculation pattern."""
        # 6000 / 30000 = 0.20 > 0.15
        record = {
            "gross_profit": 6000,
            "sale_price": 30000,
            "days_to_sale": 40,  # Over threshold to isolate ratio test
            "trade_in_vin": None,
            "financing_type": "cash",
            "warranty_sold": 0,
            "buyer_distance_miles": 100,
        }
        result = scorer.score_record(record)

        assert result.factor_scores["above_margin"] > 0

    def test_factor_evaluation_ratio_below_threshold(self, scorer: SaleScorer) -> None:
        """Test ratio that doesn't meet threshold."""
        # 3000 / 30000 = 0.10 < 0.15
        record = {"gross_profit": 3000, "sale_price": 30000}
        result = scorer.score_record(record)

        assert result.factor_scores["above_margin"] == 0

    def test_missing_column_graceful(self, scorer: SaleScorer) -> None:
        """Test that missing columns are handled gracefully."""
        record: dict = {}  # Empty record
        result = scorer.score_record(record)

        assert result.percentage == 0
        assert result.total_score == 0
