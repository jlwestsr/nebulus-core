"""Knowledge refinement based on feedback and outcomes.

Analyzes feedback patterns to suggest improvements to scoring
factors, business rules, and system behavior.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from nebulus_core.intelligence.core.feedback import (
    FeedbackManager,
    FeedbackType,
)
from nebulus_core.intelligence.core.knowledge import KnowledgeManager


@dataclass
class WeightAdjustment:
    """Suggested adjustment to a scoring factor weight.

    Attributes:
        category: The scoring category containing the factor.
        factor_name: Name of the factor to adjust.
        current_weight: The factor's current weight value.
        suggested_weight: The proposed new weight value.
        confidence: Confidence level (0.0 to 1.0) in the suggestion.
        reasoning: Human-readable explanation for the adjustment.
    """

    category: str
    factor_name: str
    current_weight: int
    suggested_weight: int
    confidence: float
    reasoning: str


@dataclass
class RuleModification:
    """Suggested modification to a business rule.

    Attributes:
        rule_name: Name of the rule to modify.
        modification_type: Type of change: ``"adjust"``, ``"remove"``,
            or ``"add"``.
        current_value: The rule's current value, if applicable.
        suggested_value: The proposed new value, if applicable.
        confidence: Confidence level (0.0 to 1.0) in the suggestion.
        reasoning: Human-readable explanation for the modification.
    """

    rule_name: str
    modification_type: str  # "adjust", "remove", "add"
    current_value: str | None = None
    suggested_value: str | None = None
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class RefinementReport:
    """Report of suggested refinements.

    Attributes:
        generated_at: Timestamp when the report was generated.
        feedback_analyzed: Number of feedback entries analyzed.
        satisfaction_rate: Ratio of positive feedback (0.0 to 1.0).
        weight_adjustments: Suggested weight changes for scoring factors.
        rule_modifications: Suggested changes to business rules.
        general_suggestions: Free-text improvement suggestions.
        metrics_review: Key-value pairs of metric status information.
    """

    generated_at: datetime
    feedback_analyzed: int
    satisfaction_rate: float
    weight_adjustments: list[WeightAdjustment] = field(default_factory=list)
    rule_modifications: list[RuleModification] = field(default_factory=list)
    general_suggestions: list[str] = field(default_factory=list)
    metrics_review: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the report to a plain dictionary.

        Returns:
            Dictionary representation of the report, suitable for
            JSON serialization.
        """
        return {
            "generated_at": self.generated_at.isoformat(),
            "feedback_analyzed": self.feedback_analyzed,
            "satisfaction_rate": self.satisfaction_rate,
            "weight_adjustments": [
                {
                    "category": adj.category,
                    "factor_name": adj.factor_name,
                    "current_weight": adj.current_weight,
                    "suggested_weight": adj.suggested_weight,
                    "confidence": adj.confidence,
                    "reasoning": adj.reasoning,
                }
                for adj in self.weight_adjustments
            ],
            "rule_modifications": [
                {
                    "rule_name": mod.rule_name,
                    "modification_type": mod.modification_type,
                    "current_value": mod.current_value,
                    "suggested_value": mod.suggested_value,
                    "confidence": mod.confidence,
                    "reasoning": mod.reasoning,
                }
                for mod in self.rule_modifications
            ],
            "general_suggestions": self.general_suggestions,
            "metrics_review": self.metrics_review,
        }


class KnowledgeRefiner:
    """Analyze feedback to refine domain knowledge.

    Uses feedback patterns to suggest adjustments to scoring factor
    weights, business rules, and overall system behavior.

    Attributes:
        MIN_FEEDBACK_FOR_ANALYSIS: Minimum feedback entries required
            before generating suggestions.
        LOW_SATISFACTION_THRESHOLD: Satisfaction rate below which a
            warning is generated.
        WEIGHT_ADJUSTMENT_THRESHOLD: Negative feedback rate that
            triggers a weight review.
    """

    # Thresholds for suggestions
    MIN_FEEDBACK_FOR_ANALYSIS = 10
    LOW_SATISFACTION_THRESHOLD = 0.5
    WEIGHT_ADJUSTMENT_THRESHOLD = 0.3  # 30% negative feedback triggers review

    def __init__(
        self,
        knowledge_manager: KnowledgeManager,
        feedback_manager: FeedbackManager,
    ) -> None:
        """Initialize the knowledge refiner.

        Args:
            knowledge_manager: Manager for domain knowledge.
            feedback_manager: Manager for feedback data.
        """
        self.knowledge = knowledge_manager
        self.feedback = feedback_manager

    def analyze_and_suggest(
        self,
        days: int = 30,
        min_confidence: float = 0.5,
    ) -> RefinementReport:
        """Analyze recent feedback and generate refinement suggestions.

        Args:
            days: Number of days of feedback to analyze.
            min_confidence: Minimum confidence for including suggestions.

        Returns:
            A ``RefinementReport`` containing all suggestions.
        """
        # Get feedback summary
        summary = self.feedback.get_summary(days=days)

        # Initialize report
        report = RefinementReport(
            generated_at=datetime.now(tz=timezone.utc),
            feedback_analyzed=summary.total_count,
            satisfaction_rate=(
                summary.positive_count / summary.total_count
                if summary.total_count > 0
                else 0.0
            ),
        )

        # Check if we have enough feedback
        if summary.total_count < self.MIN_FEEDBACK_FOR_ANALYSIS:
            report.general_suggestions.append(
                f"Insufficient feedback for detailed analysis. "
                f"Need at least {self.MIN_FEEDBACK_FOR_ANALYSIS} entries, "
                f"currently have {summary.total_count}."
            )
            return report

        # Analyze scoring feedback
        self._analyze_scoring_feedback(report, days, min_confidence)

        # Analyze recommendation outcomes
        self._analyze_outcomes(report, days)

        # Check overall satisfaction
        if report.satisfaction_rate < self.LOW_SATISFACTION_THRESHOLD:
            report.general_suggestions.append(
                f"Overall satisfaction rate ({report.satisfaction_rate:.1%}) "
                f"is below threshold "
                f"({self.LOW_SATISFACTION_THRESHOLD:.0%}). "
                "Review negative feedback patterns for improvement "
                "opportunities."
            )

        # Review metrics alignment
        self._review_metrics(report)

        return report

    def _analyze_scoring_feedback(  # noqa: C901
        self,
        report: RefinementReport,
        days: int,
        min_confidence: float,
    ) -> None:
        """Analyze feedback on scoring to suggest weight adjustments.

        Args:
            report: The report to populate with suggestions.
            days: Number of days of feedback to consider.
            min_confidence: Minimum confidence for including suggestions.
        """
        # Get scoring-specific feedback
        scoring_feedback = self.feedback.get_feedback(
            feedback_type=FeedbackType.SCORING,
            limit=1000,
        )

        if not scoring_feedback:
            return

        # Group by category and factor
        factor_feedback: dict[str, dict[str, list[int]]] = {}

        for fb in scoring_feedback:
            if not fb.context:
                continue

            category = fb.context.get("category", "unknown")
            factors = fb.context.get("factors", [])

            if category not in factor_feedback:
                factor_feedback[category] = {}

            for factor in factors:
                if factor not in factor_feedback[category]:
                    factor_feedback[category][factor] = []
                factor_feedback[category][factor].append(fb.rating.value)

        # Analyze each factor
        all_factors = self.knowledge.get_all_scoring_factors()

        for category, factors in factor_feedback.items():
            for factor_name, ratings in factors.items():
                if len(ratings) < 3:  # Need at least 3 data points
                    continue

                negative_rate = sum(1 for r in ratings if r < 0) / len(ratings)

                # Check if factor needs adjustment
                if negative_rate > self.WEIGHT_ADJUSTMENT_THRESHOLD:
                    # Find current weight
                    current_weight = 0
                    if category in all_factors:
                        for f in all_factors[category]:
                            if f.name == factor_name:
                                current_weight = f.weight
                                break

                    # Calculate suggested adjustment
                    adjustment_factor = 1 - (negative_rate * 0.5)
                    suggested_weight = int(current_weight * adjustment_factor)

                    confidence = min(
                        len(ratings) / 20, 1.0
                    )  # More data = more confidence

                    if confidence >= min_confidence:
                        report.weight_adjustments.append(
                            WeightAdjustment(
                                category=category,
                                factor_name=factor_name,
                                current_weight=current_weight,
                                suggested_weight=suggested_weight,
                                confidence=confidence,
                                reasoning=(
                                    f"{negative_rate:.0%} negative "
                                    f"feedback rate based on "
                                    f"{len(ratings)} ratings"
                                ),
                            )
                        )

    def _analyze_outcomes(self, report: RefinementReport, days: int) -> None:
        """Analyze recommendation outcomes for patterns.

        Args:
            report: The report to populate with outcome metrics.
            days: Number of days of feedback to consider.
        """
        # Get recommendations with outcomes
        feedback_with_outcomes = self.feedback.get_feedback(
            feedback_type=FeedbackType.RECOMMENDATION,
            has_outcome=True,
            limit=1000,
        )

        if not feedback_with_outcomes:
            return

        # Analyze outcome patterns
        positive_keywords = [
            "success",
            "helped",
            "good",
            "improved",
            "increase",
        ]
        negative_keywords = [
            "failed",
            "worse",
            "bad",
            "decrease",
            "wrong",
        ]

        positive_outcomes = 0
        negative_outcomes = 0

        for fb in feedback_with_outcomes:
            if not fb.outcome:
                continue

            outcome_lower = fb.outcome.lower()

            if any(kw in outcome_lower for kw in positive_keywords):
                positive_outcomes += 1
            elif any(kw in outcome_lower for kw in negative_keywords):
                negative_outcomes += 1

        total = positive_outcomes + negative_outcomes
        if total > 0:
            success_rate = positive_outcomes / total

            report.metrics_review["recommendation_success_rate"] = success_rate
            report.metrics_review["recommendations_with_outcomes"] = total

            if success_rate < 0.5:
                report.general_suggestions.append(
                    f"Recommendation success rate "
                    f"({success_rate:.0%}) is below 50%. "
                    "Consider reviewing the factors used "
                    "for recommendations."
                )

    def _review_metrics(self, report: RefinementReport) -> None:
        """Review if current metrics are being achieved.

        Args:
            report: The report to populate with metric targets.
        """
        metrics = self.knowledge.get_metrics()

        for metric_name, metric in metrics.items():
            report.metrics_review[f"{metric_name}_target"] = metric.target
            report.metrics_review[f"{metric_name}_warning"] = metric.warning
            report.metrics_review[f"{metric_name}_critical"] = metric.critical

    def apply_weight_adjustments(
        self,
        adjustments: list[WeightAdjustment],
        min_confidence: float = 0.7,
    ) -> dict[str, bool]:
        """Apply suggested weight adjustments to knowledge base.

        Only adjustments meeting the minimum confidence threshold
        are applied.

        Args:
            adjustments: List of weight adjustments to apply.
            min_confidence: Minimum confidence required to apply.

        Returns:
            Dictionary mapping factor names to success status.
        """
        results: dict[str, bool] = {}

        for adj in adjustments:
            if adj.confidence < min_confidence:
                results[adj.factor_name] = False
                continue

            success = self.knowledge.update_scoring_factor(
                category=adj.category,
                name=adj.factor_name,
                weight=adj.suggested_weight,
            )
            results[adj.factor_name] = success

        return results

    def get_improvement_priorities(self) -> list[dict[str, Any]]:
        """Get prioritized list of improvement areas.

        Analyzes negative feedback patterns and scoring feedback to
        produce a ranked list of areas needing attention.

        Returns:
            List of improvement areas sorted by priority score
            (highest first).
        """
        priorities: list[dict[str, Any]] = []

        # Analyze negative feedback patterns
        patterns = self.feedback.get_negative_feedback_patterns(limit=5)

        for pattern in patterns:
            priorities.append(
                {
                    "area": "query_handling",
                    "issue": pattern.get("query", "Unknown query pattern"),
                    "frequency": pattern.get("count", 0),
                    "priority": min(pattern.get("count", 0) / 10, 1.0),
                    "suggestion": ("Review query handling for this pattern"),
                }
            )

        # Check scoring categories
        summary = self.feedback.get_summary(
            feedback_type=FeedbackType.SCORING,
            days=30,
        )

        if summary.negative_count > summary.positive_count:
            priorities.append(
                {
                    "area": "scoring",
                    "issue": ("More negative than positive feedback " "on scoring"),
                    "frequency": summary.negative_count,
                    "priority": 0.8,
                    "suggestion": ("Review scoring factor weights " "and calculations"),
                }
            )

        # Sort by priority
        priorities.sort(key=lambda x: -x["priority"])

        return priorities

    def generate_summary_report(self) -> str:
        """Generate a human-readable summary report.

        Returns:
            Formatted multi-line summary string.
        """
        report = self.analyze_and_suggest(days=30)

        lines = [
            "Knowledge Refinement Report",
            "=" * 40,
            f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M')}",
            f"Feedback Analyzed: {report.feedback_analyzed}",
            f"Satisfaction Rate: {report.satisfaction_rate:.1%}",
            "",
        ]

        if report.weight_adjustments:
            lines.append("Suggested Weight Adjustments:")
            lines.append("-" * 30)
            for adj in report.weight_adjustments:
                lines.append(
                    f"  {adj.category}/{adj.factor_name}: "
                    f"{adj.current_weight} -> {adj.suggested_weight} "
                    f"(confidence: {adj.confidence:.0%})"
                )
                lines.append(f"    Reason: {adj.reasoning}")
            lines.append("")

        if report.rule_modifications:
            lines.append("Suggested Rule Modifications:")
            lines.append("-" * 30)
            for mod in report.rule_modifications:
                lines.append(f"  {mod.rule_name}: {mod.modification_type}")
                lines.append(f"    Reason: {mod.reasoning}")
            lines.append("")

        if report.general_suggestions:
            lines.append("General Suggestions:")
            lines.append("-" * 30)
            for suggestion in report.general_suggestions:
                lines.append(f"  - {suggestion}")
            lines.append("")

        return "\n".join(lines)
