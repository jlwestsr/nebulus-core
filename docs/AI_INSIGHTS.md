# Project AI Insights (Long-Term Memory)

## Purpose

This document captures project-specific behavioral nuances, recurring pitfalls, and
architectural decisions for AI agent continuity. It is not documentation — it is
institutional knowledge that prevents repeated mistakes. Update this file whenever
you encounter a new pitfall or architectural constraint during development.

## 1. Architectural Patterns

### Package Layout

```text
src/nebulus_core/
├── cli/              # Click CLI framework + commands
│   └── commands/     # Service, model, memory command groups
├── platform/         # Adapter protocol, detection, registry
├── llm/              # OpenAI-compatible HTTP client
├── vector/           # ChromaDB client + episodic memory layer
├── memory/           # Models, graph store, consolidator
├── intelligence/     # Data ingestion, analysis, knowledge management
│   ├── core/         # 13 engine modules (classifier, orchestrator, etc.)
│   └── templates/    # Vertical templates (dealership, medical, legal)
└── testing/          # Shared test fixtures and factories
```

### Platform Adapter Protocol

The `PlatformAdapter` protocol in `platform/base.py` is the central integration
point. Platform projects (Prime, Edge) implement this protocol and register via
entry points. Core code accesses all platform-specific config through the adapter.

Required properties: `platform_name`, `services`, `llm_base_url`, `chroma_settings`,
`default_model`, `data_dir`.

Required methods: `start_services()`, `stop_services()`, `restart_services()`,
`get_logs()`, `platform_specific_commands()`.

### ChromaDB Dual Mode

`VectorClient` supports both connection patterns:

- **HTTP mode** (Prime): `{"mode": "http", "host": "localhost", "port": 8001}`
- **Embedded mode** (Edge): `{"mode": "embedded", "path": "intelligence/storage/vectors"}`

The adapter provides `chroma_settings` — core never decides the connection mode.

### Dual Memory Architecture

The LTM system uses two parallel stores:

- **EpisodicMemory** (ChromaDB via VectorClient): Semantic search over raw memories.
  Default collection: `ltm_episodic_memory`.
- **GraphStore** (NetworkX → JSON): Knowledge graph for entity relationships.
  Storage path provided by adapter via `data_dir`.
- **Consolidator**: "Sleep cycle" that reads unarchived episodic memories, calls
  the LLM to extract entities/relations, writes them to the graph, and archives
  the processed memories.

### Non-Obvious Decisions

- Graph store persists to disk on every write (add_entity, add_relation). No batching.
  This is intentional for durability but means bulk imports are slow.
- The `Consolidator` takes all dependencies as constructor args (episodic, graph, llm,
  model). No hidden env vars. The CLI commands wire everything together.
- `EpisodicMemory.mark_archived()` makes N+1 ChromaDB calls (one get + one update
  per memory). Acceptable for MVP; bulk API would be a future optimization.
- CLI commands use lazy imports inside the command functions to avoid pulling in
  ChromaDB/NetworkX at CLI startup time.

### Git Branching (Critical)

- **NEVER commit directly to `main`.** This was a mistake in early phases.
- All work goes on feature branches (`feat/`, `fix/`, `docs/`, `chore/`).
- Branches merge into `develop`. `main` is for releases only.
- Always create the branch before starting work, not after.

## 2. Recurring Pitfalls

### Dependency Management

- **ChromaDB metadata type constraint**: ChromaDB only accepts primitive types
  (str, int, float, bool) in metadata fields. Complex types must be stringified.
  The `EpisodicMemory.get_unarchived()` method filters metadata to extract
  `timestamp` and `archived` into their proper MemoryItem fields.
- **NetworkX JSON serialization**: `node_link_data`/`node_link_graph` with
  `edges="links"` requires NetworkX 3.2+. The `edges` parameter name changed
  across versions.

### Testing Gotchas

- **No live services in tests**: All tests use mocks or temp files. ChromaDB is
  never started. LLM calls are mocked. GraphStore uses `tmp_path` fixtures.
- **Use project venv**: Tests must run with `./venv/bin/python -m pytest` or
  after `source venv/bin/activate`. The system Python may not have dependencies.
- **MockAdapter in conftest.py**: All CLI tests depend on the `MockAdapter` fixture.
  When adding new properties to `PlatformAdapter`, update `MockAdapter` too or
  protocol conformance tests will fail.

### Cross-Repo Coordination

- **Protocol changes require adapter updates**: Adding a property to
  `PlatformAdapter` means updating PrimeAdapter and EdgeAdapter. Always check
  both platform repos after modifying the protocol.
- **Editable installs can go stale**: If you change `pyproject.toml` entry points
  or package structure, re-run `pip install -e .` in consuming projects.

## 3. Migration Status

### Phase 1: Foundation — COMPLETE

- CLI framework, platform detection, adapter protocol
- LLMClient (OpenAI-compatible HTTP)
- VectorClient (ChromaDB HTTP + embedded)

### Phase 2: Data Layer — COMPLETE

- Memory models (Entity, Relation, MemoryItem, GraphStats)
- GraphStore (NetworkX + JSON persistence)
- EpisodicMemory (built on VectorClient)
- Consolidator (LLMClient replaces Ollama)
- PrimeAdapter created in nebulus-prime
- Memory CLI commands wired to real implementations

### Phase 3: Intelligence — COMPLETE

- 13 core modules extracted from Edge into `nebulus_core.intelligence.core`
- All `httpx` async Brain calls replaced with sync `LLMClient.chat()`
- Direct `chromadb.PersistentClient` replaced with `VectorClient` injection
- 3 domain templates (dealership, medical, legal) bundled as package data via `importlib.resources`
- All modules use constructor dependency injection (db_path, llm, vector_client)
- 280 intelligence tests + 39 pre-existing = 319 total tests

### Phase 4: Cleanup — IN PROGRESS

- Shared test fixtures and factories in `nebulus_core.testing`
- Replace duplicated code in nebulus-prime with nebulus-core imports
- Replace duplicated code in nebulus-edge with nebulus-core imports
- Create EdgeAdapter
- Tag v0.1.0
