# ADR-025: Config entry schema version 3, aligned with upstream

**Date:** 2026-11-14
**Status:** Accepted — fixes #172.

## Context

This integration shares its domain (`mikrotik_router`) with the upstream `tomaae` integration
it was forked from. Users switch between the two through HACS, and their config entries carry
over.

In September 2026 upstream moved its config entries to **version 3**: 3.1 moved the
integration-wide `zone` option into per-entity device-tracker options (the HA 2026.8 zone
model), and 3.3 removed integration-set temperature display units. Our flow handler declared
`VERSION = 2`.

Home Assistant refuses an entry whose major version is higher than the handler's, and does so
in `ConfigEntry.async_migrate` **before** calling the integration's `async_migrate_entry`. The
entry fails to load with "Config entry … has version 3 which is higher than the current
version 2" (#172). Nothing in our migration code can recover it; only the handler version
decides.

An upstream 3.x entry otherwise loads fine here. Its `data` keys are the same as ours
(`host`, `port`, `username`, `password`, `ssl`, `verify_ssl`, `name`), and every option we read
has a default. The keys upstream added or removed (`device_tracker_scan_interval`, `zone`) are
ignored or default.

## Decision

- The flow handler declares **`VERSION = 3`, `MINOR_VERSION = 1`**, from
  `CONFIG_ENTRY_VERSION` / `CONFIG_ENTRY_MINOR_VERSION` in `const.py`.
- `async_migrate_entry`:
  - **1 → 3.1:** adds `verify_ssl` (the old 1 → 2 step), then sets 3.1.
  - **2 → 3.1:** no data change, version number only.
  - **3.x:** left as it is, including upstream's 3.2 / 3.3. Minor versions are backwards
    compatible by HA convention, and we don't rewrite another integration's minor number.
  - **> 3:** refused (`return False`). Current HA refuses these before calling us; older HA
    versions within our floor do call the handler, and must not load an unknown schema blind.
- Version 3 here means "the schema this integration reads", not "upstream's 3.x migrations
  have run". We don't port upstream's per-entity zone or temperature migrations: our code keeps
  the integration-wide `zone` option and doesn't set temperature display units.

Existing entries are rewritten to 3.1 (option (a) in the review), rather than accepting
version 2 and 3 side by side without a rewrite (option (b)). That keeps the stored version
equal to the handler's, which is what HA expects, and avoids re-running migration on every
start.

## Alternatives Considered

**Accept both 2 and 3 without rewriting (option (b)).** Avoids the rollback trap below, but
leaves entries permanently "needing migration": HA calls `async_migrate_entry` on every start,
and a future HA check that migration actually advanced the version would break it.

**Port upstream's 3.1 / 3.3 migrations.** They exist to serve upstream's code paths (per-entity
tracker zones, no integration-set temperature unit), which we don't have. Porting them would
change behaviour for our users with no benefit.

**Tell affected users to delete and re-add the integration.** Loses entity customisations and
history linkage. Not acceptable for a problem we can fix in code.

## Consequences

- Entries created by upstream (3.x) load in this integration (#172).
- **Rollback trap:** after upgrading, an entry is at 3.1. Rolling back to **v2.3.23 or older**
  hits the same "higher than the current version 2" error. To roll back, restore an HA backup
  taken before the upgrade, or delete and re-add the integration. The release note must say
  so.
- A user who moves from upstream to here loses a non-`home` zone chosen in upstream's
  per-entity tracker options; device trackers fall back to our integration-wide `zone` option
  (default `home`), which they can set in our options flow.
- Moving from here back to upstream: our 3.1 entries skip upstream's `< 3` zone migration, so
  upstream's trackers use its default zone; upstream's 3.2 / 3.3 steps run normally.
- If upstream moves to version 4, the same failure returns. Upstream entry versions should be
  checked when reviewing upstream changes.
