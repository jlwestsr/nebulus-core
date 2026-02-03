# CLAUDE.md - Nebulus Core

## Project Overview

Nebulus Core is the shared Python library for the Nebulus AI ecosystem. It provides the platform adapter protocol, CLI framework, LLM client, ChromaDB wrapper, memory system, and (eventually) the intelligence layer. Platform projects (nebulus-prime for Linux, nebulus-edge for macOS) install this library and register adapters via entry points.

**Core principle**: Platform-agnostic. No Docker, no MLX, no Ollama imports. All platform behavior is injected through adapters.

**Required reading**:

- [AI_DIRECTIVES.md](AI_DIRECTIVES.md) — Agent role, operational guardrails, coding style, and testing standards.
- [WORKFLOW.md](WORKFLOW.md) — Git branching, commit workflows, verification, and cross-repo coordination.

## Tech Stack

- **Language**: Python 3.10+ (minimum compatibility across Linux and macOS)
- **Package layout**: `src/nebulus_core/` (setuptools with `src` layout)
- **CLI**: `click` + `rich` (entry: `nebulus_core.cli.main:cli`)
- **Models**: `pydantic`
- **LLM**: `httpx` (OpenAI-compatible HTTP client)
- **Vectors**: `chromadb` (HTTP and embedded modes)
- **Graph**: `networkx` (JSON file persistence)
- **Testing**: `pytest` (config in `pyproject.toml`)
- **Linting**: `black` (line-length 88), `flake8`

## Project Structure

```text
src/nebulus_core/
  __init__.py           # Package version
  cli/
    main.py             # CLI entry point with platform auto-detection
    output.py           # Rich formatting helpers
    commands/
      services.py       # up, down, status, restart, logs
      models.py         # model list, model get
      memory.py         # memory status, memory consolidate
  platform/
    base.py             # PlatformAdapter protocol + ServiceInfo model
    detection.py        # OS/hardware auto-detection
    registry.py         # Adapter discovery via entry points
  llm/
    client.py           # OpenAI-compatible HTTP client (LLMClient)
  vector/
    client.py           # ChromaDB dual-mode wrapper (VectorClient)
    episodic.py         # Episodic memory layer (EpisodicMemory)
  memory/
    models.py           # Entity, Relation, MemoryItem, GraphStats
    graph_store.py      # NetworkX knowledge graph (GraphStore)
    consolidator.py     # LLM-powered memory consolidation (Consolidator)
  intelligence/         # Phase 3 — not yet populated
  testing/              # Shared test utilities
tests/                  # Unit tests (pytest)
docs/
  plans/                # Implementation plans
  AI_INSIGHTS.md        # Long-term agent memory
```

## Coding Standards

### Python (Mandatory)

- **Python 3.10+ syntax**: `str | None` not `Optional[str]`, `list[str]` not `List[str]`
- **Type hints** on ALL function signatures
- **Google-style docstrings** on all public functions with Args, Returns, Raises sections
- **Formatting**: must pass `black` (line-length 88) and `flake8`
- **No platform-specific code**: never import docker, ansible, mlx, ollama, or similar

### When Editing Existing Files

- Small readability improvements (unused imports, etc.) in the file being edited are encouraged
- Search `src/` before creating new utility functions — reuse existing implementations
- Check `pyproject.toml` before adding new dependencies

## Git Workflow

- **Work on `main`** — this repo uses `main` as the primary branch (not `develop`)
- **Conventional commits**: `feat:`, `fix:`, `docs:`, `chore:` prefixes
- `git push origin` requires explicit user approval — always ask first

## Running Tests

```bash
# Activate venv first
source venv/bin/activate

# Run pytest
pytest

# Run linters
black --check src/ tests/
flake8 src/ tests/
```

Pytest config: `pyproject.toml` — test paths: `tests/`, python paths: `src`.

## Key Patterns

### Platform Adapter Protocol

Platform projects register via entry points in their `pyproject.toml`:

```toml
[project.entry-points."nebulus.platform"]
prime = "nebulus_prime.adapter:PrimeAdapter"
```

The adapter provides: `platform_name`, `services`, `llm_base_url`, `chroma_settings`, `default_model`, `data_dir`.

### Cross-Repo Development

```bash
# Editable install for platform projects
cd /path/to/nebulus-prime
pip install -e ../nebulus-core
```

After changing core, re-run tests in platform projects to verify compatibility.

## Multi-File Changes

For changes affecting more than 2 files or introducing new architecture, create an implementation plan in `docs/plans/` and get approval before proceeding.

## Long-Term Memory

Read [docs/AI_INSIGHTS.md](docs/AI_INSIGHTS.md) at the start of each session. Update it when encountering:

- Project-specific nuances not captured elsewhere
- Recurring pitfalls (dependency conflicts, config traps, test quirks)
- Architectural constraints or non-obvious design decisions
