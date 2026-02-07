# Cleanup Track — Phase 2: Test Coverage & Code Quality

**Track**: `cleanup_20260207`
**Branch**: `cleanup/test-coverage-phase2`
**Date**: 2026-02-07

## Audit Findings

### Zero Test Coverage

The CLI command modules (`services.py`, `models.py`, `memory.py`) and `output.py` had 0% test coverage — they were the only production source files without any tests.

### Source Defects

1. **`episodic.py:90` — Metadata mutation**: `get_unarchived()` called `.pop()` on the raw metadata dict returned by ChromaDB, mutating the internal data structure. This could cause data loss on subsequent reads within the same session.

2. **`consolidator.py:113` — Unhandled `JSONDecodeError`**: `_extract_facts()` called `json.loads()` on LLM output without catching `json.JSONDecodeError`. Malformed JSON with matching braces (e.g. `{invalid json}`) would propagate an unhandled exception.

### Test Quality

Several older test files were missing `-> None` return type hints and docstrings on test methods, inconsistent with the project's coding standards.

## Changes Made

### Step 1: CLI Command Tests (17 new tests)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_cli/test_services.py` | 8 | `check_status()` with ONLINE/OFFLINE/TIMEOUT/ERROR; `up`, `down`, `restart` commands |
| `tests/test_cli/test_models.py` | 3 | `list_models` with models, engine error, empty list |
| `tests/test_cli/test_memory.py` | 4 | `status` with stats and unavailable; `consolidate` success and failure |
| `tests/test_cli/test_output.py` | 2 | `print_banner()` smoke test; `create_status_table()` column validation |

### Step 2: Source Defects Fixed

| File | Fix |
|------|-----|
| `src/nebulus_core/vector/episodic.py` | Copy metadata dict before `.pop()`: `dict(results["metadatas"][i])` |
| `src/nebulus_core/memory/consolidator.py` | Wrap `json.loads()` in `try/except json.JSONDecodeError` with warning log |

### Step 3: Test Quality Cleanup

| File | Change |
|------|--------|
| `tests/test_testing/test_factories.py` | Added `-> None` return types and docstrings to all 6 test methods |
| `tests/test_memory/test_models.py` | Added `-> None` return types and docstrings to all 7 test methods |

## Verification

```
pytest tests/ -v          # 372 passed (355 existing + 17 new)
black --check src/ tests/ # All files formatted
flake8 src/ tests/        # No violations
```
