# Phase 4: Cleanup — Design Document

**Goal:** Eliminate duplicated code in nebulus-prime and nebulus-edge by replacing local implementations with imports from nebulus-core, then tag v0.1.0.

**Architecture:** Full rewire of both platform projects. Delete duplicated files, update all imports to `nebulus_core.*`, create EdgeAdapter, fix hardcoded LLM/ChromaDB calls. Core gets minimal shared test fixtures.

**Execution order:** Core first (fixtures/docs), then Prime (smaller, already has adapter), then Edge (larger, needs adapter), then cross-repo verification and v0.1.0 tag.

---

## 1. nebulus-core Changes

### Shared Test Fixtures (`src/nebulus_core/testing/`)

Three modules:

- **`fixtures.py`** — pytest fixtures: `mock_llm_client` (MagicMock spec'd to LLMClient with configurable `.chat()` return), `mock_vector_client` (spec'd to VectorClient with fake collection), `mock_adapter` (spec'd to PlatformAdapter with sensible defaults for `llm_base_url`, `chroma_settings`, `data_dir`).
- **`factories.py`** — helper functions: `make_memory_item(**overrides)`, `make_entity(**overrides)`, `make_relation(**overrides)` returning valid instances with reasonable defaults.
- **`__init__.py`** — re-exports all public fixtures and factories.

### Documentation Updates

- `AI_INSIGHTS.md` — update Phase 2 and 3 to COMPLETE, add Phase 4 notes.
- Ecosystem `CLAUDE.md` — update migration phases table.

### Tagging

After both platform projects pass tests with core imports, tag `v0.1.0` on nebulus-core.

---

## 2. nebulus-prime Cleanup

### Files to Delete (4 files)

All in `src/core/memory/`:

| File | Replaced By |
|------|-------------|
| `models.py` | `nebulus_core.memory.models` |
| `graph_store.py` | `nebulus_core.memory.graph_store` |
| `vector_store.py` | `nebulus_core.vector.client` + `nebulus_core.vector.episodic` |
| `consolidator.py` | `nebulus_core.memory.consolidator` |

### Files to Rewire

- **`src/core/memory/cli_extension.py`** — change imports to use `GraphStore`, `EpisodicMemory`, `Consolidator`, `VectorClient`, `LLMClient` from nebulus-core. Wire dependencies through the adapter (`chroma_settings`, `llm_base_url`, `data_dir` from `PrimeAdapter`).
- **`src/mcp_server/db.py`** — replace `chromadb.HttpClient` instantiation with `VectorClient` from core. Conversation/message/preference methods are Prime-specific and stay, but the underlying ChromaDB client changes.
- **`src/mcp_server/scheduler.py`** — replace hardcoded `http://ollama:11434/api/generate` httpx call with `LLMClient`. Get base URL from adapter or constructor parameter.

### Test Updates

- `tests/test_memory.py` — update imports from `core.memory.*` to `nebulus_core.memory.*` and `nebulus_core.vector.*`. Use shared fixtures from `nebulus_core.testing`.
- `tests/test_scheduler.py` — mock `LLMClient` instead of raw httpx.

### Dependency

Verify `nebulus-core` is in Prime's `pyproject.toml` dependencies.

---

## 3. nebulus-edge Cleanup

### Create EdgeAdapter

New file `nebulus_edge/adapter.py`:

- Implements `PlatformAdapter` protocol
- `platform_name` = `"edge"`
- `llm_base_url` = MLX server endpoint (from env/config)
- `chroma_settings` = `{"mode": "embedded", "path": "intelligence/storage/vectors"}`
- `default_model` = from env/config
- `data_dir` = local data path
- Register via entry point: `[project.entry-points."nebulus.platform"]` → `edge = "nebulus_edge.adapter:EdgeAdapter"`

### Directories to Delete

- **`intelligence/core/`** — all 13 modules. Replaced by `nebulus_core.intelligence.core.*`.
- **`intelligence/templates/`** — base.py + 3 YAML config dirs. Replaced by `nebulus_core.intelligence.templates.*`.

### Directories to Keep But Rewire

- **`intelligence/api/`** — 5 route files (query, data, insights, knowledge, feedback). Update imports from `intelligence.core.*` to `nebulus_core.intelligence.core.*`. These are Edge-specific FastAPI endpoints.
- **`intelligence/server.py`** — update imports. Construct orchestrator/engines using `LLMClient` and `VectorClient` from core.

### Files Left As-Is

- **`body/functions/intelligence.py`** — calls intelligence API over HTTP, not core directly. No change needed.

### Test Updates

- `tests/intelligence/` — 10 test files. Update imports to `nebulus_core.intelligence.core.*`. Use shared fixtures from `nebulus_core.testing`.

### Dependency

Add `nebulus-core` to Edge's dependencies (editable install for dev).

---

## 4. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking platform tests when rewiring imports | Compare core API signatures against local versions before deleting; fix mismatches in core if needed |
| Prime's LTMClient has conversation/message logic not in core | Only swap the ChromaDB connection layer; business logic methods stay in Prime |
| Edge API routes may use `await` on formerly-async methods | Core versions are sync (converted in Phase 3); check each route for `await` calls and adjust |
| Edge has no pyproject.toml entry point setup | Create or modify packaging config as part of EdgeAdapter task |

## 5. Verification

At each step:

- `pytest` in the repo being modified
- `black --check src/ tests/` and `flake8 src/ tests/`
- `git diff` review before committing

Cross-repo verification after all three repos are updated: run `pytest` in all three.
