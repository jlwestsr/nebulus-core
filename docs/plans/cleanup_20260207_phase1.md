# Phase 1: Core Decoupling — Ecosystem Stabilization

**Track**: `cleanup_20260207`
**Branch**: `cleanup/core-decoupling-phase1`
**Date**: 2026-02-07

## Audit Findings

The nebulus-core codebase was already well-decoupled — no platform-specific imports
exist in `src/`, LLMClient and VectorClient accept config via constructor injection,
and the PlatformAdapter protocol is clean. However, three gaps were identified:

1. **No graceful degradation** — CLI exits fatally if no adapter is installed, but
   error messages lack diagnostic context (e.g., which adapters are available).
2. **Hardcoded default port** (8001) in VectorClient as a silent fallback — violates
   explicit configuration principle.
3. **No validation** — LLMClient accepts empty/invalid URLs silently, VectorClient
   accepts incomplete settings silently.
4. **No test coverage** for failure scenarios (registry, CLI bootstrap, validation).

## Changes Made

### Source Changes

| File | Change |
|------|--------|
| `src/nebulus_core/platform/registry.py` | Added `adapter_available()` for non-fatal checking. Improved `load_adapter()` error messages to list available adapters. Added try/except around `ep.load()` to wrap import failures with descriptive message. |
| `src/nebulus_core/platform/__init__.py` | Exported `adapter_available` in `__all__`. |
| `src/nebulus_core/llm/client.py` | Added base_url validation: rejects empty, whitespace-only, and non-HTTP/HTTPS URLs with descriptive ValueError. |
| `src/nebulus_core/vector/client.py` | Removed hardcoded `host="localhost"` and `port=8001` defaults. HTTP mode now requires explicit `host` and `port`. Embedded mode validates `path` is present. Added unknown mode rejection. |

### Test Changes

| File | Tests Added |
|------|-------------|
| `tests/test_platform.py` | 5 tests: registry failure (no adapter), error includes available adapters, import failure wrapping, `adapter_available()` true/false |
| `tests/test_llm/test_client.py` | 6 tests: empty URL, whitespace URL, invalid scheme, no scheme, https accepted, chat raises on unreachable server |
| `tests/test_cli/test_main.py` | 4 tests (new file): `get_adapter()` before init, CLI with missing adapter, CLI with detection failure, `--version` flag |
| `tests/test_vector/test_client.py` | 8 tests (new file): HTTP mode missing host/port/both, embedded missing path, unknown mode, default mode validation, heartbeat false on failure, heartbeat true on success |

## Verification

```
pytest tests/ -v          → 355 passed
black --check src/ tests/ → all clean
flake8 src/ tests/        → all clean
```

## Breaking Changes

- **VectorClient**: HTTP mode no longer silently defaults to `localhost:8001`.
  Callers must provide explicit `host` and `port` in settings. All existing platform
  adapters already provide these values, so no downstream impact expected.
- **LLMClient**: Empty or non-HTTP base URLs now raise ValueError at construction
  time instead of failing silently on first request.
