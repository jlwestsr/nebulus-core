"""Tests for the vertical templates module."""

import pytest

from nebulus_core.intelligence.templates import (
    VerticalTemplate,
    list_templates,
    load_template,
)


class TestListTemplates:
    """Tests for list_templates function."""

    def test_list_templates(self) -> None:
        """list_templates includes all three bundled verticals."""
        templates = list_templates()
        assert "dealership" in templates
        assert "medical" in templates
        assert "legal" in templates

    def test_list_templates_returns_list(self) -> None:
        """list_templates returns a list type."""
        templates = list_templates()
        assert isinstance(templates, list)


class TestLoadTemplate:
    """Tests for load_template function."""

    def test_load_dealership_template(self) -> None:
        """load_template returns a VerticalTemplate for dealership."""
        template = load_template("dealership")
        assert isinstance(template, VerticalTemplate)
        assert template.name == "dealership"

    def test_load_medical_template(self) -> None:
        """load_template returns medical template with correct display name."""
        template = load_template("medical")
        assert template.name == "medical"
        assert template.display_name == "Medical Practice"

    def test_load_legal_template(self) -> None:
        """load_template returns legal template with correct display name."""
        template = load_template("legal")
        assert template.name == "legal"
        assert template.display_name == "Law Firm"

    def test_load_nonexistent_template(self) -> None:
        """load_template raises ValueError for unknown template name."""
        with pytest.raises(ValueError, match="not found"):
            load_template("nonexistent")


class TestVerticalTemplate:
    """Tests for VerticalTemplate class."""

    @pytest.fixture
    def dealership_template(self) -> VerticalTemplate:
        return load_template("dealership")

    @pytest.fixture
    def medical_template(self) -> VerticalTemplate:
        return load_template("medical")

    @pytest.fixture
    def legal_template(self) -> VerticalTemplate:
        return load_template("legal")

    def test_display_name(self, dealership_template: VerticalTemplate) -> None:
        """Dealership template has correct display name."""
        assert dealership_template.display_name == "Auto Dealership"

    def test_description(self, dealership_template: VerticalTemplate) -> None:
        """Dealership template has a non-empty description."""
        assert len(dealership_template.description) > 0

    def test_get_primary_key_hints_dealership(
        self, dealership_template: VerticalTemplate
    ) -> None:
        """Dealership template includes VIN and stock_number as primary key hints."""
        hints = dealership_template.get_primary_key_hints()
        assert "vin" in hints
        assert "VIN" in hints
        assert "stock_number" in hints

    def test_get_primary_key_hints_medical(
        self, medical_template: VerticalTemplate
    ) -> None:
        """Medical template includes patient_id and mrn as primary key hints."""
        hints = medical_template.get_primary_key_hints()
        assert "patient_id" in hints
        assert "mrn" in hints

    def test_get_primary_key_hints_legal(
        self, legal_template: VerticalTemplate
    ) -> None:
        """Legal template includes case_id and matter_id as primary key hints."""
        hints = legal_template.get_primary_key_hints()
        assert "case_id" in hints
        assert "matter_id" in hints

    def test_get_data_sources(self, dealership_template: VerticalTemplate) -> None:
        """Dealership template defines inventory and sales data sources."""
        sources = dealership_template.get_data_sources()
        assert "inventory" in sources
        assert "sales" in sources
        assert "required_columns" in sources["inventory"]

    def test_get_scoring_factors(self, dealership_template: VerticalTemplate) -> None:
        """Dealership template defines scoring factors including perfect_sale."""
        scoring = dealership_template.get_scoring_factors()
        assert "perfect_sale" in scoring
        assert "dealer_financing" in scoring["perfect_sale"]

    def test_get_business_rules(self, dealership_template: VerticalTemplate) -> None:
        """Dealership template defines business rules including max_mileage."""
        rules = dealership_template.get_business_rules()
        assert len(rules) > 0
        assert any(r["name"] == "max_mileage" for r in rules)

    def test_get_metrics(self, dealership_template: VerticalTemplate) -> None:
        """Dealership template defines metrics including days_on_lot."""
        metrics = dealership_template.get_metrics()
        assert "days_on_lot" in metrics
        assert "target" in metrics["days_on_lot"]

    def test_get_canned_queries(self, dealership_template: VerticalTemplate) -> None:
        """Dealership template provides canned queries with name and sql."""
        queries = dealership_template.get_canned_queries()
        assert len(queries) > 0
        assert all("name" in q for q in queries)
        assert all("sql" in q for q in queries)

    def test_find_canned_query(self, dealership_template: VerticalTemplate) -> None:
        """find_canned_query returns matching query by name."""
        query = dealership_template.find_canned_query("aged_inventory")
        assert query is not None
        assert "sql" in query

    def test_find_nonexistent_canned_query(
        self, dealership_template: VerticalTemplate
    ) -> None:
        """find_canned_query returns None for unknown query name."""
        query = dealership_template.find_canned_query("nonexistent")
        assert query is None

    def test_get_system_prompt(self, dealership_template: VerticalTemplate) -> None:
        """Dealership system prompt mentions dealership context."""
        prompt = dealership_template.get_system_prompt()
        assert len(prompt) > 0
        assert "dealership" in prompt.lower()

    def test_get_strategic_prompt(self, dealership_template: VerticalTemplate) -> None:
        """Dealership strategic prompt mentions inventory."""
        prompt = dealership_template.get_strategic_prompt()
        assert len(prompt) > 0
        assert "inventory" in prompt.lower()

    def test_validate_data_source_valid(
        self, dealership_template: VerticalTemplate
    ) -> None:
        """Validation passes when all required columns are present."""
        result = dealership_template.validate_data_source(
            "inventory",
            ["vin", "make", "model", "year", "days_on_lot"],
        )
        assert result["valid"] is True
        assert len(result["missing_required"]) == 0

    def test_validate_data_source_missing_required(
        self, dealership_template: VerticalTemplate
    ) -> None:
        """Validation fails when required columns are missing."""
        result = dealership_template.validate_data_source(
            "inventory",
            ["vin", "make"],
        )
        assert result["valid"] is False
        assert "model" in result["missing_required"]
        assert "year" in result["missing_required"]

    def test_validate_data_source_unknown_source(
        self, dealership_template: VerticalTemplate
    ) -> None:
        """Validation passes with warning for unknown data source."""
        result = dealership_template.validate_data_source(
            "unknown_source",
            ["col1", "col2"],
        )
        assert result["valid"] is True
        assert "warning" in result

    def test_medical_template_scoring(self, medical_template: VerticalTemplate) -> None:
        """Medical template defines ideal_visit and patient_engagement scoring."""
        scoring = medical_template.get_scoring_factors()
        assert "ideal_visit" in scoring
        assert "patient_engagement" in scoring

    def test_legal_template_scoring(self, legal_template: VerticalTemplate) -> None:
        """Legal template defines matter_health and timekeeper_productivity scoring."""
        scoring = legal_template.get_scoring_factors()
        assert "matter_health" in scoring
        assert "timekeeper_productivity" in scoring

    def test_medical_template_hipaa_warning(
        self, medical_template: VerticalTemplate
    ) -> None:
        """Medical template system prompt mentions HIPAA or privacy."""
        prompt = medical_template.get_system_prompt()
        assert "hipaa" in prompt.lower() or "privacy" in prompt.lower()

    def test_legal_template_privilege_warning(
        self, legal_template: VerticalTemplate
    ) -> None:
        """Legal template system prompt mentions privilege or confidential."""
        prompt = legal_template.get_system_prompt()
        assert "privilege" in prompt.lower() or "confidential" in prompt.lower()
