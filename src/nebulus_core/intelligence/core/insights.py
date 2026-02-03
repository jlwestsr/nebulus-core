"""Automated insight generation.

Analyzes data to surface trends, anomalies, and actionable insights
without requiring user prompts.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from nebulus_core.intelligence.core.knowledge import KnowledgeManager


class InsightType(Enum):
    """Types of insights that can be generated."""

    TREND = "trend"
    ANOMALY = "anomaly"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    MILESTONE = "milestone"
    COMPARISON = "comparison"


class InsightPriority(Enum):
    """Priority levels for insights."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Insight:
    """An automatically generated insight."""

    insight_type: InsightType
    priority: InsightPriority
    title: str
    description: str
    data_points: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    expires_at: datetime | None = None
    table_name: str | None = None
    category: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the insight.
        """
        return {
            "insight_type": self.insight_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "data_points": self.data_points,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
            "expires_at": (self.expires_at.isoformat() if self.expires_at else None),
            "table_name": self.table_name,
            "category": self.category,
        }


@dataclass
class InsightReport:
    """Collection of insights from an analysis run."""

    generated_at: datetime
    tables_analyzed: list[str]
    insights: list[Insight] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the report.
        """
        return {
            "generated_at": self.generated_at.isoformat(),
            "tables_analyzed": self.tables_analyzed,
            "insights": [i.to_dict() for i in self.insights],
            "summary": self.summary,
            "insight_count": len(self.insights),
            "by_priority": self._count_by_priority(),
            "by_type": self._count_by_type(),
        }

    def _count_by_priority(self) -> dict[str, int]:
        """Count insights by priority.

        Returns:
            Dictionary mapping priority names to counts.
        """
        counts: dict[str, int] = {}
        for insight in self.insights:
            priority = insight.priority.value
            counts[priority] = counts.get(priority, 0) + 1
        return counts

    def _count_by_type(self) -> dict[str, int]:
        """Count insights by type.

        Returns:
            Dictionary mapping type names to counts.
        """
        counts: dict[str, int] = {}
        for insight in self.insights:
            itype = insight.insight_type.value
            counts[itype] = counts.get(itype, 0) + 1
        return counts


class InsightGenerator:
    """Generate insights from data analysis."""

    def __init__(
        self,
        db_path: Path,
        knowledge: KnowledgeManager | None = None,
    ) -> None:
        """Initialize the insight generator.

        Args:
            db_path: Path to the SQLite database.
            knowledge: Optional KnowledgeManager for domain context.
        """
        self.db_path = db_path
        self.knowledge = knowledge

    def generate_insights(
        self,
        tables: list[str] | None = None,
    ) -> InsightReport:
        """Generate insights from data analysis.

        Args:
            tables: List of tables to analyze (None = all).

        Returns:
            InsightReport with generated insights.
        """
        report = InsightReport(
            generated_at=datetime.now(tz=timezone.utc),
            tables_analyzed=[],
            insights=[],
        )

        if not self.db_path.exists():
            report.summary = "No database found. Upload data to generate insights."
            return report

        # Get tables to analyze
        if tables is None:
            tables = self._list_tables()

        report.tables_analyzed = tables

        if not tables:
            report.summary = "No tables available for analysis."
            return report

        # Run various analyses
        for table in tables:
            self._analyze_table(table, report)

        # Generate summary
        report.summary = self._generate_summary(report)

        return report

    def _list_tables(self) -> list[str]:
        """List all tables in the database.

        Returns:
            List of table names in the database.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def _analyze_table(self, table_name: str, report: InsightReport) -> None:
        """Analyze a single table and add insights to report.

        Args:
            table_name: Name of the table to analyze.
            report: InsightReport to append insights to.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Get table schema
            cursor = conn.execute(f'PRAGMA table_info("{table_name}")')
            columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]

            # Get row count
            cursor = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cursor.fetchone()[0]

            if row_count == 0:
                return

            # Find numeric columns for analysis
            numeric_cols = [
                c["name"]
                for c in columns
                if c["type"].upper() in ("INTEGER", "REAL", "NUMERIC")
            ]

            # Analyze numeric columns
            for col in numeric_cols:
                self._analyze_numeric_column(conn, table_name, col, row_count, report)

            # Check for date-based trends
            date_cols = [
                c["name"]
                for c in columns
                if "date" in c["name"].lower() or "time" in c["name"].lower()
            ]
            for col in date_cols:
                self._analyze_date_column(conn, table_name, col, report)

            # Check for inventory aging (if applicable)
            if "days_on_lot" in [c["name"] for c in columns]:
                self._analyze_inventory_aging(conn, table_name, report)

            # Check for distribution insights
            self._analyze_distributions(conn, table_name, columns, report)

        finally:
            conn.close()

    def _analyze_numeric_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column: str,
        total_rows: int,
        report: InsightReport,
    ) -> None:
        """Analyze a numeric column for insights.

        Args:
            conn: Active SQLite connection.
            table_name: Name of the table.
            column: Name of the numeric column.
            total_rows: Total row count in the table.
            report: InsightReport to append insights to.
        """
        # Get basic statistics
        cursor = conn.execute(f"""
            SELECT
                MIN("{column}") as min_val,
                MAX("{column}") as max_val,
                AVG("{column}") as avg_val,
                COUNT(*) as count_val
            FROM "{table_name}"
            WHERE "{column}" IS NOT NULL
            """)
        stats = cursor.fetchone()

        if not stats or stats["count_val"] == 0:
            return

        # kept for future range analysis
        _min_val = stats["min_val"]  # noqa: F841
        _max_val = stats["max_val"]  # noqa: F841
        avg_val = stats["avg_val"]

        # Check for outliers (values > 3 standard deviations)
        cursor = conn.execute(f"""
            SELECT
                AVG("{column}") as mean,
                AVG("{column}" * "{column}")
                    - AVG("{column}") * AVG("{column}") as variance
            FROM "{table_name}"
            WHERE "{column}" IS NOT NULL
            """)
        var_stats = cursor.fetchone()
        variance = var_stats["variance"] or 0
        stddev = variance**0.5 if variance > 0 else 0

        if stddev > 0:
            threshold = avg_val + (3 * stddev)
            cursor = conn.execute(
                f"""
                SELECT COUNT(*) FROM "{table_name}"
                WHERE "{column}" > ?
                """,
                (threshold,),
            )
            outlier_count = cursor.fetchone()[0]

            if outlier_count > 0 and outlier_count / total_rows > 0.01:
                report.insights.append(
                    Insight(
                        insight_type=InsightType.ANOMALY,
                        priority=InsightPriority.MEDIUM,
                        title=f"Outliers detected in {column}",
                        description=(
                            f"Found {outlier_count} records with "
                            f"{column} values significantly above "
                            f"average ({threshold:.2f})"
                        ),
                        data_points={
                            "column": column,
                            "outlier_count": outlier_count,
                            "threshold": threshold,
                            "average": avg_val,
                        },
                        recommendations=[
                            f"Review records with " f"{column} > {threshold:.2f}",
                            "Check if these represent " "data quality issues",
                        ],
                        table_name=table_name,
                    )
                )

    def _analyze_date_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column: str,
        report: InsightReport,
    ) -> None:
        """Analyze a date column for trends.

        Args:
            conn: Active SQLite connection.
            table_name: Name of the table.
            column: Name of the date column.
            report: InsightReport to append insights to.
        """
        # Simplified analysis - could be extended
        pass

    def _analyze_inventory_aging(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        report: InsightReport,
    ) -> None:
        """Analyze inventory aging for dealership data.

        Args:
            conn: Active SQLite connection.
            table_name: Name of the table.
            report: InsightReport to append insights to.
        """
        # Get aging distribution
        cursor = conn.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN days_on_lot <= 30
                    THEN 1 ELSE 0 END) as fresh,
                SUM(CASE WHEN days_on_lot > 30
                    AND days_on_lot <= 60
                    THEN 1 ELSE 0 END) as aged,
                SUM(CASE WHEN days_on_lot > 60
                    AND days_on_lot <= 90
                    THEN 1 ELSE 0 END) as stale,
                SUM(CASE WHEN days_on_lot > 90
                    THEN 1 ELSE 0 END) as critical
            FROM "{table_name}"
            """)
        aging = cursor.fetchone()

        if not aging or aging["total"] == 0:
            return

        total = aging["total"]
        critical_pct = aging["critical"] / total if total > 0 else 0
        stale_pct = aging["stale"] / total if total > 0 else 0

        # High priority if >10% is critical
        if critical_pct > 0.1:
            report.insights.append(
                Insight(
                    insight_type=InsightType.RISK,
                    priority=InsightPriority.HIGH,
                    title="High aged inventory",
                    description=(
                        f"{aging['critical']} vehicles "
                        f"({critical_pct:.0%}) have been on lot for "
                        f"over 90 days. This represents significant "
                        f"carrying costs."
                    ),
                    data_points={
                        "total_vehicles": total,
                        "critical_count": aging["critical"],
                        "critical_percentage": critical_pct,
                        "stale_count": aging["stale"],
                    },
                    recommendations=[
                        "Consider price reductions on " "90+ day vehicles",
                        "Review acquisition strategy to " "avoid slow-moving inventory",
                        "Analyze characteristics of aged " "vehicles for patterns",
                    ],
                    table_name=table_name,
                    category="inventory_health",
                )
            )
        elif stale_pct > 0.15:
            report.insights.append(
                Insight(
                    insight_type=InsightType.RISK,
                    priority=InsightPriority.MEDIUM,
                    title="Growing stale inventory",
                    description=(
                        f"{aging['stale']} vehicles "
                        f"({stale_pct:.0%}) are between 60-90 days. "
                        f"Monitor closely to prevent aging further."
                    ),
                    data_points={
                        "stale_count": aging["stale"],
                        "stale_percentage": stale_pct,
                    },
                    recommendations=[
                        "Proactively market 60-90 day vehicles",
                        "Consider targeted promotions",
                    ],
                    table_name=table_name,
                    category="inventory_health",
                )
            )

        # Opportunity if inventory is fresh
        fresh_pct = aging["fresh"] / total if total > 0 else 0
        if fresh_pct > 0.7:
            report.insights.append(
                Insight(
                    insight_type=InsightType.OPPORTUNITY,
                    priority=InsightPriority.LOW,
                    title="Healthy inventory turnover",
                    description=(
                        f"{fresh_pct:.0%} of inventory is under "
                        f"30 days old. Good inventory velocity!"
                    ),
                    data_points={
                        "fresh_count": aging["fresh"],
                        "fresh_percentage": fresh_pct,
                    },
                    recommendations=[
                        "Maintain current acquisition strategy",
                        "Consider expanding inventory " "if demand supports it",
                    ],
                    table_name=table_name,
                    category="inventory_health",
                )
            )

    def _analyze_distributions(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        columns: list[dict[str, str]],
        report: InsightReport,
    ) -> None:
        """Analyze value distributions for categorical columns.

        Args:
            conn: Active SQLite connection.
            table_name: Name of the table.
            columns: List of column info dicts with name and type keys.
            report: InsightReport to append insights to.
        """
        text_cols = [c["name"] for c in columns if c["type"].upper() == "TEXT"]

        for col in text_cols[:5]:  # Limit to avoid too many insights
            cursor = conn.execute(f"""
                SELECT "{col}", COUNT(*) as count
                FROM "{table_name}"
                WHERE "{col}" IS NOT NULL
                GROUP BY "{col}"
                ORDER BY count DESC
                LIMIT 5
                """)
            distribution = cursor.fetchall()

            if len(distribution) >= 2:
                top_val = distribution[0]
                total = sum(d[1] for d in distribution)
                top_pct = top_val[1] / total if total > 0 else 0

                # Flag if one value dominates (>60%)
                if top_pct > 0.6 and total > 10:
                    report.insights.append(
                        Insight(
                            insight_type=InsightType.COMPARISON,
                            priority=InsightPriority.LOW,
                            title=f"Concentration in {col}",
                            description=(
                                f"'{top_val[0]}' represents "
                                f"{top_pct:.0%} of values in {col}. "
                                f"Consider if this represents "
                                f"opportunity or risk."
                            ),
                            data_points={
                                "column": col,
                                "dominant_value": top_val[0],
                                "percentage": top_pct,
                                "total_records": total,
                            },
                            table_name=table_name,
                        )
                    )

    def _generate_summary(self, report: InsightReport) -> str:
        """Generate a summary of the insights.

        Args:
            report: The InsightReport to summarize.

        Returns:
            Human-readable summary string.
        """
        if not report.insights:
            return "No significant insights found in the current data."

        high_priority = sum(
            1
            for i in report.insights
            if i.priority in (InsightPriority.HIGH, InsightPriority.CRITICAL)
        )

        summary_parts = [
            f"Generated {len(report.insights)} insights from "
            f"{len(report.tables_analyzed)} tables."
        ]

        if high_priority > 0:
            summary_parts.append(
                f"{high_priority} high-priority items " f"require attention."
            )

        by_type = report._count_by_type()
        if "risk" in by_type:
            summary_parts.append(f"Found {by_type['risk']} risk indicators.")
        if "opportunity" in by_type:
            summary_parts.append(f"Identified {by_type['opportunity']} opportunities.")

        return " ".join(summary_parts)

    def get_high_priority_insights(
        self,
        tables: list[str] | None = None,
    ) -> list[Insight]:
        """Get only high-priority insights.

        Args:
            tables: List of tables to analyze (None = all).

        Returns:
            List of high or critical priority insights.
        """
        report = self.generate_insights(tables)
        return [
            i
            for i in report.insights
            if i.priority in (InsightPriority.HIGH, InsightPriority.CRITICAL)
        ]

    def get_insights_by_category(
        self,
        category: str,
        tables: list[str] | None = None,
    ) -> list[Insight]:
        """Get insights for a specific category.

        Args:
            category: Category to filter by.
            tables: List of tables to analyze (None = all).

        Returns:
            List of insights matching the category.
        """
        report = self.generate_insights(tables)
        return [i for i in report.insights if i.category == category]
