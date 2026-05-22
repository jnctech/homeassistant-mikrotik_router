# ADR-010: Claude Code Tooling Baseline + Mechanical Quality Gates via pyproject.toml

**Date:** 2026-05-22
**Status:** Accepted

## Context

Quality bars in this repo (SonarCloud Grade A, cognitive complexity ≤15 per function, ≥80% new-code coverage, zero ruff errors) were documented in `CLAUDE.md` and `docs/quality-gates.md` but enforced *socially* — by reviewer attention, by memory, by the pre-PR checklist that contributors had to remember to run. The CI workflows enforced ruff lint, ruff format, hassfest, bandit, gitleaks, manifest-drift, zip-structure — but not complexity, not coverage thresholds, not the pre-PR checklist itself.

Three pieces of drift exposed this:

1. **ISS-260512-ci-manifest-drift** — runtime deps in `manifest.json` (pinned `<4.0`) had quietly diverged from `requirements*.txt` (unpinned, resolved to 4.x). v2.3.14 was shipped *untested* against the version it was hotfixing. The fix (PR #69) added a CI guard, but the broader pattern — *two sources of truth for the same fact* — remained in tool config (ruff in `.pre-commit-config.yaml` args, complexity in `setup.cfg` flake8 block that nothing read, etc.).

2. **AGENTS.md / CLAUDE.md duplication** — `AGENTS.md` was a tracked near-duplicate of `CLAUDE.md` with stale "Codex Sonnet/Opus" branding from an earlier toolchain choice. Two near-identical files invite divergence; one will be updated, the other won't. (The same pattern is flagged in the sibling `gedcom-tree-parser` project, which decided not to adopt `AGENTS.md` for the explicit reason that it would "duplicate `CLAUDE.md`, would drift" — a deliberate choice grounded in the user's own audit work, see "Decision §3" below.)

3. **Stale config blocks** — `setup.cfg` carried `[flake8]` and `[pylint]` sections that ruff replaced in ADR-003. Leftover dead config is the exact failure mode that produced ISS-260512.

Concurrently, the Ultimate Claude Code Guide ([cc.bruniaux.com/guide/ultimate-guide/](https://cc.bruniaux.com/guide/ultimate-guide/)) documents a baseline `.claude/` shape (committed `settings.json` with hooks, `commands/`, `agents/`, `skills/`) that this repo had not adopted — contributors got no Claude-Code-level guardrails specific to this codebase, only the user-global `~/.claude/CLAUDE.md`.

## Decision

### 1. Consolidate Python tool config into `pyproject.toml`

`pyproject.toml` is the **single source of truth** for ruff (lint + format + complexity), pytest, and coverage. `setup.cfg` is deleted. `Pipfile` is deleted (legacy, no tooling consumed it).

The integration is not pip-distributed (HACS installs it into `custom_components/mikrotik_router/`); `pyproject.toml` is tool-config-only, with no `[project]` or `[build-system]` block. Runtime dependencies remain in `manifest.json` with CI manifest-drift guard (PR #69) asserting `requirements*.txt` consistency.

### 2. Mechanically enforce complexity ≤15 and coverage ≥80%

Two quality bars move from documentation to CI gates:

- `[tool.ruff.lint.mccabe]` `max-complexity = 15` — enforces ADR-007 retroactively. Verified on adoption: zero violations in `custom_components/mikrotik_router/`.
- `[tool.coverage.report]` `fail_under = 80` — converts the documented 80% target into a `pytest --cov` exit-code gate.

Per-file ignore for `tests/**` on C901 — table-driven test patterns legitimately exceed the gate; the gate applies to integration code, not test scaffolding.

### 3. Delete `AGENTS.md`

This is a Claude-only repo. `CLAUDE.md` is the canonical Claude Code project memory file (per the Ultimate Guide cheatsheet "Memory & Settings" table). Cross-agent (`AGENTS.md` for Codex/Aider) is not a use case here, and a near-duplicate file is documentation drift waiting to happen.

### 4. Adopt a committed `.claude/` scaffolding

A baseline that any cloning contributor inherits:

- `.claude/settings.json` — team-shared permissions allowlist (read-only Bash wildcards: ruff, pytest, pre-commit, git read-only, jq, cat on manifest) + hook declarations.
- `.claude/hooks/pre-bash-force-push-guard.sh` — PreToolUse Bash hook; blocks `git push --force` targeting `master`/`main`. Exit 2 to block. Dev/feature branches pass through.
- `.claude/hooks/post-edit-ruff.sh` — PostToolUse on Edit/Write/MultiEdit for `*.py` files; runs `ruff check --fix` on just the touched file. Non-blocking (exit 0). Tight feedback loop per Ultimate Guide §9.5.
- `.claude/hooks/user-prompt-smart-suggest.sh` — UserPromptSubmit; detects PR-creation intent and prints a one-line reminder of the pre-PR checklist unless the prompt already references it. Non-blocking.
- `.claude/commands/pre-pr-check.md` — slash command running the documented pre-PR sequence (ruff lint + format + pytest with coverage + doc-update checks + version-triplet check + PR-target sanity).
- `.claude/commands/release-bump.md` — atomic version-triplet update across `manifest.json`, `README.md`, `info.md`, plus CHANGE-REGISTER.md staged entry. Mechanises the three-file lockstep that CR-260417 / CR-260507 / CR-260509 repeatedly tripped on.
- `.claude/agents/coordinator-reviewer.md` — specialised review agent (Sonnet) for `coordinator.py` changes; checks ADR-007 helper-extraction, ADR-009 attribute filtering, lock discipline (ISS-260509), HA async patterns, UID stability, coverage. Coordinator.py is the highest-touch file in the repo and warrants a domain-aware reviewer.
- `.claude/skills/claude-md-sizing/SKILL.md` — encoded audit of the Ultimate Guide's "120 lines hard limit + pointer strategy" rule. Used on demand; CLAUDE.md is currently 48 lines (well under) but as the repo grows, drift is inevitable.

Hooks use Git Bash on Windows (`#!/usr/bin/env bash`), matching the convention established in the user's other Python project (`gedcom-tree-parser`), which standardised on Git Bash on Windows for all agent operations (its PLAN.md spells out: "Development host is a Windows PC. You [the agent] run inside Git Bash."). The Ultimate Guide's `examples/hooks/bash/` directory uses the same `#!/usr/bin/env bash` shape, so this convention also keeps the hooks portable to Linux dev containers if the test workflow ever moves off Windows.

## Alternatives Considered

### A. Leave tool config in `setup.cfg` + pre-commit args
Rejected. Three sources of truth (setup.cfg flake8 block, pre-commit ruff args, no centralised config) is exactly the drift pattern that produced ISS-260512. IDE integration also misses ruff config that lives in pre-commit args.

### B. Build a full `[project]` + `[build-system]` section so `pip install -e ".[dev]"` works
Considered. Pattern used in `gedcom-tree-parser/CLAUDE.md`. Rejected for this repo because the integration is not pip-distributed; adding a build backend (hatchling/setuptools) adds tooling complexity for no production benefit. Re-evaluate if the dev workflow ever needs editable install.

### C. PowerShell hooks (`.ps1`) instead of Bash
Considered because the development host is Windows. Rejected — the user's established convention (gedcom-tree-parser, config repo) is Git Bash on Windows; the Ultimate Guide's `examples/hooks/bash/` directory is the canonical reference. Bash hooks work identically on Linux dev containers, which simplifies any future move to docker-dev based development.

### D. Adopt Claudeception (self-evolving skills) and Claude Reflect System
Considered. Rejected for this iteration. Both add governance burden (review proposed skill updates each session; audit skill history quarterly per Ultimate Guide "Security Warnings" table). Single-maintainer public repo with stable workflow — overhead exceeds value. Reassess when PR throughput exceeds ~5/week or when contributor count grows.

### E. Just the C901 complexity gate, defer the rest
Considered. Rejected because the `.claude/` scaffolding is the leverage — without it, contributors don't know about the C901 gate until CI fails their PR. The committed scaffolding teaches the workflow on first session.

## Consequences

### Positive

- **Drift removed across four surfaces:** ruff config now lives in one file; complexity bar mechanically enforced; coverage bar mechanically enforced; pre-PR checklist exposed as a `/pre-pr-check` slash command instead of memory-only.
- **Tighter feedback loop:** `post-edit-ruff.sh` surfaces lint issues immediately after Edit, not at pre-commit / CI time.
- **Force-push safety:** `pre-bash-force-push-guard.sh` makes accidental destruction of release history materially harder.
- **Lower onboarding friction:** a new contributor in this repo gets project-specific Claude Code guardrails on first session, with documented expectations.
- **Future-proof:** `claude-md-sizing` skill catches CLAUDE.md drift before it becomes a 200-line wall.

### Negative

- **Local ruff version drift exposed:** local ruff (0.11.4) and pre-commit-pinned ruff (v0.9.0) disagree on format style for 26 files (style-only, no lint issues). Surfaced during T2.1 verification. This pre-existed the PR — pre-commit `ruff format` wasn't running on commit, so format drift accumulated silently. **Tracked as a new issue (ISS-260522-ruff-format-drift) for a separate PR** to (a) re-format on a pinned ruff version, (b) pin ruff version in CI to match pre-commit, (c) optionally autoupdate.
- **More files for contributors to learn:** `.claude/` adds 8 new files. Mitigated by self-documenting filenames + inline comments + this ADR.
- **PreToolUse hook tax:** every Bash invocation incurs a sub-100ms shell-script overhead. Negligible in practice; can be measured if it becomes a problem.

### Neutral

- No change to the integration's runtime behaviour — this is pure tooling/process.
- SonarCloud configuration unchanged; the new gates are *additive* to existing CI, not replacements.
- ADR-003, ADR-007, ADR-009 unchanged — this ADR mechanises them rather than supersedes them.
