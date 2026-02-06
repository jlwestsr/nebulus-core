# Nebulus Core

Shared Python library for the Nebulus AI ecosystem. Provides the platform adapter protocol, CLI framework, LLM client, ChromaDB wrapper, memory system, and intelligence layer used by all platform and application projects.

**Core principle:** Platform-agnostic. No Docker, no MLX, no Ollama. All platform behavior is injected through adapters.

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| CLI | Click + Rich | Command framework and formatted output |
| LLM | httpx | OpenAI-compatible HTTP client |
| Vectors | ChromaDB | Dual-mode (HTTP + embedded) vector storage |
| Graph | NetworkX | Knowledge graph with JSON persistence |
| Models | Pydantic | Data validation and serialization |
| Data | Pandas + SQLAlchemy | Data processing and SQL queries |
| Parsing | BeautifulSoup4 + PyYAML | HTML and config file parsing |
| Testing | pytest | Unit and integration tests |

## Architecture

```
Platform Projects (Prime, Edge)
    │
    │  register adapters via entry points
    ▼
┌─────────────────────────────────────────────────┐
│                  nebulus-core                     │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │   CLI    │  │ Platform │  │  LLM Client   │  │
│  │  (Click) │  │ Adapter  │  │  (httpx)      │  │
│  └──────────┘  │ Protocol │  └───────────────┘  │
│                └──────────┘                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Vector  │  │  Memory  │  │ Intelligence  │  │
│  │ (Chroma) │  │ (Graph)  │  │   (13 engines)│  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  Domain Templates (dealership, medical,  │    │
│  │  legal, accounting)                      │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
    ▲                              ▲
    │                              │
  Prime (Linux)               Edge (macOS)
  TabbyAPI + Docker            MLX + PM2
```

## Project Structure

```
src/nebulus_core/
├── __init__.py              # Package version
├── cli/
│   ├── main.py              # CLI entry point with platform auto-detection
│   ├── output.py            # Rich formatting helpers
│   └── commands/
│       ├── services.py      # up, down, status, restart, logs
│       ├── models.py        # model list, model get
│       └── memory.py        # memory status, memory consolidate
├── platform/
│   ├── base.py              # PlatformAdapter protocol + ServiceInfo
│   ├── detection.py         # OS/hardware auto-detection
│   └── registry.py          # Adapter discovery via entry points
├── llm/
│   └── client.py            # OpenAI-compatible HTTP client (LLMClient)
├── vector/
│   ├── client.py            # ChromaDB dual-mode wrapper (VectorClient)
│   └── episodic.py          # Episodic memory layer
├── memory/
│   ├── models.py            # Entity, Relation, MemoryItem, GraphStats
│   ├── graph_store.py       # NetworkX knowledge graph (GraphStore)
│   └── consolidator.py      # LLM-powered memory consolidation
├── intelligence/
│   ├── core/                # 13 engine modules
│   │   ├── orchestrator.py  # Workflow orchestration
│   │   ├── ingest.py        # Data ingestion (CSV, multi-source)
│   │   ├── classifier.py    # Domain classification
│   │   ├── pii.py           # PII detection
│   │   ├── security.py      # Security utilities
│   │   ├── sql_engine.py    # SQLite semantic queries
│   │   ├── vector_engine.py # ChromaDB semantic search
│   │   ├── insights.py      # Statistical analysis
│   │   ├── scoring.py       # Entity scoring/ranking
│   │   ├── refinement.py    # LLM-powered refinement
│   │   ├── feedback.py      # User feedback tracking
│   │   ├── knowledge.py     # Knowledge management
│   │   └── audit.py         # Audit logging
│   └── templates/           # Vertical domain templates
│       ├── base.py
│       ├── dealership/
│       ├── medical/
│       └── legal/
└── testing/
    ├── fixtures.py          # Mock fixtures (LLMClient, VectorClient, Adapter)
    └── factories.py         # Test factories (Entity, Relation, MemoryItem)
```

## Setup

### Prerequisites

- Python 3.10+
- Git

### Installation

```bash
# Clone
git clone git@github.com:jlwestsr/nebulus-core.git
cd nebulus-core

# Create and activate venv
python3 -m venv venv
source venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Cross-Repo Development

Platform projects use editable installs to pick up local changes:

```bash
cd /path/to/nebulus-prime   # or nebulus-edge
pip install -e ../nebulus-core
```

## Usage

### CLI

```bash
# Platform auto-detection
nebulus status

# Service management
nebulus services up
nebulus services down
nebulus services restart

# Model management
nebulus models list
nebulus models get <model-name>

# Memory
nebulus memory status
nebulus memory consolidate
```

### Platform Adapter Protocol

Platform projects register adapters via entry points in their `pyproject.toml`:

```toml
[project.entry-points."nebulus.platform"]
prime = "nebulus_prime.adapter:PrimeAdapter"
```

The adapter provides: `platform_name`, `services`, `llm_base_url`, `chroma_settings`, `default_model`, `data_dir`.

### ChromaDB Dual Mode

```python
# HTTP mode (Prime — connects to Docker container)
chroma_settings = {"mode": "http", "host": "localhost", "port": 8001}

# Embedded mode (Edge — local file storage)
chroma_settings = {"mode": "embedded", "path": "intelligence/storage/vectors"}
```

### LLM Client

```python
from nebulus_core.llm.client import LLMClient

client = LLMClient(base_url="http://localhost:5000/v1")
response = client.chat(
    messages=[{"role": "user", "content": "Hello"}],
    model="default-model",
)
```

## Testing

```bash
source venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test module
pytest tests/test_memory/

# Linting
black --check src/ tests/
flake8 src/ tests/
```

## Development

- **Branching:** `develop` is the integration branch. Feature branches (`feat/`, `fix/`, `docs/`, `chore/`) merge into `develop`. `main` is for releases only.
- **Commits:** Conventional commits — `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`
- **Code style:** `black` (line-length 88) + `flake8`. Type hints mandatory. Google-style docstrings on public functions.
- **Testing:** Run `pytest` before every commit. Mock external dependencies (ChromaDB, LLM servers).

## Related Projects

| Project | Purpose |
|---------|---------|
| [nebulus-prime](https://github.com/jlwestsr/nebulus-prime) | Linux deployment (Docker, TabbyAPI, NVIDIA GPU) |
| [nebulus-edge](https://github.com/jlwestsr/nebulus-edge) | macOS deployment (bare-metal MLX, Apple Silicon) |
| [nebulus-gantry](https://github.com/jlwestsr/nebulus-gantry) | Full-stack AI chat UI (React/FastAPI) |
| [nebulus-atom](https://github.com/jlwestsr/nebulus-atom) | Autonomous AI engineer CLI |
| [nebulus-forge](https://github.com/jlwestsr/nebulus-forge) | AI-native project scaffolding |

## License

MIT
