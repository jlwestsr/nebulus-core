"""Feedback capture and learning system.

Captures user feedback on recommendations and query results
to enable continuous improvement of the intelligence system.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class FeedbackType(Enum):
    """Types of feedback."""

    QUERY_RESULT = "query_result"
    RECOMMENDATION = "recommendation"
    SCORING = "scoring"
    INSIGHT = "insight"


class FeedbackRating(Enum):
    """Rating values for feedback."""

    VERY_NEGATIVE = -2
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1
    VERY_POSITIVE = 2


@dataclass
class Feedback:
    """A feedback entry."""

    id: int | None
    feedback_type: FeedbackType
    rating: FeedbackRating
    timestamp: datetime
    query: str | None = None
    response: str | None = None
    context: dict[str, Any] | None = None
    comment: str | None = None
    user_id: str | None = None
    outcome: str | None = None
    outcome_timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the feedback entry.
        """
        return {
            "id": self.id,
            "feedback_type": self.feedback_type.value,
            "rating": self.rating.value,
            "timestamp": self.timestamp.isoformat(),
            "query": self.query,
            "response": self.response,
            "context": json.dumps(self.context) if self.context else None,
            "comment": self.comment,
            "user_id": self.user_id,
            "outcome": self.outcome,
            "outcome_timestamp": (
                self.outcome_timestamp.isoformat() if self.outcome_timestamp else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Feedback":
        """Create from dictionary.

        Args:
            data: Dictionary with feedback fields.

        Returns:
            A new Feedback instance.
        """
        return cls(
            id=data.get("id"),
            feedback_type=FeedbackType(data["feedback_type"]),
            rating=FeedbackRating(data["rating"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            query=data.get("query"),
            response=data.get("response"),
            context=(json.loads(data["context"]) if data.get("context") else None),
            comment=data.get("comment"),
            user_id=data.get("user_id"),
            outcome=data.get("outcome"),
            outcome_timestamp=(
                datetime.fromisoformat(data["outcome_timestamp"])
                if data.get("outcome_timestamp")
                else None
            ),
        )


@dataclass
class FeedbackSummary:
    """Summary of feedback statistics."""

    total_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    average_rating: float
    by_type: dict[str, int]
    recent_comments: list[str]


class FeedbackManager:
    """Manage feedback collection and analysis."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the feedback manager.

        Args:
            db_path: Path to the feedback SQLite database file.
        """
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure the feedback database and schema exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feedback_type TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    query TEXT,
                    response TEXT,
                    context TEXT,
                    comment TEXT,
                    user_id TEXT,
                    outcome TEXT,
                    outcome_timestamp TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_type
                ON feedback(feedback_type)
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_rating
                ON feedback(rating)
                """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
                ON feedback(timestamp)
                """)
            conn.commit()
        finally:
            conn.close()

    def submit_feedback(
        self,
        feedback_type: FeedbackType,
        rating: FeedbackRating,
        query: str | None = None,
        response: str | None = None,
        context: dict[str, Any] | None = None,
        comment: str | None = None,
        user_id: str | None = None,
    ) -> int:
        """Submit feedback on a query or recommendation.

        Args:
            feedback_type: Type of item being rated.
            rating: The rating value.
            query: The original query (if applicable).
            response: The system response.
            context: Additional context (table name, SQL, etc.).
            comment: Optional user comment.
            user_id: Optional user identifier.

        Returns:
            ID of the created feedback entry.
        """
        feedback = Feedback(
            id=None,
            feedback_type=feedback_type,
            rating=rating,
            timestamp=datetime.now(tz=timezone.utc),
            query=query,
            response=response,
            context=context,
            comment=comment,
            user_id=user_id,
        )

        conn = sqlite3.connect(self.db_path)
        try:
            data = feedback.to_dict()
            cursor = conn.execute(
                """
                INSERT INTO feedback
                (feedback_type, rating, timestamp, query, response,
                 context, comment, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["feedback_type"],
                    data["rating"],
                    data["timestamp"],
                    data["query"],
                    data["response"],
                    data["context"],
                    data["comment"],
                    data["user_id"],
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0
        finally:
            conn.close()

    def record_outcome(
        self,
        feedback_id: int,
        outcome: str,
    ) -> bool:
        """Record the actual outcome for a feedback entry.

        This allows tracking whether recommendations led to good results.

        Args:
            feedback_id: ID of the feedback entry.
            outcome: Description of the actual outcome.

        Returns:
            True if updated successfully.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                UPDATE feedback
                SET outcome = ?, outcome_timestamp = ?
                WHERE id = ?
                """,
                (
                    outcome,
                    datetime.now(tz=timezone.utc).isoformat(),
                    feedback_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_feedback(
        self,
        feedback_type: FeedbackType | None = None,
        min_rating: FeedbackRating | None = None,
        max_rating: FeedbackRating | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        has_outcome: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Feedback]:
        """Query feedback entries with filters.

        Args:
            feedback_type: Filter by type.
            min_rating: Minimum rating value.
            max_rating: Maximum rating value.
            start_time: Filter after this time.
            end_time: Filter before this time.
            has_outcome: Filter by whether outcome is recorded.
            limit: Maximum entries to return.
            offset: Offset for pagination.

        Returns:
            List of matching Feedback objects.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = "SELECT * FROM feedback WHERE 1=1"
            params: list[Any] = []

            if feedback_type:
                query += " AND feedback_type = ?"
                params.append(feedback_type.value)

            if min_rating:
                query += " AND rating >= ?"
                params.append(min_rating.value)

            if max_rating:
                query += " AND rating <= ?"
                params.append(max_rating.value)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())

            if has_outcome is not None:
                if has_outcome:
                    query += " AND outcome IS NOT NULL"
                else:
                    query += " AND outcome IS NULL"

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [Feedback.from_dict(dict(row)) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_summary(
        self,
        feedback_type: FeedbackType | None = None,
        days: int = 30,
    ) -> FeedbackSummary:
        """Get summary statistics for feedback.

        Args:
            feedback_type: Filter by type (None for all).
            days: Number of days to include.

        Returns:
            FeedbackSummary with aggregated statistics.
        """
        start_time = datetime.now(tz=timezone.utc) - timedelta(days=days)

        conn = sqlite3.connect(self.db_path)
        try:
            base_query = "FROM feedback WHERE timestamp >= ?"
            params: list[Any] = [start_time.isoformat()]

            if feedback_type:
                base_query += " AND feedback_type = ?"
                params.append(feedback_type.value)

            # Get counts
            cursor = conn.execute(
                f"SELECT COUNT(*) {base_query}",
                params,
            )
            total_count = cursor.fetchone()[0]

            # Get rating breakdown
            cursor = conn.execute(
                f"""
                SELECT
                    SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END) as positive,
                    SUM(CASE WHEN rating < 0 THEN 1 ELSE 0 END) as negative,
                    SUM(CASE WHEN rating = 0 THEN 1 ELSE 0 END) as neutral,
                    AVG(rating) as avg_rating
                {base_query}
                """,
                params,
            )
            row = cursor.fetchone()
            positive_count = row[0] or 0
            negative_count = row[1] or 0
            neutral_count = row[2] or 0
            average_rating = row[3] or 0.0

            # Get counts by type
            cursor = conn.execute(
                f"""
                SELECT feedback_type, COUNT(*) as count
                {base_query}
                GROUP BY feedback_type
                """,
                params,
            )
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # Get recent comments
            cursor = conn.execute(
                f"""
                SELECT comment
                {base_query} AND comment IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 5
                """,
                params,
            )
            recent_comments = [row[0] for row in cursor.fetchall()]

            return FeedbackSummary(
                total_count=total_count,
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count,
                average_rating=average_rating,
                by_type=by_type,
                recent_comments=recent_comments,
            )
        finally:
            conn.close()

    def get_negative_feedback_patterns(
        self,
        feedback_type: FeedbackType | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Analyze patterns in negative feedback.

        Returns queries/contexts that received negative feedback
        to identify areas for improvement.

        Args:
            feedback_type: Filter by type.
            limit: Maximum patterns to return.

        Returns:
            List of pattern dicts with query, context, count,
            avg_rating, and comments.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = """
                SELECT query, context, COUNT(*) as count,
                       AVG(rating) as avg_rating,
                       GROUP_CONCAT(comment, ' | ') as comments
                FROM feedback
                WHERE rating < 0
            """
            params: list[Any] = []

            if feedback_type:
                query += " AND feedback_type = ?"
                params.append(feedback_type.value)

            query += """
                GROUP BY query
                HAVING count >= 1
                ORDER BY count DESC, avg_rating ASC
                LIMIT ?
            """
            params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_feedback_for_refinement(
        self,
        min_feedback_count: int = 5,
    ) -> dict[str, Any]:
        """Get feedback analysis for knowledge refinement.

        Analyzes feedback to suggest improvements to scoring
        factors and business rules.

        Args:
            min_feedback_count: Minimum feedback entries needed
                for category-level analysis.

        Returns:
            Dict with refinement suggestions including satisfaction
            rate, scoring feedback, outcome tracking, and suggestions.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Get overall satisfaction rate
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END) as positive,
                    SUM(CASE WHEN rating < 0 THEN 1 ELSE 0 END) as negative
                FROM feedback
                """)
            row = cursor.fetchone()
            total = row[0] or 0
            positive = row[1] or 0
            negative = row[2] or 0

            satisfaction_rate = positive / total if total > 0 else 0

            # Get feedback by scoring category
            cursor = conn.execute(
                """
                SELECT
                    json_extract(context, '$.category') as category,
                    COUNT(*) as count,
                    AVG(rating) as avg_rating
                FROM feedback
                WHERE feedback_type = 'scoring'
                  AND context IS NOT NULL
                GROUP BY category
                HAVING count >= ?
                """,
                (min_feedback_count,),
            )
            scoring_feedback = {
                row[0]: {"count": row[1], "avg_rating": row[2]}
                for row in cursor.fetchall()
                if row[0]
            }

            # Get feedback on recommendations with outcomes
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome LIKE '%success%'
                             OR outcome LIKE '%good%'
                             OR outcome LIKE '%helped%'
                             THEN 1 ELSE 0 END) as positive_outcomes
                FROM feedback
                WHERE feedback_type = 'recommendation'
                  AND outcome IS NOT NULL
                """)
            row = cursor.fetchone()
            outcome_total = row[0] or 0
            positive_outcomes = row[1] or 0

            return {
                "total_feedback": total,
                "satisfaction_rate": satisfaction_rate,
                "positive_count": positive,
                "negative_count": negative,
                "scoring_feedback": scoring_feedback,
                "outcome_tracking": {
                    "total_with_outcomes": outcome_total,
                    "positive_outcomes": positive_outcomes,
                    "outcome_success_rate": (
                        positive_outcomes / outcome_total if outcome_total > 0 else 0
                    ),
                },
                "suggestions": self._generate_suggestions(
                    satisfaction_rate, scoring_feedback
                ),
            }
        finally:
            conn.close()

    def _generate_suggestions(
        self,
        satisfaction_rate: float,
        scoring_feedback: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Generate improvement suggestions based on feedback.

        Args:
            satisfaction_rate: Ratio of positive to total feedback.
            scoring_feedback: Per-category scoring feedback stats.

        Returns:
            List of human-readable suggestion strings.
        """
        suggestions = []

        if satisfaction_rate < 0.6:
            suggestions.append(
                "Overall satisfaction is below 60%. Consider reviewing "
                "the most common negative feedback patterns."
            )

        for category, stats in scoring_feedback.items():
            if stats["avg_rating"] < 0:
                suggestions.append(
                    f"Scoring category '{category}' has negative average "
                    "rating. Consider reviewing factor weights."
                )

        if not suggestions:
            suggestions.append(
                "Feedback is generally positive. " "Continue monitoring for trends."
            )

        return suggestions

    def export_feedback(
        self,
        output_path: Path,
        include_context: bool = True,
    ) -> int:
        """Export feedback to JSON file.

        Args:
            output_path: Path for the output JSON file.
            include_context: Whether to include context data.

        Returns:
            Number of entries exported.
        """
        feedback_list = self.get_feedback(limit=100000)

        export_data = []
        for fb in feedback_list:
            data = fb.to_dict()
            if not include_context:
                data.pop("context", None)
            export_data.append(data)

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        return len(export_data)
