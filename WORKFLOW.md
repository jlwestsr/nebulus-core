# Development Workflow

## Conventional Commits

Use the following prefixes for all commit messages:

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `chore:` — Maintenance (configs, dependencies, gitignore)

## Python Environment

**MANDATORY**: Use the project's local virtual environment (`venv/`). Do NOT use global system packages or other environments. Activate immediately:

```bash
source venv/bin/activate
```

When working across repos, use editable installs:

```bash
cd /path/to/nebulus-prime
pip install -e ../nebulus-core

cd /path/to/nebulus-edge
pip install -e ../nebulus-core
```

## Git Tracking & Branching

- **Work directly on `main`** for this repo (nebulus-core uses `main` as the primary branch, not `develop`).
- **Push Authorization**: All pushes to `origin` require explicit, just-in-time user approval.
- For larger features, create local branches with `feat/`, `fix/`, `docs/`, `chore/` prefixes and merge into `main` before pushing.

## Workflows by Commit Type

### Feature (`feat`)

1. Create an implementation plan in `docs/plans/` for non-trivial features.
2. Implement changes with tests (TDD preferred).
3. Run `pytest` to verify.
4. Commit to `main` (or merge feature branch into `main`).
5. Ask for permission, then `git push origin main`.

### Bug Fix (`fix`)

1. Reproduce the bug with a failing test.
2. Implement fix.
3. Verify the failing test now passes AND no regressions.
4. Commit and push (with approval).

### Documentation (`docs`)

1. Update docs, README, or plan files.
2. Check rendering and links.
3. Commit and push (with approval).

### Maintenance (`chore`)

1. Update configs, dependencies, or tooling.
2. Run `pytest` to verify no regressions.
3. Commit and push (with approval).

## Verification

### Before Pushing

```bash
# Activate venv
source venv/bin/activate

# Run tests
pytest

# Run linters
black --check src/ tests/
flake8 src/ tests/
```

### Cross-Repo Verification

After changing nebulus-core, verify platform projects still work:

```bash
# In nebulus-prime
pip install -e ../nebulus-core
pytest tests/test_adapter.py

# In nebulus-edge (when adapter exists)
pip install -e ../nebulus-core
pytest tests/test_adapter.py
```

## Security

- Never commit secrets, API keys, or personal tokens.
- Never hardcode file paths or service endpoints — they come from the adapter.
- All LLM calls go through `LLMClient`, never directly to inference engines.
