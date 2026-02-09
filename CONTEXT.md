# CONTEXT.md — Nebulus Core

> **Audience:** AI agents (Claude, Gemini, Copilot) working on the Nebulus Core codebase.
> For operational guardrails, see [AI_DIRECTIVES.md](AI_DIRECTIVES.md). For git workflow, see [WORKFLOW.md](WORKFLOW.md).

## Project Identity

Nebulus Core (`v0.1.0`) is the shared Python library that all Nebulus ecosystem projects depend on. It owns the platform adapter protocol, CLI framework, LLM client, ChromaDB wrapper, knowledge graph, memory consolidation, and the intelligence layer (13 engine modules + 3 domain templates). Platform projects — Prime (Linux/Docker/NVIDIA) and Edge (macOS/MLX/Apple Silicon) — install this package and register adapters via Python entry points.

**Invariants:**

- Platform-agnostic: never import `docker`, `ansible`, `mlx`, `ollama`, or similar
- Adapter injection: all platform behavior flows through the `PlatformAdapter` protocol
- Dual ChromaDB: HTTP mode for Prime (Docker), embedded mode for Edge (local files)
- All LLM calls go through `LLMClient` — never call inference engines directly
- Constructor injection everywhere: no hidden globals, no module-level singletons

## Module Deep Dive

### PlatformAdapter Lifecycle

The adapter protocol (`src/nebulus_core/platform/base.py`) is the most critical integration point. It uses Python's `typing.Protocol` with `@runtime_checkable` for structural subtyping — platform projects don't need to inherit from a base class, just satisfy the interface.

**Discovery flow:**

1. Platform project defines a concrete adapter class implementing the `PlatformAdapter` protocol
2. Registers it via `pyproject.toml` entry point under `"nebulus.platform"`:
   ```toml
   [project.entry-points."nebulus.platform"]
   prime = "nebulus_prime.adapter:PrimeAdapter"
   ```
3. At CLI startup, `registry.py` calls `importlib.metadata.entry_points(group="nebulus.platform")` to discover available adapters
4. `detection.py` runs OS/hardware checks (Linux vs macOS ARM) to select the matching adapter
5. The adapter instance is stored in the Click context (`ctx.obj["adapter"]`) and threaded through all commands

**Protocol surface (6 properties + 4 methods):**

| Member | Type | Purpose |
|--------|------|---------|
| `platform_name` | `str` | Identifier (`"prime"`, `"edge"`) |
| `services` | `list[ServiceInfo]` | Managed services with ports and health endpoints |
| `llm_base_url` | `str` | OpenAI-compatible inference endpoint URL |
| `chroma_settings` | `dict` | `{"mode": "http", "host": ..., "port": ...}` or `{"mode": "embedded", "path": ...}` |
| `default_model` | `str` | Default LLM model name |
| `data_dir` | `Path` | Root for persistent data (graph JSON, cache) |
| `start_services()` | `-> None` | Start all platform services |
| `stop_services()` | `-> None` | Stop all platform services |
| `restart_services(service)` | `-> None` | Restart one or all services |
| `get_logs(service, follow)` | `-> None` | Stream service logs |
| `platform_specific_commands()` | `-> list` | Additional Click commands injected into the CLI |

`ServiceInfo` is a Pydantic model with: `name`, `port`, `health_endpoint`, `description`.

### Intelligence Orchestrator

The `IntelligenceOrchestrator` (`src/nebulus_core/intelligence/core/orchestrator.py`) is the main entry point for all questions to the intelligence system. It coordinates 13 engine modules through a classify → gather → synthesize pipeline.

**Query flow:**

```
User question
    │
    ▼
QuestionClassifier
    │  classify(question, schema) → ClassificationResult
    │  QueryType: SQL_ONLY | SEMANTIC_ONLY | STRATEGIC | HYBRID
    ▼
Context Gathering (parallel where possible)
    ├── SQLEngine.natural_to_sql() → execute() → rows
    ├── VectorEngine.search_similar() → semantic matches
    └── KnowledgeManager.export_for_prompt() → domain rules
    │
    ▼
LLM Synthesis
    │  SYNTHESIS_PROMPT (data-driven) or STRATEGIC_PROMPT (strategic)
    │  LLMClient.chat() → final answer
    ▼
IntelligenceResponse
    answer, supporting_data, reasoning, sql_used, similar_records,
    classification, confidence
```

**All dependencies are injected via constructor:** `classifier`, `sql_engine`, `vector_engine`, `knowledge`, `llm`, `model`. No engine instantiates its own dependencies.

### Domain Templates

Vertical templates in `intelligence/templates/` configure the intelligence layer for specific industries:

- **`dealership/`** — Auto dealership analytics (inventory scoring, sales metrics)
- **`medical/`** — Healthcare data analysis
- **`legal/`** — Legal document and case analysis

Each template contains a `config.yaml` with scoring factors, business rules, key metrics, and canned queries. The `VerticalTemplate` base class (`templates/base.py`) loads and validates these configs. Template name is passed to `orchestrator.ask()` to activate domain-specific prompting in strategic queries.

## Data Flow

### Ingestion → Query → Response

```
CSV files
    │  DataIngestor
    ▼
SQLite (schema-inferred tables)    ChromaDB collections
    │  SQLEngine                        │  VectorEngine
    │  natural_to_sql() + execute()     │  search_similar()
    └──────────────┬────────────────────┘
                   ▼
          IntelligenceOrchestrator._gather_context()
                   │
                   ▼  LLMClient.chat()
          IntelligenceOrchestrator._synthesize()
                   │
                   ▼
          IntelligenceResponse
```

### Episodic Memory → Knowledge Graph (Consolidation)

```
Events / conversations
    │  EpisodicMemory.add_memory()
    ▼
ChromaDB (ltm_episodic_memory collection)
    │  Consolidator.consolidate()
    │  1. Fetch unarchived memories (limit 20)
    │  2. LLM extracts entities + relations as JSON
    │  3. Parse with robust brace-matching fallback
    ▼
GraphStore (NetworkX DiGraph → JSON file)
    │  add_entity(), add_relation()
    │  persists on every write
    ▼
Knowledge graph available for querying
    get_neighbors(), get_stats()
```

## Key Design Patterns

### Structural Typing (Protocol)

The `PlatformAdapter` uses `typing.Protocol` rather than ABC inheritance. This means platform projects satisfy the interface through structural subtyping — they just need to implement the right methods and properties. The `@runtime_checkable` decorator allows `isinstance()` checks at runtime.

### Constructor Injection

Every module receives its dependencies via constructor arguments. `LLMClient`, `VectorClient`, `PlatformAdapter`, and all intelligence engines are passed in, never instantiated internally. This makes every module independently testable with mock dependencies.

### Pydantic Models

All data contracts use Pydantic v2 models:

- `ServiceInfo` — platform service descriptor
- `Entity`, `Relation` — knowledge graph nodes and edges
- `MemoryItem` — episodic memory unit
- `GraphStats` — graph summary metrics

Pydantic provides validation, serialization, and clear schema documentation.

### CLI Lazy Imports

Commands in `src/nebulus_core/cli/commands/` use function-level imports to avoid pulling heavy dependencies (`chromadb`, `networkx`, `pandas`) at CLI startup. The CLI stays responsive even when optional packages take time to initialize.

### Dual ChromaDB Mode

The `VectorClient` constructor branches on `chroma_settings["mode"]`:

- `"http"` → `chromadb.HttpClient(host=..., port=...)` for containerized deployments
- `"embedded"` → `chromadb.PersistentClient(path=...)` for local file storage

This is the only point in the codebase where ChromaDB connection mode is decided. All downstream code works with the same `chromadb.Collection` interface.

## Testing Strategy

**372 tests**, all passing. Located in `tests/` with the structure mirroring `src/nebulus_core/`.

### Test Infrastructure

- **Fixtures** (`nebulus_core.testing.fixtures`): `create_mock_llm_client()`, `create_mock_vector_client()`, `create_mock_adapter()` — pre-configured mocks for all external integration points
- **Factories** (`nebulus_core.testing.factories`): `make_entity()`, `make_relation()`, `make_memory_item()` — factory functions with sensible defaults and `**overrides`
- **CLI tests**: Use `click.testing.CliRunner` with a mock adapter injected into the Click context
- **Graph tests**: Use pytest `tmp_path` fixtures for isolated JSON persistence

### Testing Principles

- **No live services**: All external dependencies (ChromaDB, LLM servers) are mocked
- **Type hints on all test functions** (including return types)
- **Google-style docstrings on all test functions**
- **Silent exception handlers** all have logging enabled (added in cleanup phase 3)
- **Metadata mutation safety**: Tests verify that ChromaDB metadata dicts are copied before `.pop()` operations

### Running Tests

```bash
source venv/bin/activate
pytest                        # 372 tests
black --check src/ tests/     # formatting
flake8 src/ tests/            # linting
```

## Known Constraints

| Constraint | Detail | Impact |
|------------|--------|--------|
| ChromaDB metadata | Values must be `str`, `int`, `float`, or `bool` — no nested dicts or lists | Flatten metadata before storing |
| NetworkX serialization | All node/edge attributes must be JSON-serializable | Avoid complex objects in graph properties |
| Graph persistence | Persists on every write (no batching) | Acceptable at current scale; may need batching later |
| Consolidator JSON parsing | LLM output may contain malformed JSON | Uses `find("{")` / `rfind("}")` brace-matching fallback |
| Editable installs | Can go stale after branch switches | Reinstall with `pip install -e .` after checkout |
| EpisodicMemory archival | `mark_archived()` makes N+1 ChromaDB calls | Acceptable for MVP batch sizes (limit 20) |
| Sync-only LLM client | `LLMClient.chat()` is synchronous (httpx, not async) | No async/await in the intelligence layer |

## File Quick Reference

| Path | What It Is |
|------|-----------|
| `src/nebulus_core/platform/base.py` | PlatformAdapter protocol + ServiceInfo model |
| `src/nebulus_core/platform/detection.py` | OS/hardware auto-detection logic |
| `src/nebulus_core/platform/registry.py` | Entry point discovery and adapter loading |
| `src/nebulus_core/cli/main.py` | CLI entry point with platform auto-detection |
| `src/nebulus_core/cli/output.py` | Rich console formatting helpers |
| `src/nebulus_core/llm/client.py` | OpenAI-compatible HTTP client |
| `src/nebulus_core/vector/client.py` | ChromaDB dual-mode wrapper |
| `src/nebulus_core/vector/episodic.py` | Episodic memory with archival lifecycle |
| `src/nebulus_core/memory/models.py` | Entity, Relation, MemoryItem, GraphStats |
| `src/nebulus_core/memory/graph_store.py` | NetworkX knowledge graph (JSON persistence) |
| `src/nebulus_core/memory/consolidator.py` | LLM-powered memory consolidation |
| `src/nebulus_core/intelligence/core/orchestrator.py` | Main query orchestration pipeline |
| `src/nebulus_core/intelligence/core/classifier.py` | Question classification (SQL, semantic, strategic) |
| `src/nebulus_core/intelligence/core/sql_engine.py` | Natural language to SQL |
| `src/nebulus_core/intelligence/core/vector_engine.py` | Semantic search over ChromaDB |
| `src/nebulus_core/intelligence/core/ingest.py` | CSV to SQLite data ingestion |
| `src/nebulus_core/intelligence/core/pii.py` | PII detection and masking |
| `src/nebulus_core/intelligence/templates/base.py` | VerticalTemplate base class |
| `src/nebulus_core/testing/fixtures.py` | Mock fixtures for LLM, Vector, Adapter |
| `src/nebulus_core/testing/factories.py` | Test data factories |

## Resources

- [CLAUDE.md](CLAUDE.md) — Project instructions for AI agents
- [AI_DIRECTIVES.md](AI_DIRECTIVES.md) — Agent role, guardrails, coding style
- [WORKFLOW.md](WORKFLOW.md) — Git branching, commit, and verification workflow
- [docs/AI_INSIGHTS.md](docs/AI_INSIGHTS.md) — Long-term session memory and recurring pitfalls
- [docs/plans/](docs/plans/) — Implementation plans (date-prefixed)
