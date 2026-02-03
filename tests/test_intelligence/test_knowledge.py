"""Tests for the knowledge management module."""

from pathlib import Path

import pytest

from nebulus_core.intelligence.core.knowledge import (
    BusinessRule,
    KnowledgeManager,
    Metric,
    ScoringFactor,
)
from nebulus_core.intelligence.templates import load_template


@pytest.fixture
def temp_knowledge_path(tmp_path: Path) -> Path:
    """Create a temporary knowledge file path."""
    return tmp_path / "knowledge.json"


@pytest.fixture
def dealership_config() -> dict:
    """Load dealership template config."""
    template = load_template("dealership")
    return template.config


@pytest.fixture
def knowledge_manager(
    temp_knowledge_path: Path, dealership_config: dict
) -> KnowledgeManager:
    """Create a KnowledgeManager with dealership config."""
    return KnowledgeManager(temp_knowledge_path, dealership_config)


class TestScoringFactor:
    """Tests for ScoringFactor dataclass."""

    def test_create_scoring_factor(self) -> None:
        """Test creating a scoring factor."""
        factor = ScoringFactor(
            name="test_factor",
            description="Test description",
            weight=25,
            calculation="column = true",
        )

        assert factor.name == "test_factor"
        assert factor.weight == 25


class TestBusinessRule:
    """Tests for BusinessRule dataclass."""

    def test_create_business_rule(self) -> None:
        """Test creating a business rule."""
        rule = BusinessRule(
            name="test_rule",
            description="Test description",
            condition="value > 0",
            severity="warning",
        )

        assert rule.name == "test_rule"
        assert rule.severity == "warning"


class TestMetric:
    """Tests for Metric dataclass."""

    def test_create_metric(self) -> None:
        """Test creating a metric."""
        metric = Metric(
            name="test_metric",
            description="Test description",
            target=100,
            warning=80,
            critical=50,
            lower_is_better=False,
        )

        assert metric.name == "test_metric"
        assert metric.target == 100
        assert metric.lower_is_better is False


class TestKnowledgeManager:
    """Tests for KnowledgeManager class."""

    def test_load_from_template(self, knowledge_manager: KnowledgeManager) -> None:
        """Test that knowledge loads from template config."""
        factors = knowledge_manager.get_scoring_factors("perfect_sale")

        assert len(factors) > 0
        factor_names = [f.name for f in factors]
        assert "dealer_financing" in factor_names
        assert "trade_in" in factor_names

    def test_get_all_scoring_factors(self, knowledge_manager: KnowledgeManager) -> None:
        """Test getting all scoring factors."""
        all_factors = knowledge_manager.get_all_scoring_factors()

        assert "perfect_sale" in all_factors
        assert len(all_factors["perfect_sale"]) > 0

    def test_update_scoring_factor(self, knowledge_manager: KnowledgeManager) -> None:
        """Test updating a scoring factor weight."""
        result = knowledge_manager.update_scoring_factor(
            category="perfect_sale",
            name="dealer_financing",
            weight=30,
        )

        assert result is True

        factors = knowledge_manager.get_scoring_factors("perfect_sale")
        factor = next(f for f in factors if f.name == "dealer_financing")
        assert factor.weight == 30

    def test_update_nonexistent_factor(
        self, knowledge_manager: KnowledgeManager
    ) -> None:
        """Test updating a factor that doesn't exist."""
        result = knowledge_manager.update_scoring_factor(
            category="perfect_sale",
            name="nonexistent",
            weight=50,
        )

        assert result is False

    def test_get_business_rules(self, knowledge_manager: KnowledgeManager) -> None:
        """Test getting business rules."""
        rules = knowledge_manager.get_business_rules()

        assert len(rules) > 0
        rule_names = [r.name for r in rules]
        assert "max_mileage" in rule_names

    def test_add_business_rule(self, knowledge_manager: KnowledgeManager) -> None:
        """Test adding a new business rule."""
        rule = knowledge_manager.add_business_rule(
            name="custom_rule",
            description="Custom test rule",
            condition="test > 0",
            severity="warning",
        )

        assert rule.name == "custom_rule"

        rules = knowledge_manager.get_business_rules()
        assert any(r.name == "custom_rule" for r in rules)

    def test_get_metrics(self, knowledge_manager: KnowledgeManager) -> None:
        """Test getting metrics."""
        metrics = knowledge_manager.get_metrics()

        assert "days_on_lot" in metrics
        assert metrics["days_on_lot"].target == 45

    def test_get_metric(self, knowledge_manager: KnowledgeManager) -> None:
        """Test getting a specific metric."""
        metric = knowledge_manager.get_metric("days_on_lot")

        assert metric is not None
        assert metric.target == 45
        assert metric.lower_is_better is True

    def test_get_nonexistent_metric(self, knowledge_manager: KnowledgeManager) -> None:
        """Test getting a metric that doesn't exist."""
        metric = knowledge_manager.get_metric("nonexistent")
        assert metric is None

    def test_add_custom_knowledge(self, knowledge_manager: KnowledgeManager) -> None:
        """Test adding custom knowledge."""
        knowledge_manager.add_custom_knowledge("my_key", {"data": "value"})

        result = knowledge_manager.get_custom_knowledge("my_key")
        assert result == {"data": "value"}

    def test_get_nonexistent_custom_knowledge(
        self, knowledge_manager: KnowledgeManager
    ) -> None:
        """Test getting custom knowledge that doesn't exist."""
        result = knowledge_manager.get_custom_knowledge("nonexistent")
        assert result is None

    def test_export_for_prompt(self, knowledge_manager: KnowledgeManager) -> None:
        """Test exporting knowledge for LLM prompt."""
        prompt = knowledge_manager.export_for_prompt()

        assert "Domain Knowledge" in prompt
        assert "Perfect Sale" in prompt
        assert "Business Rules" in prompt
        assert "Key Metrics" in prompt

    def test_to_dict(self, knowledge_manager: KnowledgeManager) -> None:
        """Test converting knowledge to dict."""
        data = knowledge_manager.to_dict()

        assert "scoring_factors" in data
        assert "rules" in data
        assert "metrics" in data

    def test_persistence(
        self, temp_knowledge_path: Path, dealership_config: dict
    ) -> None:
        """Test that changes persist to file."""
        km1 = KnowledgeManager(temp_knowledge_path, dealership_config)
        km1.add_custom_knowledge("persist_test", "test_value")

        km2 = KnowledgeManager(temp_knowledge_path, dealership_config)
        result = km2.get_custom_knowledge("persist_test")
        assert result == "test_value"

    def test_without_template_config(self, temp_knowledge_path: Path) -> None:
        """Test creating KnowledgeManager without template config."""
        km = KnowledgeManager(temp_knowledge_path, template_config=None)

        factors = km.get_scoring_factors("any_category")
        assert factors == []

        rules = km.get_business_rules()
        assert rules == []
