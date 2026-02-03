"""Tests for the data ingestion module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nebulus_core.intelligence.core.ingest import DataIngestor, IngestResult
from nebulus_core.intelligence.core.pii import PIIDetector

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Return a temporary database path using pytest's tmp_path."""
    return tmp_path / "test.db"


@pytest.fixture
def pii_detector() -> PIIDetector:
    """Return a default PIIDetector."""
    return PIIDetector()


@pytest.fixture
def mock_vector_engine() -> MagicMock:
    """Return a mocked VectorEngine."""
    engine = MagicMock()
    engine.embed_records.return_value = 3
    engine.delete_collection.return_value = True
    return engine


@pytest.fixture
def sample_csv() -> str:
    """Sample CSV content for testing."""
    return (
        "vin,make,model,year,price\n"
        "ABC123,Honda,Accord,2020,25000\n"
        "DEF456,Toyota,Camry,2021,28000\n"
        "GHI789,Ford,F-150,2019,35000\n"
    )


@pytest.fixture
def dealership_template() -> MagicMock:
    """Return a mock VerticalTemplate with dealership PK hints."""
    tpl = MagicMock()
    tpl.get_primary_key_hints.return_value = [
        "vin",
        "VIN",
        "stock_number",
        "stocknumber",
        "stock_no",
        "StockNumber",
        "Stock_Number",
    ]
    return tpl


@pytest.fixture
def medical_template() -> MagicMock:
    """Return a mock VerticalTemplate with medical PK hints."""
    tpl = MagicMock()
    tpl.get_primary_key_hints.return_value = [
        "patient_id",
        "patientid",
        "PatientID",
        "mrn",
        "MRN",
        "Patient_ID",
    ]
    return tpl


@pytest.fixture
def legal_template() -> MagicMock:
    """Return a mock VerticalTemplate with legal PK hints."""
    tpl = MagicMock()
    tpl.get_primary_key_hints.return_value = [
        "case_id",
        "caseid",
        "CaseID",
        "matter_id",
        "MatterID",
        "Case_ID",
    ]
    return tpl


@pytest.fixture
def ingestor(
    temp_db: Path,
    pii_detector: PIIDetector,
    dealership_template: MagicMock,
) -> DataIngestor:
    """Create a DataIngestor with dealership template."""
    return DataIngestor(
        db_path=temp_db,
        pii_detector=pii_detector,
        template=dealership_template,
    )


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestDataIngestor:
    """Tests for DataIngestor class."""

    def test_ingest_csv_basic(
        self,
        ingestor: DataIngestor,
        sample_csv: str,
    ) -> None:
        """Test basic CSV ingestion."""
        result = ingestor.ingest_csv(sample_csv, "test_table")

        assert isinstance(result, IngestResult)
        assert result.table_name == "test_table"
        assert result.rows_imported == 3
        assert "vin" in result.columns
        assert "make" in result.columns

    def test_ingest_csv_bytes(
        self,
        ingestor: DataIngestor,
        sample_csv: str,
    ) -> None:
        """Test CSV ingestion from bytes."""
        result = ingestor.ingest_csv(sample_csv.encode("utf-8"), "test_table")
        assert result.rows_imported == 3

    def test_primary_key_detection_dealership(
        self,
        ingestor: DataIngestor,
        sample_csv: str,
    ) -> None:
        """Test primary key detection for dealership template."""
        result = ingestor.ingest_csv(sample_csv, "test_table")
        assert result.primary_key == "vin"

    def test_column_name_cleaning(self, ingestor: DataIngestor) -> None:
        """Test that column names are cleaned properly."""
        csv_content = "First Name,Last-Name,Phone Number\nJohn,Doe,555-1234\n"
        result = ingestor.ingest_csv(csv_content, "test_table")

        assert "first_name" in result.columns
        assert "last_name" in result.columns
        assert "phone_number" in result.columns

    def test_column_type_inference(
        self,
        ingestor: DataIngestor,
        sample_csv: str,
    ) -> None:
        """Test column type inference."""
        result = ingestor.ingest_csv(sample_csv, "test_table")

        assert result.column_types["year"] == "INTEGER"
        assert result.column_types["price"] == "INTEGER"
        assert result.column_types["make"] == "TEXT"

    def test_list_tables(
        self,
        ingestor: DataIngestor,
        sample_csv: str,
    ) -> None:
        """Test listing tables."""
        ingestor.ingest_csv(sample_csv, "table1")
        ingestor.ingest_csv(sample_csv, "table2")

        tables = ingestor.list_tables()
        assert "table1" in tables
        assert "table2" in tables

    def test_get_table_schema(
        self,
        ingestor: DataIngestor,
        sample_csv: str,
    ) -> None:
        """Test getting table schema."""
        ingestor.ingest_csv(sample_csv, "test_table")

        schema = ingestor.get_table_schema("test_table")
        assert schema["table_name"] == "test_table"
        assert schema["row_count"] == 3
        assert "vin" in schema["columns"]

    def test_preview_table(
        self,
        ingestor: DataIngestor,
        sample_csv: str,
    ) -> None:
        """Test previewing table data."""
        ingestor.ingest_csv(sample_csv, "test_table")

        preview = ingestor.preview_table("test_table", limit=2)
        assert len(preview) == 2
        assert preview[0]["make"] == "Honda"

    def test_delete_table(
        self,
        ingestor: DataIngestor,
        sample_csv: str,
    ) -> None:
        """Test deleting a table."""
        ingestor.ingest_csv(sample_csv, "test_table")
        assert "test_table" in ingestor.list_tables()

        result = ingestor.delete_table("test_table")
        assert result is True
        assert "test_table" not in ingestor.list_tables()

    def test_delete_nonexistent_table(self, ingestor: DataIngestor) -> None:
        """Test deleting a table that doesn't exist."""
        result = ingestor.delete_table("nonexistent")
        assert result is False

    def test_ingest_empty_csv_raises(self, ingestor: DataIngestor) -> None:
        """Test that empty CSV raises ValueError."""
        with pytest.raises(ValueError, match="Failed to parse"):
            ingestor.ingest_csv("", "test_table")

    def test_ingest_headers_only_raises(self, ingestor: DataIngestor) -> None:
        """Test that CSV with only headers raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            ingestor.ingest_csv("col1,col2,col3\n", "test_table")

    def test_duplicate_primary_key_warning(self, ingestor: DataIngestor) -> None:
        """Test that duplicate primary keys generate a warning."""
        csv_content = "vin,make,model\nABC123,Honda,Accord\nABC123,Toyota,Camry\n"
        result = ingestor.ingest_csv(csv_content, "test_table")

        assert any("duplicates" in w.lower() for w in result.warnings)

    def test_medical_template_primary_key(
        self,
        temp_db: Path,
        pii_detector: PIIDetector,
        medical_template: MagicMock,
    ) -> None:
        """Test primary key detection for medical template."""
        ingestor = DataIngestor(
            db_path=temp_db,
            pii_detector=pii_detector,
            template=medical_template,
        )
        csv_content = (
            "patient_id,first_name,last_name\n" "P001,John,Doe\n" "P002,Jane,Smith\n"
        )
        result = ingestor.ingest_csv(csv_content, "patients")
        assert result.primary_key == "patient_id"

    def test_legal_template_primary_key(
        self,
        temp_db: Path,
        pii_detector: PIIDetector,
        legal_template: MagicMock,
    ) -> None:
        """Test primary key detection for legal template."""
        ingestor = DataIngestor(
            db_path=temp_db,
            pii_detector=pii_detector,
            template=legal_template,
        )
        csv_content = (
            "case_id,client_name,matter_type\n"
            "C001,Acme Corp,litigation\n"
            "C002,Smith LLC,transactional\n"
        )
        result = ingestor.ingest_csv(csv_content, "matters")
        assert result.primary_key == "case_id"

    def test_vector_engine_embedding(
        self,
        temp_db: Path,
        pii_detector: PIIDetector,
        mock_vector_engine: MagicMock,
        sample_csv: str,
        dealership_template: MagicMock,
    ) -> None:
        """Test that VectorEngine.embed_records is called on ingest."""
        ingestor = DataIngestor(
            db_path=temp_db,
            pii_detector=pii_detector,
            vector_engine=mock_vector_engine,
            template=dealership_template,
        )
        result = ingestor.ingest_csv(sample_csv, "test_table")

        assert result.records_embedded == 3
        mock_vector_engine.embed_records.assert_called_once()

    def test_vector_engine_delete_on_table_delete(
        self,
        temp_db: Path,
        pii_detector: PIIDetector,
        mock_vector_engine: MagicMock,
        sample_csv: str,
        dealership_template: MagicMock,
    ) -> None:
        """Test that deleting a table also deletes the vector collection."""
        ingestor = DataIngestor(
            db_path=temp_db,
            pii_detector=pii_detector,
            vector_engine=mock_vector_engine,
            template=dealership_template,
        )
        ingestor.ingest_csv(sample_csv, "test_table")
        ingestor.delete_table("test_table")

        mock_vector_engine.delete_collection.assert_called_once_with("test_table")

    def test_no_template_falls_back_to_generic(
        self,
        temp_db: Path,
        pii_detector: PIIDetector,
    ) -> None:
        """Test that no template uses generic PK hints."""
        ingestor = DataIngestor(
            db_path=temp_db,
            pii_detector=pii_detector,
        )
        csv_content = "id,name,value\n1,alpha,100\n2,beta,200\n"
        result = ingestor.ingest_csv(csv_content, "generic_table")
        assert result.primary_key == "id"
