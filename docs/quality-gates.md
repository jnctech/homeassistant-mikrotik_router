# Quality Gates

## Branch model

- **`dev`** — the integration branch. **All** PRs target `dev`.
- **`master`** — release-only and branch-protected (changes require a PR, so it can't be fast-forwarded directly). **Release flow:** open a `dev → master` PR, merge it, then **immediately back-merge `master → dev`** (a fast-forward that gives `dev` the release merge commit). Tag/release on `master`.
- **Invariant:** after each release `master` is an ancestor of `dev` (`dev ⊇ master`). The back-merge restores it; until that's done the guard stays red — so the branches can't silently diverge (no more undetected "reconcile dev with master" debt).

Enforced by [`.github/workflows/branch-sync-guard.yml`](../.github/workflows/branch-sync-guard.yml):
- **Ancestry check** (push to `master`/`dev`, plus nightly) — fails if `master` has commits not on `dev`; fix by back-merging `master → dev`.
- **PR-target check** (PRs to `master`) — fails unless the PR head is `dev`.

The release isn't complete until the back-merge lands and the ancestry check is green.

## CI Tooling

| Gate | Tool | Status |
|------|------|--------|
| Format | Ruff | Active |
| Lint | Ruff | Active |
| Security | Bandit + gitleaks | Active |
| Tests | pytest + pytest-homeassistant-custom-component | Active |
| Coverage | Codecov + SonarCloud | Active |
| HACS | hassfest + hacs/action | Active |

## SonarCloud

- **Project:** `jnctech_homeassistant-mikrotik_router`
- **Org:** `jnctech-homeassistant-mikrotik-router`

### Quality Targets (non-negotiable)

| Metric | Target |
|--------|--------|
| Reliability | Grade A |
| Security | Grade A |
| Maintainability | Grade A |
| Cognitive complexity | ≤15 per function |
| New code coverage | ≥80% |
| Duplication | <3% (new code) |

### Exclusions (see `sonar-project.properties`)
- **Coverage:** platform wiring files, pure data descriptors, const, exceptions
- **CPD:** `sensor_types.py`, `coordinator.py`, `tests/` (intentional structural repetition)

## Review Gates

Beyond the mechanical CI gates above, non-trivial changes go through structured
review before merge. These are process gates (reviewer-run), not CI-enforced.

### Multi-agent audit panels (design & diagnosis)

For non-trivial work — new features, bug root-causing, architectural decisions — the
change is reasoned through a multi-perspective panel before/with implementation:

- **Recon** — read the actual source; establish the facts.
- **Review** — assess the approach against existing patterns and ADRs.
- **Junior-dev questions** — surface the clarifying questions an implementer would ask.
- **Senior-dev challenge** — adversarially attack the proposal: edge cases, the
  load-bearing assumption, simpler alternatives.

Governing rule: **cite-or-null** — every factual claim about the code cites its source
(`file:line`, command/tool output) or is explicitly marked UNVERIFIED. Unknowns are
reported, never resolved with a plausible guess.

### Specialized review passes (pre-PR)

Changed code is run through focused review agents (see the Pre-PR Checklist):

- **Simplification** (`/simplify`) — clarity, reuse, consistency; no behaviour change.
- **Silent-failure hunt** — swallowed errors, inadequate fallbacks, masked failures.
- **Code review** — adherence to the coding standards, ADRs, and project patterns.
- **Domain reviewer** — `coordinator.py` changes also get the committed
  `coordinator-reviewer` agent (ADR-010): helper-extraction (ADR-007), attribute
  filtering (ADR-009), lock discipline, async patterns, UID stability.

Other passes used when relevant: comment-accuracy, type-design, and PR test-coverage
analysis. For live behaviour validation each release, see
[Release Validation](release-validation.md).

## Local Development (Devcontainer)

1. Open the repo in VS Code
2. When prompted, select **Reopen in Container** (or use the command palette: `Dev Containers: Reopen in Container`)
3. The container installs all deps from `requirements_dev.txt` automatically
4. Run tests: `pytest tests/ -v --tb=short`
5. Run with coverage: `pytest -v --cov=custom_components/mikrotik_router --cov-report=term-missing`
6. Lint: `ruff check custom_components/mikrotik_router tests`
7. Format: `ruff format custom_components/mikrotik_router tests`

## Pre-commit Hooks

gitleaks, ruff, bandit, trailing-whitespace, end-of-file-fixer, check-yaml, no-commit-to-branch (master)

## Pre-PR Checklist

1. `pytest tests/ -v` — all green
2. `/simplify` on changed code
3. Silent-failure-hunter on changed files
4. Code review agent
5. **Docs audit:**
   - README/info.md version and feature list match code
   - CHANGE-REGISTER.md has CR entry for this branch
   - ISSUES.md statuses updated for resolved/progressed issues
   - ADR created if decision changes data format, entity identity, API contract, or migration
   - architecture.md updated if new patterns or structural changes introduced
6. Branch up to date, working tree clean
7. PR targets jnctech fork
