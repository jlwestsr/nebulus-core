# CONTEXT.md — Nebulus Core

> **Critical:** Read [AI_DIRECTIVES.md](AI_DIRECTIVES.md) and [WORKFLOW.md](WORKFLOW.md) before making changes. They define operational guardrails, coding standards, and git workflow rules.

## Project Overview

Nebulus Core is the shared Python library that all Nebulus ecosystem projects depend on. It owns the platform adapter protocol, CLI framework, LLM client, ChromaDB wrapper, knowledge graph, memory consolidation, and the intelligence layer (13 engine modules + domain templates). Platform projects (Prime for Linux, Edge for macOS) install this package and register adapters via Python entry points.

- **Platform-agnostic:** Never import docker, ansible, mlx, ollama, or similar
- **Adapter injection:** All platform behavior flows through the `PlatformAdapter` protocol
- **Dual ChromaDB:** HTTP mode for Prime (Docker), embedded mode for Edge (local files)
- **All LLM calls** go through `LLMClient` — never call inference engines directly

## Key Patterns

### Platform Adapter Protocol

Defined in `src/nebulus_core/platform/base.py`. Platform projects implement this protocol and register via entry points. Core discovers adapters at runtime through `registry.py` and auto-detects the platform via `detection.py`.

Required adapter properties: `platform_name`, `services`, `llm_base_url`, `chroma_settings`, `default_model`, `data_dir`.

### Dependency Injection

All modules use constructor injection. `LLMClient`, `VectorClient`, and `PlatformAdapter` are passed in — never instantiated internally. This keeps modules testable and platform-agnostic.

### CLI Lazy Imports

CLI commands in `src/nebulus_core/cli/commands/` use lazy imports to avoid pulling heavy dependencies (chromadb, networkx, pandas) at startup. The CLI stays responsive even when optional packages aren't installed.

### Memory Architecture

Dual memory system:
- **EpisodicMemory** (`vector/episodic.py`) — ChromaDB-backed conversation and event storage
- **GraphStore** (`memory/graph_store.py`) — NetworkX knowledge graph with JSON file persistence (persists on every write, no batching)
- **Consolidator** (`memory/consolidator.py`) — LLM-powered memory consolidation across both stores

### Intelligence Layer

13 engine modules in `intelligence/core/` extracted from nebulus-edge. All use sync `LLMClient.chat()` (not async httpx). Domain templates in `intelligence/templates/` provide vertical configurations (dealership, medical, legal).

## Current Priorities

1. **Venv and tests must stay green** — 332 tests, all passing
2. **MCP server migration** — Extract MCP from Prime into `nebulus_core.mcp` (next major work item)
3. **Missing CLI tests** — CLI commands have no dedicated test coverage yet
4. **No cross-project integration tests** — only unit tests exist

## Known Issues

- ChromaDB metadata values must be str, int, float, or bool — no nested dicts or lists
- NetworkX JSON serialization requires all node/edge attributes to be JSON-serializable
- Graph store persists on every write — acceptable for current scale, may need batching later
- Editable installs (`pip install -e .`) can go stale after branch switches — reinstall after checkout

## Coding Standards

- **Python 3.10+**: `str | None` not `Optional[str]`, `list[str]` not `List[str]`
- **Type hints** on ALL function signatures
- **Google-style docstrings** on all public functions (Args, Returns, Raises)
- **Formatting**: `black` (line-length 88) + `flake8`
- **No platform-specific code** in this repo

## Git Workflow

- **Never commit directly to `main`** — all work on feature branches from `develop`
- Branch prefixes: `feat/`, `fix/`, `docs/`, `chore/`
- Merge to `develop` with `--no-ff`
- `main` receives merges from `develop` for releases only
- Push requires explicit approval

## Testing

```bash
source venv/bin/activate
pytest                        # 332 tests
black --check src/ tests/     # formatting
flake8 src/ tests/            # linting
```

Mock external dependencies — no live ChromaDB or LLM servers in tests. Use fixtures from `nebulus_core.testing.fixtures` and factories from `nebulus_core.testing.factories`.

## Resources

- [CLAUDE.md](CLAUDE.md) — Full project instructions for AI agents
- [AI_DIRECTIVES.md](AI_DIRECTIVES.md) — Agent role and guardrails
- [WORKFLOW.md](WORKFLOW.md) — Git and development workflow
- [docs/AI_INSIGHTS.md](docs/AI_INSIGHTS.md) — Long-term session memory
- [docs/plans/](docs/plans/) — Implementation plans (date-prefixed)
