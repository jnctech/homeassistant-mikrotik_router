# ADR-012: Store runtime data on `ConfigEntry.runtime_data`

**Date:** 2026-06-08
**Status:** Accepted

## Context

The integration stored its per-entry runtime objects — the two coordinators, wrapped in `MikrotikData` — in `hass.data[DOMAIN][entry_id]`, and looked them up by `entry_id` in the cleanup services, the platforms, and diagnostics. Home Assistant's current guidance, and the Integration Quality-Scale **`runtime-data`** rule (Bronze), is to store per-entry runtime state on the typed `ConfigEntry.runtime_data` instead.

The old pattern: (a) an untyped global dict keyed by `entry_id`; (b) manual lifecycle (set in `async_setup_entry`, `pop` in `async_unload_entry`); (c) "is this entry loaded?" is implicit; (d) no typed access to the stored object.

## Decision

1. Introduce `type MikrotikConfigEntry = ConfigEntry[MikrotikData]` (`coordinator.py`).
2. `async_setup_entry` assigns `config_entry.runtime_data = MikrotikData(...)`; Home Assistant clears it on unload (no manual `pop`).
3. All readers use `config_entry.runtime_data`:
   - the cleanup services via `_get_mikrotik_data()`, which resolves the entry with `hass.config_entries.async_get_entry(entry_id)` and validates `isinstance(runtime_data, MikrotikData)` — logging **"not found in registry"** vs **"not loaded (state=…)"** distinctly;
   - `entity.py`, `device_tracker.py`, `diagnostics.py` read it directly (they only run after setup populates it).
4. `async_unload_entry` removes the shared services only when no *other* loaded entry remains (via `hass.config_entries.async_loaded_entries(DOMAIN)`), replacing the old `hass.data[DOMAIN]`-emptiness check. The filter excludes the current entry by `entry_id`, so it is correct whether or not HA still lists the unloading entry as loaded.
5. Entry-point handlers are typed `MikrotikConfigEntry` for typed `runtime_data` access (`async_migrate_entry` excepted — `runtime_data` isn't populated at migrate time).

## Consequences

**Positive**
- Satisfies the Bronze `runtime-data` rule.
- Typed access to runtime state; the typed `ConfigEntry` is the **seed of the broader typed data model** for the planned coordinator decomposition.
- Less manual lifecycle code — HA owns teardown; no `setdefault`/`pop`.
- Better diagnostics: a stale `entry_id` and a not-loaded integration now produce different, actionable log lines (the old code's "not found" was misleading for the not-loaded case).

**Trade-offs / risks**
- Correctness rests on HA's documented contracts (`runtime_data` auto-cleared on unload; `async_loaded_entries` returns loaded entries). The unload teardown is written to be correct under either ordering of the unload transition.
- The migration touched the cleanup-service tests (they now use a `runtime_data`-backed mock via `_hass_with_loaded_entry`).

## Verification

- **593 passed, 5 skipped** (devbox `python:3.13`, `__pycache__` cleared — see note below).
- Full pre-PR gate: code-review (no blocking issues), silent-failure-hunter (one MEDIUM applied — split the not-found/not-loaded diagnostics, log `entry.state`), code-simplifier (typed `async_reload_entry`/platform `async_setup_entry`, `any()` for the unload check). All applied.

> **Testing-hygiene note:** an earlier "593 passed" for this branch was a *false green* from stale root-owned `__pycache__` on the devbox (re-extracting a branch over the same dir ran old bytecode). It hid 8 broken cleanup-service tests. The devbox runbook now mandates clearing `__pycache__` and running with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.

## Notes

The firmware-version single-source-of-truth prototype (branch `proto/fw-version-sot`) carries a draft **ADR-012**; since this runtime-data ADR lands first on `dev`, that prototype ADR renumbers to **ADR-013** when it lands.
