# CLAUDE.md - Mikrotik Router HACS Integration

## Project

- **Domain:** `mikrotik_router` | **Version:** 2.3.23 | **IoT:** `local_polling` (30s)
- **HA Min:** 2024.3.0 | **Python:** 3.13 | **Fork of:** `tomaae/homeassistant-mikrotik_router`
- **Deps:** `librouteros>=3.4.1,<5`, `mac-vendor-lookup>=0.1.12`
- **Platforms:** sensor, binary_sensor, switch, button, device_tracker, update

## AI Model Selection

Under the maintainer's current Claude Max subscription, default to **Opus 5.5** for all work in this repo — bug fixes, refactoring, tests, architecture, design. Co-author tag: `Claude Opus 5.5`.

The per-context tiering (Sonnet for routine, Opus for design) only applies if the maintainer is back on a metered plan; revisit then.

## Quality Targets (non-negotiable)

- SonarCloud Grade A: reliability, security, maintainability
- Cognitive complexity ≤15 per function
- New code coverage ≥80%
- Zero ruff errors

## Testing

- Tests require Docker on Windows — `homeassistant` won't pip install natively
- Refactoring pattern: ADR-007 (see `docs/decisions/`)

## Standards & References

- [HA Coding Standards](docs/ha-coding-standards.md) — async rules, entity patterns, datetime, type hints
- [Quality Gates](docs/quality-gates.md) — CI, SonarCloud targets, pre-commit, pre-PR checklist
- [Architecture Notes](docs/architecture.md) — coordinator design, API client, helper structure

## Pre-PR Checklist (overrides global)

See [Quality Gates](docs/quality-gates.md) for full checklist. Key additions vs global:
- PR description is the change record (Summary / Post-Deploy Actions / Test Plan); reference issues with `Fixes #N` / `Closes #N`
- ADR required for data format, entity identity, API contract, or migration changes
- info.md and README version match manifest.json

## Git

- **Branches:** `master` (main), `dev`, `feature/<desc>`, `fix/<desc>`
- **Commits:** Conventional (`fix:`, `feat:`, `docs:`, `refactor:`, `chore:`)
- **PR target:** jnctech fork, never upstream unless explicitly told
- **Sync model (keep `dev ⊇ master`):** features → `dev` → `master`; cut releases by **merging** `dev → master`. If a hotfix lands on `master` first, **back-merge `master → dev` with a real merge commit** — never re-apply the same change as a parallel "dev parity" commit (that manufactures permanent divergence; see ISS-260608). Invariant: `git merge-base --is-ancestor origin/master origin/dev` is always true.

## Change tracking

Since 2026-10-15, changes are tracked in **git + GitHub Issues**:
- **Change record:** conventional commits plus the PR description. There are no new `CR-` IDs.
- **Issues:** tracked in GitHub Issues (`gh issue …`, always with `-R jnctech/homeassistant-mikrotik_router`). New issue titles carry a date prefix (`ISS-|ENH-YYMMDD-<topic>`). Close them from the PR, noting that `Fixes #N` only fires once the commit reaches `master`, i.e. at release.
- **`docs/CHANGE-REGISTER.md` and `docs/ISSUES.md` are deprecated.** They are frozen as read-only history: never write to them, and if a write is denied, don't route around it. Historical `CR-`/`ISS-` IDs in them and in ADRs remain valid references.
- **Session state:** goes in `.remember/remember.md` (gitignored), so anything load-bearing must also be committed.

## Tracking visibility (public vs private)

This is a **public** fork. GitHub Issues/PRs, `docs/FEATURE-POLL.md`, `docs/architecture.md`, and `docs/decisions/ADR-*` are visible to every user. Keep them **integration-facing**: bugs, enhancements, ADRs, and changes about the code/behaviour, with no homelab specifics.

Anything sensitive or internal goes in **`docs/internal/`** (gitignored — see `.gitignore`): tokens, MACs, internal hostnames, router captures/debug dumps, and pure session/process meta. When filing, ask: *is this about the integration's code (public), or does it carry homelab specifics / session meta (→ `docs/internal/`)?*
