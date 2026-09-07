# Contributing

Thanks for contributing to the Mikrotik Router integration. This is a
maintained fork of `tomaae/homeassistant-mikrotik_router` with its own quality
bar; the notes below are the conventions we actually apply when reviewing PRs,
distilled from recent contributions. Following them up front gets your PR merged
faster.

Contributions are very welcome — including from AI-assisted workflows. What we
review is the **result**, against the standards below.

## Before you open a PR

- **Target `dev`, not `master`.** Features and fixes merge to `dev`; `master` is
  release-only. Branch as `feature/<desc>` or `fix/<desc>`.
- **Format with Ruff** (`ruff format` + `ruff check`) — zero lint errors.
- **Add tests** (see [Testing](#testing)) and run the suite locally.
- **Fill in the PR template** and link the issue you're addressing.

You do **not** need to touch `README.md` / `info.md` "What's New", the change
register, or the issue tracker — the maintainer folds those in at merge and
credits you there. Focus on the code, tests, and (if applicable) an ADR.

## Conventions we enforce

These are the recurring review points — addressing them pre-empts a change-request.

### 1. Null-not-guess (no fabricated values)

A field that is **absent, empty, or non-numeric must resolve to `None`/`unknown`,
never to a plausible-but-wrong default.** Do not synthesise a value (e.g. a "now"
timestamp for a missing session-uptime, or a version of `0` standing in for
"unknown"). If the router didn't report it, the sensor should read `unknown`.

### 2. Clear stale data on early-return paths

When a fetch's source is empty or you early-return, **reset the dataset slot to
`{}`** so a value that disappears mid-session doesn't linger as if current.
`get_ups()` is the pattern to follow:

```python
def get_something(self) -> None:
    result = self.api.query("/some/path")
    if not result:
        _LOGGER.debug("Mikrotik %s /some/path returned no data", self.host)
        self.ds["something"] = {}   # clear stale data
        return
    ...
```

### 3. Log absent-data returns at DEBUG

Every "no data / branch skipped" return should emit a `_LOGGER.debug(...)` so
"the router reported nothing" is distinguishable from "this code never ran".
Consistent with `get_system_health` / `get_capabilities`.

### 4. Capability-gate new data sources

New fetches that only apply to some hardware must be gated, not run
unconditionally. Detect support in `get_capabilities()` and gate the fetch:

```python
self.support_lte = bool(self.api.query("/interface/lte"))
...
await self._run_if_enabled(self.get_lte_signal, requires=self.support_lte)
```

Routers without the feature then get **no new entities** (empty dataset →
nothing created). Verify the detection probe is *safe* on non-supporting
hardware (returns empty, not an error).

### 5. Redact identifiers

Personally-identifying or sensitive fields (IMEI/IMSI/ICCID, serials, keys) are
collected but shipped `entity_registry_enabled_default=False` **and** added to
`TO_REDACT` in `const.py` so diagnostics don't leak them.

### 6. Keep private homelab data out of public files

A CI guard (`homelab-leak`) blocks private IPs/MACs in public, integration-facing
files. Use documentation ranges / example OUIs in docs and non-test code. (`tests/`
is exempt as example data — but prefer generic subnets there too.)

## Testing

Tests run under Docker (the `homeassistant` package won't pip-install natively on
Windows). New tests must be **spec'd / real-typed — do not lean on unspecced
`MagicMock` "yes-man" objects** that pass regardless of typos or renames.

- **Coordinator logic:** drive the *real* method against a canned API boundary —
  build the coordinator with `make_coordinator(api_responses={...})` (which uses
  the real `MikrotikCoordinator` + `MockMikrotikAPI`) and assert on the resulting
  `ds[...]` **behaviour**, not internal representation. See the LTE tests in
  `tests/test_coordinator.py` for the shape, including the stale-clear and
  absent-field cases.
- **Entity surface:** build the **real** `Mikrotik*EntityDescription` dataclass
  (not a mock) and assert `native_value` / `is_on` / disabled-by-default. The
  entity-golden framework (ADR-014) is the direction for snapshot coverage.
- Cover the **absent / disappeared / non-numeric** paths, not just the happy path
  — those are where null-not-guess and stale-clear bugs hide.

## ADRs (design decisions)

Data-format, entity-identity, API-contract, or migration changes need an ADR in
`docs/decisions/`. **Assign the number before you write** — take the *next unused*
number and check the reserved/claimed list in
[`docs/decisions/README.md`](docs/decisions/README.md#numbering--assign-before-you-write)
so you don't collide with a reserved or in-flight number. If unsure, name the file
`ADR-NEXT-<slug>.md`; the maintainer assigns the number and adds the index row at
merge.

## Hardware-gated features

If your change targets hardware the maintainer doesn't have (LTE modems, SFP,
specific PoE boards), **live-validate on your device** and say so in the PR
(model, RouterOS version, what you observed). Contributor hardware validation is
often what lets a feature ship at all.

## What happens at merge

We preserve your authorship (merge commit, not squash-over) and credit you in the
release notes / change register. CI on fork PRs needs a maintainer to approve the
run — don't worry if checks haven't started yet.
