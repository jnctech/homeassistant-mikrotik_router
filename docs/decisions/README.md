# Architecture Decision Records

Lightweight records of key design decisions for mikrotik_router HACS integration.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-arp-failed-filtering.md) | ARP Failed-Status Filtering Strategy | Accepted |
| [ADR-002](ADR-002-dispatcher-new-devices.md) | New Device Discovery Without Log Spam | Proposed |
| [ADR-003](ADR-003-ruff-migration.md) | Ruff Replaces Black+flake8 | Accepted |
| [ADR-004](ADR-004-blocking-io-wrapping.md) | Blocking I/O Wrapped with async_add_executor_job | Accepted |
| [ADR-005](ADR-005-lock-context-managers.md) | Lock Context Managers Replace Manual acquire/release | Accepted |
| [ADR-006](ADR-006-naive-datetime-removal.md) | Replace naive datetime.now() with HA utility | Accepted |
| [ADR-007](ADR-007-complexity-reduction-extraction.md) | Cognitive Complexity Reduction via Helper Extraction | Accepted |
| [ADR-008](ADR-008-upstream-feature-port.md) | Port Upstream Feature Requests (#310, #321, #334, #298) | Accepted |
| [ADR-009](ADR-009-attribute-filtering-by-hardware.md) | Entity Attribute Filtering by Hardware Capability | Accepted |
| [ADR-010](ADR-010-claude-tooling-baseline.md) | Claude Code Tooling Baseline + Mechanical Quality Gates via pyproject.toml | Accepted |

## Template

```markdown
# ADR-NNN: Title

**Date:** YYYY-MM-DD
**Status:** Accepted | Superseded by ADR-NNN | Deprecated

## Context
What problem or need prompted this decision?

## Decision
What did we decide, and what are the key design choices?

## Alternatives Considered
What other approaches were evaluated and why were they rejected?

## Consequences
What are the trade-offs, risks, and follow-on constraints?
```

## Notes

- ADRs are **immutable once accepted** — never edit a decision after the fact. If the decision changes, create a new ADR marked "Supersedes ADR-NNN" and update the old one to "Superseded by ADR-NNN".
- ADRs live alongside the code — check `docs/ISSUES.md` for tactical issues that may eventually warrant an ADR.
- For cross-project patterns, see `~/Code/develop/homelab-docs/` (future: extract template there).
