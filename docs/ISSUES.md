# Issues — Mikrotik Router HACS Integration

## Current Priorities

1. ISS-260320-options-flow-crash — Options flow crash on HA 2025.12+ (#470, #471)
2. ISS-260320-blocking-io — Blocking I/O in async methods
3. ISS-260320-sonarcloud-token — SonarCloud token expired

---

## Active

### ISS-260320-options-flow-crash — Options flow crash on HA 2025.12+
**Type:** Bug
**Priority:** Critical
**Created:** 2026-03-20
**Status:** 🟢 Active — fix in PR #19
**Source:** GitHub #470, #471

**Done:**
- ✅ Root cause identified: broken conditional `__init__` in `OptionsFlowWithConfigEntry` subclass
- ✅ Fix implemented: remove custom `__init__`, delegate to parent which stores as `_config_entry`

**Remaining:**
- Deploy to HA for validation
- Merge PR #19
- Create release v2.3.6
- Comment on upstream issues #470, #471

---

### ISS-260320-blocking-io — Blocking I/O in async methods
**Type:** Bug
**Priority:** High
**Created:** 2026-03-20
**Status:** 🟢 Active — fix in PR #19

**Done:**
- ✅ All `switch.py` async methods wrapped in `async_add_executor_job`
- ✅ `button.py` `async_press` wrapped
- ✅ `update.py` `async_install` wrapped (both RouterOS and RouterBOARD)
- ✅ `config_flow.py` `api.connect()` wrapped

**Remaining:**
- Deploy to HA for validation
- Merge PR #19

---

### ISS-260320-deadlock-run-script — Deadlock in mikrotikapi.py run_script
**Type:** Bug
**Priority:** Critical
**Created:** 2026-03-20
**Status:** 🟢 Active — fix in PR #19

**Done:**
- ✅ All manual `lock.acquire()`/`release()` replaced with `with self.lock:` context managers
- ✅ `run_script()` deadlock on missing script fixed

**Remaining:**
- Deploy to HA for validation
- Merge PR #19

---

### ISS-260320-sonarcloud-token — SonarCloud token expired
**Type:** Infrastructure
**Priority:** Medium
**Created:** 2026-03-20
**Status:** 🟢 Active

**Remaining:**
- Regenerate SONAR_TOKEN in GitHub repo secrets
- Verify SonarCloud analysis runs on next push

---

## Backlog

### ISS-260320-ruff-migration — Migrate from Black+flake8 to Ruff
**Type:** Quality
**Priority:** Low
**Created:** 2026-03-20
**Status:** 🟡 Backlog

**Remaining:**
- Replace Black + flake8 with Ruff in pre-commit and CI
- Add `pyproject.toml` with Ruff config
- Update CI workflow

---

### ISS-260320-deprecated-datetime — Remaining naive datetime.now() calls
**Type:** Bug
**Priority:** Medium
**Created:** 2026-03-20
**Status:** 🟡 Backlog
**Source:** coordinator.py lines 577, 606, 1547

**Remaining:**
- Replace `datetime.now()` with `homeassistant.util.dt.now()`
- Audit all datetime usage in coordinator.py

---

### ISS-260320-test-coverage — Increase test coverage to ≥80%
**Type:** Testing
**Priority:** High
**Created:** 2026-03-20
**Status:** 🟢 Active — first batch in feature/tests-and-refactor

**Done:**
- ✅ `helper.py` — format_attribute, format_value (13 tests)
- ✅ `apiparser.py` — all helper functions: from_entry, from_entry_bool, get_uid, generate_keymap, matches_only, can_skip, fill_defaults, fill_vals, fill_ensure_vals, fill_vals_proc (52 tests)
- ✅ `mikrotikapi.py` — init, connect, query, set_value, run_script, error handling, lock management (30 tests)
- ✅ `coordinator.py` — get_arp, get_dns, option properties, set_value/execute delegation (12 tests)

**Remaining (TODO — prioritised by coverage impact):**

Phase 2 — coordinator.py data methods:
- get_interface (208 LOC) — interface discovery, type detection, PoE fields
- get_nat / get_mangle / get_filter — firewall rule parsing + dedup logic
- get_dhcp — lease parsing, active-address resolution, server lookup
- get_system_resource — CPU, memory, disk, uptime parsing
- get_firmware_update — version comparison, update availability
- process_accounting — client traffic snapshot processing

Phase 3 — platform entities:
- sensor.py — native_value, unit conversion, traffic calculation
- switch.py — async_turn_on/off with executor wrapping (regression tests for blocking I/O fix)
- button.py — async_press executor wrapping
- update.py — async_install, release_notes fetching, version list generation
- device_tracker.py — is_connected logic, timeout handling, state property
- binary_sensor.py — is_on property, PPP secret status

Phase 4 — integration lifecycle:
- __init__.py — async_setup_entry, async_unload_entry, async_migrate_entry
- entity.py — MikrotikEntity class, device_info, unique_id, _check_entity_exists, _run_entity_setup_loop

**Reference:** Current coverage ~11%, target ≥80% for SonarCloud Grade A

---

### ISS-260320-refactor-dedup — Refactor duplicated patterns
**Type:** Refactoring
**Priority:** Medium
**Created:** 2026-03-20
**Status:** 🟡 Backlog

**Remaining:**
- coordinator.py: extract firewall rule dedup helper (get_nat/get_mangle/get_filter share ~75 LOC pattern)
- switch.py: extract base class for NAT/Mangle/Filter/Queue UID lookup (~50 LOC)
- apiparser.py: extract shared path traversal from from_entry/from_entry_bool (~20 LOC)
- *_types.py: extract shared entity description base class (~80 LOC)

**Reference:** SonarCloud CPD exclusions already cover sensor_types.py and coordinator.py intentional repetition

---

## Completed

### ISS-260320-options-flow-crash — Options flow crash on HA 2025.12+
**Type:** Bug | **Priority:** Critical | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)

### ISS-260320-blocking-io — Blocking I/O in async methods
**Type:** Bug | **Priority:** High | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)

### ISS-260320-deadlock-run-script — Deadlock in mikrotikapi.py run_script
**Type:** Bug | **Priority:** Critical | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)
