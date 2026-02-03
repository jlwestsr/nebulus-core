"""PII (Personally Identifiable Information) detection and masking.

Provides automatic detection and optional masking of sensitive data
to support HIPAA, legal privilege, and general privacy compliance.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PIIType(Enum):
    """Types of PII that can be detected."""

    SSN = "ssn"
    PHONE = "phone"
    EMAIL = "email"
    CREDIT_CARD = "credit_card"
    DATE_OF_BIRTH = "date_of_birth"
    DRIVERS_LICENSE = "drivers_license"
    PASSPORT = "passport"
    MEDICAL_RECORD = "medical_record"
    IP_ADDRESS = "ip_address"
    BANK_ACCOUNT = "bank_account"


@dataclass
class PIIMatch:
    """A detected PII match."""

    pii_type: PIIType
    value: str
    masked_value: str
    column: str | None = None
    row_index: int | None = None
    confidence: float = 1.0


@dataclass
class PIIReport:
    """Report of PII detected in a dataset."""

    total_records: int
    records_with_pii: int
    pii_by_type: dict[PIIType, int] = field(default_factory=dict)
    pii_by_column: dict[str, list[PIIType]] = field(default_factory=dict)
    samples: list[PIIMatch] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        """Check if any PII was detected."""
        return self.records_with_pii > 0

    @property
    def pii_columns(self) -> set[str]:
        """Get set of columns containing PII."""
        return set(self.pii_by_column.keys())


class PIIDetector:
    """Detect PII in data using pattern matching."""

    # Regex patterns for PII detection
    PATTERNS = {
        PIIType.SSN: [
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            re.compile(r"\b\d{3}\s\d{2}\s\d{4}\b"),
            re.compile(r"\b(?!9\d{2})[0-8]\d{2}\d{2}\d{4}\b"),
        ],
        PIIType.PHONE: [
            re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            re.compile(r"\+\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        ],
        PIIType.EMAIL: [
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        ],
        PIIType.CREDIT_CARD: [
            re.compile(r"\b4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
            re.compile(r"\b5[1-5]\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
            re.compile(r"\b3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}\b"),
            re.compile(r"\b6(?:011|5\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        ],
        PIIType.DATE_OF_BIRTH: [
            re.compile(r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19|20)\d{2}\b"),
        ],
        PIIType.IP_ADDRESS: [
            re.compile(
                r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
                r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
            ),
        ],
        PIIType.MEDICAL_RECORD: [
            re.compile(r"\bMRN[-:\s]*\d{6,10}\b", re.IGNORECASE),
            re.compile(r"\bPATIENT[-_\s]?ID[-:\s]*\d{6,12}\b", re.IGNORECASE),
        ],
    }

    # Column name hints that suggest PII content
    COLUMN_HINTS = {
        PIIType.SSN: ["ssn", "social_security", "social", "ss_number", "ss_num"],
        PIIType.PHONE: ["phone", "mobile", "cell", "telephone", "tel", "fax"],
        PIIType.EMAIL: ["email", "e_mail", "email_address", "mail"],
        PIIType.CREDIT_CARD: ["credit_card", "card_number", "cc_number", "card_num"],
        PIIType.DATE_OF_BIRTH: ["dob", "birth_date", "date_of_birth", "birthday"],
        PIIType.DRIVERS_LICENSE: ["license", "drivers_license", "dl_number"],
        PIIType.MEDICAL_RECORD: [
            "mrn",
            "medical_record",
            "patient_id",
            "chart_number",
        ],
        PIIType.BANK_ACCOUNT: ["account", "bank_account", "routing", "aba"],
    }

    MASK_CHAR = "*"

    def __init__(
        self,
        detect_types: list[PIIType] | None = None,
        sample_limit: int = 5,
    ) -> None:
        """Initialize the PII detector.

        Args:
            detect_types: Types of PII to detect (None = all).
            sample_limit: Max number of sample matches to include in report.
        """
        self.detect_types = detect_types or list(PIIType)
        self.sample_limit = sample_limit

    def _mask_value(self, value: str, pii_type: PIIType) -> str:
        """Mask a PII value, preserving structure for verification.

        Args:
            value: The original PII value.
            pii_type: Type of PII.

        Returns:
            Masked value with partial visibility.
        """
        if not value:
            return value

        if pii_type == PIIType.SSN:
            return (
                f"***-**-{value[-4:]}"
                if len(value) >= 4
                else self.MASK_CHAR * len(value)
            )

        elif pii_type == PIIType.PHONE:
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 4:
                return f"***-***-{digits[-4:]}"
            return self.MASK_CHAR * len(value)

        elif pii_type == PIIType.EMAIL:
            parts = value.split("@")
            if len(parts) == 2:
                local = parts[0]
                domain = parts[1]
                masked_local = (
                    local[0] + self.MASK_CHAR * (len(local) - 1) if local else ""
                )
                return f"{masked_local}@{domain}"
            return self.MASK_CHAR * len(value)

        elif pii_type == PIIType.CREDIT_CARD:
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 4:
                return f"****-****-****-{digits[-4:]}"
            return self.MASK_CHAR * len(value)

        elif pii_type == PIIType.IP_ADDRESS:
            parts = value.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
            return self.MASK_CHAR * len(value)

        else:
            if len(value) > 1:
                return value[0] + self.MASK_CHAR * (len(value) - 1)
            return self.MASK_CHAR * len(value)

    def _detect_in_value(self, value: str) -> list[tuple]:
        """Detect PII in a single string value.

        Returns:
            List of (PIIType, matched_value) tuples.
        """
        if not isinstance(value, str) or not value:
            return []

        matches = []
        for pii_type in self.detect_types:
            if pii_type not in self.PATTERNS:
                continue

            for pattern in self.PATTERNS[pii_type]:
                for match in pattern.finditer(value):
                    matches.append((pii_type, match.group()))

        return matches

    def _check_column_hints(self, column_name: str) -> PIIType | None:
        """Check if a column name suggests PII content.

        Returns:
            Suspected PIIType or None.
        """
        col_lower = column_name.lower()
        for pii_type, hints in self.COLUMN_HINTS.items():
            if pii_type in self.detect_types:
                for hint in hints:
                    if hint in col_lower:
                        return pii_type
        return None

    def scan_records(
        self,
        records: list[dict[str, Any]],
        include_samples: bool = True,
    ) -> PIIReport:
        """Scan a list of records for PII.

        Args:
            records: List of record dictionaries.
            include_samples: Whether to include sample matches.

        Returns:
            PIIReport with detection results.
        """
        report = PIIReport(
            total_records=len(records),
            records_with_pii=0,
            pii_by_type={},
            pii_by_column={},
            samples=[],
            warnings=[],
        )

        if not records:
            return report

        warned_columns: set[str] = set()
        records_with_pii: set[int] = set()

        for row_idx, record in enumerate(records):
            for column, value in record.items():
                if column not in warned_columns:
                    suspected_type = self._check_column_hints(column)
                    if suspected_type:
                        report.warnings.append(
                            f"Column '{column}' name suggests "
                            f"{suspected_type.value} content"
                        )
                        warned_columns.add(column)

                str_value = str(value) if value is not None else ""
                matches = self._detect_in_value(str_value)

                for pii_type, matched_value in matches:
                    records_with_pii.add(row_idx)

                    report.pii_by_type[pii_type] = (
                        report.pii_by_type.get(pii_type, 0) + 1
                    )

                    if column not in report.pii_by_column:
                        report.pii_by_column[column] = []
                    if pii_type not in report.pii_by_column[column]:
                        report.pii_by_column[column].append(pii_type)

                    if include_samples and len(report.samples) < self.sample_limit:
                        report.samples.append(
                            PIIMatch(
                                pii_type=pii_type,
                                value=matched_value,
                                masked_value=self._mask_value(matched_value, pii_type),
                                column=column,
                                row_index=row_idx,
                            )
                        )

        report.records_with_pii = len(records_with_pii)
        return report

    def mask_records(
        self,
        records: list[dict[str, Any]],
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Mask PII in records.

        Args:
            records: List of record dictionaries.
            columns: Specific columns to mask (None = all with PII).

        Returns:
            Records with PII masked.
        """
        masked_records = []

        for record in records:
            masked_record = dict(record)

            for column, value in record.items():
                if columns and column not in columns:
                    continue

                str_value = str(value) if value is not None else ""
                matches = self._detect_in_value(str_value)

                masked_value = str_value
                for pii_type, matched_value in matches:
                    masked = self._mask_value(matched_value, pii_type)
                    masked_value = masked_value.replace(matched_value, masked)

                if masked_value != str_value:
                    masked_record[column] = masked_value

            masked_records.append(masked_record)

        return masked_records

    def get_pii_summary(self, report: PIIReport) -> str:
        """Generate a human-readable summary of PII detection.

        Args:
            report: PIIReport from scanning.

        Returns:
            Summary string.
        """
        if not report.has_pii:
            return "No PII detected in the dataset."

        lines = [
            "PII Detection Summary:",
            f"  Records scanned: {report.total_records}",
            f"  Records with PII: {report.records_with_pii} "
            f"({report.records_with_pii / report.total_records * 100:.1f}%)",
            "",
            "PII Types Found:",
        ]

        for pii_type, count in sorted(report.pii_by_type.items(), key=lambda x: -x[1]):
            lines.append(f"  - {pii_type.value}: {count} occurrences")

        if report.pii_by_column:
            lines.append("")
            lines.append("Columns Containing PII:")
            for column, types in sorted(report.pii_by_column.items()):
                type_names = ", ".join(t.value for t in types)
                lines.append(f"  - {column}: {type_names}")

        if report.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in report.warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)
