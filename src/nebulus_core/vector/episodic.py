"""Episodic memory layer built on VectorClient.

Stores and retrieves raw memory items using ChromaDB vector search.
Supports archiving memories after consolidation into the knowledge graph.
"""

import logging

from nebulus_core.memory.models import MemoryItem
from nebulus_core.vector.client import VectorClient

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """ChromaDB-backed episodic memory store.

    Args:
        vector_client: A configured VectorClient instance.
        collection_name: ChromaDB collection name for episodic memories.
    """

    def __init__(
        self,
        vector_client: VectorClient,
        collection_name: str = "ltm_episodic_memory",
    ) -> None:
        self.client = vector_client
        self.collection = vector_client.get_or_create_collection(collection_name)

    def add_memory(self, item: MemoryItem) -> None:
        """Add a memory item to the vector store.

        Args:
            item: The memory item to store.
        """
        try:
            metadata: dict = {
                "timestamp": item.timestamp,
                "archived": item.archived,
            }
            metadata.update(item.metadata)

            self.collection.add(
                documents=[item.content],
                metadatas=[metadata],
                ids=[item.id],
            )
            logger.debug("Added memory item %s to vector store.", item.id)
        except Exception as e:
            logger.error("Error adding memory to ChromaDB: %s", e)

    def query(self, query_text: str, n_results: int = 5) -> list[str]:
        """Perform semantic search over episodic memories.

        Args:
            query_text: The text to search for.
            n_results: Maximum number of results.

        Returns:
            List of matching document strings.
        """
        try:
            results = self.collection.query(
                query_texts=[query_text], n_results=n_results
            )
            docs: list[str] = []
            if results and results["documents"]:
                for doc_list in results["documents"]:
                    docs.extend(doc_list)
            return docs
        except Exception as e:
            logger.error("Error querying ChromaDB: %s", e)
            return []

    def get_unarchived(self, n_results: int = 20) -> list[MemoryItem]:
        """Retrieve unarchived memories for consolidation.

        Args:
            n_results: Maximum number of items to retrieve.

        Returns:
            List of unarchived MemoryItem instances.
        """
        try:
            results = self.collection.get(
                where={"archived": False}, limit=n_results
            )
            items: list[MemoryItem] = []
            if results["ids"]:
                for i, _id in enumerate(results["ids"]):
                    raw_meta = (
                        results["metadatas"][i]
                        if results["metadatas"]
                        else {}
                    )
                    # Extract known fields from ChromaDB metadata
                    timestamp = raw_meta.pop("timestamp", None)
                    archived = raw_meta.pop("archived", False)
                    # Only keep string-valued entries for MemoryItem.metadata
                    extra: dict[str, str] = {
                        k: v for k, v in raw_meta.items() if isinstance(v, str)
                    }
                    item_kwargs: dict = {
                        "id": _id,
                        "content": results["documents"][i],
                        "archived": bool(archived),
                        "metadata": extra,
                    }
                    if timestamp is not None:
                        item_kwargs["timestamp"] = float(timestamp)
                    items.append(MemoryItem(**item_kwargs))
            return items
        except Exception as e:
            logger.error("Error fetching unarchived memories: %s", e)
            return []

    def mark_archived(self, memory_ids: list[str]) -> None:
        """Mark memories as archived after consolidation.

        Args:
            memory_ids: List of memory IDs to archive.
        """
        try:
            for mid in memory_ids:
                existing = self.collection.get(ids=[mid])
                if existing["ids"]:
                    meta = existing["metadatas"][0]
                    meta["archived"] = True
                    self.collection.update(ids=[mid], metadatas=[meta])
        except Exception as e:
            logger.error("Error marking memories as archived: %s", e)
