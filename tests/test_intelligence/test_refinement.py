"""Tests for the knowledge refinement module."""

from pathlib import Path

import pytest

from nebulus_core.intelligence.core.feedback import (
    FeedbackManager,
    FeedbackRating,
    FeedbackType,
)
from nebulus_core.intelligence.core.knowledge import KnowledgeManager
from nebulus_core.intelligence.core.refinement import (
    KnowledgeRefiner,
    WeightAdjustment,
)
from nebulus_core.intelligence.templates import load_template


@pytest.fixture
def temp_knowledge_path(tmp_path: Path) -> Path:
    """Create a temporary knowledge file path."""
    return tmp_path / "knowledge.json"


@pytest.fixture
def temp_feedback_db(tmp_path: Path) -> Path:
    """Create a temporary feedback database path."""
    return tmp_path / "feedback.db"


@pytest.fixture
def knowledge_manager(tmp_path: Path) -> KnowledgeManager:
    """Create a KnowledgeManager instance with dealership template."""
    template = load_template("dealership")
    return KnowledgeManager(tmp_path / "knowledge.json", template.config)


@pytest.fixture
def feedback_manager(tmp_path: Path) -> FeedbackManager:
    """Create a FeedbackManager instance."""
    return FeedbackManager(tmp_path / "feedback.db")


@pytest.fixture
def refiner(
    knowledge_manager: KnowledgeManager,
    feedback_manager: FeedbackManager,
) -> KnowledgeRefiner:
    """Create a KnowledgeRefiner instance."""
    return KnowledgeRefiner(knowledge_manager, feedback_manager)


class TestKnowledgeRefiner:
    """Tests for KnowledgeRefiner class."""

    def test_analyze_insufficient_feedback(self, refiner: KnowledgeRefiner) -> None:
        """Test analysis with insufficient feedback."""
        report = refiner.analyze_and_suggest(days=30)

        assert report.feedback_analyzed == 0
        assert len(report.general_suggestions) > 0
        assert "Insufficient feedback" in report.general_suggestions[0]

    def test_analyze_with_feedback(
        self,
        refiner: KnowledgeRefiner,
        feedback_manager: FeedbackManager,
    ) -> None:
        """Test analysis with enough feedback."""
        for i in range(15):
            rating = FeedbackRating.POSITIVE if i % 2 == 0 else FeedbackRating.NEGATIVE
            feedback_manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=rating,
            )

        report = refiner.analyze_and_suggest(days=30)

        assert report.feedback_analyzed == 15
        assert report.satisfaction_rate > 0

    def test_analyze_scoring_feedback(
        self,
        refiner: KnowledgeRefiner,
        feedback_manager: FeedbackManager,
    ) -> None:
        """Test analysis of scoring-specific feedback."""
        # Submit negative feedback on scoring
        for _ in range(5):
            feedback_manager.submit_feedback(
                feedback_type=FeedbackType.SCORING,
                rating=FeedbackRating.NEGATIVE,
                context={
                    "category": "perfect_sale",
                    "factors": ["trade_in"],
                },
            )

        # Add some general feedback to meet minimum
        for _ in range(10):
            feedback_manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=FeedbackRating.POSITIVE,
            )

        report = refiner.analyze_and_suggest(days=30, min_confidence=0.1)

        # Should suggest weight adjustment for trade_in
        assert report.feedback_analyzed == 15

    def test_analyze_low_satisfaction(
        self,
        refiner: KnowledgeRefiner,
        feedback_manager: FeedbackManager,
    ) -> None:
        """Test analysis with low satisfaction rate."""
        # Submit mostly negative feedback
        for _ in range(12):
            feedback_manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=FeedbackRating.NEGATIVE,
            )
        for _ in range(3):
            feedback_manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=FeedbackRating.POSITIVE,
            )

        report = refiner.analyze_and_suggest(days=30)

        # Should flag low satisfaction
        assert report.satisfaction_rate < 0.5
        low_satisfaction_warning = any(
            "satisfaction rate" in s.lower() for s in report.general_suggestions
        )
        assert low_satisfaction_warning

    def test_get_improvement_priorities(
        self,
        refiner: KnowledgeRefiner,
        feedback_manager: FeedbackManager,
    ) -> None:
        """Test getting improvement priorities."""
        # Submit negative feedback on same query
        for _ in range(5):
            feedback_manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=FeedbackRating.NEGATIVE,
                query="complex query",
            )

        priorities = refiner.get_improvement_priorities()

        assert len(priorities) >= 1
        assert all("priority" in p for p in priorities)

    def test_generate_summary_report(
        self,
        refiner: KnowledgeRefiner,
        feedback_manager: FeedbackManager,
    ) -> None:
        """Test generating summary report."""
        # Add some feedback
        for _ in range(12):
            feedback_manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=FeedbackRating.POSITIVE,
            )

        report = refiner.generate_summary_report()

        assert "Knowledge Refinement Report" in report
        assert "Satisfaction Rate" in report

    def test_apply_weight_adjustments(
        self,
        refiner: KnowledgeRefiner,
        knowledge_manager: KnowledgeManager,
    ) -> None:
        """Test applying weight adjustments."""
        # Get current weight
        factors = knowledge_manager.get_scoring_factors("perfect_sale")
        trade_in_factor = next(
            (f for f in factors if f.name == "trade_in"),
            None,
        )
        original_weight = trade_in_factor.weight if trade_in_factor else 20

        # Create adjustment
        adjustments = [
            WeightAdjustment(
                category="perfect_sale",
                factor_name="trade_in",
                current_weight=original_weight,
                suggested_weight=original_weight - 5,
                confidence=0.8,
                reasoning="Test adjustment",
            )
        ]

        results = refiner.apply_weight_adjustments(adjustments, min_confidence=0.7)

        assert results.get("trade_in") is True

        # Verify weight was updated
        factors = knowledge_manager.get_scoring_factors("perfect_sale")
        updated_factor = next(
            (f for f in factors if f.name == "trade_in"),
            None,
        )
        assert updated_factor.weight == original_weight - 5

    def test_apply_adjustments_below_confidence(
        self, refiner: KnowledgeRefiner
    ) -> None:
        """Test that low-confidence adjustments are skipped."""
        adjustments = [
            WeightAdjustment(
                category="perfect_sale",
                factor_name="trade_in",
                current_weight=20,
                suggested_weight=15,
                confidence=0.3,  # Below threshold
                reasoning="Low confidence",
            )
        ]

        results = refiner.apply_weight_adjustments(adjustments, min_confidence=0.7)

        assert results.get("trade_in") is False


class TestRefinementReport:
    """Tests for RefinementReport class."""

    def test_report_to_dict(
        self,
        refiner: KnowledgeRefiner,
        feedback_manager: FeedbackManager,
    ) -> None:
        """Test converting report to dictionary."""
        # Add minimal feedback
        for _ in range(12):
            feedback_manager.submit_feedback(
                feedback_type=FeedbackType.QUERY_RESULT,
                rating=FeedbackRating.POSITIVE,
            )

        report = refiner.analyze_and_suggest()
        data = report.to_dict()

        assert "generated_at" in data
        assert "feedback_analyzed" in data
        assert "satisfaction_rate" in data
        assert "weight_adjustments" in data
        assert "general_suggestions" in data


class TestWeightAdjustment:
    """Tests for WeightAdjustment dataclass."""

    def test_create_adjustment(self) -> None:
        """Test creating a weight adjustment."""
        adj = WeightAdjustment(
            category="perfect_sale",
            factor_name="trade_in",
            current_weight=20,
            suggested_weight=15,
            confidence=0.75,
            reasoning="Negative feedback pattern",
        )

        assert adj.category == "perfect_sale"
        assert adj.suggested_weight < adj.current_weight
        assert adj.confidence == 0.75
