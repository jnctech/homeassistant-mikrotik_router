---
description: Run the project's pre-PR gate — ruff lint+format, pytest with coverage, doc-update checks, version-triplet check.
disable-model-invocation: true
---

# Pre-PR Check

Mechanical gate for the CLAUDE.md "Pre-PR Checklist (overrides global)".
Run this **before** opening a PR — it catches the most common rejection reasons.

## Steps (run in order, stop on first failure)

### 1. Ruff lint (includes C901 complexity ≤15)

```bash
python -m ruff check custom_components/mikrotik_router tests
```

Expected: `All checks passed!`
On failure: fix the violation. The C901 rule enforces ADR-007 — extract a helper rather than relaxing the gate.

### 2. Ruff format check

```bash
python -m ruff format --check custom_components/mikrotik_router tests
```

Expected: `N files already formatted`.
On failure: run `python -m ruff format custom_components/mikrotik_router tests`, review the diff, commit separately if format-only.

### 3. Pytest with coverage gate (fail_under=80 from pyproject.toml)

> **Note:** On Windows, tests require Docker (`homeassistant` won't pip-install natively). Use the project's docker-dev test container.

```bash
pytest tests/ -v --cov=custom_components/mikrotik_router --cov-report=term-missing
```

Expected: ≥80% total coverage; all tests pass.
On failure: add tests for uncovered lines; do not lower `fail_under`.

### 4. Documentation gates

For each of the following, verify presence on the current branch:

| Doc | Check |
|-----|-------|
| `docs/CHANGE-REGISTER.md` | A `CR-YYMMDD-<branch-slug>` entry exists at the top. |
| `docs/ISSUES.md` | Any issue this PR closes/progresses has updated Status. |
| `docs/decisions/` | If this PR introduces a data-format / entity-identity / API-contract / migration change, an ADR is included. |

Commands to grep for the entries:

```bash
BRANCH_SLUG=$(git rev-parse --abbrev-ref HEAD | sed 's|^feature/||;s|^fix/||')
grep -n "CR-.*$BRANCH_SLUG" docs/CHANGE-REGISTER.md
```

### 5. Version triplet (only if this PR bumps the version)

```bash
MANIFEST_VER=$(jq -r '.version' custom_components/mikrotik_router/manifest.json)
grep -n "$MANIFEST_VER" README.md info.md
```

Expected: `manifest.json`, `README.md`, `info.md` all show the same version.
On mismatch: use `/release-bump <version>` to update atomically.

### 6. PR target sanity

Default target is the **jnctech fork**, never the upstream `tomaae/homeassistant-mikrotik_router` unless the user has explicitly said "upstream". Print the intended target and pause for confirmation before opening.

## Exit criteria

Report a one-line PASS/FAIL summary per step. If all pass, you are clear to open the PR with `gh pr create --base dev ...` (or `--base master` for hotfixes).
