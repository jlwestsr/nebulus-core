"""Domain knowledge management for business rules and scoring."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ScoringFactor:
    """A factor that contributes to outcome quality scoring."""

    name: str
    description: str
    weight: int
    calculation: str  # SQL-like expression or description


@dataclass
class BusinessRule:
    """A business rule or constraint."""

    name: str
    description: str
    condition: str  # SQL-like condition
    severity: str = "warning"  # warning, error, info


@dataclass
class Metric:
    """A key performance metric with targets."""

    name: str
    description: str
    target: float
    warning: float
    critical: float
    lower_is_better: bool = True


@dataclass
class DomainKnowledge:
    """Container for all domain knowledge."""

    scoring_factors: dict[str, list[ScoringFactor]] = field(default_factory=dict)
    rules: list[BusinessRule] = field(default_factory=list)
    metrics: dict[str, Metric] = field(default_factory=dict)
    custom_knowledge: dict[str, Any] = field(default_factory=dict)


class KnowledgeManager:
    """Manage domain knowledge for a business."""

    def __init__(
        self,
        knowledge_path: Path,
        template_config: dict | None = None,
    ) -> None:
        """Initialize the knowledge manager.

        Args:
            knowledge_path: Path to store custom knowledge JSON.
            template_config: Optional template config to load defaults from.
        """
        self.knowledge_path = knowledge_path
        self.knowledge = DomainKnowledge()

        if template_config:
            self._load_from_template(template_config)

        self._load_custom()

    def _load_from_template(self, config: dict) -> None:
        """Load default knowledge from template config.

        Args:
            config: Template configuration dictionary containing scoring,
                rules, and metrics sections.
        """
        scoring_config = config.get("scoring", {})
        for category, factors in scoring_config.items():
            self.knowledge.scoring_factors[category] = []
            for name, factor_data in factors.items():
                self.knowledge.scoring_factors[category].append(
                    ScoringFactor(
                        name=name,
                        description=factor_data.get("description", ""),
                        weight=factor_data.get("weight", 0),
                        calculation=factor_data.get("calculation", ""),
                    )
                )

        rules_config = config.get("rules", [])
        for rule_data in rules_config:
            self.knowledge.rules.append(
                BusinessRule(
                    name=rule_data.get("name", ""),
                    description=rule_data.get("description", ""),
                    condition=rule_data.get("condition", ""),
                    severity=rule_data.get("severity", "warning"),
                )
            )

        metrics_config = config.get("metrics", {})
        for name, metric_data in metrics_config.items():
            self.knowledge.metrics[name] = Metric(
                name=name,
                description=metric_data.get("description", ""),
                target=metric_data.get("target", 0),
                warning=metric_data.get("warning", 0),
                critical=metric_data.get("critical", 0),
                lower_is_better=metric_data.get("lower_is_better", True),
            )

    def _load_custom(self) -> None:
        """Load custom knowledge overrides from JSON file."""
        if not self.knowledge_path.exists():
            return

        try:
            with open(self.knowledge_path) as f:
                custom = json.load(f)

            for category, factors in custom.get("scoring_factors", {}).items():
                if category not in self.knowledge.scoring_factors:
                    self.knowledge.scoring_factors[category] = []
                for factor_data in factors:
                    existing = next(
                        (
                            f
                            for f in self.knowledge.scoring_factors[category]
                            if f.name == factor_data["name"]
                        ),
                        None,
                    )
                    if existing:
                        existing.weight = factor_data.get("weight", existing.weight)
                        existing.description = factor_data.get(
                            "description", existing.description
                        )
                    else:
                        self.knowledge.scoring_factors[category].append(
                            ScoringFactor(
                                name=factor_data["name"],
                                description=factor_data.get("description", ""),
                                weight=factor_data.get("weight", 0),
                                calculation=factor_data.get("calculation", ""),
                            )
                        )

            for rule_data in custom.get("rules", []):
                existing = next(
                    (r for r in self.knowledge.rules if r.name == rule_data["name"]),
                    None,
                )
                if not existing:
                    self.knowledge.rules.append(
                        BusinessRule(
                            name=rule_data["name"],
                            description=rule_data.get("description", ""),
                            condition=rule_data.get("condition", ""),
                            severity=rule_data.get("severity", "warning"),
                        )
                    )

            self.knowledge.custom_knowledge.update(custom.get("custom", {}))

        except (json.JSONDecodeError, KeyError):
            pass  # Ignore malformed custom knowledge

    def save_custom(self) -> None:
        """Save custom knowledge to JSON file."""
        self.knowledge_path.parent.mkdir(parents=True, exist_ok=True)

        custom: dict[str, Any] = {
            "scoring_factors": {},
            "rules": [],
            "custom": self.knowledge.custom_knowledge,
        }

        for category, factors in self.knowledge.scoring_factors.items():
            custom["scoring_factors"][category] = [
                {
                    "name": f.name,
                    "description": f.description,
                    "weight": f.weight,
                    "calculation": f.calculation,
                }
                for f in factors
            ]

        custom["rules"] = [
            {
                "name": r.name,
                "description": r.description,
                "condition": r.condition,
                "severity": r.severity,
            }
            for r in self.knowledge.rules
        ]

        with open(self.knowledge_path, "w") as f:
            json.dump(custom, f, indent=2)

    def get_scoring_factors(
        self, category: str = "perfect_sale"
    ) -> list[ScoringFactor]:
        """Get scoring factors for a category.

        Args:
            category: The scoring category name.

        Returns:
            List of scoring factors for the category.
        """
        return self.knowledge.scoring_factors.get(category, [])

    def get_all_scoring_factors(
        self,
    ) -> dict[str, list[ScoringFactor]]:
        """Get all scoring factors.

        Returns:
            Dictionary mapping category names to scoring factor lists.
        """
        return self.knowledge.scoring_factors

    def update_scoring_factor(
        self,
        category: str,
        name: str,
        weight: int | None = None,
        description: str | None = None,
    ) -> bool:
        """Update a scoring factor's weight or description.

        Args:
            category: The scoring category containing the factor.
            name: Name of the factor to update.
            weight: New weight value, if updating.
            description: New description, if updating.

        Returns:
            True if the factor was found and updated, False otherwise.
        """
        factors = self.knowledge.scoring_factors.get(category, [])
        for factor in factors:
            if factor.name == name:
                if weight is not None:
                    factor.weight = weight
                if description is not None:
                    factor.description = description
                self.save_custom()
                return True
        return False

    def get_business_rules(self) -> list[BusinessRule]:
        """Get all business rules.

        Returns:
            List of all business rules.
        """
        return self.knowledge.rules

    def add_business_rule(
        self,
        name: str,
        description: str,
        condition: str,
        severity: str = "warning",
    ) -> BusinessRule:
        """Add a new business rule.

        Args:
            name: Rule name.
            description: Human-readable description.
            condition: SQL-like condition expression.
            severity: Rule severity level (warning, error, info).

        Returns:
            The newly created BusinessRule.
        """
        rule = BusinessRule(
            name=name,
            description=description,
            condition=condition,
            severity=severity,
        )
        self.knowledge.rules.append(rule)
        self.save_custom()
        return rule

    def get_metrics(self) -> dict[str, Metric]:
        """Get all metrics.

        Returns:
            Dictionary mapping metric names to Metric objects.
        """
        return self.knowledge.metrics

    def get_metric(self, name: str) -> Metric | None:
        """Get a specific metric.

        Args:
            name: The metric name.

        Returns:
            The Metric if found, None otherwise.
        """
        return self.knowledge.metrics.get(name)

    def add_custom_knowledge(self, key: str, value: Any) -> None:
        """Add custom knowledge.

        Args:
            key: Knowledge key.
            value: Knowledge value (any JSON-serializable type).
        """
        self.knowledge.custom_knowledge[key] = value
        self.save_custom()

    def get_custom_knowledge(self, key: str) -> Any | None:
        """Get custom knowledge by key.

        Args:
            key: The knowledge key.

        Returns:
            The stored value if found, None otherwise.
        """
        return self.knowledge.custom_knowledge.get(key)

    def export_for_prompt(self) -> str:
        """Format knowledge for LLM context injection.

        Returns:
            Markdown-formatted string of all domain knowledge.
        """
        lines = ["## Domain Knowledge", ""]

        if self.knowledge.scoring_factors:
            lines.append("### What Makes a Good Outcome")
            for category, factors in self.knowledge.scoring_factors.items():
                lines.append(f"\n**{category.replace('_', ' ').title()}:**")
                for f in sorted(factors, key=lambda x: -x.weight):
                    lines.append(f"- {f.description} (weight: {f.weight})")

        if self.knowledge.rules:
            lines.append("\n### Business Rules")
            for rule in self.knowledge.rules:
                lines.append(f"- **{rule.name}**: {rule.description}")

        if self.knowledge.metrics:
            lines.append("\n### Key Metrics")
            for name, metric in self.knowledge.metrics.items():
                direction = "lower" if metric.lower_is_better else "higher"
                lines.append(
                    f"- **{name}**: target {metric.target}, "
                    f"warning at {metric.warning}, "
                    f"critical at {metric.critical} "
                    f"({direction} is better)"
                )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Export knowledge as a dictionary.

        Returns:
            Dictionary representation of all domain knowledge.
        """
        return {
            "scoring_factors": {
                category: [
                    {
                        "name": f.name,
                        "description": f.description,
                        "weight": f.weight,
                        "calculation": f.calculation,
                    }
                    for f in factors
                ]
                for category, factors in (self.knowledge.scoring_factors.items())
            },
            "rules": [
                {
                    "name": r.name,
                    "description": r.description,
                    "condition": r.condition,
                    "severity": r.severity,
                }
                for r in self.knowledge.rules
            ],
            "metrics": {
                name: {
                    "description": m.description,
                    "target": m.target,
                    "warning": m.warning,
                    "critical": m.critical,
                    "lower_is_better": m.lower_is_better,
                }
                for name, m in self.knowledge.metrics.items()
            },
            "custom": self.knowledge.custom_knowledge,
        }
