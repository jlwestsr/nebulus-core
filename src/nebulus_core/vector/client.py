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
            self.client = chromadb.PersistentClient(
                path=settings["path"],
            )
        else:
            self.client = chromadb.HttpClient(
                host=settings.get("host", "localhost"),
                port=settings.get("port", 8001),
            )

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Get an existing collection or create a new one.

        Args:
            name: Collection name.

        Returns:
            ChromaDB Collection instance.
        """
        return self.client.get_or_create_collection(name=name)

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
