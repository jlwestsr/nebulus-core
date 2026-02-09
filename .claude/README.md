# Claude Code Configuration — nebulus-core

**Project Type:** Python Library
**Configuration Date:** 2026-02-06

---

## Overview

Per-project Claude Code plugin configuration for the Nebulus Core shared library. This configuration is optimized for library development with heavy focus on type checking and code quality.

## Enabled Plugins

### High Priority

- ✅ **Pyright LSP** — Type checking for Python library code
- ✅ **Serena** — Semantic code navigation for library structure
- ✅ **Superpowers** — TDD and debugging workflows

### Medium Priority

- ✅ **Context7** — Live docs for dependencies (pydantic, chromadb, sqlalchemy, networkx)
- ✅ **PR Review Toolkit** — Automated code quality checks
- ✅ **Commit Commands** — Git workflow automation
- ✅ **Feature Dev** — Feature development workflows

## Disabled Plugins

- ❌ **TypeScript LSP** — No TypeScript in library
- ❌ **GitHub** — No GitHub integration needed for library development
- ❌ **Playwright** — No UI testing
- ❌ **Supabase** — Not using Supabase
- ❌ **Ralph Loop** — No automation loops

## LSP Configuration

### Pyright

Configuration: `pyrightconfig.json` (project root)

**Settings:**

- Type checking: basic
- Python version: 3.10+
- Include: `src/`
- Exclude: `__pycache__`, `.pytest_cache`, `.mypy_cache`
- Virtual environment: `./venv`

## Testing

This project uses pytest for testing:

```bash
pytest tests/ -v
```

## Workflow

This library follows the develop→main git workflow:

1. Branch off `develop` for new work
2. Merge features back to `develop` with `--no-ff`
3. Release from `develop` to `main` with version tags

## Why These Plugins?

**Pyright LSP** — Critical for maintaining type hint quality in shared library code. Catches type errors before they propagate to platform projects.

**Serena** — Library has complex module structure (CLI, intelligence, data, platform adapters). Semantic navigation is essential.

**Superpowers** — Library code should be test-driven. TDD and debugging skills keep quality high.

**Context7** — Dependencies like pydantic and chromadb have frequent updates. Live docs ensure we use current APIs.

## Maintenance

Update this configuration when:

- Adding new dependencies that benefit from Context7 docs
- Performance issues (disable low-value plugins)
- New Claude Code plugins that benefit library development

---

*Part of the West AI Labs plugin strategy. See `/docs/claude-code-plugin-strategy.md` for ecosystem-wide strategy.*
