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
│   └── commands/     # Service, model, memory, tools command groups
├── platform/         # Adapter protocol, detection, registry
├── llm/              # OpenAI-compatible HTTP client
├── vector/           # ChromaDB client + episodic memory layer
├── memory/           # Models, graph store, consolidator
├── mcp/              # MCP tool server (FastMCP, 10 tools)
│   └── tools/        # filesystem, search, web, documents, shell
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
`default_model`, `data_dir`, `mcp_settings`.

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

### Cleanup Track Learnings (2026-02-07)

Track `cleanup_20260207` completed 3 phases in a single session. Key learnings:

- **ChromaDB metadata mutation**: `EpisodicMemory.get_unarchived()` must copy the
  metadata dict before calling `.pop()` to avoid mutating ChromaDB's internal state.
  Pattern: `dict(results["metadatas"][i])` before extracting fields.
- **LLM JSON extraction resilience**: `Consolidator._extract_facts()` extracts JSON
  from LLM responses using `find("{")` / `rfind("}")` and must handle
  `json.JSONDecodeError` for malformed JSON within matching braces.
- **CLI test pattern**: All CLI commands tested via `click.testing.CliRunner` with
  mock adapter injected as `obj={"adapter": adapter, "console": console}`. Lazy
  imports inside command functions require patching at the source module path, not
  the CLI module namespace.
- **Silent exception handlers**: Bare `except Exception:` blocks that return defaults
  without logging make debugging impossible. Always add `logger.error(...)` with
  context about which operation failed and the exception value.
- **Rich Table introspection in tests**: `Table.rows` objects don't stringify cell
  content. To assert on cell values, inspect `table.columns[i]._cells` instead.
- **Test consistency standard**: All test methods must have `-> None` return type
  hints and Google-style docstrings. This is now enforced across all 437 tests.

### Cleanup Track Results (2026-02-07)

| Phase | Focus | Changes |
|-------|-------|---------|
| 1 | Core decoupling | Validation, graceful degradation, missing-adapter errors |
| 2 | Test coverage | 17 CLI tests, episodic.py mutation fix, consolidator.py JSONDecodeError fix |
| 3 | Consistency & observability | 40 test type hints, 4 vector_engine.py loggers, AI_INSIGHTS update |

Final metrics (at time of cleanup): 372 tests, 0 test methods missing `-> None`,
0 silent exception handlers, 0 known source defects, `black` + `flake8` clean.

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

### Phase 4: Cleanup — COMPLETE

- Shared test fixtures and factories in `nebulus_core.testing`
- Cleanup track `cleanup_20260207`: Phase 1 (core decoupling), Phase 2 (CLI tests,
  defect fixes), Phase 3 (test consistency, silent failure logging)
- Documentation foundation: README.md and CONTEXT.md rewritten for v0.1.0
- Tagged `v0.1.0` on `main` at merge commit `4fc3f76` (2026-02-09)

### v0.1.0 Release Notes (2026-02-09)

Release includes all 4 migration phases complete:
- Platform Adapter protocol with auto-detection and entry point discovery
- CLI framework (`nebulus` command) with service, model, and memory management
- LLM client (OpenAI-compatible, httpx)
- ChromaDB dual-mode vector storage (HTTP + embedded)
- Knowledge graph (NetworkX + JSON persistence)
- LLM-powered memory consolidation (episodic → graph)
- Intelligence layer — 13 engine modules + 3 domain templates
- Shared testing infrastructure (fixtures + factories)
- 372 passing tests, `black` + `flake8` clean

### MCP Core Migration (2026-02-09)

Extracted 10 platform-agnostic MCP tools from `nebulus-prime/src/mcp_server/server.py`
into `nebulus_core.mcp`. Prime's scheduler tools (3), LTM REST API, task management
REST API, and web dashboard remain in Prime.

**Module structure**: `config.py` (MCPConfig Pydantic model), `server.py` (create_server
factory), `tools/` (5 modules: filesystem, search, web, documents, shell).

**Key design decisions**:
- Each tool module exports `register(mcp, config)` — decoupled from server creation.
- `MCPConfig.workspace_path` replaces hardcoded `/workspace` — platform adapters inject
  their own value via `mcp_settings`.
- Security settings (allowed_commands, blocked_operators, command_timeout) are
  configurable per-platform, not hardcoded.
- Google search dependencies are optional (`pip install nebulus-core[google]`).
- `FastMCP.list_tools()` is async in mcp 1.26+ — CLI `nebulus tools list` uses
  `asyncio.run()` to bridge sync Click commands.

**Dependencies added**: `mcp[cli]`, `selectolax`, `pypdf`, `python-docx`,
`duckduckgo-search`, `uvicorn`. Optional: `google-api-python-client`,
`googlesearch-python`.

**Test patterns**: Tool modules tested by mocking `FastMCP.tool()` decorator with a
capture pattern that stores registered functions by name. This avoids running a real
MCP server while testing tool logic directly. Search helpers with lazy imports
(googlesearch, googleapiclient) must be patched at source package path, not at the
consuming module.

65 new tests. Total: 437 tests, `black` + `flake8` clean.

### Downstream Prime MCP Cleanup (2026-02-09)

Refactored `nebulus-prime/src/mcp_server/server.py` to import tools from core instead
of defining them locally. Net result: -501 lines across 5 files.

**Changes**:
- `server.py`: Replaced 10 local tool definitions + `_validate_path()` + 3 search
  helpers with `create_server(MCPConfig(workspace_path="/workspace"))`. Only 3
  scheduler tools remain Prime-local.
- `requirements.txt`: Removed 8 packages now transitive via nebulus-core (`mcp[cli]`,
  `duckduckgo-search`, `httpx`, `pypdf`, `python-docx`, `selectolax`, `chromadb`,
  `beautifulsoup4`). Core ref updated from `@main` to `@develop`.
- `adapter.py`: Added `mcp_settings` property to `PrimeAdapter`.
- `test_mcp_tools.py`: Rewrote — 4 tests covering scheduler tools + `create_server`
  config verification. Old filesystem/search/scrape tests removed (covered by core).
- `test_parsers.py`: Deleted entirely (PDF/DOCX tests covered by core's 65 tests).

**Patterns for future downstream migrations (Edge)**:
- Mock `nebulus_core.mcp.create_server` with a `_make_mock_mcp()` helper that tracks
  tool registrations via `tool.side_effect`. Verify platform-specific tools are
  registered and that `create_server` receives the correct `MCPConfig`.
- Don't recreate tests for core tools in platform repos — they're tested in core.

### Post-v0.1.0 Remaining Work

- ~~MCP server migration — extract MCP from Prime into `nebulus_core.mcp`~~ **Done** (2026-02-09)
- ~~Downstream Prime cleanup — import MCP tools from core, remove duplicated tool code~~ **Done** (2026-02-09)
- Replace remaining duplicated code in nebulus-prime with nebulus-core imports
- Replace duplicated code in nebulus-edge with nebulus-core imports
- Create EdgeAdapter

## 4. Documentation & Wiki

*   **GitHub wiki**: Cloned at `../nebulus-core.wiki/` (sibling directory). Uses SSH remote (`git@github.com:jlwestsr/nebulus-core.wiki.git`), `master` branch.
*   **Wiki pages** (9): Home, Architecture-Overview, Platform-Adapter-Protocol, Intelligence-Layer, MCP-Tool-Server, Audit-Logger, Installation-Guide, LLM-Client, Vector-Client.
*   **Wiki initialization**: GitHub wikis must be initialized via the web UI first (create one placeholder page), then local content can be force-pushed.
*   **Ecosystem wikis**: All four project wikis are live:
    - `nebulus-core.wiki` — 8 pages (this project)
    - `nebulus-edge.wiki` — 5 pages
    - `nebulus-gantry.wiki` — 9 pages
    - `nebulus-prime.wiki` — 10 pages
*   **Cross-project doc sync**: When a feature ships, update the corresponding wiki. Wiki repos are independent git repos — commit and push separately from the main repo.
*   **Audit-Logger wiki page**: Documents the full AuditLogger API including common pitfalls (Path not str, AuditEvent not kwargs, timestamp required, get_events not query, audit_log not audit_events). Keep in sync with actual API if it changes.

## 5. Documentation Learnings (2026-02-09)

- **README.md scope**: For a shared library, document modules with usage examples and
  API surface tables — not just a project structure tree. The PlatformAdapter protocol
  table (6 properties + 5 methods) is the most referenced section by downstream devs.
- **CONTEXT.md audience**: Written for AI agents, not humans. Include invariants,
  data flow diagrams, known constraints with impact analysis, and a file quick
  reference table. Agents need to know *where things are* and *what will break*.
- **Link validation**: All internal markdown links must be verified against the
  filesystem before committing. Use a simple shell loop over referenced paths.
- **Tag management**: The `v0.1.0` tag was originally placed on an older commit
  (`c612717`) before all cleanup work landed. When retagging, delete locally with
  `git tag -d` then recreate, and force-push with `git push origin <tag> --force`.
- **Release merge pattern**: `develop` → `main` with `--no-ff` and a descriptive
  merge commit (`release: v0.1.0`). Tag the merge commit, not develop HEAD.

## 6. Gemini Ecosystem Watcher Extension (2026-02-09)

### What Was Built

Gemini CLI extension at `extensions/ecosystem-watcher/` that injects recent Overlord
swarm activity into every Gemini session, enabling "shared consciousness" across agents.

**Components**:
- `gemini-extension.json` — Extension manifest
- `hooks/hooks.json` — BeforeAgent hook declaration (fires before every agent turn)
- `hooks/sync_memory.py` — Core logic: fetches 15 recent `update`/`decision` entries
  from `OverlordMemory`, 5-min TTL file cache, outputs `additionalContext` Markdown
- `commands/ecosystem-status.toml` — `/ecosystem-status` slash command for verbose output
- 13 tests in `tests/test_extensions/test_sync_memory.py`

### Key Design Decisions

- **Reuses Phase 1 `OverlordMemory`**: Import happens inside the fetch function body
  (lazy import) to avoid hard dependency if nebulus-core isn't installed in the Gemini
  environment. This means `patch("sync_memory.OverlordMemory")` won't work in tests —
  must patch at source: `patch("nebulus_core.memory.overlord.OverlordMemory")`.
- **File-based TTL cache** at `.cache/memory_snapshot.json`: Avoids hitting SQLite on
  every agent turn. 5-minute TTL is a tradeoff between freshness and overhead.
- **Hook protocol**: stdout is reserved for the JSON response only. All diagnostics go
  to stderr. Exit code 2 blocks the turn entirely — never use it for soft failures.
- **Category filtering**: Only `update` and `decision` categories are fetched. Other
  categories (failure, release, dispatch, pattern) are excluded to keep token overhead
  manageable. The `/ecosystem-status` command uses the same filter.
- **Timestamp trimming**: Timestamps truncated to minute precision (`[:16]`) in Markdown
  output to save tokens.

### Gemini Extension Patterns (Reference)

- **Manifest** (`gemini-extension.json`): `name`, `version`, `description`. Hooks go in
  separate `hooks/hooks.json`, not in the manifest.
- **Hooks** (`hooks/hooks.json`): Nested structure — `hooks.BeforeAgent[].hooks[]` with
  `type: "command"` and `command` field. Use `${extensionPath}` for portable paths.
- **Hook output**: `{"hookSpecificOutput": {"additionalContext": "..."}}` — the string
  is appended to the agent's context. Keep it Markdown, keep it concise.
- **Custom commands** (`commands/*.toml`): `prompt` field (required), `description`
  (optional). Shell execution via `!{...}`, file injection via `@{...}`, args via
  `{{args}}`. Processing order: file → shell → args.
- **Precedence**: Extension commands have lowest priority. Conflicts get prefixed with
  extension name (e.g., `/ecosystem-watcher.ecosystem-status`).

### Follow-Up Items (Flagged by Gemini PM)

- **Cache platform-awareness**: Current cache lives relative to the extension directory.
  May need routing through `PlatformAdapter` for Edge/Prime consistency if the extension
  is installed in different locations per platform.
- **Token overhead monitoring**: 15 entries is manageable now but should be monitored as
  swarm activity scales. Consider dynamic limiting based on entry length. Gemini PM
  elevated this to high priority (2026-02-09).

### Gemini Headless Mode Limitations

Gemini CLI in headless mode (`gemini -p "..."`) has restricted tool access — `codebase_investigator`,
`run_shell_command`, and `cli_help` all return "Tool execution denied by policy." This means
Gemini cannot execute `overlord memory remember` commands or read files when invoked headlessly.
Workaround: log Overlord memory entries directly via `OverlordMemory.remember()` in Python
and relay the confirmation to Gemini.

### Session Handoff Notes (2026-02-09)

- **Next priority** (per Gemini PM): nebulus-atom v2 design implementation per
  `nebulus-atom/docs/plans/2026-02-05-nebulus-atom-v2-design.md`. Check
  `conductor/tracks.md` for sub-tasks. Verify no other agents are active in the repo.
- **All ecosystem-watcher deliverables complete**: extension built, tested (467 passing),
  committed, pushed, documented in AI_INSIGHTS, logged to Overlord memory, posted to
  #nebulus-ops, and approved by Gemini PM.
