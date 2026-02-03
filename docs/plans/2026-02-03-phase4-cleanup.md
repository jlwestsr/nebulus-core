# Phase 4: Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate duplicated code in nebulus-prime and nebulus-edge, replacing with nebulus-core imports, and tag v0.1.0.

**Architecture:** Three repos touched in order: core (test fixtures), prime (delete duplicates, rewire MCP server), edge (create adapter, delete intelligence/, rewire API routes). Cross-repo verification before tagging.

**Tech Stack:** Python 3.10+, pytest, click, chromadb, httpx, FastAPI (edge only), nebulus-core

---

## Repo Paths

- **Core:** `/home/jlwestsr/projects/west_ai_labs/nebulus-core`
- **Prime:** `/home/jlwestsr/projects/west_ai_labs/nebulus`
- **Edge:** `/home/jlwestsr/projects/west_ai_labs/nebulus_edge`

---

### Task 1: Shared Test Fixtures — Factories

**Repo:** nebulus-core

**Files:**
- Create: `src/nebulus_core/testing/factories.py`
- Test: `tests/test_testing/test_factories.py`

**Step 1: Write the failing test**

```python
"""Tests for shared test factories."""

from nebulus_core.memory.models import Entity, MemoryItem, Relation
from nebulus_core.testing.factories import make_entity, make_memory_item, make_relation


class TestFactories:
    def test_make_entity_defaults(self):
        e = make_entity()
        assert isinstance(e, Entity)
        assert e.id
        assert e.type

    def test_make_entity_overrides(self):
        e = make_entity(id="srv-1", type="Server")
        assert e.id == "srv-1"
        assert e.type == "Server"

    def test_make_relation_defaults(self):
        r = make_relation()
        assert isinstance(r, Relation)
        assert r.source
        assert r.target
        assert r.relation

    def test_make_relation_overrides(self):
        r = make_relation(source="a", target="b", relation="LINKS")
        assert r.source == "a"
        assert r.target == "b"
        assert r.relation == "LINKS"

    def test_make_memory_item_defaults(self):
        m = make_memory_item()
        assert isinstance(m, MemoryItem)
        assert m.content
        assert m.id
        assert m.archived is False

    def test_make_memory_item_overrides(self):
        m = make_memory_item(content="custom", archived=True)
        assert m.content == "custom"
        assert m.archived is True
```

**Step 2: Run test to verify it fails**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && source venv/bin/activate && pytest tests/test_testing/test_factories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nebulus_core.testing.factories'`

**Step 3: Write minimal implementation**

```python
"""Factory functions for creating test instances of core models."""

from nebulus_core.memory.models import Entity, MemoryItem, Relation


def make_entity(**overrides) -> Entity:
    """Create an Entity with sensible defaults.

    Args:
        **overrides: Fields to override on the Entity.

    Returns:
        A valid Entity instance.
    """
    defaults = {"id": "test-entity", "type": "TestType"}
    defaults.update(overrides)
    return Entity(**defaults)


def make_relation(**overrides) -> Relation:
    """Create a Relation with sensible defaults.

    Args:
        **overrides: Fields to override on the Relation.

    Returns:
        A valid Relation instance.
    """
    defaults = {"source": "src-node", "target": "tgt-node", "relation": "TEST_REL"}
    defaults.update(overrides)
    return Relation(**defaults)


def make_memory_item(**overrides) -> MemoryItem:
    """Create a MemoryItem with sensible defaults.

    Args:
        **overrides: Fields to override on the MemoryItem.

    Returns:
        A valid MemoryItem instance.
    """
    defaults = {"content": "Test memory content"}
    defaults.update(overrides)
    return MemoryItem(**defaults)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_testing/test_factories.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/nebulus_core/testing/factories.py tests/test_testing/test_factories.py
git commit -m "feat: add shared test factories for Entity, Relation, MemoryItem"
```

---

### Task 2: Shared Test Fixtures — Mock Fixtures

**Repo:** nebulus-core

**Files:**
- Create: `src/nebulus_core/testing/fixtures.py`
- Modify: `src/nebulus_core/testing/__init__.py`
- Test: `tests/test_testing/test_fixtures.py`

**Step 1: Write the failing test**

```python
"""Tests for shared test fixtures."""

from unittest.mock import MagicMock

from nebulus_core.testing.fixtures import (
    create_mock_adapter,
    create_mock_llm_client,
    create_mock_vector_client,
)


class TestMockLLMClient:
    def test_returns_mock(self):
        mock = create_mock_llm_client()
        assert hasattr(mock, "chat")
        assert hasattr(mock, "list_models")
        assert hasattr(mock, "health_check")

    def test_chat_returns_string(self):
        mock = create_mock_llm_client()
        result = mock.chat(messages=[{"role": "user", "content": "hi"}])
        assert isinstance(result, str)

    def test_custom_chat_response(self):
        mock = create_mock_llm_client(chat_response="custom answer")
        assert mock.chat(messages=[]) == "custom answer"


class TestMockVectorClient:
    def test_returns_mock(self):
        mock = create_mock_vector_client()
        assert hasattr(mock, "get_or_create_collection")
        assert hasattr(mock, "list_collections")

    def test_collection_has_methods(self):
        mock = create_mock_vector_client()
        col = mock.get_or_create_collection("test")
        assert hasattr(col, "add")
        assert hasattr(col, "query")
        assert hasattr(col, "get")


class TestMockAdapter:
    def test_has_required_properties(self):
        mock = create_mock_adapter()
        assert mock.platform_name == "test"
        assert isinstance(mock.llm_base_url, str)
        assert isinstance(mock.chroma_settings, dict)
        assert mock.default_model
        assert mock.data_dir

    def test_custom_overrides(self):
        mock = create_mock_adapter(platform_name="custom", default_model="gpt-4")
        assert mock.platform_name == "custom"
        assert mock.default_model == "gpt-4"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_testing/test_fixtures.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

`src/nebulus_core/testing/fixtures.py`:

```python
"""Mock fixtures for testing against nebulus-core interfaces."""

from pathlib import Path
from unittest.mock import MagicMock


def create_mock_llm_client(chat_response: str = "mock LLM response") -> MagicMock:
    """Create a mock LLMClient with working chat().

    Args:
        chat_response: Default return value for chat().

    Returns:
        MagicMock with LLMClient interface.
    """
    mock = MagicMock()
    mock.chat.return_value = chat_response
    mock.list_models.return_value = []
    mock.health_check.return_value = True
    return mock


def create_mock_vector_client() -> MagicMock:
    """Create a mock VectorClient with a fake collection.

    Returns:
        MagicMock with VectorClient interface.
    """
    mock = MagicMock()
    collection = MagicMock()
    collection.add = MagicMock()
    collection.query = MagicMock(return_value={"documents": [[]]})
    collection.get = MagicMock(return_value={"ids": [], "documents": [], "metadatas": []})
    collection.update = MagicMock()
    mock.get_or_create_collection.return_value = collection
    mock.list_collections.return_value = []
    mock.heartbeat.return_value = True
    return mock


def create_mock_adapter(**overrides) -> MagicMock:
    """Create a mock PlatformAdapter with sensible defaults.

    Args:
        **overrides: Properties to override (e.g. platform_name="edge").

    Returns:
        MagicMock with PlatformAdapter interface.
    """
    defaults = {
        "platform_name": "test",
        "llm_base_url": "http://localhost:5000/v1",
        "chroma_settings": {"mode": "http", "host": "localhost", "port": 8001},
        "default_model": "test-model",
        "data_dir": Path("/tmp/test-data"),
        "services": [],
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(type(mock), key, property(lambda self, v=value: v))
    return mock
```

Update `src/nebulus_core/testing/__init__.py`:

```python
"""Shared test utilities, fixtures, and factories."""

from nebulus_core.testing.factories import make_entity, make_memory_item, make_relation
from nebulus_core.testing.fixtures import (
    create_mock_adapter,
    create_mock_llm_client,
    create_mock_vector_client,
)

__all__ = [
    "create_mock_adapter",
    "create_mock_llm_client",
    "create_mock_vector_client",
    "make_entity",
    "make_memory_item",
    "make_relation",
]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_testing/ -v`
Expected: PASS (all tests)

**Step 5: Run full suite + linters**

Run: `pytest && black --check src/ tests/ && flake8 src/ tests/`

**Step 6: Commit**

```bash
git add src/nebulus_core/testing/ tests/test_testing/
git commit -m "feat: add shared mock fixtures for LLMClient, VectorClient, PlatformAdapter"
```

---

### Task 3: Update AI_INSIGHTS.md

**Repo:** nebulus-core

**Files:**
- Modify: `docs/AI_INSIGHTS.md`

**Step 1: Update the migration status section**

Change Phase 3 from "NOT STARTED" to "COMPLETE" with details:
- 13 core modules extracted from Edge
- 3 domain templates bundled as package data
- All httpx async calls replaced with sync LLMClient
- Direct chromadb replaced with VectorClient injection
- 280 intelligence tests + 39 pre-existing = 319 total

Change Phase 4 from "NOT STARTED" to "IN PROGRESS".

Update the package layout to show populated `intelligence/` directory.

**Step 2: Commit**

```bash
git add docs/AI_INSIGHTS.md
git commit -m "docs: update AI_INSIGHTS.md with Phase 3 completion"
```

---

### Task 4: Prime — Delete Duplicated Memory Files

**Repo:** nebulus-prime

**Files:**
- Delete: `src/core/memory/models.py`
- Delete: `src/core/memory/graph_store.py`
- Delete: `src/core/memory/vector_store.py`
- Delete: `src/core/memory/consolidator.py`

**Step 1: Verify nebulus-core is installed**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus && source venv/bin/activate && pip install -e ../nebulus-core`

**Step 2: Delete the duplicated files**

```bash
cd /home/jlwestsr/projects/west_ai_labs/nebulus
rm src/core/memory/models.py
rm src/core/memory/graph_store.py
rm src/core/memory/vector_store.py
rm src/core/memory/consolidator.py
```

**Step 3: Update `src/core/memory/__init__.py`** (if it exists)

Remove any imports of the deleted modules. If this file re-exports classes, update it to import from nebulus-core instead:

```python
"""Memory module — delegates to nebulus-core shared library."""

from nebulus_core.memory.models import Entity, GraphStats, MemoryItem, Relation
from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.consolidator import Consolidator
from nebulus_core.vector.client import VectorClient
from nebulus_core.vector.episodic import EpisodicMemory
```

Or if nothing imports from `src.core.memory` as a package, just leave `__init__.py` empty.

**Step 4: Do NOT commit yet** — the tests and cli_extension still reference the old imports. Tasks 5-7 fix those.

---

### Task 5: Prime — Rewire CLI Extension

**Repo:** nebulus-prime

**Files:**
- Modify: `src/core/memory/cli_extension.py`

**Step 1: Rewrite with core imports**

The current file imports from local `.graph_store`, `.vector_store`, `.consolidator`. Replace with nebulus-core imports and wire through the adapter:

```python
"""CLI Extension for Memory Module.

Registers 'memory' commands with the main application entry point.
"""

import click
from rich.console import Console
from rich.table import Table

from nebulus_core.llm.client import LLMClient
from nebulus_core.memory.consolidator import Consolidator
from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.vector.client import VectorClient
from nebulus_core.vector.episodic import EpisodicMemory


console = Console()


def register_commands(cli_group: click.Group):
    """Register memory commands to the main CLI group."""

    @cli_group.group()
    def memory():
        """Manage Long-Term Memory (LTM)."""
        pass

    @memory.command()
    @click.pass_context
    def status(ctx):
        """Show memory system status."""
        from nebulus_core.platform.registry import get_adapter

        adapter = get_adapter()
        graph = GraphStore(storage_path=adapter.data_dir / "memory_graph.json")
        vec = VectorClient(settings=adapter.chroma_settings)

        stats = graph.get_stats()

        table = Table(title="Memory System Status")
        table.add_column("Component", style="cyan")
        table.add_column("Metric", style="magenta")
        table.add_column("Value", style="green")

        table.add_row("Graph Store", "Nodes", str(stats.node_count))
        table.add_row("Graph Store", "Edges", str(stats.edge_count))
        table.add_row(
            "Graph Store", "Entity Types", ", ".join(stats.entity_types[:5])
        )

        try:
            healthy = vec.heartbeat()
            chroma_status = "Connected" if healthy else "Offline"
            chroma_style = "green" if healthy else "red"
        except Exception:
            chroma_status = "Offline"
            chroma_style = "red"
        table.add_row(
            "Vector Store",
            "Status",
            f"[{chroma_style}]{chroma_status}[/{chroma_style}]",
        )

        console.print(table)

    @memory.command()
    @click.pass_context
    def consolidate(ctx):
        """Trigger manual memory consolidation (Sleep Cycle)."""
        from nebulus_core.platform.registry import get_adapter

        adapter = get_adapter()
        console.print(
            "[bold yellow]Starting memory consolidation...[/bold yellow]"
        )

        vec_client = VectorClient(settings=adapter.chroma_settings)
        episodic = EpisodicMemory(vec_client)
        graph = GraphStore(
            storage_path=adapter.data_dir / "memory_graph.json"
        )
        llm = LLMClient(base_url=adapter.llm_base_url)

        consolidator = Consolidator(
            episodic=episodic,
            graph=graph,
            llm=llm,
            model=adapter.default_model,
        )
        result = consolidator.consolidate()
        console.print(f"[bold green]Done.[/bold green] {result}")
```

**Note:** Check if `get_adapter` exists in `nebulus_core.platform.registry`. If not, the adapter can be passed via `click.Context` or instantiated directly. Adjust accordingly.

**Step 2: Verify syntax** — no test yet, just ensure imports resolve.

---

### Task 6: Prime — Rewire MCP Server db.py

**Repo:** nebulus-prime

**Files:**
- Modify: `src/mcp_server/db.py`

**Step 1: Replace ChromaDB instantiation with VectorClient**

The `LTMClient` class stays (it has Prime-specific conversation/message/preference logic). Only the ChromaDB connection changes.

Replace the `__init__` method:

```python
import uuid
import time
from typing import Any, Dict, List, Optional

from nebulus_core.vector.client import VectorClient


class LTMClient:
    def __init__(self, host: str = "chromadb", port: int = 8000):
        """Initialize connection to ChromaDB service via VectorClient."""
        try:
            self.vector_client = VectorClient(
                settings={"mode": "http", "host": host, "port": port}
            )
            # Initialize collections
            self.conversations = self.vector_client.get_or_create_collection(
                "conversations"
            )
            self.messages = self.vector_client.get_or_create_collection("messages")
            self.attachments = self.vector_client.get_or_create_collection(
                "attachments"
            )
            self.users = self.vector_client.get_or_create_collection("users")
        except Exception as e:
            print(f"Error initializing ChromaDB client: {e}")
            raise e
```

Remove the `import chromadb` and `from chromadb.config import Settings` lines. All other methods stay unchanged — they operate on collections which are the same ChromaDB Collection objects.

---

### Task 7: Prime — Rewire Scheduler LLM Call

**Repo:** nebulus-prime

**Files:**
- Modify: `src/mcp_server/scheduler.py`

**Step 1: Replace `generate_llm_response()` function**

Current function (lines 128-141) uses hardcoded `http://ollama:11434/api/generate`. Replace with:

```python
from nebulus_core.llm.client import LLMClient


def generate_llm_response(prompt: str) -> str:
    """Call LLM to generate text using nebulus-core LLMClient."""
    import os

    base_url = os.getenv("NEBULUS_LLM_URL", "http://localhost:5000/v1")
    model = os.getenv("NEBULUS_MODEL", "llama3.1")

    llm = LLMClient(base_url=base_url, timeout=120.0)
    try:
        return llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
        )
    finally:
        llm.close()
```

Remove `import httpx` from the top of the file (check it's not used elsewhere in the file first — it isn't, only `generate_llm_response` uses it).

---

### Task 8: Prime — Update Tests

**Repo:** nebulus-prime

**Files:**
- Modify: `tests/test_memory.py`

**Step 1: Update imports**

Replace:
```python
from src.core.memory.models import Entity, Relation, MemoryItem
from src.core.memory.graph_store import GraphStore
from src.core.memory.vector_store import VectorStore
```

With:
```python
from nebulus_core.memory.models import Entity, Relation, MemoryItem
from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.vector.client import VectorClient
```

**Step 2: Update the vector store test**

The `test_vector_store_add` test patches `src.core.memory.vector_store.chromadb.HttpClient`. This test needs rewriting since VectorStore no longer exists. Replace with a test that verifies the `VectorClient` works with mock ChromaDB:

```python
@patch("nebulus_core.vector.client.chromadb")
def test_vector_client_creates_collection(mock_chromadb):
    """Test VectorClient creates collections via ChromaDB."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chromadb.HttpClient.return_value = mock_client

    client = VectorClient(settings={"mode": "http", "host": "localhost", "port": 8001})
    col = client.get_or_create_collection("test")

    mock_client.get_or_create_collection.assert_called_once()
```

**Step 3: Run Prime tests**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus && source venv/bin/activate && pytest tests/test_memory.py -v`
Expected: PASS

**Step 4: Run full Prime test suite**

Run: `pytest`

**Step 5: Run linters**

Run: `black --check src/ tests/ nebulus_prime/ && flake8 src/ tests/ nebulus_prime/`

**Step 6: Commit all Prime changes**

```bash
git add -A
git commit -m "feat: replace duplicated memory code with nebulus-core imports

Delete local models.py, graph_store.py, vector_store.py, consolidator.py.
Rewire cli_extension to use core GraphStore, EpisodicMemory, Consolidator.
Replace chromadb.HttpClient in MCP db.py with VectorClient.
Replace hardcoded Ollama endpoint in scheduler with LLMClient."
```

---

### Task 9: Edge — Create EdgeAdapter

**Repo:** nebulus-edge

**Files:**
- Create: `nebulus_edge/__init__.py`
- Create: `nebulus_edge/adapter.py`
- Test: `tests/test_adapter.py`

**Step 1: Install nebulus-core as editable dependency**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus_edge && pip install -e ../nebulus-core`

**Step 2: Create package directory**

```bash
mkdir -p /home/jlwestsr/projects/west_ai_labs/nebulus_edge/nebulus_edge
```

**Step 3: Write the failing test**

```python
"""Tests for the Edge platform adapter."""

from pathlib import Path

from nebulus_core.platform.base import PlatformAdapter

from nebulus_edge.adapter import EdgeAdapter


class TestEdgeAdapter:
    def test_implements_protocol(self):
        adapter = EdgeAdapter()
        assert isinstance(adapter, PlatformAdapter)

    def test_platform_name(self):
        adapter = EdgeAdapter()
        assert adapter.platform_name == "edge"

    def test_llm_base_url_is_string(self):
        adapter = EdgeAdapter()
        assert isinstance(adapter.llm_base_url, str)
        assert "http" in adapter.llm_base_url

    def test_chroma_settings_embedded(self):
        adapter = EdgeAdapter()
        settings = adapter.chroma_settings
        assert settings["mode"] == "embedded"
        assert "path" in settings

    def test_default_model(self):
        adapter = EdgeAdapter()
        assert isinstance(adapter.default_model, str)

    def test_data_dir_is_path(self):
        adapter = EdgeAdapter()
        assert isinstance(adapter.data_dir, Path)
```

**Step 4: Run test to verify it fails**

Run: `pytest tests/test_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 5: Write implementation**

`nebulus_edge/__init__.py`:
```python
"""Nebulus Edge — macOS Apple Silicon platform package."""
```

`nebulus_edge/adapter.py`:
```python
"""EdgeAdapter — macOS Apple Silicon platform adapter for the Nebulus ecosystem.

Provides platform-specific configuration for bare-metal MLX inference,
embedded ChromaDB, and PM2-managed services.
"""

import os
from pathlib import Path

from nebulus_core.platform.base import ServiceInfo


class EdgeAdapter:
    """macOS Apple Silicon platform adapter using PM2."""

    @property
    def platform_name(self) -> str:
        """Platform identifier."""
        return "edge"

    @property
    def llm_base_url(self) -> str:
        """MLX server endpoint."""
        host = os.getenv("NEBULUS_LLM_HOST", "localhost")
        port = os.getenv("NEBULUS_LLM_PORT", "8080")
        return f"http://{host}:{port}/v1"

    @property
    def chroma_settings(self) -> dict:
        """ChromaDB embedded mode settings."""
        default_path = str(
            Path(__file__).parent.parent / "intelligence" / "storage" / "vectors"
        )
        return {
            "mode": "embedded",
            "path": os.getenv("NEBULUS_CHROMA_PATH", default_path),
        }

    @property
    def default_model(self) -> str:
        """Default MLX model name."""
        return os.getenv("NEBULUS_MODEL", "mlx-community/Meta-Llama-3.1-8B-Instruct")

    @property
    def data_dir(self) -> Path:
        """Root directory for persistent data."""
        return Path(
            os.getenv(
                "NEBULUS_DATA_DIR",
                str(Path(__file__).parent.parent / "intelligence" / "storage"),
            )
        )

    @property
    def services(self) -> list[ServiceInfo]:
        """Managed PM2 services."""
        return [
            ServiceInfo(
                name="brain",
                port=8080,
                health_endpoint="http://localhost:8080/v1/models",
                description="MLX LLM inference server",
            ),
            ServiceInfo(
                name="intelligence",
                port=8081,
                health_endpoint="http://localhost:8081/health",
                description="Intelligence data analysis service",
            ),
        ]

    def start_services(self) -> None:
        """Start services via PM2."""
        import subprocess

        subprocess.run(["pm2", "start", "ecosystem.config.js"], check=True)

    def stop_services(self) -> None:
        """Stop services via PM2."""
        import subprocess

        subprocess.run(["pm2", "stop", "all"], check=True)

    def restart_services(self, service: str | None = None) -> None:
        """Restart one or all services."""
        import subprocess

        cmd = ["pm2", "restart"]
        cmd.append(service if service else "all")
        subprocess.run(cmd, check=True)

    def get_logs(self, service: str, follow: bool = False) -> None:
        """Stream PM2 logs."""
        import subprocess

        cmd = ["pm2", "logs", service]
        if not follow:
            cmd.append("--nostream")
        subprocess.run(cmd)

    def platform_specific_commands(self) -> list:
        """No extra CLI commands for now."""
        return []
```

**Step 6: Run tests**

Run: `pytest tests/test_adapter.py -v`
Expected: PASS

**Step 7: Update pyproject.toml entry points**

Add to `pyproject.toml`:
```toml
[project.entry-points."nebulus.platform"]
edge = "nebulus_edge.adapter:EdgeAdapter"
```

Also add `nebulus-core` to dependencies if not present.

**Step 8: Commit**

```bash
git add nebulus_edge/ tests/test_adapter.py pyproject.toml
git commit -m "feat: create EdgeAdapter implementing PlatformAdapter protocol"
```

---

### Task 10: Edge — Delete Duplicated Intelligence Core and Templates

**Repo:** nebulus-edge

**Files:**
- Delete: `intelligence/core/audit.py`
- Delete: `intelligence/core/classifier.py`
- Delete: `intelligence/core/feedback.py`
- Delete: `intelligence/core/ingest.py`
- Delete: `intelligence/core/insights.py`
- Delete: `intelligence/core/knowledge.py`
- Delete: `intelligence/core/orchestrator.py`
- Delete: `intelligence/core/pii.py`
- Delete: `intelligence/core/refinement.py`
- Delete: `intelligence/core/scoring.py`
- Delete: `intelligence/core/security.py`
- Delete: `intelligence/core/sql_engine.py`
- Delete: `intelligence/core/vector_engine.py`
- Delete: `intelligence/templates/base.py`
- Delete: `intelligence/templates/dealership/` (entire directory)
- Delete: `intelligence/templates/medical/` (entire directory)
- Delete: `intelligence/templates/legal/` (entire directory)

**Step 1: Delete the files**

```bash
cd /home/jlwestsr/projects/west_ai_labs/nebulus_edge

# Delete core modules
rm intelligence/core/audit.py
rm intelligence/core/classifier.py
rm intelligence/core/feedback.py
rm intelligence/core/ingest.py
rm intelligence/core/insights.py
rm intelligence/core/knowledge.py
rm intelligence/core/orchestrator.py
rm intelligence/core/pii.py
rm intelligence/core/refinement.py
rm intelligence/core/scoring.py
rm intelligence/core/security.py
rm intelligence/core/sql_engine.py
rm intelligence/core/vector_engine.py

# Delete templates
rm intelligence/templates/base.py
rm -rf intelligence/templates/dealership
rm -rf intelligence/templates/medical
rm -rf intelligence/templates/legal
```

**Step 2: Update `intelligence/core/__init__.py`** to re-export from nebulus-core:

```python
"""Intelligence core — re-exports from nebulus_core.intelligence.core."""

from nebulus_core.intelligence.core import (
    AuditLogger,
    ClassificationResult,
    DataIngestor,
    FeedbackManager,
    InsightGenerator,
    IntelligenceOrchestrator,
    KnowledgeManager,
    KnowledgeRefiner,
    PIIDetector,
    PIIReport,
    PIIType,
    QueryType,
    QuestionClassifier,
    SaleScorer,
    SQLEngine,
    ValidationError,
    VectorEngine,
)
```

**Step 3: Update `intelligence/templates/__init__.py`** to re-export from nebulus-core:

```python
"""Intelligence templates — re-exports from nebulus_core.intelligence.templates."""

from nebulus_core.intelligence.templates import (
    VerticalTemplate,
    list_templates,
    load_template,
)
```

**Step 4: Do NOT commit yet** — API routes and tests need rewiring first.

---

### Task 11: Edge — Rewire API Routes

**Repo:** nebulus-edge

**Files:**
- Modify: `intelligence/api/query.py`
- Modify: `intelligence/api/data.py`
- Modify: `intelligence/api/insights.py`
- Modify: `intelligence/api/knowledge.py`
- Modify: `intelligence/api/feedback.py`
- Modify: `intelligence/api/__init__.py`

**Step 1: Update imports in all 5 route files**

In each file, replace `from intelligence.core.` with `from nebulus_core.intelligence.core.` and `from intelligence.templates` with `from nebulus_core.intelligence.templates`.

Example for `query.py`:
```python
# Before
from intelligence.core.knowledge import KnowledgeManager
from intelligence.core.orchestrator import IntelligenceOrchestrator
from intelligence.core.scoring import SaleScorer
from intelligence.core.sql_engine import SQLEngine, UnsafeQueryError
from intelligence.core.vector_engine import VectorEngine
from intelligence.templates import load_template

# After
from nebulus_core.intelligence.core.knowledge import KnowledgeManager
from nebulus_core.intelligence.core.orchestrator import IntelligenceOrchestrator
from nebulus_core.intelligence.core.scoring import SaleScorer
from nebulus_core.intelligence.core.sql_engine import SQLEngine
from nebulus_core.intelligence.core.security import ValidationError
from nebulus_core.intelligence.core.vector_engine import VectorEngine
from nebulus_core.intelligence.templates import load_template
```

Apply the same pattern to `data.py`, `insights.py`, `knowledge.py`, `feedback.py`.

**Step 2: Check for async/await issues**

The original Edge modules were async. Core versions are sync. Search each route file for `await` calls to intelligence core methods and remove the `await` keyword. FastAPI route handlers can be sync or async — if a route only calls sync functions, make the handler `def` instead of `async def`.

**Step 3: Update `intelligence/api/__init__.py`** if needed (imports should still work since the route modules themselves are in the same location).

**Step 4: Check `intelligence/server.py`**

The server stores `brain_url` in `app.state`. Routes currently construct objects like `IntelligenceOrchestrator(brain_url=request.app.state.brain_url, ...)`. Core's orchestrator takes `llm: LLMClient` instead. Update server.py to:

1. Import `LLMClient` and `VectorClient` from core
2. In the lifespan, construct and store shared instances:

```python
from nebulus_core.llm.client import LLMClient
from nebulus_core.vector.client import VectorClient

# In lifespan:
app.state.llm = LLMClient(base_url=BRAIN_URL)
app.state.vector_client = VectorClient(
    settings={"mode": "embedded", "path": str(VECTOR_PATH)}
)
```

3. Update route handlers to use `request.app.state.llm` and `request.app.state.vector_client` when constructing core objects.

---

### Task 12: Edge — Rewire Tests

**Repo:** nebulus-edge

**Files:**
- Modify: All 10 files in `tests/intelligence/`

**Step 1: Update imports in all test files**

Replace `from intelligence.core.` with `from nebulus_core.intelligence.core.` and `from intelligence.templates` with `from nebulus_core.intelligence.templates` in each test file.

The test logic should remain the same — only import paths change.

**Step 2: Run Edge tests**

Run: `pytest tests/intelligence/ -v`
Expected: PASS

**Step 3: Run full Edge test suite**

Run: `pytest`

**Step 4: Run linters**

Run: `black --check intelligence/ tests/ nebulus_edge/ && flake8 intelligence/ tests/ nebulus_edge/`

**Step 5: Commit all Edge changes**

```bash
git add -A
git commit -m "feat: replace duplicated intelligence code with nebulus-core imports

Create EdgeAdapter implementing PlatformAdapter protocol.
Delete 13 core modules and 3 template directories (now in nebulus-core).
Rewire API routes and tests to import from nebulus_core.intelligence.
Replace direct httpx/chromadb usage with LLMClient/VectorClient."
```

---

### Task 13: Cross-Repo Verification

**Step 1: Run core tests**

```bash
cd /home/jlwestsr/projects/west_ai_labs/nebulus-core
source venv/bin/activate
pytest && black --check src/ tests/ && flake8 src/ tests/
```
Expected: 325+ tests pass (319 + new testing tests), linters clean.

**Step 2: Run Prime tests**

```bash
cd /home/jlwestsr/projects/west_ai_labs/nebulus
source venv/bin/activate
pip install -e ../nebulus-core
pytest
```
Expected: All Prime tests pass.

**Step 3: Run Edge tests**

```bash
cd /home/jlwestsr/projects/west_ai_labs/nebulus_edge
source venv/bin/activate
pip install -e ../nebulus-core
pytest
```
Expected: All Edge tests pass.

---

### Task 14: Update Ecosystem CLAUDE.md

**Repo:** nebulus-core (or parent)

**Files:**
- Modify: `/home/jlwestsr/projects/west_ai_labs/CLAUDE.md`

**Step 1: Update migration phases table**

| Phase | Scope | Status |
|-------|-------|--------|
| 1. Foundation | CLI framework, platform detection, adapter protocol, LLM client | Done |
| 2. Data Layer | ChromaDB LTM, episodic memory, knowledge graph, document indexing | Done |
| 3. Intelligence | Data ingestion, PII, knowledge mgmt, feedback, domain templates | Done |
| 4. Cleanup | Replace hardcoded calls, remove duplicated code, tag v0.1.0 | Done |

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update ecosystem CLAUDE.md — all phases complete"
```

---

### Task 15: Tag v0.1.0

**Repo:** nebulus-core

**Step 1: Verify version in pyproject.toml and __init__.py**

Both should already say `0.1.0`.

**Step 2: Create annotated tag**

```bash
cd /home/jlwestsr/projects/west_ai_labs/nebulus-core
git tag -a v0.1.0 -m "v0.1.0: First release of nebulus-core

Includes:
- CLI framework with platform auto-detection
- PlatformAdapter protocol + entry-point discovery
- LLMClient (OpenAI-compatible HTTP)
- VectorClient (ChromaDB HTTP + embedded)
- EpisodicMemory + GraphStore + Consolidator
- Intelligence layer: 13 core modules + 3 domain templates
- Shared test fixtures and factories"
```

**Step 3: Ask user before pushing tag**

Do NOT push without explicit approval.
