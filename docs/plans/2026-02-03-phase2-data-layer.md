# Phase 2: Data Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract the memory/data layer from nebulus-prime into nebulus-core as platform-agnostic modules, create PrimeAdapter, and wire the shared CLI.

**Architecture:** Pydantic models, a NetworkX-based knowledge graph, a ChromaDB episodic memory layer (built on the existing VectorClient), and an LLM-powered consolidator that replaces hardcoded Ollama calls with the existing LLMClient. A new PrimeAdapter in nebulus-prime registers via entry points and provides all platform-specific config.

**Tech Stack:** Python 3.10+, Pydantic, NetworkX, ChromaDB (via existing VectorClient), httpx (via existing LLMClient), Click, pytest

---

## Task 1: Update PlatformAdapter Protocol

**Files:**
- Modify: `src/nebulus_core/platform/base.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_platform.py`

**Step 1: Write failing test for new protocol properties**

Add to `tests/test_platform.py`:

```python
from pathlib import Path

def test_adapter_has_default_model(mock_adapter):
    """Adapter must expose a default model name."""
    assert isinstance(mock_adapter.default_model, str)
    assert len(mock_adapter.default_model) > 0

def test_adapter_has_data_dir(mock_adapter):
    """Adapter must expose a data directory path."""
    assert isinstance(mock_adapter.data_dir, Path)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_platform.py::test_adapter_has_default_model tests/test_platform.py::test_adapter_has_data_dir -v`
Expected: FAIL with AttributeError

**Step 3: Update MockAdapter in conftest.py**

Add to `MockAdapter` class in `tests/conftest.py`:

```python
from pathlib import Path

@property
def default_model(self) -> str:
    return "test-model"

@property
def data_dir(self) -> Path:
    return Path("/tmp/test-nebulus-data")
```

**Step 4: Update PlatformAdapter protocol in base.py**

Add to `PlatformAdapter` in `src/nebulus_core/platform/base.py`:

```python
from pathlib import Path

@property
def default_model(self) -> str:
    """Default LLM model name for this platform."""
    ...

@property
def data_dir(self) -> Path:
    """Root directory for persistent data (graph, cache, etc.)."""
    ...
```

**Step 5: Run tests to verify they pass**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_platform.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/nebulus_core/platform/base.py tests/conftest.py tests/test_platform.py
git commit -m "feat: add default_model and data_dir to PlatformAdapter protocol"
```

---

## Task 2: Memory Models

**Files:**
- Create: `src/nebulus_core/memory/models.py`
- Modify: `src/nebulus_core/memory/__init__.py`
- Create: `tests/test_memory/test_models.py`

**Step 1: Write failing tests**

Create `tests/test_memory/test_models.py`:

```python
"""Tests for memory data models."""

import time

from nebulus_core.memory.models import Entity, Relation, MemoryItem, GraphStats


class TestEntity:
    def test_create_entity(self):
        e = Entity(id="server-1", type="Server")
        assert e.id == "server-1"
        assert e.type == "Server"
        assert e.properties == {}

    def test_entity_with_properties(self):
        e = Entity(id="srv", type="Server", properties={"ip": "10.0.0.1"})
        assert e.properties["ip"] == "10.0.0.1"


class TestRelation:
    def test_create_relation(self):
        r = Relation(source="a", target="b", relation="CONNECTS_TO")
        assert r.source == "a"
        assert r.target == "b"
        assert r.relation == "CONNECTS_TO"
        assert r.weight == 1.0

    def test_custom_weight(self):
        r = Relation(source="a", target="b", relation="X", weight=0.5)
        assert r.weight == 0.5


class TestMemoryItem:
    def test_defaults(self):
        m = MemoryItem(content="test content")
        assert m.content == "test content"
        assert m.archived is False
        assert m.metadata == {}
        assert len(m.id) > 0
        assert m.timestamp <= time.time()

    def test_explicit_id(self):
        m = MemoryItem(id="custom-id", content="test")
        assert m.id == "custom-id"


class TestGraphStats:
    def test_create_stats(self):
        s = GraphStats(node_count=5, edge_count=3, entity_types=["Server", "Person"])
        assert s.node_count == 5
        assert s.edge_count == 3
        assert "Server" in s.entity_types
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_memory/test_models.py -v`
Expected: FAIL with ImportError

**Step 3: Create memory models**

Create `src/nebulus_core/memory/models.py`:

```python
"""Data models for the hybrid long-term memory system.

Pydantic models for entities, relations, and memory items used in both
the knowledge graph and vector stores.
"""

import time
import uuid

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Represents a node in the knowledge graph."""

    id: str = Field(
        ..., description="Unique identifier for the entity (e.g., 'Production Server')"
    )
    type: str = Field(
        ..., description="Type of the entity (e.g., 'Server', 'Person')"
    )
    properties: dict[str, str] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Relation(BaseModel):
    """Represents an edge in the knowledge graph."""

    source: str = Field(..., description="ID of the source entity")
    target: str = Field(..., description="ID of the target entity")
    relation: str = Field(
        ..., description="Type of relationship (e.g., 'HAS_IP', 'OWNED_BY')"
    )
    weight: float = Field(1.0, description="Confidence or importance weight")


class MemoryItem(BaseModel):
    """Represents a raw memory log or fact."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str = Field(..., description="The raw text content")
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, str] = Field(default_factory=dict)
    archived: bool = Field(
        False, description="Whether this item has been consolidated"
    )


class GraphStats(BaseModel):
    """Statistics about the current state of the knowledge graph."""

    node_count: int
    edge_count: int
    entity_types: list[str]
```

Update `src/nebulus_core/memory/__init__.py`:

```python
"""Knowledge graph and memory consolidation."""

from nebulus_core.memory.models import Entity, GraphStats, MemoryItem, Relation

__all__ = ["Entity", "GraphStats", "MemoryItem", "Relation"]
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_memory/test_models.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/nebulus_core/memory/models.py src/nebulus_core/memory/__init__.py tests/test_memory/test_models.py
git commit -m "feat: add memory data models (Entity, Relation, MemoryItem, GraphStats)"
```

---

## Task 3: Graph Store

**Files:**
- Create: `src/nebulus_core/memory/graph_store.py`
- Create: `tests/test_memory/test_graph_store.py`

**Step 1: Write failing tests**

Create `tests/test_memory/test_graph_store.py`:

```python
"""Tests for the knowledge graph store."""

from pathlib import Path

import pytest

from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.models import Entity, Relation


@pytest.fixture
def graph_path(tmp_path):
    return tmp_path / "test_graph.json"


@pytest.fixture
def graph(graph_path):
    return GraphStore(storage_path=graph_path)


class TestGraphStore:
    def test_empty_graph_stats(self, graph):
        stats = graph.get_stats()
        assert stats.node_count == 0
        assert stats.edge_count == 0
        assert stats.entity_types == []

    def test_add_entity(self, graph):
        entity = Entity(id="srv-1", type="Server")
        graph.add_entity(entity)
        stats = graph.get_stats()
        assert stats.node_count == 1
        assert "Server" in stats.entity_types

    def test_add_relation(self, graph):
        graph.add_entity(Entity(id="a", type="Server"))
        graph.add_entity(Entity(id="b", type="Database"))
        graph.add_relation(
            Relation(source="a", target="b", relation="CONNECTS_TO")
        )
        stats = graph.get_stats()
        assert stats.edge_count == 1

    def test_add_relation_auto_creates_nodes(self, graph):
        graph.add_relation(
            Relation(source="x", target="y", relation="LINKS")
        )
        stats = graph.get_stats()
        assert stats.node_count == 2
        assert stats.edge_count == 1

    def test_get_neighbors(self, graph):
        graph.add_entity(Entity(id="a", type="T"))
        graph.add_entity(Entity(id="b", type="T"))
        graph.add_relation(
            Relation(source="a", target="b", relation="REL")
        )
        neighbors = graph.get_neighbors("a")
        assert len(neighbors) == 1
        assert neighbors[0] == ("REL", "b")

    def test_get_neighbors_unknown_node(self, graph):
        assert graph.get_neighbors("nonexistent") == []

    def test_persistence(self, graph_path):
        g1 = GraphStore(storage_path=graph_path)
        g1.add_entity(Entity(id="persistent", type="Test"))
        del g1

        g2 = GraphStore(storage_path=graph_path)
        stats = g2.get_stats()
        assert stats.node_count == 1

    def test_idempotent_add_entity(self, graph):
        entity = Entity(id="srv", type="Server")
        graph.add_entity(entity)
        graph.add_entity(entity)
        stats = graph.get_stats()
        assert stats.node_count == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_memory/test_graph_store.py -v`
Expected: FAIL with ImportError

**Step 3: Create graph store**

Create `src/nebulus_core/memory/graph_store.py`:

```python
"""Knowledge graph store backed by NetworkX.

Persists a directed graph to a JSON file. Used for long-term
structured knowledge extracted from episodic memories.
"""

import json
import logging
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from nebulus_core.memory.models import Entity, GraphStats, Relation

logger = logging.getLogger(__name__)


class GraphStore:
    """Directed knowledge graph with JSON file persistence.

    Args:
        storage_path: Path to the JSON file for graph persistence.
    """

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.graph = nx.DiGraph()
        self._ensure_storage_dir()
        self._load()

    def _ensure_storage_dir(self) -> None:
        """Create parent directories if they don't exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        """Load graph from JSON file if it exists."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                self.graph = json_graph.node_link_graph(
                    data, directed=True, edges="links"
                )
                logger.info(
                    "Loaded graph from %s with %d nodes.",
                    self.storage_path,
                    self.graph.number_of_nodes(),
                )
            except Exception as e:
                logger.error("Failed to load graph: %s", e)
                self.graph = nx.DiGraph()
        else:
            logger.info("No existing graph found. Initialized empty graph.")

    def _save(self) -> None:
        """Persist graph to JSON file."""
        try:
            data = json_graph.node_link_data(self.graph, edges="links")
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save graph: %s", e)

    def add_entity(self, entity: Entity) -> None:
        """Add a node to the graph. Idempotent.

        Args:
            entity: The entity to add.
        """
        self.graph.add_node(entity.id, type=entity.type, **entity.properties)
        self._save()

    def add_relation(self, relation: Relation) -> None:
        """Add a directional edge between nodes.

        Auto-creates missing source/target nodes as type 'Unknown'.

        Args:
            relation: The relation to add.
        """
        if not self.graph.has_node(relation.source):
            logger.warning(
                "Source node %s does not exist. Adding as generic entity.",
                relation.source,
            )
            self.graph.add_node(relation.source, type="Unknown")

        if not self.graph.has_node(relation.target):
            logger.warning(
                "Target node %s does not exist. Adding as generic entity.",
                relation.target,
            )
            self.graph.add_node(relation.target, type="Unknown")

        self.graph.add_edge(
            relation.source,
            relation.target,
            relation=relation.relation,
            weight=relation.weight,
        )
        self._save()

    def get_neighbors(self, node_id: str) -> list[tuple[str, str]]:
        """Get 1-hop neighbors for a node.

        Args:
            node_id: The node to query.

        Returns:
            List of (relation_type, target_node_id) tuples.
        """
        if not self.graph.has_node(node_id):
            return []

        results = []
        for neighbor in self.graph.neighbors(node_id):
            edge_data = self.graph.get_edge_data(node_id, neighbor)
            relation_type = edge_data.get("relation", "RELATED_TO")
            results.append((relation_type, neighbor))
        return results

    def get_stats(self) -> GraphStats:
        """Return current graph statistics.

        Returns:
            GraphStats with node count, edge count, and entity types.
        """
        types = set()
        for _, data in self.graph.nodes(data=True):
            if "type" in data:
                types.add(data["type"])

        return GraphStats(
            node_count=self.graph.number_of_nodes(),
            edge_count=self.graph.number_of_edges(),
            entity_types=sorted(types),
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_memory/test_graph_store.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/nebulus_core/memory/graph_store.py tests/test_memory/test_graph_store.py
git commit -m "feat: add GraphStore with NetworkX persistence"
```

---

## Task 4: Episodic Memory

**Files:**
- Create: `src/nebulus_core/vector/episodic.py`
- Modify: `src/nebulus_core/vector/__init__.py`
- Create: `tests/test_vector/test_episodic.py`

**Step 1: Write failing tests**

Create `tests/test_vector/test_episodic.py`:

```python
"""Tests for the episodic memory layer."""

from unittest.mock import MagicMock, patch

import pytest

from nebulus_core.memory.models import MemoryItem
from nebulus_core.vector.episodic import EpisodicMemory


@pytest.fixture
def mock_collection():
    collection = MagicMock()
    collection.add = MagicMock()
    collection.query = MagicMock(return_value={"documents": [["doc1", "doc2"]]})
    collection.get = MagicMock(
        return_value={
            "ids": ["id1", "id2"],
            "documents": ["content1", "content2"],
            "metadatas": [
                {"timestamp": 1.0, "archived": False},
                {"timestamp": 2.0, "archived": False},
            ],
        }
    )
    collection.update = MagicMock()
    return collection


@pytest.fixture
def mock_vector_client(mock_collection):
    client = MagicMock()
    client.get_or_create_collection.return_value = mock_collection
    return client


@pytest.fixture
def episodic(mock_vector_client):
    return EpisodicMemory(mock_vector_client)


class TestEpisodicMemory:
    def test_init_creates_collection(self, mock_vector_client):
        EpisodicMemory(mock_vector_client)
        mock_vector_client.get_or_create_collection.assert_called_once_with(
            "ltm_episodic_memory"
        )

    def test_custom_collection_name(self, mock_vector_client):
        EpisodicMemory(mock_vector_client, collection_name="custom")
        mock_vector_client.get_or_create_collection.assert_called_once_with("custom")

    def test_add_memory(self, episodic, mock_collection):
        item = MemoryItem(id="test-id", content="hello world")
        episodic.add_memory(item)
        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args[1]
        assert call_kwargs["ids"] == ["test-id"]
        assert call_kwargs["documents"] == ["hello world"]

    def test_query(self, episodic, mock_collection):
        results = episodic.query("search text", n_results=3)
        mock_collection.query.assert_called_once_with(
            query_texts=["search text"], n_results=3
        )
        assert results == ["doc1", "doc2"]

    def test_get_unarchived(self, episodic, mock_collection):
        items = episodic.get_unarchived(n_results=10)
        mock_collection.get.assert_called_once_with(
            where={"archived": False}, limit=10
        )
        assert len(items) == 2
        assert items[0].id == "id1"
        assert items[0].content == "content1"

    def test_mark_archived(self, episodic, mock_collection):
        mock_collection.get.return_value = {
            "ids": ["id1"],
            "documents": ["c"],
            "metadatas": [{"archived": False}],
        }
        episodic.mark_archived(["id1"])
        mock_collection.update.assert_called_once()
        call_kwargs = mock_collection.update.call_args[1]
        assert call_kwargs["metadatas"][0]["archived"] is True
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_vector/test_episodic.py -v`
Expected: FAIL with ImportError

**Step 3: Create episodic memory**

Create `src/nebulus_core/vector/episodic.py`:

```python
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
                    items.append(
                        MemoryItem(
                            id=_id,
                            content=results["documents"][i],
                            metadata=(
                                results["metadatas"][i]
                                if results["metadatas"]
                                else {}
                            ),
                        )
                    )
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
```

Update `src/nebulus_core/vector/__init__.py`:

```python
"""ChromaDB vector store and memory layer."""

from nebulus_core.vector.client import VectorClient
from nebulus_core.vector.episodic import EpisodicMemory

__all__ = ["EpisodicMemory", "VectorClient"]
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_vector/test_episodic.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/nebulus_core/vector/episodic.py src/nebulus_core/vector/__init__.py tests/test_vector/test_episodic.py
git commit -m "feat: add EpisodicMemory layer on top of VectorClient"
```

---

## Task 5: Consolidator

**Files:**
- Create: `src/nebulus_core/memory/consolidator.py`
- Create: `tests/test_memory/test_consolidator.py`

**Step 1: Write failing tests**

Create `tests/test_memory/test_consolidator.py`:

```python
"""Tests for the memory consolidator."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nebulus_core.memory.consolidator import Consolidator
from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.models import MemoryItem


@pytest.fixture
def graph(tmp_path):
    return GraphStore(storage_path=tmp_path / "graph.json")


@pytest.fixture
def mock_episodic():
    ep = MagicMock()
    ep.get_unarchived.return_value = [
        MemoryItem(id="m1", content="Server prod-1 has IP 10.0.0.1"),
        MemoryItem(id="m2", content="Alice owns the prod-1 server"),
    ]
    ep.mark_archived = MagicMock()
    return ep


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm_response = json.dumps(
        {
            "entities": [
                {"id": "prod-1", "type": "Server"},
                {"id": "10.0.0.1", "type": "IP"},
            ],
            "relations": [
                {
                    "source": "prod-1",
                    "target": "10.0.0.1",
                    "relation": "HAS_IP",
                }
            ],
        }
    )
    llm.chat.return_value = llm_response
    return llm


@pytest.fixture
def consolidator(mock_episodic, graph, mock_llm):
    return Consolidator(
        episodic=mock_episodic,
        graph=graph,
        llm=mock_llm,
        model="test-model",
    )


class TestConsolidator:
    def test_consolidate_processes_memories(self, consolidator, mock_episodic):
        result = consolidator.consolidate()
        assert "2" in result  # processed 2 memories
        mock_episodic.mark_archived.assert_called_once_with(["m1", "m2"])

    def test_consolidate_updates_graph(self, consolidator, graph):
        consolidator.consolidate()
        stats = graph.get_stats()
        # Each memory produces same 2 entities (idempotent adds)
        assert stats.node_count >= 2
        assert stats.edge_count >= 1

    def test_consolidate_no_memories(self, graph, mock_llm):
        ep = MagicMock()
        ep.get_unarchived.return_value = []
        c = Consolidator(episodic=ep, graph=graph, llm=mock_llm, model="m")
        result = c.consolidate()
        assert "No" in result or "0" in result

    def test_consolidate_llm_returns_invalid_json(
        self, mock_episodic, graph
    ):
        llm = MagicMock()
        llm.chat.return_value = "I cannot extract entities from this."
        c = Consolidator(
            episodic=mock_episodic, graph=graph, llm=llm, model="m"
        )
        result = c.consolidate()
        # Should not crash, just skip
        assert result is not None

    def test_consolidate_uses_llm_chat(self, consolidator, mock_llm):
        consolidator.consolidate()
        assert mock_llm.chat.call_count == 2  # once per memory
        call_kwargs = mock_llm.chat.call_args_list[0][1]
        assert call_kwargs["model"] == "test-model"
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_memory/test_consolidator.py -v`
Expected: FAIL with ImportError

**Step 3: Create consolidator**

Create `src/nebulus_core/memory/consolidator.py`:

```python
"""Memory consolidator ("sleep cycle").

Fetches unarchived episodic memories, uses the LLM to extract structured
facts (entities and relations), and updates the knowledge graph.
"""

import json
import logging

from nebulus_core.llm.client import LLMClient
from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.models import Entity, Relation
from nebulus_core.vector.episodic import EpisodicMemory

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
Analyze the following text and extract key entities and relationships.
Return ONLY a JSON object with this structure:
{{
    "entities": [{{"id": "EntityName", "type": "EntityType"}}],
    "relations": [{{"source": "EntityName", "target": "TargetEntity", "relation": "RELATION_TYPE"}}]
}}

Text: "{text}"
"""


class Consolidator:
    """Extracts structured knowledge from episodic memories.

    Args:
        episodic: EpisodicMemory instance for fetching raw memories.
        graph: GraphStore instance for persisting extracted knowledge.
        llm: LLMClient instance for LLM inference.
        model: Model name to use for extraction.
    """

    def __init__(
        self,
        episodic: EpisodicMemory,
        graph: GraphStore,
        llm: LLMClient,
        model: str,
    ) -> None:
        self.episodic = episodic
        self.graph = graph
        self.llm = llm
        self.model = model

    def consolidate(self) -> str:
        """Run the consolidation cycle.

        Returns:
            Summary string describing what was processed.
        """
        logger.info("Starting memory consolidation cycle...")

        memories = self.episodic.get_unarchived(n_results=20)
        if not memories:
            logger.info("No new memories to consolidate.")
            return "No new memories to consolidate."

        logger.info("Processing %d memory items.", len(memories))

        processed_ids: list[str] = []
        total_entities = 0
        total_relations = 0

        for memory in memories:
            try:
                facts = self._extract_facts(memory.content)
                counts = self._update_graph(facts)
                total_entities += counts[0]
                total_relations += counts[1]
                processed_ids.append(memory.id)
            except Exception as e:
                logger.error("Failed to process memory %s: %s", memory.id, e)

        if processed_ids:
            self.episodic.mark_archived(processed_ids)
            logger.info("Archived %d memory items.", len(processed_ids))

        return (
            f"Processed {len(processed_ids)} memories, "
            f"extracted {total_entities} entities and "
            f"{total_relations} relations."
        )

    def _extract_facts(self, text: str) -> dict:
        """Use the LLM to extract entities and relations from text.

        Args:
            text: Raw memory text.

        Returns:
            Dict with 'entities' and 'relations' lists.
        """
        prompt = _EXTRACTION_PROMPT.format(text=text)

        try:
            content = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
            )

            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
            else:
                logger.warning("Could not find JSON in LLM response.")
                return {"entities": [], "relations": []}
        except Exception as e:
            logger.error("LLM extraction failed: %s", e)
            return {"entities": [], "relations": []}

    def _update_graph(self, facts: dict) -> tuple[int, int]:
        """Update the graph store with extracted facts.

        Args:
            facts: Dict with 'entities' and 'relations' lists.

        Returns:
            Tuple of (entities_added, relations_added).
        """
        entity_count = 0
        relation_count = 0

        for ent in facts.get("entities", []):
            try:
                entity = Entity(
                    id=ent["id"],
                    type=ent.get("type", "Unknown"),
                    properties={},
                )
                self.graph.add_entity(entity)
                entity_count += 1
            except Exception as e:
                logger.warning("Skipping invalid entity %s: %s", ent, e)

        for rel in facts.get("relations", []):
            try:
                relation = Relation(
                    source=rel["source"],
                    target=rel["target"],
                    relation=rel["relation"],
                    weight=1.0,
                )
                self.graph.add_relation(relation)
                relation_count += 1
            except Exception as e:
                logger.warning("Skipping invalid relation %s: %s", rel, e)

        return entity_count, relation_count
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest tests/test_memory/test_consolidator.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/nebulus_core/memory/consolidator.py tests/test_memory/test_consolidator.py
git commit -m "feat: add Consolidator using LLMClient instead of Ollama"
```

---

## Task 6: Update Memory CLI Commands

**Files:**
- Modify: `src/nebulus_core/cli/commands/memory.py`

**Step 1: Update the memory status command**

The existing `memory.py` already has forward-looking imports. Update it to use the real module paths now that they exist:

Replace contents of `src/nebulus_core/cli/commands/memory.py`:

```python
"""Memory management commands."""

from pathlib import Path

import click
from rich.console import Console


@click.group("memory")
def memory_group() -> None:
    """Manage long-term memory systems."""
    pass


@memory_group.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show LTM system status and metrics."""
    console: Console = ctx.obj["console"]
    adapter = ctx.obj["adapter"]

    # Graph store status
    try:
        from nebulus_core.memory.graph_store import GraphStore

        graph_path = Path(adapter.data_dir) / "memory_graph.json"
        graph = GraphStore(storage_path=graph_path)
        stats = graph.get_stats()
        console.print(
            f"[cyan]Knowledge Graph:[/cyan] {stats.node_count} nodes, "
            f"{stats.edge_count} edges"
        )
        if stats.entity_types:
            console.print(f"  Entity types: {', '.join(stats.entity_types)}")
    except Exception as e:
        console.print(f"[yellow]Knowledge Graph:[/yellow] unavailable ({e})")

    # Vector store status
    try:
        from nebulus_core.vector.client import VectorClient

        vec = VectorClient(settings=adapter.chroma_settings)
        collections = vec.list_collections()
        console.print(
            f"[cyan]Vector Store:[/cyan] {len(collections)} collections"
        )
        for col in collections:
            console.print(f"  - {col}")
    except Exception as e:
        console.print(f"[yellow]Vector Store:[/yellow] unavailable ({e})")


@memory_group.command()
@click.pass_context
def consolidate(ctx: click.Context) -> None:
    """Trigger manual memory consolidation cycle."""
    console: Console = ctx.obj["console"]
    adapter = ctx.obj["adapter"]

    console.print("[cyan]Starting memory consolidation...[/cyan]")

    try:
        from nebulus_core.llm.client import LLMClient
        from nebulus_core.memory.consolidator import Consolidator
        from nebulus_core.memory.graph_store import GraphStore
        from nebulus_core.vector.client import VectorClient
        from nebulus_core.vector.episodic import EpisodicMemory

        vec_client = VectorClient(settings=adapter.chroma_settings)
        episodic = EpisodicMemory(vec_client)
        graph_path = Path(adapter.data_dir) / "memory_graph.json"
        graph = GraphStore(storage_path=graph_path)
        llm = LLMClient(base_url=adapter.llm_base_url)

        consolidator = Consolidator(
            episodic=episodic,
            graph=graph,
            llm=llm,
            model=adapter.default_model,
        )
        result = consolidator.consolidate()
        console.print(f"[green]Done.[/green] {result}")
    except Exception as e:
        console.print(f"[red]Consolidation failed:[/red] {e}")
```

**Step 2: Run full test suite**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add src/nebulus_core/cli/commands/memory.py
git commit -m "feat: wire memory CLI commands to real implementations"
```

---

## Task 7: Update Memory __init__ Exports

**Files:**
- Modify: `src/nebulus_core/memory/__init__.py`

**Step 1: Update exports to include all public classes**

```python
"""Knowledge graph and memory consolidation."""

from nebulus_core.memory.consolidator import Consolidator
from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.models import Entity, GraphStats, MemoryItem, Relation

__all__ = [
    "Consolidator",
    "Entity",
    "GraphStats",
    "GraphStore",
    "MemoryItem",
    "Relation",
]
```

**Step 2: Verify no import errors**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -c "from nebulus_core.memory import Consolidator, GraphStore, Entity, Relation, MemoryItem, GraphStats; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/nebulus_core/memory/__init__.py
git commit -m "chore: update memory package exports"
```

---

## Task 8: Create PrimeAdapter

**Files:**
- Create: `nebulus-prime/src/nebulus_prime/__init__.py`
- Create: `nebulus-prime/src/nebulus_prime/adapter.py`
- Modify: `nebulus-prime/pyproject.toml`
- Create: `nebulus-prime/tests/test_adapter.py`

**Note:** This task is in the nebulus-prime repo, not nebulus-core.

**Step 1: Write failing test**

Create `nebulus-prime/tests/test_adapter.py`:

```python
"""Tests for the PrimeAdapter."""

from pathlib import Path

from nebulus_core.platform.base import PlatformAdapter

from nebulus_prime.adapter import PrimeAdapter


class TestPrimeAdapter:
    def test_satisfies_protocol(self):
        adapter = PrimeAdapter()
        assert isinstance(adapter, PlatformAdapter)

    def test_platform_name(self):
        assert PrimeAdapter().platform_name == "prime"

    def test_llm_base_url(self):
        adapter = PrimeAdapter()
        assert "http" in adapter.llm_base_url

    def test_chroma_settings(self):
        adapter = PrimeAdapter()
        settings = adapter.chroma_settings
        assert settings["mode"] == "http"
        assert "host" in settings
        assert "port" in settings

    def test_default_model(self):
        adapter = PrimeAdapter()
        assert isinstance(adapter.default_model, str)
        assert len(adapter.default_model) > 0

    def test_data_dir(self):
        adapter = PrimeAdapter()
        assert isinstance(adapter.data_dir, Path)

    def test_services(self):
        adapter = PrimeAdapter()
        assert isinstance(adapter.services, list)
        assert len(adapter.services) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-prime && python -m pytest tests/test_adapter.py -v`
Expected: FAIL with ImportError

**Step 3: Create package structure**

Create `nebulus-prime/src/nebulus_prime/__init__.py`:

```python
"""Nebulus Prime - Linux platform adapter."""
```

**Step 4: Create the adapter**

Create `nebulus-prime/src/nebulus_prime/adapter.py`:

```python
"""PrimeAdapter - Linux platform adapter for the Nebulus ecosystem.

Provides platform-specific configuration for Docker Compose-based services
running TabbyAPI (LLM), ChromaDB (vectors), and Open WebUI (frontend).
"""

import os
import subprocess
from pathlib import Path

from nebulus_core.platform.base import ServiceInfo


class PrimeAdapter:
    """Linux platform adapter using Docker Compose."""

    @property
    def platform_name(self) -> str:
        """Platform identifier."""
        return "prime"

    @property
    def llm_base_url(self) -> str:
        """TabbyAPI endpoint."""
        host = os.getenv("NEBULUS_LLM_HOST", "localhost")
        port = os.getenv("NEBULUS_LLM_PORT", "5000")
        return f"http://{host}:{port}/v1"

    @property
    def chroma_settings(self) -> dict:
        """ChromaDB HTTP connection settings."""
        return {
            "mode": "http",
            "host": os.getenv("NEBULUS_CHROMA_HOST", "localhost"),
            "port": int(os.getenv("NEBULUS_CHROMA_PORT", "8001")),
        }

    @property
    def default_model(self) -> str:
        """Default LLM model name."""
        return os.getenv("NEBULUS_MODEL", "llama3.1")

    @property
    def data_dir(self) -> Path:
        """Root directory for persistent data."""
        return Path(os.getenv("NEBULUS_DATA_DIR", "data"))

    @property
    def services(self) -> list[ServiceInfo]:
        """Managed Docker Compose services."""
        return [
            ServiceInfo(
                name="tabbyapi",
                port=5000,
                health_endpoint="http://localhost:5000/v1/models",
                description="TabbyAPI LLM inference server",
            ),
            ServiceInfo(
                name="chromadb",
                port=8001,
                health_endpoint="http://localhost:8001/api/v1/heartbeat",
                description="ChromaDB vector database",
            ),
            ServiceInfo(
                name="open-webui",
                port=3000,
                health_endpoint="http://localhost:3000",
                description="Open WebUI frontend",
            ),
        ]

    def start_services(self) -> None:
        """Start services via Docker Compose."""
        subprocess.run(
            ["docker", "compose", "up", "-d"],
            check=True,
        )

    def stop_services(self) -> None:
        """Stop services via Docker Compose."""
        subprocess.run(
            ["docker", "compose", "down"],
            check=True,
        )

    def restart_services(self, service: str | None = None) -> None:
        """Restart one or all services.

        Args:
            service: Specific service name, or None for all.
        """
        cmd = ["docker", "compose", "restart"]
        if service:
            cmd.append(service)
        subprocess.run(cmd, check=True)

    def get_logs(self, service: str, follow: bool = False) -> None:
        """Stream Docker Compose logs.

        Args:
            service: Service name.
            follow: Whether to follow/tail.
        """
        cmd = ["docker", "compose", "logs"]
        if follow:
            cmd.append("-f")
        cmd.append(service)
        subprocess.run(cmd)

    def platform_specific_commands(self) -> list:
        """No extra CLI commands for now."""
        return []
```

**Step 5: Update pyproject.toml**

Add to `nebulus-prime/pyproject.toml` after the `[project.scripts]` section:

```toml
[project.entry-points."nebulus.platform"]
prime = "nebulus_prime.adapter:PrimeAdapter"
```

Also update `[tool.setuptools.packages.find]`:

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["src", "src.*", "nebulus_prime", "nebulus_prime.*"]
```

And add `nebulus-core` as a dependency in `[project] dependencies`:

```
"nebulus-core",
```

**Step 6: Run tests**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-prime && pip install -e ../nebulus-core && python -m pytest tests/test_adapter.py -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add src/nebulus_prime/__init__.py src/nebulus_prime/adapter.py pyproject.toml tests/test_adapter.py
git commit -m "feat: create PrimeAdapter with entry point registration"
```

---

## Task 9: Run Full Test Suite & Final Verification

**Step 1: Run nebulus-core full test suite**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && python -m pytest -v`
Expected: ALL PASS

**Step 2: Run nebulus-prime adapter test**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-prime && python -m pytest tests/test_adapter.py -v`
Expected: ALL PASS

**Step 3: Verify imports work end-to-end**

Run:
```bash
cd /home/jlwestsr/projects/west_ai_labs/nebulus-core
python -c "
from nebulus_core.memory import Consolidator, GraphStore, Entity, Relation, MemoryItem, GraphStats
from nebulus_core.vector import VectorClient, EpisodicMemory
from nebulus_core.llm.client import LLMClient
from nebulus_core.platform.base import PlatformAdapter
print('All imports OK')
"
```
Expected: `All imports OK`
