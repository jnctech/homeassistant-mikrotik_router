# Issues — Mikrotik Router HACS Integration

## Current Priorities

1. ISS-260512-ci-manifest-drift — CI installs `librouteros` unpinned and resolves to 4.0.1, while `manifest.json` pins `<4.0`; v2.3.14 hotfix was effectively untested against the version it shipped to (external audit 2026-05-12). **Fix in `fix/ci-manifest-drift-guard`.**
2. ISS-260509-mikrotikapi-concurrency — `set_value`/`execute` iterate the librouteros response outside the API lock; fixed in v2.3.16 (#64)
2. ISS-260509-ha-2026.5-untested — HA 2026.5.0 not yet validated against the integration; testing planned
3. ISS-260417-librouteros-4x-break — librouteros 4.0.1 breaks `connect()` kwarg; hotfix v2.3.14 pinned `<4.0` (proper 4.x migration tracked separately)
4. ISS-260320-new-device-discovery — New devices require HA restart (UID tracking in place, dispatcher needs entity guard hardening)

---

## Active

### ISS-260512-ci-manifest-drift — CI tested against the wrong librouteros version
**Type:** Bug (process / supply chain)
**Priority:** High
**Created:** 2026-05-12
**Status:** 🟡 In Progress — fix in `fix/ci-manifest-drift-guard`

**Symptom:**
External audit found that `.github/workflows/ci.yml` was installing `librouteros` unpinned (`pip install mac-vendor-lookup librouteros`), so CI resolved to whatever PyPI returned — currently `librouteros 4.0.1`. `manifest.json` pins `librouteros>=3.4.1,<4.0` (added in commit b6ad8e0 / v2.3.14 to work around the 4.x `connect()` break). HA therefore installs `<4.0` while every CI run since the hotfix tested against 4.x. The v2.3.14 hotfix was effectively shipped untested against the version it was hotfixing.

**Contributing factors:**
- `requirements.txt`, `requirements_dev.txt`, `requirements_tests.txt` all left `librouteros>=3.4.1` without an upper bound — even if CI installed from one of them, it would still resolve to 4.x.
- No CI guard asserts manifest ↔ requirements consistency, so the drift was invisible.
- `release.yml` builds the zip but no CI job verifies the artefact's HACS root-flat layout — an adjacent latent risk.

**Fix:**
1. Pin `librouteros>=3.4.1,<4.0` in all three `requirements*.txt`.
2. CI `tests` job installs from `manifest.json` (the same pattern already proven in the `dependency-audit` job at lines 106–115).
3. New `manifest-drift` job fails the PR if any `requirements*.txt` diverges from `manifest.json`.
4. New `zip-structure` job builds the release zip the same way `release.yml` does and asserts `manifest.json` is at the zip root.

**Follow-up (separate work):**
- `ISS-260512-librouteros-concurrency-adr` — document the API concurrency model (client ownership, lock scope, timeouts, mid-response failure mode).
- `ENH-260512-librouteros-test-matrix` — explicit version matrix (`3.4.1`, latest `3.x`, expected-fail `4.x`) before relaxing the `<4.0` cap.

---

### ISS-260509-mikrotikapi-concurrency — set_value/execute corrupt socket under rapid use
**Type:** Bug
**Priority:** High
**Created:** 2026-05-09
**Status:** 🟡 In Progress — fix in `fix/api-concurrency-lock` (v2.3.16)

**Symptom:**
Rapidly toggling PoE switches in the HA UI causes the integration to disconnect. Traceback shows librouteros' `parse_word` raising `ValueError: not enough values to unpack (expected 3, got 2)` while iterating the response inside `_find_entry`. Subsequent polls then time out with `building list for path /ip/arp : timed out` and the coordinator marks itself disconnected. Reported in #64 (RB5009UPr+S+IN, RouterOS 7.22.2, HA 2026.5.0 / Python 3.14).

**Root cause:**
`MikrotikAPI.set_value()` and `MikrotikAPI.execute()` call `query(path, return_list=False)` which returns the librouteros `Path` object **outside** the API lock. They then call `_find_entry(response, ...)` — which iterates the Path and performs additional socket reads — also **outside** the lock. The 30s coordinator poll (`get_arp`, `get_health`, etc.) acquires the lock and reads from the same TCP socket concurrently. The librouteros parser sees a half-finished sentence from the interleaved reads and raises. `run_script()` already does this correctly (iterates inside the lock), so it was the model for the fix.

**Fix:**
Move `_find_entry` and the subsequent `response.update()` / `response(command, **params)` calls inside the existing `with self.lock:` block in `set_value` and `execute`. No public API changes.

**Why this just surfaced:**
The race has existed since the current `set_value`/`execute` shape was introduced. HA moved to Python 3.14 in [2026.3](https://www.home-assistant.io/blog/2026/03/04/release-20263/#running-on-python-314-), so the runtime change alone doesn't explain the timing — there were no reports of this race during the 2026.3 / 2026.4 windows. The first report (#64) is against 2026.5.0; whether 2026.5.0 changed something specific (service dispatch timing, executor pool sizing, or similar) is still being investigated. Either way the lock fix is correct and the race must be closed regardless of cause. Reporter confirmation requested in the GH thread (rollback test against v2.3.14).

---

### ISS-260509-ha-2026.5-untested — HA 2026.5.0 not yet validated
**Type:** Compatibility
**Priority:** Medium
**Created:** 2026-05-09
**Status:** 🟡 Backlog

**Context:**
HA 2026.5.0 (released 2026-05-06) is the first version where a user (#64) has reported the integration breaking. HA has been on Python 3.14 since [2026.3](https://www.home-assistant.io/blog/2026/03/04/release-20263/#running-on-python-314-), so the runtime alone isn't a sufficient explanation — the race in `set_value`/`execute` was present in 2026.3 and 2026.4 too without prior reports. The integration's CI matrix and local dev environment still target Python 3.13.

**Plan:**
- ✅ Add Python 3.14 to the CI matrix for the test job (done in `chore/sync-v2316-to-dev`)
- 🟡 Validate the integration manually against HA 2026.5.0 (PoE switching, device tracker, sensors, services) — **awaiting hardware/HA instance access**
- 🟡 Diff HA 2026.4 → 2026.5 release notes / commits for service-dispatch or executor-pool changes — **2026.5 release notes searched: no executor or service-dispatch changes called out (notable items were `serialx` migration, entity-ID domain matching, doorbell event standardization, infrared platform); will need to grep HA repo commits between 2026.4 and 2026.5 tags for `executor`, `async_add_executor_job`, `service_call`, `WebSocket` if #64 reproduces on v2.3.16**
- Document any 2026.5.0-specific behaviour in README compatibility notes

---

### ISS-260507-ups-empty-path — Empty `/system/ups` path disconnects the integration
**Type:** Bug
**Priority:** High
**Created:** 2026-05-07
**Status:** 🔴 Closed — fixed in v2.3.15 (PR for `fix/v2.3.15-ups-poe-current`)

**Symptom:**
On routers with the UPS package enabled but no UPS configured, the integration tile shows "Failed setup, will retry: Mikrotik Disconnected" and never loads. Logs:
```
ERROR ... Mikrotik <host> error while path : no such item
DEBUG ... Finished fetching ... data in 3.380 seconds (success: False)
```
Reported in #61 (RouterOS 7.22.1 on CCR2116-12G-4S+).

**Root cause:**
`coordinator.get_ups()` always issued the `/system/ups monitor` query because the parsed `enabled` field defaulted to `True` when `/system/ups` was empty. The `vals` entry for `enabled` uses `source="disabled"` with `reverse=True`; `from_entry_bool` returns `not default` when the source key is missing, so `enabled` becomes `True` for an empty path. RouterOS then rejects `monitor` with "no such item", and `_query_command` treats it as a connection failure.

**Fix:**
Bail out of `get_ups()` early when `/system/ups` returns no entries — clear `ds["ups"]` and skip both `parse_api` and the `monitor` query.

---

### ISS-260507-poe-current-unit — PoE out current displayed 1000× too large
**Type:** Bug
**Priority:** Medium
**Created:** 2026-05-07
**Status:** 🔴 Closed — fixed in v2.3.15 (PR for `fix/v2.3.15-ups-poe-current`)

**Symptom:**
PoE out current sensor displays `~1234.56 mA` for a port drawing ~25 mA (DE locale shows `1.234,56 mA`). Reported in #60 (RB5009UPr+S+IN, RouterOS 7.22.2).

**Root cause:**
`sensor_types.py` declared `poe_out_current` with `native_unit_of_measurement=AMPERE` and `suggested_unit_of_measurement=MILLIAMPERE`. RouterOS reports the value already in milliamperes (test fixtures use raw integers like `180`, `310`), so HA's unit conversion turned `180 A → 180000 mA`.

**Fix:**
Set `native_unit_of_measurement=MILLIAMPERE`; remove `suggested_unit_of_measurement`.

---

### ISS-260417-librouteros-4x-break — librouteros 4.0.1 breaks connection for all users
**Type:** Bug
**Priority:** Critical
**Created:** 2026-04-17
**Status:** 🟡 In Progress — hotfix branch `fix/librouteros-4x-pin` (v2.3.14) pins `librouteros<4.0`. Proper 4.x migration tracked separately.

**Symptom:**
Users on v2.3.13 (or any prior release) see: `connect() got an unexpected keyword argument 'login_methods'. Did you mean 'login_method'?`

**Root cause:**
librouteros 4.0.1 renamed the `connect()` keyword argument `login_methods` → `login_method`. `manifest.json` declared `librouteros>=3.4.1` with no upper bound, so HACS auto-installed 4.0.1 on upgrade. `mikrotikapi.py:102` still passes the old name.

**Related GitHub issues:**
- #55 (reported 2026-04-10) — direct stack trace
- #56 (reported 2026-04-13) — same symptom post-HA-2026.4.2 update; references upstream #477

**Hotfix (v2.3.14):**
- `manifest.json`: pin `librouteros>=3.4.1,<4.0`

**Follow-up (new ISS to be created for future release):**
- Rename kwarg in `mikrotikapi.py` to `login_method`
- Audit remaining librouteros 4.0.1 breaking changes
- Bump floor to `>=4.0`, drop upper bound

---

### ISS-260320-new-device-discovery — New devices require HA restart to appear
**Type:** Feature
**Priority:** Medium
**Created:** 2026-03-20
**Status:** 🟡 In Progress — UID tracking infrastructure done, dispatcher disabled pending entity guard fix

**Done:**
- ✅ `_check_new_uids()` tracks UIDs per entity-relevant data path (`_ENTITY_UID_PATHS`)
- ✅ `_check_entity_exists()` guard improved (early return if entity_id in platform.entities)
- ✅ device_tracker callback ignores dispatches from main coordinator
- ✅ First-run skip prevents redundant entity setup during startup

**Remaining:**
- Harden entity guard: `async_add_entities` still causes "does not generate unique IDs" when called for existing entities even with the guard. Investigate HA's `EntityPlatform.entities` dict timing.
- Re-enable dispatcher once guard is validated in live environment
- Test: add new host mid-run, verify entity created without log errors

---

## Backlog

### ISS-260326-tracker-wireless-detection — Device tracker uses old wireless detection logic
**Type:** Bug
**Priority:** Medium
**Created:** 2026-03-26
**Status:** 🔴 Closed — fixed in feature/v240-issues

**Context:**
`device_tracker.py` lines 157, 169, 199 check `source in ["capsman", "wireless"]` to determine wireless behavior (connection state, icon, attributes). The new `_is_wireless_host()` method in coordinator.py correctly detects wireless clients via bridge host table (fixing hAP ac2), but device_tracker still uses the old check.

**Impact:**
On routers with empty registration tables (hAP ac2 with new WiFi package), wireless clients discovered via bridge table have `source="arp"`, so the device tracker:
- Uses timeout-based `is_connected` instead of registration-based
- Shows wired icon instead of wireless
- Does not show wireless signal/rate attributes

**Fix:**
- Add `is_wireless` bool field to host data in coordinator (set by `_is_wireless_host`)
- Update device_tracker.py to check `self._data.get("is_wireless")` instead of source

---

## Completed

### ISS-260320-new-device-discovery — New devices require HA restart to appear
**Type:** Feature | **Priority:** High | **Created:** 2026-03-20
**Status:** 🟡 Partially done — UID tracking in place, dispatcher disabled pending entity guard hardening

### ISS-260320-refactor-dedup — Refactor duplicated patterns
**Type:** Refactoring | **Priority:** Medium | **Created:** 2026-03-20
**Status:** 🔴 Closed — firewall helper extracted (feature/v240-issues), switch toggle extracted (PR #51), apiparser extracted (PR #30). Entity description mixin deferred.

### ISS-260320-test-coverage — Increase test coverage to ≥80%
**Type:** Testing | **Priority:** High | **Created:** 2026-03-20
**Status:** 🔴 Closed — 86% coverage achieved (565 tests, Phase 5 PR)

### ISS-260321-cognitive-complexity — Reduce cognitive complexity to ≤15 per function
**Type:** Quality | **Priority:** High | **Created:** 2026-03-21
**Status:** 🔴 Closed — fixed in refactor/legacy-cleanup (PR #30 + PR #51)

### ISS-260321-silent-failures — Silent failure patterns from security audit
**Type:** Bug/Quality | **Priority:** Medium | **Created:** 2026-03-21
**Status:** 🔴 Closed — fixed in refactor/legacy-cleanup (PR #30 + PR #51)

### ISS-260326-slow-load — Startup bottlenecks blocking HA loading
**Type:** Bug/Performance | **Priority:** High | **Created:** 2026-03-26
**Status:** 🔴 Closed — fixed in v2.3.12 (claude/fix-homeassistant-slow-load)

### ISS-260320-deprecated-datetime — Remaining naive datetime.now() calls
**Type:** Bug | **Priority:** Medium | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.12 (claude/fix-homeassistant-slow-load)

### ISS-260325-attribute-bloat — ~1300 junk attributes on interface and tracker entities
**Type:** Bug/Quality | **Priority:** High | **Created:** 2026-03-25
**Status:** 🔴 Closed — fixed in v2.3.11-beta.1 (feature/attribute-cleanup)

### ISS-260325-mangle-dedup — Mangle rules with different interfaces removed as duplicates
**Type:** Bug | **Priority:** High | **Created:** 2026-03-25
**Status:** 🔴 Closed — fixed in PR #40 (fix/mangle-duplicate-interface)

### ISS-260324-arp-incomplete — ARP "incomplete" status incorrectly shows device as home
**Type:** Bug | **Priority:** High | **Created:** 2026-03-24
**Status:** 🔴 Closed — fixed in v2.3.10 (PR #38)

### ISS-260322-upstream-frs — Port upstream feature requests
**Type:** Feature | **Priority:** High | **Created:** 2026-03-22
**Status:** 🔴 Closed — released in v2.3.9 (PR #32)

### ISS-260320-options-flow-crash — Options flow crash on HA 2025.12+
**Type:** Bug | **Priority:** Critical | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)

### ISS-260320-blocking-io — Blocking I/O in async methods
**Type:** Bug | **Priority:** High | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)

### ISS-260320-deadlock-run-script — Deadlock in mikrotikapi.py run_script
**Type:** Bug | **Priority:** Critical | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)

### ISS-260320-sonarcloud-token — SonarCloud token expired
**Type:** Infrastructure | **Priority:** Medium | **Created:** 2026-03-20
**Status:** 🔴 Closed — burner token set, SonarCloud passing

### ISS-260320-dispatcher-spam — Duplicate entity log errors from update_sensors
**Type:** Bug | **Priority:** High | **Created:** 2026-03-20
**Status:** 🔴 Closed — dispatcher disabled in v2.3.8 (PR #26). Proper fix tracked as ISS-260320-new-device-discovery

### ISS-260320-ruff-migration — Migrate from Black+flake8 to Ruff
**Type:** Quality | **Priority:** Low | **Created:** 2026-03-20
**Status:** 🔴 Closed — completed in PR #29 (feature/tests-and-refactor). CI uses ruff, all files formatted.
