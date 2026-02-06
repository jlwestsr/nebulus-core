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

- **NEVER commit directly to `main`.** All work happens on feature branches.
- **Branch workflow:** Create a branch with `feat/`, `fix/`, `docs/`, `chore/` prefix → do all work there → merge into `develop` when complete.
- **`develop`** is the integration branch. `main` is for releases only.
- **Push Authorization**: All pushes to `origin` require explicit, just-in-time user approval.

## Workflows by Commit Type

### Feature (`feat`)

1. Create branch: `git checkout -b feat/<name> develop`
2. Create an implementation plan in `docs/plans/` for non-trivial features.
3. Implement changes with tests (TDD preferred).
4. Run `pytest` to verify.
5. Merge to develop: `git checkout develop && git merge feat/<name>`
6. Delete branch: `git branch -d feat/<name>`
7. Ask for permission, then `git push origin develop`.

### Bug Fix (`fix`)

1. Create branch: `git checkout -b fix/<name> develop`
2. Reproduce the bug with a failing test.
3. Implement fix.
4. Verify the failing test now passes AND no regressions.
5. Merge to develop and push (with approval).

### Documentation (`docs`)

1. Create branch: `git checkout -b docs/<name> develop`
2. Update docs, README, or plan files.
3. Check rendering and links.
4. Merge to develop and push (with approval).

### Maintenance (`chore`)

1. Create branch: `git checkout -b chore/<name> develop`
2. Update configs, dependencies, or tooling.
3. Run `pytest` to verify no regressions.
4. Merge to develop and push (with approval).

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
