"""Sale quality scoring based on domain knowledge."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nebulus_core.intelligence.core.knowledge import KnowledgeManager, ScoringFactor
from nebulus_core.intelligence.core.security import (
    quote_identifier,
    validate_sql_query,
    validate_table_name,
)


@dataclass
class ScoredRecord:
    """A record with its quality score."""

    record: dict[str, Any]
    total_score: float
    max_possible: float
    percentage: float
    factor_scores: dict[str, float]
    factor_details: dict[str, str]


class SaleScorer:
    """Score sales based on "perfect sale" criteria."""

    def __init__(
        self,
        db_path: Path,
        knowledge: KnowledgeManager,
        category: str = "perfect_sale",
    ) -> None:
        """Initialize the sale scorer.

        Args:
            db_path: Path to SQLite database.
            knowledge: KnowledgeManager with scoring factors.
            category: Scoring category to use (default: perfect_sale).
        """
        self.db_path = db_path
        self.knowledge = knowledge
        self.category = category

    def _get_factors(self) -> list[ScoringFactor]:
        """Get scoring factors for the category.

        Returns:
            List of scoring factors for the configured category.
        """
        return self.knowledge.get_scoring_factors(self.category)

    def _evaluate_factor(  # noqa: C901
        self,
        factor: ScoringFactor,
        record: dict[str, Any],
    ) -> tuple[float, str]:
        """Evaluate a single scoring factor for a record.

        Args:
            factor: The scoring factor to evaluate.
            record: Dictionary of column values.

        Returns:
            Tuple of (score, detail_message).
        """
        calculation = factor.calculation.lower()

        # Parse common calculation patterns
        # Pattern: "column IS NOT NULL"
        if "is not null" in calculation:
            col_name = calculation.split(" is not null")[0].strip()
            if col_name in record and record[col_name] is not None:
                return (factor.weight, f"{factor.name}: Yes")
            return (0, f"{factor.name}: No")

        # Pattern: "column = true" or "column = 'value'"
        if " = " in calculation:
            parts = calculation.split(" = ")
            col_name = parts[0].strip()
            expected = parts[1].strip().strip("'\"")

            if col_name in record:
                actual = record[col_name]
                # Handle boolean comparisons
                if expected == "true":
                    if actual in (True, 1, "true", "True", "1"):
                        return (factor.weight, f"{factor.name}: Yes")
                elif expected == "false":
                    if actual in (False, 0, "false", "False", "0"):
                        return (factor.weight, f"{factor.name}: Yes")
                elif str(actual).lower() == expected.lower():
                    return (factor.weight, f"{factor.name}: {actual}")
            return (0, f"{factor.name}: No")

        # Pattern: "column <= value" or "column < value"
        if " <= " in calculation or " < " in calculation:
            op = " <= " if " <= " in calculation else " < "
            parts = calculation.split(op)
            col_name = parts[0].strip()
            threshold = float(parts[1].strip())

            if col_name in record and record[col_name] is not None:
                actual = float(record[col_name])
                if op == " <= " and actual <= threshold:
                    return (
                        factor.weight,
                        f"{factor.name}: {actual} (target: <={threshold})",
                    )
                elif op == " < " and actual < threshold:
                    return (
                        factor.weight,
                        f"{factor.name}: {actual} (target: <{threshold})",
                    )
            return (0, f"{factor.name}: Did not meet threshold")

        # Pattern: ratio comparison "a / b > value" (must check BEFORE simple > check)
        if " / " in calculation and " > " in calculation:
            # e.g., "gross_profit / sale_price > 0.15"
            parts = calculation.split(" > ")
            ratio_expr = parts[0].strip()
            threshold = float(parts[1].strip())

            ratio_parts = ratio_expr.split(" / ")
            numerator_col = ratio_parts[0].strip()
            denominator_col = ratio_parts[1].strip()

            if (
                numerator_col in record
                and denominator_col in record
                and record[numerator_col] is not None
                and record[denominator_col] is not None
                and record[denominator_col] != 0
            ):
                ratio = float(record[numerator_col]) / float(record[denominator_col])
                if ratio > threshold:
                    return (
                        factor.weight,
                        f"{factor.name}: {ratio:.1%}" f" (target: >{threshold:.0%})",
                    )
            return (0, f"{factor.name}: Did not meet margin target")

        # Pattern: "column >= value" or "column > value"
        if " >= " in calculation or " > " in calculation:
            op = " >= " if " >= " in calculation else " > "
            parts = calculation.split(op)
            col_name = parts[0].strip()
            threshold = float(parts[1].strip())

            if col_name in record and record[col_name] is not None:
                actual = float(record[col_name])
                if op == " >= " and actual >= threshold:
                    return (
                        factor.weight,
                        f"{factor.name}: {actual} (target: >={threshold})",
                    )
                elif op == " > " and actual > threshold:
                    return (
                        factor.weight,
                        f"{factor.name}: {actual} (target: >{threshold})",
                    )
            return (0, f"{factor.name}: Did not meet threshold")

        # Default: if we can't parse the calculation, don't score it
        return (0, f"{factor.name}: Unable to evaluate")

    def score_record(self, record: dict[str, Any]) -> ScoredRecord:
        """Score a single record against all factors.

        Args:
            record: Dictionary of column values.

        Returns:
            ScoredRecord with scores and details.
        """
        factors = self._get_factors()
        factor_scores: dict[str, float] = {}
        factor_details: dict[str, str] = {}
        total_score = 0.0
        max_possible = sum(f.weight for f in factors)

        for factor in factors:
            score, detail = self._evaluate_factor(factor, record)
            factor_scores[factor.name] = score
            factor_details[factor.name] = detail
            total_score += score

        percentage = (total_score / max_possible * 100) if max_possible > 0 else 0

        return ScoredRecord(
            record=record,
            total_score=total_score,
            max_possible=max_possible,
            percentage=percentage,
            factor_scores=factor_scores,
            factor_details=factor_details,
        )

    def score_table(
        self,
        table_name: str,
        limit: int | None = None,
        order_by_score: bool = True,
    ) -> list[ScoredRecord]:
        """Score all records in a table.

        Args:
            table_name: Name of the table to score.
            limit: Optional limit on number of records.
            order_by_score: If True, return sorted by score descending.

        Returns:
            List of ScoredRecord objects.
        """
        # Validate table name to prevent SQL injection
        validate_table_name(table_name)
        quoted_name = quote_identifier(table_name)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(f"SELECT * FROM {quoted_name}")
            records = [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

        # Score all records
        scored = [self.score_record(record) for record in records]

        # Sort by score if requested
        if order_by_score:
            scored.sort(key=lambda x: -x.percentage)

        # Apply limit
        if limit:
            scored = scored[:limit]

        return scored

    def score_query(
        self,
        sql: str,
        order_by_score: bool = True,
    ) -> list[ScoredRecord]:
        """Score records from a custom SQL query.

        Args:
            sql: SELECT query to execute.
            order_by_score: If True, return sorted by score descending.

        Returns:
            List of ScoredRecord objects.
        """
        # Validate SQL query to prevent injection attacks
        validate_sql_query(sql, allow_write=False)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            records = [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

        # Score all records
        scored = [self.score_record(record) for record in records]

        # Sort by score if requested
        if order_by_score:
            scored.sort(key=lambda x: -x.percentage)

        return scored

    def get_score_distribution(self, table_name: str) -> dict[str, Any]:
        """Get score distribution statistics for a table.

        Args:
            table_name: Name of the table to analyze.

        Returns:
            Dict with min, max, avg, and distribution buckets.
        """
        scored = self.score_table(table_name, order_by_score=False)

        if not scored:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "distribution": {},
            }

        percentages = [s.percentage for s in scored]

        # Create distribution buckets
        buckets = {
            "excellent (80-100)": 0,
            "good (60-79)": 0,
            "average (40-59)": 0,
            "below_average (20-39)": 0,
            "poor (0-19)": 0,
        }

        for pct in percentages:
            if pct >= 80:
                buckets["excellent (80-100)"] += 1
            elif pct >= 60:
                buckets["good (60-79)"] += 1
            elif pct >= 40:
                buckets["average (40-59)"] += 1
            elif pct >= 20:
                buckets["below_average (20-39)"] += 1
            else:
                buckets["poor (0-19)"] += 1

        return {
            "count": len(scored),
            "min": min(percentages),
            "max": max(percentages),
            "avg": sum(percentages) / len(percentages),
            "distribution": buckets,
        }

    def get_factor_performance(self, table_name: str) -> dict[str, dict[str, Any]]:
        """Analyze which factors are most/least achieved.

        Args:
            table_name: Name of the table to analyze.

        Returns:
            Dict mapping factor name to performance stats.
        """
        scored = self.score_table(table_name, order_by_score=False)

        if not scored:
            return {}

        factors = self._get_factors()
        performance: dict[str, dict[str, Any]] = {}

        for factor in factors:
            achieved = sum(1 for s in scored if s.factor_scores.get(factor.name, 0) > 0)
            total = len(scored)
            performance[factor.name] = {
                "weight": factor.weight,
                "achieved": achieved,
                "total": total,
                "rate": achieved / total if total > 0 else 0,
                "description": factor.description,
            }

        return performance
