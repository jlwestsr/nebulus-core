# Nebulus Core

**Shared Python library for the Nebulus AI ecosystem.**

Nebulus Core is the platform-agnostic backbone of the Nebulus stack. It provides the CLI framework, LLM client, vector storage, knowledge graph, memory consolidation, and a full intelligence layer with domain templates. Platform projects — [Nebulus Prime](https://github.com/jlwestsr/nebulus-prime) (Linux) and [Nebulus Edge](https://github.com/jlwestsr/nebulus-edge) (macOS) — install this library and inject platform-specific behavior through the adapter protocol.

**Core principle:** No Docker, no MLX, no Ollama. All platform behavior is injected through adapters.

> A [West AI Labs](https://github.com/jlwestsr) system.

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| CLI | Click + Rich | Command framework and formatted terminal output |
| LLM | httpx | OpenAI-compatible HTTP client |
| Vectors | ChromaDB | Dual-mode vector storage (HTTP and embedded) |
| Graph | NetworkX | Knowledge graph with JSON file persistence |
| Models | Pydantic | Data validation and serialization |
| Data | Pandas + SQLAlchemy | Data processing, ingestion, and text-to-SQL |
| Parsing | BeautifulSoup4 + PyYAML | HTML parsing and YAML config loading |
| Testing | pytest | 437 unit tests with full mock coverage |

## Architecture

```
Platform Projects (Prime, Edge)
    │
    │  register adapters via entry points
    ▼
┌─────────────────────────────────────────────────────┐
│                   nebulus-core                        │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │   CLI    │  │ Platform │  │    LLM Client     │  │
│  │  (Click) │  │ Adapter  │  │ (OpenAI-compat.)  │  │
│  └──────────┘  │ Protocol │  └───────────────────┘  │
│                └──────────┘                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Vector  │  │  Memory  │  │   Intelligence    │  │
│  │ (Chroma) │  │ (Graph)  │  │   (13 engines)    │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │  Domain Templates (dealership, medical, legal)│    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
    ▲                                 ▲
    │                                 │
  Prime (Linux)                  Edge (macOS)
  TabbyAPI + Docker               MLX + PM2
```

## Modules

### `cli` — Command Framework

The `nebulus` CLI auto-detects the platform (Linux or macOS ARM) and loads the registered adapter. Commands are organized into groups:

- **`nebulus status`** — Service health overview (default command)
- **`nebulus services`** — `up`, `down`, `restart`, `logs` for platform services
- **`nebulus models`** — `list` available LLM models from the inference server
- **`nebulus memory`** — `status` of LTM systems, `consolidate` to trigger a memory cycle
- **`nebulus tools`** — `start` the MCP tool server, `list` registered tools

Platform adapters can inject additional commands via `platform_specific_commands()`.

### `platform` — Adapter Protocol

The `PlatformAdapter` protocol (defined in [`platform/base.py`](src/nebulus_core/platform/base.py)) is the central integration point. Platform projects implement this protocol and register via Python entry points. Core discovers adapters at runtime through `registry.py` and auto-detects the correct platform via `detection.py`.

**Required properties:**

| Property | Type | Description |
|----------|------|-------------|
| `platform_name` | `str` | Identifier (e.g. `"prime"` or `"edge"`) |
| `services` | `list[ServiceInfo]` | All managed services with ports and health endpoints |
| `llm_base_url` | `str` | OpenAI-compatible inference endpoint |
| `chroma_settings` | `dict` | ChromaDB connection config (HTTP or embedded mode) |
| `default_model` | `str` | Default LLM model name |
| `data_dir` | `Path` | Root directory for persistent data |

**Required methods:** `start_services()`, `stop_services()`, `restart_services()`, `get_logs()`, `platform_specific_commands()`

### `llm` — LLM Client

`LLMClient` is a thin wrapper around httpx that speaks the OpenAI chat completions API. Every LLM call in the ecosystem goes through this client — platform projects never call inference engines directly.

```python
from nebulus_core.llm.client import LLMClient

with LLMClient(base_url="http://localhost:5000/v1") as client:
    response = client.chat(
        messages=[{"role": "user", "content": "Hello"}],
        model="default-model",
    )
```

Supports: `chat()`, `list_models()`, `health_check()`, and context manager usage.

### `vector` — ChromaDB Wrapper

`VectorClient` supports two connection modes, selected by the adapter's `chroma_settings`:

```python
# HTTP mode (Prime — containerized ChromaDB)
{"mode": "http", "host": "localhost", "port": 8001}

# Embedded mode (Edge — local file storage)
{"mode": "embedded", "path": "intelligence/storage/vectors"}
```

`EpisodicMemory` builds on `VectorClient` to provide semantic search over raw memory items, with archival support for the consolidation lifecycle.

### `memory` — Knowledge Graph

- **`GraphStore`** — NetworkX directed graph persisted as JSON. Stores entities and relations extracted from memory.
- **`Consolidator`** — LLM-powered "sleep cycle" that processes unarchived episodic memories, extracts entities and relations, and writes them to the graph store.
- **Pydantic models:** `Entity`, `Relation`, `MemoryItem`, `GraphStats`.

### `mcp` — MCP Tool Server

Platform-agnostic [Model Context Protocol](https://modelcontextprotocol.io/) tool server. Provides 10 tools (filesystem operations, web search, code search, web scraping, document parsing, shell execution) that any platform project can assemble into a running server.

```python
from nebulus_core.mcp import MCPConfig, create_server

config = MCPConfig(workspace_path=Path("/my/workspace"))
mcp = create_server(config)
app = mcp.sse_app()  # Starlette ASGI app
```

Platform adapters supply workspace paths and security settings via `mcp_settings`. The CLI exposes `nebulus tools start` and `nebulus tools list`.

### `intelligence` — Query Orchestration

13 engine modules coordinated by the `IntelligenceOrchestrator`:

1. **Classifier** — Routes questions to the right engine(s) (SQL, semantic, strategic, hybrid)
2. **SQL Engine** — Natural language to SQL via LLM, executes against ingested data
3. **Vector Engine** — Semantic search across ChromaDB collections
4. **Knowledge Manager** — Domain-specific business rules and metrics
5. **Data Ingestor** — CSV to SQLite with schema inference
6. **PII Detector** — Scans and masks personally identifiable information
7. **Scoring** — Entity scoring and ranking
8. **Refinement** — LLM-powered answer refinement
9. **Feedback** — User feedback tracking
10. **Insights** — Statistical analysis of ingested data
11. **Security** — SQL validation utilities
12. **Audit** — Audit logging
13. **Orchestrator** — Coordinates all of the above

**Domain templates** in `intelligence/templates/` provide vertical configurations (dealership, medical, legal) with scoring factors, business rules, and canned queries loaded from YAML configs.

## Installation

### Prerequisites

- Python 3.10+
- Git

### Local Setup

```bash
git clone git@github.com:jlwestsr/nebulus-core.git
cd nebulus-core

python3 -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Cross-Repo Development

Platform projects use editable installs to pick up local core changes immediately:

```bash
cd /path/to/nebulus-prime   # or nebulus-edge
pip install -e ../nebulus-core
```

## Platform Adapter Registration

Platform projects register their adapter via entry points in `pyproject.toml`:

```toml
[project.entry-points."nebulus.platform"]
prime = "nebulus_prime.adapter:PrimeAdapter"
```

The adapter class must satisfy the `PlatformAdapter` protocol. At runtime, `nebulus-core` discovers available adapters via `importlib.metadata.entry_points()`, auto-detects the current platform, and loads the matching adapter.

## Testing

```bash
source venv/bin/activate

# Run all tests (372 tests)
pytest

# Verbose output
pytest -v

# Run a specific test module
pytest tests/test_memory/

# Linting
black --check src/ tests/
flake8 src/ tests/
```

All tests mock external dependencies (ChromaDB, LLM servers). Use shared fixtures from `nebulus_core.testing.fixtures` and factories from `nebulus_core.testing.factories`.

## Development

- **Branching:** Feature branches (`feat/`, `fix/`, `docs/`, `chore/`) from `develop`. Merge to `develop` with `--no-ff`. `main` is releases only.
- **Commits:** Conventional commits — `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`
- **Code style:** `black` (line-length 88) + `flake8`. Type hints mandatory on all signatures. Google-style docstrings on public functions.
- **Python version:** 3.10+ syntax (`str | None`, `list[str]`)

See [WORKFLOW.md](WORKFLOW.md) for the full git workflow and [AI_DIRECTIVES.md](AI_DIRECTIVES.md) for coding standards.

## Related Projects

| Project | Purpose |
|---------|---------|
| [nebulus-prime](https://github.com/jlwestsr/nebulus-prime) | Linux deployment — Docker Compose, TabbyAPI, NVIDIA GPU |
| [nebulus-edge](https://github.com/jlwestsr/nebulus-edge) | macOS deployment — bare-metal MLX, Apple Silicon |
| [nebulus-gantry](https://github.com/jlwestsr/nebulus-gantry) | Full-stack AI chat UI (React + FastAPI) |
| [nebulus-atom](https://github.com/jlwestsr/nebulus-atom) | Autonomous AI engineer CLI with Swarm multi-agent orchestration |
| [nebulus-forge](https://github.com/jlwestsr/nebulus-forge) | AI-native project scaffolding CLI |

## License

MIT
