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
| [ADR-011](ADR-011-capsman-attributes.md) | CAPsMAN AP-virtual interface — additive attribute, no source flip | Accepted |
| [ADR-012](ADR-012-config-entry-runtime-data.md) | Store runtime data on `ConfigEntry.runtime_data` (typed) | Accepted |
| [ADR-013](ADR-013-entity-naming-disambiguation.md) | Entity-naming disambiguation for colliding clients + DHCP servers | Accepted |
| [ADR-014](ADR-014-entity-golden-tests.md) | Entity-golden test framework (syrupy snapshots over a mocked API boundary) | Accepted |
| [ADR-017](ADR-017-poe-energy-accumulation.md) | PoE-out energy accumulation (measured + nameplate estimate) | Accepted |
| [ADR-018](ADR-018-netwatch-name-precedence.md) | Netwatch entity naming by `name` (name→comment→static precedence) | Accepted |

## Numbering — assign before you write

ADR numbers are **sequential and never reused**. Before starting an ADR, pick the
**next unused** number from the table below, and check the reserved/claimed list so
you don't collide with a number that is spoken-for but not yet on `dev`. Contributors:
the maintainer confirms the number and adds the index row **at merge** — if in doubt,
name your file `ADR-NEXT-<slug>.md` and we'll assign it.

**Next unused ADR number: `020`.**

Reserved / claimed (not yet merged, so absent from the table above — do **not** reuse):

| ADR | Reserved for | State |
|-----|--------------|-------|
| 015 | librouteros 4.x migration / salvage (`ISS-260417`) | Reserved (unwritten) |
| 016 | Coordinator decomposition (deferred) | Reserved (unwritten) |
| 019 | LTE modem sensors — PR [#116](https://github.com/jnctech/homeassistant-mikrotik_router/pull/116) (@zvldz) | Claimed, pending merge |

> **Why this section exists:** the index above previously stopped at ADR-014 while
> 015/016 were reserved and 017/018 had already shipped — invisible to anyone picking
> a number. A contributor reasonably grabbed 015 (→ renumbered to 019 at review). Keep
> this list current and **add the index row when an ADR merges** so the gap can't reopen.

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
