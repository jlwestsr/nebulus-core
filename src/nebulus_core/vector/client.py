"""ChromaDB client wrapper supporting HTTP and embedded modes."""

import chromadb


class VectorClient:
    """Unified ChromaDB client.

    Supports both HTTP mode (for containerized ChromaDB) and embedded
    mode (for in-process ChromaDB on a single machine).

    Args:
        settings: Connection configuration dict.
            HTTP mode: {"mode": "http", "host": str, "port": int}
            Embedded mode: {"mode": "embedded", "path": str}
    """

    def __init__(self, settings: dict) -> None:
        mode = settings.get("mode", "http")
        if mode == "embedded":
            if "path" not in settings:
                raise ValueError(
                    "Embedded mode requires 'path' in settings. "
                    "Example: {'mode': 'embedded', 'path': '/data/vectors'}"
                )
            self.client = chromadb.PersistentClient(
                path=settings["path"],
            )
        elif mode == "http":
            if "host" not in settings or "port" not in settings:
                raise ValueError(
                    "HTTP mode requires 'host' and 'port' in settings. "
                    "Example: {'mode': 'http', 'host': 'localhost', 'port': 8001}"
                )
            self.client = chromadb.HttpClient(
                host=settings["host"],
                port=settings["port"],
            )
        else:
            raise ValueError(
                f"Unknown VectorClient mode: '{mode}'. "
                "Supported modes: 'http', 'embedded'."
            )

    def get_or_create_collection(
        self,
        name: str,
        metadata: dict | None = None,
    ) -> chromadb.Collection:
        """Get an existing collection or create a new one.

        Args:
            name: Collection name.
            metadata: Optional collection metadata (e.g. HNSW settings).

        Returns:
            ChromaDB Collection instance.
        """
        kwargs: dict = {"name": name}
        if metadata is not None:
            kwargs["metadata"] = metadata
        return self.client.get_or_create_collection(**kwargs)

    def list_collections(self) -> list[str]:
        """List all collection names.

        Returns:
            List of collection name strings.
        """
        collections = self.client.list_collections()
        return [c.name for c in collections]

    def delete_collection(self, name: str) -> None:
        """Delete a collection by name.

        Args:
            name: Collection name to delete.
        """
        self.client.delete_collection(name=name)

    def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Add documents to a collection (creates collection if needed).

        Args:
            collection_name: Target collection name.
            ids: Document IDs.
            documents: Document texts.
            metadatas: Optional metadata dicts per document.
        """
        collection = self.get_or_create_collection(collection_name)
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas or [{}] * len(ids),
        )

    def search(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Semantic search in a collection.

        Args:
            collection_name: Collection to search.
            query: Query text.
            n_results: Maximum number of results.
            where: Optional ChromaDB where filter.

        Returns:
            ChromaDB query result dict with ids, documents, distances, metadatas.
        """
        collection = self.get_or_create_collection(collection_name)
        kwargs: dict = {"query_texts": [query], "n_results": n_results}
        if where is not None:
            kwargs["where"] = where
        return collection.query(**kwargs)

    def delete_documents(self, collection_name: str, ids: list[str]) -> None:
        """Delete documents by ID from a collection.

        Args:
            collection_name: Collection containing the documents.
            ids: Document IDs to delete.
        """
        collection = self.get_or_create_collection(collection_name)
        collection.delete(ids=ids)

    def heartbeat(self) -> bool:
        """Check if ChromaDB is reachable.

        Returns:
            True if ChromaDB responds, False otherwise.
        """
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False
