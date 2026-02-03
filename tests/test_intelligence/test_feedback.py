"""Tests for the feedback module."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from nebulus_core.intelligence.core.feedback import (
    Feedback,
    FeedbackManager,
    FeedbackRating,
    FeedbackType,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary feedback database path."""
    return tmp_path / "feedback.db"


@pytest.fixture
def manager(temp_db: Path) -> FeedbackManager:
    """Create a FeedbackManager instance."""
    return FeedbackManager(temp_db)


class TestFeedback:
    """Tests for Feedback dataclass."""

    def test_create_feedback(self) -> None:
        """Test creating a feedback entry."""
        fb = Feedback(
            id=1,
            feedback_type=FeedbackType.QUERY_RESULT,
            rating=FeedbackRating.POSITIVE,
            timestamp=datetime.now(tz=timezone.utc),
            query="How many sales?",
            response="There were 150 sales.",
        )

        assert fb.feedback_type == FeedbackType.QUERY_RESULT
        assert fb.rating == FeedbackRating.POSITIVE

    def test_to_dict(self) -> None:
        """Test converting feedback to dictionary."""
        fb = Feedback(
            id=1,
            feedback_type=FeedbackType.RECOMMENDATION,
            rating=FeedbackRating.VERY_POSITIVE,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            context={"table": "sales"},
        )

        data = fb.to_dict()

        assert data["feedback_type"] == "recommendation"
        assert data["rating"] == 2

    def test_from_dict(self) -> None:
        """Test creating feedback from dictionary."""
        data = {
            "id": 1,
            "feedback_type": "query_result",
            "rating": -1,
            "timestamp": "2024-01-15T10:30:00",
            "query": "test query",
        }

        fb = Feedback.from_dict(data)

        assert fb.feedback_type == FeedbackType.QUERY_RESULT
        assert fb.rating == FeedbackRating.NEGATIVE


class TestFeedbackManager:
    """Tests for FeedbackManager class."""

    def test_submit_feedback(self, manager: FeedbackManager) -> None:
        """Test submitting basic feedback."""
        feedback_id = manager.submit_feedback(
            feedback_type=FeedbackType.QUERY_RESULT,
            rating=FeedbackRating.POSITIVE,
            query="How many vehicles?",
            response="There are 500 vehicles.",
        )

        assert feedback_id > 0

    def test_submit_feedback_with_context(self, manager: FeedbackManager) -> None:
        """Test submitting feedback with context."""
        feedback_id = manager.submit_feedback(
            feedback_type=FeedbackType.SCORING,
            rating=FeedbackRating.NEGATIVE,
            context={"category": "perfect_sale", "factors": ["trade_in"]},
            comment="Weights seem off",
        )

        assert feedback_id > 0

        # Verify context was stored
        feedback = manager.get_feedback()[0]
        assert feedback.context["category"] == "perfect_sale"

    def test_record_outcome(self, manager: FeedbackManager) -> None:
        """Test recording an outcome for feedback."""
        # Submit initial feedback
        feedback_id = manager.submit_feedback(
            feedback_type=FeedbackType.RECOMMENDATION,
            rating=FeedbackRating.POSITIVE,
            query="What inventory should I buy?",
            response="Focus on SUVs under $35k",
        )

        # Record outcome
        success = manager.record_outcome(
            feedback_id,
            "Followed recommendation, saw 15% increase in sales",
        )

        assert success

        # Verify outcome was recorded
        feedback = manager.get_feedback(has_outcome=True)
        assert len(feedback) == 1
        assert "15% increase" in feedback[0].outcome

    def test_record_outcome_not_found(self, manager: FeedbackManager) -> None:
        """Test recording outcome for non-existent feedback."""
        success = manager.record_outcome(999, "test outcome")
        assert not success

    def test_get_feedback_filtered(self, manager: FeedbackManager) -> None:
        """Test filtering feedback by criteria."""
        # Submit multiple feedback entries
        manager.submit_feedback(
            feedback_type=FeedbackType.QUERY_RESULT,
            rating=FeedbackRating.POSITIVE,
        )
        manager.submit_feedback(
            feedback_type=FeedbackType.RECOMMENDATION,
            rating=FeedbackRating.NEGATIVE,
        )
        manager.submit_feedback(
            feedback_type=FeedbackType.QUERY_RESULT,
            rating=FeedbackRating.VERY_POSITIVE,
        )

        # Filter by type
        results = manager.get_feedback(feedback_type=FeedbackType.QUERY_RESULT)
        assert len(results) == 2

        # Filter by rating
        results = manager.get_feedback(min_rating=FeedbackRating.POSITIVE)
        assert len(results) == 2

        results = manager.get_feedback(max_rating=FeedbackRating.NEUTRAL)
        assert len(results) == 1

    def test_get_summary(self, manager: FeedbackManager) -> None:
        """Test getting feedback summary."""
        # Submit feedback
        manager.submit_feedback(
            feedback_type=FeedbackType.QUERY_RESULT,
            rating=FeedbackRating.POSITIVE,
        )
        manager.submit_feedback(
            feedback_type=FeedbackType.QUERY_RESULT,
            rating=FeedbackRating.NEGATIVE,
            comment="Not helpful",
        )
        manager.submit_feedback(
            feedback_type=FeedbackType.RECOMMENDATION,
            rating=FeedbackRating.VERY_POSITIVE,
        )

        summary = manager.get_summary(days=30)

        assert summary.total_count == 3
        assert summary.positive_count == 2
        assert summary.negative_count == 1
        assert summary.by_type["query_result"] == 2
        assert "Not helpful" in summary.recent_comments

    def test_get_summary_by_type(self, manager: FeedbackManager) -> None:
        """Test getting summary filtered by type."""
        manager.submit_feedback(
            feedback_type=FeedbackType.QUERY_RESULT,
            rating=FeedbackRating.POSITIVE,
        )
        manager.submit_feedback(
            feedback_type=FeedbackType.RECOMMENDATION,
            rating=FeedbackRating.NEGATIVE,
        )

        summary = manager.get_summary(
            feedback_type=FeedbackType.QUERY_RESULT,
            days=30,
        )

        assert summary.total_count == 1
        assert summary.positive_count == 1

    def test_get_negative_patterns(self, manager: FeedbackManager) -> None:
        """Test getting patterns in negative feedback."""
        # Submit negative feedback on same query
        for _ in range(3):
            manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=FeedbackRating.NEGATIVE,
                query="complex query",
                comment="confusing results",
            )

        patterns = manager.get_negative_feedback_patterns()

        assert len(patterns) >= 1
        assert patterns[0]["count"] == 3

    def test_get_feedback_for_refinement(self, manager: FeedbackManager) -> None:
        """Test getting refinement analysis."""
        # Submit varied feedback
        manager.submit_feedback(
            feedback_type=FeedbackType.SCORING,
            rating=FeedbackRating.POSITIVE,
            context={"category": "perfect_sale"},
        )
        manager.submit_feedback(
            feedback_type=FeedbackType.SCORING,
            rating=FeedbackRating.NEGATIVE,
            context={"category": "perfect_sale"},
        )

        analysis = manager.get_feedback_for_refinement()

        assert "total_feedback" in analysis
        assert "satisfaction_rate" in analysis
        assert "suggestions" in analysis
        assert len(analysis["suggestions"]) > 0

    def test_export_feedback(self, manager: FeedbackManager, temp_db: Path) -> None:
        """Test exporting feedback to file."""
        manager.submit_feedback(
            feedback_type=FeedbackType.QUERY_RESULT,
            rating=FeedbackRating.POSITIVE,
        )
        manager.submit_feedback(
            feedback_type=FeedbackType.RECOMMENDATION,
            rating=FeedbackRating.NEGATIVE,
        )

        export_path = temp_db.parent / "export.json"
        count = manager.export_feedback(export_path)

        assert count == 2
        assert export_path.exists()

    def test_pagination(self, manager: FeedbackManager) -> None:
        """Test pagination of feedback."""
        # Submit multiple entries
        for i in range(15):
            manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=FeedbackRating.POSITIVE,
            )

        # Get first page
        page1 = manager.get_feedback(limit=10, offset=0)
        assert len(page1) == 10

        # Get second page
        page2 = manager.get_feedback(limit=10, offset=10)
        assert len(page2) == 5


class TestFeedbackTypes:
    """Tests for different feedback types."""

    def test_all_feedback_types(self, manager: FeedbackManager) -> None:
        """Test that all feedback types can be submitted."""
        for fb_type in FeedbackType:
            feedback_id = manager.submit_feedback(
                feedback_type=fb_type,
                rating=FeedbackRating.NEUTRAL,
            )
            assert feedback_id > 0

    def test_all_rating_values(self, manager: FeedbackManager) -> None:
        """Test that all rating values work."""
        for rating in FeedbackRating:
            feedback_id = manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=rating,
            )
            assert feedback_id > 0
