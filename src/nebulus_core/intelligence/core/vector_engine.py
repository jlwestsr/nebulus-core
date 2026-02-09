"""Vector search engine using ChromaDB.

Provides semantic search over business data using embeddings,
backed by the shared VectorClient.
"""

import json
import logging
from dataclasses import dataclass

from nebulus_core.vector.client import VectorClient

logger = logging.getLogger(__name__)


@dataclass
class SimilarRecord:
    """A record found via similarity search."""

    id: str
    record: dict
    distance: float
    similarity: float


@dataclass
class PatternResult:
    """Result of pattern detection across similar records."""

    common_fields: dict[str, list]
    frequent_values: dict[str, dict[str, int]]
    numeric_ranges: dict[str, dict[str, float]]
    sample_count: int


class VectorEngine:
    """Semantic search over business data using ChromaDB.

    Wraps VectorClient to provide high-level operations such as
    embedding records, similarity search, pattern detection, and
    collection management.
    """

    def __init__(self, vector_client: VectorClient) -> None:
        """Initialize the vector engine.

        Args:
            vector_client: Shared VectorClient instance (HTTP or embedded).
        """
        self.client = vector_client

    def _get_collection(self, table_name: str):
        """Get or create a collection for a table.

        Args:
            table_name: Name of the ChromaDB collection.

        Returns:
            ChromaDB Collection instance.
        """
        return self.client.get_or_create_collection(
            name=table_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _record_to_text(self, record: dict) -> str:
        """Convert a record to text for embedding.

        Creates a natural language representation of the record
        that captures its semantic meaning.

        Args:
            record: Key-value mapping of field names to values.

        Returns:
            Dot-separated string of ``Label: value`` pairs.
        """
        parts = []
        for key, value in record.items():
            if value is not None:
                label = key.replace("_", " ").title()
                parts.append(f"{label}: {value}")
        return ". ".join(parts)

    def embed_records(
        self,
        table_name: str,
        records: list[dict],
        id_field: str,
    ) -> int:
        """Convert records to embeddings and store in ChromaDB.

        Args:
            table_name: Name of the collection.
            records: List of record dictionaries.
            id_field: Field to use as document ID.

        Returns:
            Number of records embedded.
        """
        if not records:
            return 0

        collection = self._get_collection(table_name)

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for record in records:
            record_id = str(record.get(id_field, hash(json.dumps(record, default=str))))
            ids.append(record_id)

            doc_text = self._record_to_text(record)
            documents.append(doc_text)

            metadata: dict = {}
            for k, v in record.items():
                if v is None:
                    metadata[k] = ""
                elif isinstance(v, (int, float, str, bool)):
                    metadata[k] = v
                else:
                    metadata[k] = str(v)
            metadatas.append(metadata)

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        return len(records)

    def search_similar(
        self,
        table_name: str,
        query: str,
        n_results: int = 10,
        filters: dict | None = None,
    ) -> list[SimilarRecord]:
        """Find records semantically similar to a query.

        Args:
            table_name: Collection to search.
            query: Natural language query or example text.
            n_results: Maximum results to return.
            filters: Optional metadata filters (ChromaDB where clause).

        Returns:
            List of similar records with distances.
        """
        collection = self._get_collection(table_name)

        if collection.count() == 0:
            return []

        query_params: dict = {
            "query_texts": [query],
            "n_results": min(n_results, collection.count()),
        }

        if filters:
            query_params["where"] = filters

        results = collection.query(**query_params)

        similar_records: list[SimilarRecord] = []
        if results["ids"] and results["ids"][0]:
            for i, record_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}

                similar_records.append(
                    SimilarRecord(
                        id=record_id,
                        record=metadata,
                        distance=distance,
                        similarity=1 - distance,
                    )
                )

        return similar_records

    def search_by_example(
        self,
        table_name: str,
        record_id: str,
        n_results: int = 10,
    ) -> list[SimilarRecord]:
        """Find records similar to an existing record by ID.

        Args:
            table_name: Collection to search.
            record_id: ID of the example record.
            n_results: Maximum results to return.

        Returns:
            List of similar records (excluding the example).
        """
        collection = self._get_collection(table_name)

        try:
            result = collection.get(
                ids=[record_id], include=["embeddings", "documents"]
            )
            if not result["embeddings"] or not result["embeddings"][0]:
                return []

            embedding = result["embeddings"][0]
        except Exception as e:
            logger.error("Failed to retrieve embedding for %s: %s", record_id, e)
            return []

        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results + 1,
        )

        similar_records: list[SimilarRecord] = []
        if results["ids"] and results["ids"][0]:
            for i, rid in enumerate(results["ids"][0]):
                if rid == record_id:
                    continue

                distance = results["distances"][0][i] if results["distances"] else 0
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}

                similar_records.append(
                    SimilarRecord(
                        id=rid,
                        record=metadata,
                        distance=distance,
                        similarity=1 - distance,
                    )
                )

        return similar_records[:n_results]

    def find_patterns(
        self,
        table_name: str,
        positive_ids: list[str],
    ) -> PatternResult:
        """Analyze what records with given IDs have in common.

        Useful for questions like "what makes a good sale?"
        by providing IDs of successful sales.

        Args:
            table_name: Collection to analyze.
            positive_ids: IDs of "good" example records.

        Returns:
            PatternResult with common characteristics.
        """
        collection = self._get_collection(table_name)

        try:
            result = collection.get(
                ids=positive_ids,
                include=["metadatas"],
            )
        except Exception as e:
            logger.error("Failed to retrieve metadata for pattern analysis: %s", e)
            return PatternResult(
                common_fields={},
                frequent_values={},
                numeric_ranges={},
                sample_count=0,
            )

        if not result["metadatas"]:
            return PatternResult(
                common_fields={},
                frequent_values={},
                numeric_ranges={},
                sample_count=0,
            )

        records = result["metadatas"]
        sample_count = len(records)

        common_fields: dict[str, list] = {}
        frequent_values: dict[str, dict[str, int]] = {}
        numeric_ranges: dict[str, dict[str, float]] = {}

        all_fields: set[str] = set()
        for record in records:
            all_fields.update(record.keys())

        for field in all_fields:
            values = [r.get(field) for r in records if r.get(field) not in (None, "")]

            if not values:
                continue

            common_fields[field] = values

            numeric_values: list[float] = []
            for v in values:
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    pass

            if numeric_values and len(numeric_values) == len(values):
                numeric_ranges[field] = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "avg": sum(numeric_values) / len(numeric_values),
                }
            else:
                value_counts: dict[str, int] = {}
                for v in values:
                    str_v = str(v)
                    value_counts[str_v] = value_counts.get(str_v, 0) + 1
                frequent_values[field] = value_counts

        return PatternResult(
            common_fields=common_fields,
            frequent_values=frequent_values,
            numeric_ranges=numeric_ranges,
            sample_count=sample_count,
        )

    def delete_collection(self, table_name: str) -> bool:
        """Delete a collection and all its embeddings.

        Args:
            table_name: Collection to delete.

        Returns:
            True if deleted, False if not found.
        """
        try:
            self.client.delete_collection(name=table_name)
            return True
        except Exception as e:
            logger.error("Failed to delete collection %s: %s", table_name, e)
            return False

    def list_collections(self) -> list[str]:
        """List all collection names.

        Returns:
            List of collection name strings.
        """
        return self.client.list_collections()

    def get_collection_info(self, table_name: str) -> dict:
        """Get info about a collection.

        Args:
            table_name: Collection name.

        Returns:
            Dict with name, count, and metadata keys.
        """
        try:
            collection = self._get_collection(table_name)
            return {
                "name": table_name,
                "count": collection.count(),
                "metadata": collection.metadata,
            }
        except Exception as e:
            logger.error("Failed to get collection info for %s: %s", table_name, e)
            return {"name": table_name, "count": 0, "metadata": {}}
