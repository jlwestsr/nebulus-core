"""Base template class for vertical configurations."""

import importlib.resources as pkg_resources
from pathlib import Path
from typing import Any

import yaml


class VerticalTemplate:
    """Base class for loading and accessing vertical template configurations."""

    def __init__(
        self,
        template_name: str,
        custom_config_path: Path | None = None,
    ) -> None:
        """Load a vertical template by name.

        Args:
            template_name: Name of the template (e.g., 'dealership').
            custom_config_path: Optional path to a custom config YAML overlay.
        """
        self.name = template_name
        self.config = self._load_config(template_name)

        if custom_config_path is not None:
            custom = self._load_custom_config(custom_config_path)
            self.config.update(custom)

    def _load_config(self, template_name: str) -> dict:
        """Load the bundled config.yaml for a template via importlib.resources."""
        try:
            ref = pkg_resources.files(
                f"nebulus_core.intelligence.templates.{template_name}"
            ) / "config.yaml"
            config_text = ref.read_text(encoding="utf-8")
            return yaml.safe_load(config_text)
        except (ModuleNotFoundError, FileNotFoundError) as e:
            raise ValueError(f"Template '{template_name}' not found: {e}")

    def _load_custom_config(self, config_path: Path) -> dict:
        """Load a custom config YAML file for overlay."""
        with open(config_path) as f:
            return yaml.safe_load(f)

    @property
    def display_name(self) -> str:
        """Human-readable template name."""
        return self.config.get("display_name", self.name.title())

    @property
    def description(self) -> str:
        """Template description."""
        return self.config.get("description", "")

    def get_primary_key_hints(self) -> list[str]:
        """Return column names that might be primary keys."""
        return self.config.get("primary_keys", [])

    def get_data_sources(self) -> dict:
        """Return expected data source definitions."""
        return self.config.get("data_sources", {})

    def get_scoring_factors(self) -> dict:
        """Return scoring configuration for outcome quality."""
        return self.config.get("scoring", {})

    def get_business_rules(self) -> list[dict]:
        """Return business rules and constraints."""
        return self.config.get("rules", [])

    def get_metrics(self) -> dict:
        """Return metric definitions with targets and thresholds."""
        return self.config.get("metrics", {})

    def get_canned_queries(self) -> list[dict]:
        """Return pre-built queries for common questions."""
        return self.config.get("canned_queries", [])

    def get_system_prompt(self) -> str:
        """Return customized system prompt for this vertical."""
        prompts = self.config.get("prompts", {})
        return prompts.get("system", "")

    def get_strategic_prompt(self) -> str:
        """Return prompt for strategic analysis questions."""
        prompts = self.config.get("prompts", {})
        return prompts.get("strategic_analysis", "")

    def find_canned_query(self, name: str) -> dict | None:
        """Find a canned query by name."""
        for query in self.get_canned_queries():
            if query.get("name") == name:
                return query
        return None

    def validate_data_source(
        self,
        source_name: str,
        columns: list[str],
    ) -> dict[str, Any]:
        """Validate uploaded data against expected schema.

        Args:
            source_name: Name of the data source (e.g., 'inventory').
            columns: List of column names in the uploaded data.

        Returns:
            Dict with validation results:
            - valid: bool
            - missing_required: list of missing required columns
            - matched_optional: list of matched optional columns
            - unknown_columns: list of columns not in schema
        """
        sources = self.get_data_sources()

        if source_name not in sources:
            return {
                "valid": True,
                "missing_required": [],
                "matched_optional": [],
                "unknown_columns": columns,
                "warning": f"Unknown data source type: {source_name}",
            }

        source_def = sources[source_name]
        required = set(source_def.get("required_columns", []))
        optional = set(source_def.get("optional_columns", []))
        all_expected = required | optional

        columns_lower = {c.lower(): c for c in columns}

        missing_required = []
        for req in required:
            if req.lower() not in columns_lower:
                missing_required.append(req)

        matched_optional = []
        for opt in optional:
            if opt.lower() in columns_lower:
                matched_optional.append(opt)

        unknown = []
        for col in columns:
            if col.lower() not in {c.lower() for c in all_expected}:
                unknown.append(col)

        return {
            "valid": len(missing_required) == 0,
            "missing_required": missing_required,
            "matched_optional": matched_optional,
            "unknown_columns": unknown,
        }


def list_templates() -> list[str]:
    """List all available bundled templates."""
    templates_pkg = pkg_resources.files("nebulus_core.intelligence.templates")
    templates = []

    for item in templates_pkg.iterdir():
        if item.is_dir() and (item / "config.yaml").is_file():
            templates.append(item.name)

    return sorted(templates)


def load_template(
    name: str,
    custom_config_path: Path | None = None,
) -> VerticalTemplate:
    """Load a template by name.

    Args:
        name: Template name (e.g., 'dealership').
        custom_config_path: Optional path to custom config overlay.

    Returns:
        Loaded VerticalTemplate instance.
    """
    return VerticalTemplate(name, custom_config_path=custom_config_path)
