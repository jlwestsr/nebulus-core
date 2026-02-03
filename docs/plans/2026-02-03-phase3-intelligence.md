# Phase 3: Intelligence Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract the 13 intelligence core modules and template system from nebulus-edge into nebulus-core as platform-agnostic shared code.

**Architecture:** All modules move into `nebulus_core/intelligence/core/` and `nebulus_core/intelligence/templates/`. Modules that called the Brain LLM via httpx are refactored to use the existing sync `LLMClient`. Modules that used direct ChromaDB access now use `VectorClient`. SQLite access passes `db_path: Path` as a constructor arg (no abstraction). Template YAML configs are bundled as package data via `importlib.resources`. The FastAPI server and API routes stay in nebulus-edge.

**Tech Stack:** Python 3.10+, Pydantic, pandas, sqlite3, networkx, chromadb (via VectorClient), httpx (via LLMClient), pyyaml, pytest

**Source:** All modules extracted from `/home/jlwestsr/projects/west_ai_labs/nebulus-edge/intelligence/`

**Destination:** `/home/jlwestsr/projects/west_ai_labs/nebulus-core/src/nebulus_core/intelligence/`

**Key refactoring rules:**
- Replace `from typing import Dict, List, Optional, Set, Any` with built-in generics (`dict`, `list`, `set`) and `X | None`
- Replace `import httpx` + async Brain calls with sync `LLMClient` injection
- Replace hardcoded paths with constructor `db_path: Path` or `vector_client: VectorClient` args
- Replace `from intelligence.X` imports with `from nebulus_core.intelligence.X`
- All tests use `tmp_path` fixtures for SQLite, mocks for LLMClient/VectorClient
- Use `./venv/bin/python -m pytest` to run tests (project venv has deps)

---

## Task 1: Add pyyaml dependency and create package structure

**Files:**
- Modify: `pyproject.toml`
- Create: `src/nebulus_core/intelligence/core/__init__.py`
- Create: `src/nebulus_core/intelligence/templates/__init__.py`

**Step 1: Update pyproject.toml**

Add `"pyyaml"` to the `dependencies` list.

**Step 2: Create package structure**

Create `src/nebulus_core/intelligence/core/__init__.py`:
```python
"""Intelligence core modules."""
```

The existing `src/nebulus_core/intelligence/__init__.py` already exists (empty stub from Phase 1). Leave it as-is for now — we'll update exports at the end.

Create `src/nebulus_core/intelligence/templates/__init__.py`:
```python
"""Intelligence vertical templates."""
```

**Step 3: Install updated deps**

Run: `cd /home/jlwestsr/projects/west_ai_labs/nebulus-core && ./venv/bin/pip install -e ".[dev]"`

**Step 4: Commit**

```bash
git add pyproject.toml src/nebulus_core/intelligence/core/__init__.py src/nebulus_core/intelligence/templates/__init__.py
git commit -m "chore: add pyyaml dep and intelligence package structure"
```

---

## Task 2: Security utilities (pure, zero deps)

**Files:**
- Create: `src/nebulus_core/intelligence/core/security.py`
- Create: `tests/test_intelligence/test_security.py`

**Source:** Copy `nebulus-edge/intelligence/core/security.py` (269 lines) nearly verbatim.

**Changes from Edge:**
- Replace `from typing import Optional` with `X | None` syntax
- No other changes — this module is pure Python with no external deps

**Tests:** Adapt from `nebulus-edge/tests/intelligence/test_security.py`. Update imports from `intelligence.core.security` to `nebulus_core.intelligence.core.security`.

**Step 1: Write tests first, then implement, then run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_security.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/security.py tests/test_intelligence/test_security.py
git commit -m "feat: extract security utilities from Edge"
```

---

## Task 3: PII detection (pure, zero deps)

**Files:**
- Create: `src/nebulus_core/intelligence/core/pii.py`
- Create: `tests/test_intelligence/test_pii.py`

**Source:** Copy `nebulus-edge/intelligence/core/pii.py` (395 lines).

**Changes from Edge:**
- Replace `from typing import Any, Dict, List, Optional, Set` with built-in generics
- Replace `Optional[X]` with `X | None`

**Tests:** Adapt from Edge's `test_pii.py`. Update imports.

**Step 1: Write tests first, then implement, then run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_pii.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/pii.py tests/test_intelligence/test_pii.py
git commit -m "feat: extract PII detection from Edge"
```

---

## Task 4: Template system (YAML configs as package data)

**Files:**
- Create: `src/nebulus_core/intelligence/templates/base.py`
- Create: `src/nebulus_core/intelligence/templates/dealership/config.yaml`
- Create: `src/nebulus_core/intelligence/templates/medical/config.yaml`
- Create: `src/nebulus_core/intelligence/templates/legal/config.yaml`
- Modify: `src/nebulus_core/intelligence/templates/__init__.py`
- Create: `tests/test_intelligence/test_templates.py`

**Source:** Copy `nebulus-edge/intelligence/templates/base.py` (162 lines) and all 3 config.yaml files.

**Changes from Edge:**
- `VerticalTemplate._load_config()` uses `importlib.resources` instead of `Path(__file__).parent`:
  ```python
  import importlib.resources as pkg_resources

  def _load_config(self, template_name: str) -> dict:
      try:
          ref = pkg_resources.files(
              f"nebulus_core.intelligence.templates.{template_name}"
          ) / "config.yaml"
          config_text = ref.read_text(encoding="utf-8")
          return yaml.safe_load(config_text)
      except (ModuleNotFoundError, FileNotFoundError) as e:
          raise ValueError(f"Template '{template_name}' not found: {e}")
  ```
- Add optional `custom_config_path: Path | None = None` to `__init__` for overlay
- `list_templates()` uses `importlib.resources` to discover bundled templates
- Replace typing imports with 3.10+ syntax
- Each template subdir needs an `__init__.py` for package data discovery

**Template YAML files:** Copy verbatim from Edge — dealership (238 lines), medical (293 lines), legal (342 lines).

**Tests:** Adapt from Edge's `test_templates.py`. Update imports.

**Step 1: Create template subdirectories with __init__.py files**

Create empty `__init__.py` in each template subdir for `importlib.resources` to work:
- `src/nebulus_core/intelligence/templates/dealership/__init__.py`
- `src/nebulus_core/intelligence/templates/medical/__init__.py`
- `src/nebulus_core/intelligence/templates/legal/__init__.py`

**Step 2: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_templates.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add src/nebulus_core/intelligence/templates/ tests/test_intelligence/test_templates.py
git commit -m "feat: extract template system with bundled YAML configs"
```

---

## Task 5: Knowledge management

**Files:**
- Create: `src/nebulus_core/intelligence/core/knowledge.py`
- Create: `tests/test_intelligence/test_knowledge.py`

**Source:** Copy `nebulus-edge/intelligence/core/knowledge.py` (343 lines).

**Changes from Edge:**
- Replace typing imports with 3.10+ syntax
- Constructor takes `template: VerticalTemplate | None` and `knowledge_path: Path` explicitly
- Replace `from intelligence.templates.base import ...` with `from nebulus_core.intelligence.templates.base import ...`

**Tests:** Adapt from Edge's `test_knowledge.py`. Use `tmp_path` for knowledge JSON file.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_knowledge.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/knowledge.py tests/test_intelligence/test_knowledge.py
git commit -m "feat: extract knowledge management from Edge"
```

---

## Task 6: Audit logging (SQLite)

**Files:**
- Create: `src/nebulus_core/intelligence/core/audit.py`
- Create: `tests/test_intelligence/test_audit.py`

**Source:** Copy `nebulus-edge/intelligence/core/audit.py` (500 lines).

**Changes from Edge:**
- Replace typing imports with 3.10+ syntax
- Constructor: `AuditLogger(db_path: Path)` — path injected, not hardcoded

**Tests:** Adapt from Edge's `test_audit.py`. Use `tmp_path` for SQLite db.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_audit.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/audit.py tests/test_intelligence/test_audit.py
git commit -m "feat: extract audit logging from Edge"
```

---

## Task 7: Feedback system (SQLite)

**Files:**
- Create: `src/nebulus_core/intelligence/core/feedback.py`
- Create: `tests/test_intelligence/test_feedback.py`

**Source:** Copy `nebulus-edge/intelligence/core/feedback.py` (609 lines).

**Changes from Edge:**
- Replace typing imports with 3.10+ syntax
- Constructor: `FeedbackManager(db_path: Path)` — path injected

**Tests:** Adapt from Edge's `test_feedback.py`. Use `tmp_path`.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_feedback.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/feedback.py tests/test_intelligence/test_feedback.py
git commit -m "feat: extract feedback system from Edge"
```

---

## Task 8: Scoring engine

**Files:**
- Create: `src/nebulus_core/intelligence/core/scoring.py`
- Create: `tests/test_intelligence/test_scoring.py`

**Source:** Copy `nebulus-edge/intelligence/core/scoring.py` (350 lines).

**Changes from Edge:**
- Replace typing imports with 3.10+ syntax
- Constructor: `SaleScorer(db_path: Path, knowledge: KnowledgeManager)`
- Replace `from intelligence.core.knowledge import ...` with `from nebulus_core.intelligence.core.knowledge import ...`

**Tests:** Adapt from Edge's `test_scoring.py`. Use `tmp_path` for SQLite.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_scoring.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/scoring.py tests/test_intelligence/test_scoring.py
git commit -m "feat: extract scoring engine from Edge"
```

---

## Task 9: Insight generator

**Files:**
- Create: `src/nebulus_core/intelligence/core/insights.py`
- Create: `tests/test_intelligence/test_insights.py`

**Source:** Copy `nebulus-edge/intelligence/core/insights.py` (513 lines).

**Changes from Edge:**
- Replace typing imports with 3.10+ syntax
- Constructor: `InsightGenerator(db_path: Path, knowledge: KnowledgeManager | None = None)`
- Update internal imports

**Tests:** Adapt from Edge's `test_insights.py`. Use `tmp_path`.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_insights.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/insights.py tests/test_intelligence/test_insights.py
git commit -m "feat: extract insight generator from Edge"
```

---

## Task 10: Knowledge refinement

**Files:**
- Create: `src/nebulus_core/intelligence/core/refinement.py`
- Create: `tests/test_intelligence/test_refinement.py`

**Source:** Copy `nebulus-edge/intelligence/core/refinement.py` (420 lines).

**Changes from Edge:**
- Replace typing imports
- Update imports from `intelligence.core.feedback` → `nebulus_core.intelligence.core.feedback`
- Update imports from `intelligence.core.knowledge` → `nebulus_core.intelligence.core.knowledge`

**Tests:** Adapt from Edge's `test_refinement.py`. Use `tmp_path`.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_refinement.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/refinement.py tests/test_intelligence/test_refinement.py
git commit -m "feat: extract knowledge refinement from Edge"
```

---

## Task 11: Question classifier (LLM refactor)

**Files:**
- Create: `src/nebulus_core/intelligence/core/classifier.py`
- Create: `tests/test_intelligence/test_classifier.py`

**Source:** Copy `nebulus-edge/intelligence/core/classifier.py` (282 lines).

**Changes from Edge — THIS IS A KEY REFACTOR:**
- Remove `import httpx`
- Constructor changes from `__init__(self, brain_url: str)` to:
  ```python
  def __init__(self, llm: LLMClient, model: str) -> None:
      self.llm = llm
      self.model = model
  ```
- `classify()` changes from `async` to sync:
  ```python
  def classify(self, question: str, schema: dict) -> ClassificationResult:
  ```
- Replace `_call_brain()` with direct `self.llm.chat()`:
  ```python
  content = self.llm.chat(
      messages=[{"role": "user", "content": prompt}],
      model=self.model,
      temperature=0.1,
      max_tokens=500,
  )
  ```
- `classify_simple()` stays unchanged (no LLM, rule-based)

**Tests:** Mock `LLMClient.chat()` to return classification JSON. Test both LLM and rule-based paths.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_classifier.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/classifier.py tests/test_intelligence/test_classifier.py
git commit -m "feat: extract classifier with LLMClient (replaces httpx)"
```

---

## Task 12: SQL engine (LLM refactor)

**Files:**
- Create: `src/nebulus_core/intelligence/core/sql_engine.py`
- Create: `tests/test_intelligence/test_sql_engine.py`

**Source:** Copy `nebulus-edge/intelligence/core/sql_engine.py` (313 lines).

**Changes from Edge — ANOTHER KEY REFACTOR:**
- Remove `import httpx`
- Constructor changes to:
  ```python
  def __init__(self, db_path: Path, llm: LLMClient, model: str) -> None:
  ```
- All `async` methods become sync
- Replace `_call_brain()` with `self.llm.chat()`
- `natural_to_sql()` and `explain_results()` use `self.llm.chat()` instead of httpx
- SQL validation uses `from nebulus_core.intelligence.core.security import ...`

**Tests:** Mock LLMClient for NL→SQL generation. Use `tmp_path` for SQLite. Test safety validation.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_sql_engine.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/sql_engine.py tests/test_intelligence/test_sql_engine.py
git commit -m "feat: extract SQL engine with LLMClient (replaces httpx)"
```

---

## Task 13: Vector engine (uses VectorClient)

**Files:**
- Create: `src/nebulus_core/intelligence/core/vector_engine.py`
- Create: `tests/test_intelligence/test_vector_engine.py`

**Source:** Copy `nebulus-edge/intelligence/core/vector_engine.py` (370 lines).

**Changes from Edge:**
- Remove direct `chromadb.PersistentClient` instantiation
- Constructor changes to:
  ```python
  def __init__(self, vector_client: VectorClient) -> None:
      self.client = vector_client
  ```
- Replace `self.chroma_client.get_or_create_collection(...)` with `self.client.get_or_create_collection(...)`
- Replace typing imports with 3.10+ syntax

**Tests:** Mock VectorClient. Test embedding, search, and pattern operations.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_vector_engine.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/vector_engine.py tests/test_intelligence/test_vector_engine.py
git commit -m "feat: extract vector engine using VectorClient"
```

---

## Task 14: Data ingestor

**Files:**
- Create: `src/nebulus_core/intelligence/core/ingest.py`
- Create: `tests/test_intelligence/test_ingest.py`

**Source:** Copy `nebulus-edge/intelligence/core/ingest.py` (391 lines).

**Changes from Edge:**
- Constructor takes explicit deps:
  ```python
  def __init__(
      self,
      db_path: Path,
      pii_detector: PIIDetector,
      vector_engine: VectorEngine | None = None,
      template: VerticalTemplate | None = None,
  ) -> None:
  ```
- Replace internal imports to use `nebulus_core.intelligence.core.*`
- Replace typing imports with 3.10+ syntax

**Tests:** Adapt from Edge's `test_ingest.py`. Use `tmp_path`, mock VectorEngine.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_ingest.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/ingest.py tests/test_intelligence/test_ingest.py
git commit -m "feat: extract data ingestor from Edge"
```

---

## Task 15: Orchestrator (LLM refactor, coordinates all engines)

**Files:**
- Create: `src/nebulus_core/intelligence/core/orchestrator.py`
- Create: `tests/test_intelligence/test_orchestrator.py`

**Source:** Copy `nebulus-edge/intelligence/core/orchestrator.py` (350 lines).

**Changes from Edge — MAJOR REFACTOR:**
- Remove `import httpx`
- Constructor takes all dependencies:
  ```python
  def __init__(
      self,
      classifier: QuestionClassifier,
      sql_engine: SQLEngine,
      vector_engine: VectorEngine,
      knowledge: KnowledgeManager,
      llm: LLMClient,
      model: str,
  ) -> None:
  ```
- All `async` methods become sync
- `_synthesize()` uses `self.llm.chat()` instead of httpx
- `_gather_context()` calls sync methods on injected engines
- Update all internal imports to `nebulus_core.intelligence.core.*`

**Tests:** Mock all engine dependencies. Test orchestration flow, context gathering, synthesis.

**Step 1: Write tests, implement, run**

Run: `./venv/bin/python -m pytest tests/test_intelligence/test_orchestrator.py -v`
Expected: ALL PASS

**Step 2: Commit**

```bash
git add src/nebulus_core/intelligence/core/orchestrator.py tests/test_intelligence/test_orchestrator.py
git commit -m "feat: extract orchestrator with LLMClient (replaces httpx)"
```

---

## Task 16: Wire package exports and update intelligence __init__

**Files:**
- Modify: `src/nebulus_core/intelligence/__init__.py`
- Modify: `src/nebulus_core/intelligence/core/__init__.py`
- Modify: `src/nebulus_core/intelligence/templates/__init__.py`

**Step 1: Update core/__init__.py with all public classes**

```python
"""Intelligence core modules."""

from nebulus_core.intelligence.core.audit import AuditLogger
from nebulus_core.intelligence.core.classifier import (
    ClassificationResult,
    QueryType,
    QuestionClassifier,
)
from nebulus_core.intelligence.core.feedback import FeedbackManager
from nebulus_core.intelligence.core.ingest import DataIngestor
from nebulus_core.intelligence.core.insights import InsightGenerator
from nebulus_core.intelligence.core.knowledge import KnowledgeManager
from nebulus_core.intelligence.core.orchestrator import IntelligenceOrchestrator
from nebulus_core.intelligence.core.pii import PIIDetector, PIIReport, PIIType
from nebulus_core.intelligence.core.refinement import KnowledgeRefiner
from nebulus_core.intelligence.core.scoring import SaleScorer
from nebulus_core.intelligence.core.security import ValidationError
from nebulus_core.intelligence.core.sql_engine import SQLEngine
from nebulus_core.intelligence.core.vector_engine import VectorEngine

__all__ = [
    "AuditLogger",
    "ClassificationResult",
    "DataIngestor",
    "FeedbackManager",
    "InsightGenerator",
    "IntelligenceOrchestrator",
    "KnowledgeManager",
    "KnowledgeRefiner",
    "PIIDetector",
    "PIIReport",
    "PIIType",
    "QueryType",
    "QuestionClassifier",
    "SaleScorer",
    "SQLEngine",
    "ValidationError",
    "VectorEngine",
]
```

**Step 2: Update templates/__init__.py**

```python
"""Intelligence vertical templates."""

from nebulus_core.intelligence.templates.base import (
    VerticalTemplate,
    list_templates,
    load_template,
)

__all__ = ["VerticalTemplate", "list_templates", "load_template"]
```

**Step 3: Update intelligence/__init__.py**

```python
"""Intelligence layer — data ingestion, analysis, and knowledge management."""
```

**Step 4: Verify all imports**

Run:
```bash
./venv/bin/python -c "
from nebulus_core.intelligence.core import (
    AuditLogger, QuestionClassifier, FeedbackManager, DataIngestor,
    InsightGenerator, KnowledgeManager, IntelligenceOrchestrator,
    PIIDetector, KnowledgeRefiner, SaleScorer, SQLEngine, VectorEngine,
)
from nebulus_core.intelligence.templates import VerticalTemplate, list_templates
print('All imports OK')
"
```

**Step 5: Commit**

```bash
git add src/nebulus_core/intelligence/__init__.py src/nebulus_core/intelligence/core/__init__.py src/nebulus_core/intelligence/templates/__init__.py
git commit -m "chore: wire intelligence package exports"
```

---

## Task 17: Full test suite verification

**Step 1: Run all nebulus-core tests**

Run: `./venv/bin/python -m pytest -v`
Expected: ALL PASS (previous 39 + new intelligence tests)

**Step 2: Verify import completeness**

Run:
```bash
./venv/bin/python -c "
from nebulus_core.memory import Consolidator, GraphStore, Entity
from nebulus_core.vector import VectorClient, EpisodicMemory
from nebulus_core.llm.client import LLMClient
from nebulus_core.intelligence.core import PIIDetector, SQLEngine, IntelligenceOrchestrator
from nebulus_core.intelligence.templates import VerticalTemplate, list_templates
templates = list_templates()
print(f'All imports OK. Templates: {templates}')
"
```
Expected: `All imports OK. Templates: ['dealership', 'legal', 'medical']`
