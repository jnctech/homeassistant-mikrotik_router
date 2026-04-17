# Change Register — Mikrotik Router HACS Integration

Changes listed in reverse chronological order.

---

## CR-260417-hotfix-librouteros-4x-pin — v2.3.14 hotfix: pin librouteros<4.0

**Date:** 2026-04-17
**Branch:** `fix/librouteros-4x-pin`
**Status:** In Review (targeting master)

### What Changed

| Area | Change |
|------|--------|
| `manifest.json` | Pin `librouteros>=3.4.1,<4.0`; bump version to 2.3.14 |
| `README.md` | Add v2.3.14 section explaining the pin |
| `info.md` | Add v2.3.14 entry |
| `docs/ISSUES.md` | Add ISS-260417-librouteros-4x-break |

### Why

librouteros 4.0.1 (released before 2026-04-10) renamed the `connect()` kwarg `login_methods` → `login_method`. Every new or upgrading install of v2.3.13 pulls 4.0.1 (no upper bound in manifest) and fails on first connection attempt with `connect() got an unexpected keyword argument 'login_methods'`. Reported in #55 (2026-04-10) and #56 (2026-04-13).

The pin is a minimum-risk stopgap: it restores the prior working state for all users by blocking 4.x until proper migration lands. No code changes in the integration itself, so behaviour is identical to v2.3.13 for users already on librouteros 3.x.

### Follow-up

Open a new ISS to migrate to librouteros 4.x: rename `login_methods` → `login_method` in `mikrotikapi.py:102`, audit other 4.0.1 breaking changes, then drop the upper pin.

### Quality Gate Results

Docs/config-only change; no code touched. No tests added.

---

## CR-260327-phase5-tests — Phase 5 integration tests and coverage gap closure

**Date:** 2026-03-27
**Branch:** `feature/phase5-integration-tests`
**Status:** In Review (targeting dev)

### What Changed

| Area | Change |
|------|--------|
| `tests/test_init.py` | Rewrote with 44 tests (was 4): async_setup_entry, async_unload_entry, async_reload_entry lifecycle; service handlers (cleanup_entities, cleanup_stale_hosts) with orphan removal, dry run, error paths; all helper functions (_build_valid_unique_ids, _collect_ids_for_desc, _get_mikrotik_data, _find_host_by_mac_slug, _classify_host_entity); _collect_all_descriptions platform coverage; diagnostics |
| `docs/ISSUES.md` | Closed ISS-260320-test-coverage (86% achieved); updated priorities |
| `docs/CHANGE-REGISTER.md` | Added CR-260327-phase5-tests |

### Why

ISS-260320-test-coverage Phase 5: `__init__.py` was at 96% coverage with only 4 migration/device-removal tests. The lifecycle functions (setup, unload, reload), service handlers, and helper functions were completely untested. Phase 5 brings `__init__.py` to 100% and `diagnostics.py` from 0% to 100%. Total project coverage: 86% (565 tests).

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | pending | ⏳ |
| Ruff format | pending | ⏳ |
| Tests | 565 passed, 5 skipped | ✅ |
| Coverage | 86% | ✅ (target ≥80%) |

---

## CR-260327-legacy-cleanup — SonarCloud remediation, complexity reduction, modernisation

**Date:** 2026-03-27
**Branch:** `refactor/legacy-cleanup`
**Status:** In Review (targeting dev)

### What Changed

| Area | Change |
|------|--------|
| `apiparser.py` | **Bug fix:** `from_entry_bool` now applies `reverse` to default when field absent — fixes DHCP leases/servers incorrectly showing disabled |
| `apiparser.py` | Removed identity type coercions (`str(str)`, `int(int)`) in `from_entry()` |
| `apiparser.py` | Extracted 8 helpers to reduce complexity: `_fill_val_str`, `_fill_val_bool`, `_convert_timestamp`, `_resolve_str_default`, `_process_source_entry`, `_get_uid_from_keys`, `_process_val_sub`, `_apply_combine` |
| `mikrotikapi.py` | Extracted `_query_list`, `_query_command` from `query()` (18→≤15 complexity) |
| `mikrotikapi.py` | Extracted `_find_entry` dedup helper, used by `set_value`, `execute`, `run_script` |
| `mikrotikapi.py` | **Bug fix:** `set_value`/`execute`/`run_script` now return `False` (not `True`) when entry not found |
| `mikrotikapi.py` | Added type hints to all public methods, extracted `_ensure_ssl_wrapper`, removed banner comments |
| `coordinator.py` | Extracted 15+ helpers for complexity reduction: `_detect_capabilities_v6/v7`, `_has_wifi_package`, `_async_update_client_traffic`, `_calculate_interface_traffic`, `_process_interface_metadata`, `_process_bonding`, `_arp_matches_interface`, `_match_arp_clients`, `_fallback_client_ip`, `_normalize_dhcp_lease`, `_resolve_dhcp_interface`, `_count_leases_per_server`, `_parse_queue_values`, `_parse_queue_pair` |
| `coordinator.py` | Tracker: extracted `_ensure_host_defaults`, `_first_run_availability`, `_should_ping_host`, `_ping_host` |
| `coordinator.py` | Fixed f-string in logging (S3457), removed unnecessary `list()` |
| `coordinator.py` | Queue parsing now catches `ValueError`/`IndexError` per entry |
| `coordinator.py` | Firmware version parse failure logged as warning with consequence message |
| `coordinator.py` | Fixed `default: True` + `reverse: True` in filter/raw rules (was relying on buggy from_entry_bool) |
| `switch.py` | **Silent failure fix:** `_require_write_access()` raises `HomeAssistantError` instead of silent return |
| `switch.py` | **Silent failure fix:** NAT/Mangle/Filter/Raw/Queue switches log error when rule not found (value=None) |
| `switch.py` | `MikrotikPortSwitch` uses `.get()` for `about` and `port-mac-address` |
| `switch.py` | Extracted `_CAPSMAN_MANAGED`, `_RULE_NOT_FOUND_ENABLE/DISABLE` constants |
| `entity.py` | `_handle_coordinator_update` guards against `KeyError` when entity UID disappears |
| `sensor_types.py` | Extracted 5 icon constants (S1192) |
| `config_flow.py` | Set comprehension (S7494) |
| `__init__.py` | Extracted `_collect_ids_for_desc` helper, prefixed unused params, NOSONAR on intentional `list()` |
| `tests/` | 41 new tests (apiparser helpers, mikrotikapi _find_entry/return-false, from_entry_bool reverse regression) |

### Why

SonarCloud v2.3.13 report: 29 code smells (13 CRITICAL complexity, 6 string duplication, 4 MAJOR, 8 MINOR). All pre-existing upstream patterns. Also fixes tracked issues: ISS-260321-cognitive-complexity (13 functions), ISS-260321-silent-failures (8 items), from_entry_bool reverse quirk.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 525 passed, 5 skipped | ✅ |

---

## CR-260326-wireless-client-count — Fix wireless client detection via bridge table

**Date:** 2026-03-26
**Branch:** `fix/wireless-client-count`
**Status:** Merged to dev (v2.3.13-beta.1)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | New `_is_wireless_host()` method: detects wireless clients via source, direct interface match, or bridge host table lookup |
| `coordinator.py` | `async_process_host` uses `_is_wireless_host()` instead of inline source check for client counting |
| `tests/test_coordinator.py` | 8 new tests: source wireless/capsman, direct interface, bridge lookup, wired, no wireless interfaces, hAP ac2 integration scenario |

### Why

On routers with empty WiFi registration tables (e.g. hAP ac2 with new WiFi package), all clients were counted as wired because the old check only looked at `source in ["capsman", "wireless"]`. ARP-discovered clients on wireless interfaces were missed. The new method checks the bridge host table to correctly identify wireless clients.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 484 passed, 5 skipped | ✅ |

---

## CR-260326-dhcp-server-sensors — DHCP server status and lease count sensors

**Date:** 2026-03-26
**Branch:** `feature/dhcp-server-sensors`
**Status:** Merged to dev (v2.3.13-beta.1)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Extended `get_dhcp_server()` with address-pool, enabled (from reversed `disabled`), comment, status, lease-count fields |
| `coordinator.py` | Added lease counting loop in `get_dhcp()` — tallies active leases per DHCP server |
| `coordinator.py` | Added `get_dhcp_server` to update loop before `get_dhcp` (correct order for lease counting) |
| `sensor_types.py` | New `DEVICE_ATTRIBUTES_DHCP_SERVER` attribute list |
| `sensor_types.py` | Two new sensor entity descriptions: `dhcp_server_status`, `dhcp_server_lease_count` |
| `tests/test_coordinator.py` | 7 new tests: enriched fields, defaults, status running/disabled, lease count, unknown server ignored |

### Why

DHCP server monitoring was limited to internal use (interface lookup for DHCP leases). Users want to see per-server status and lease counts for network utilization monitoring and pool exhaustion detection. Implements gap analysis item A5.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 483 passed, 5 skipped | ✅ |

---

## CR-260326-fix-slow-load — Eliminate startup bottlenecks that block HA loading

**Date:** 2026-03-26
**Branch:** `claude/fix-homeassistant-slow-load-EzXf3`
**Status:** Released (v2.3.12)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | First-run host tracking uses ARP table instead of sequential pings — eliminates O(n) blocking startup delay |
| `coordinator.py` | MAC vendor lookups parallelised via `asyncio.gather` + `_resolve_manufacturer` helper |
| `coordinator.py` | `_async_update_hwinfo` returns `bool` to skip duplicate `get_system_resource` call on hwinfo cycles |
| `coordinator.py` | `_async_run_if_connected` → `_run_if_enabled` with `requires` kwarg, reducing boilerplate |
| `coordinator.py` | All `datetime.now()` replaced with HA's `dt_now()` (timezone-aware); `last_hwinfo_update` initialised with `tzinfo=timezone.utc` |
| `coordinator.py` | Fixed chained comparison bug: `elif 0 < self.major_fw_version >= 7` → `elif self.major_fw_version >= 7` |
| `coordinator.py` | `get_system_resource` now uses `_run_if_enabled` guard (caught by silent-failure audit) |
| `apiparser.py` | Fixed `voluptuous.Optional(str)` misused as type hint → `str \| None` (PEP 604) |
| `__init__.py` | New `cleanup_entities` service: removes orphaned entities with no backing router data |
| `__init__.py` | New `cleanup_stale_hosts` service: reports/removes stale device tracker entities (dry_run default) |
| `__init__.py` | Services registered in `async_setup_entry` (not `async_setup` which is skipped for config-flow integrations) |
| `services.yaml` | Service descriptions for cleanup_entities and cleanup_stale_hosts |
| `strings.json`, `translations/en.json` | Service translation strings |
| `*.py` (6 files) | Added `from __future__ import annotations` per HA coding standards |
| `tests/` | 4 new `_resolve_manufacturer` tests (error, concurrent failure, parallel success, unknown MAC skip); `AsyncMock` for mac_lookup |

### Why

ISS-260326-slow-load: The integration was blocking HA startup by sequentially pinging every tracked host on first load. With many hosts, this added 10+ seconds to HA boot time. ARP-based first-run detection provides immediate availability data, with pings starting on the next 10s tracker cycle.

ISS-260320-deprecated-datetime: All remaining naive `datetime.now()` calls replaced with timezone-aware equivalents per HA coding standards.

Entity cleanup services address long-standing user pain point: orphaned entities from removed interfaces, deleted firewall rules, or stale DHCP hosts that accumulate over time and require manual registry editing to remove.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 465 passed, 5 skipped | ✅ |
| Code review | No bugs found | ✅ |
| Silent-failure audit | 2 fixes applied (resource guard, ARP logging) | ✅ |
| HA live test | Services working, zero errors in logs | ✅ |

---

## CR-260325-attribute-cleanup — Remove junk attributes from interface and tracker entities

**Date:** 2026-03-25
**Branch:** `feature/attribute-cleanup`
**Status:** Released (v2.3.11)

### What Changed

| Area | Change |
|------|--------|
| `entity.py` | `MikrotikInterfaceEntityMixin` now uses exclusive SFP/copper attribute selection based on `sfp-shutdown-temperature` value (not key existence); adds `client-ip/mac` and `poe-out` conditionally; `copy_attrs` gains `skip_junk` parameter to filter "unknown"/"none"/"N/A"/None values |
| `switch.py` | `MikrotikPortSwitch` now inherits `MikrotikInterfaceEntityMixin` instead of duplicating attribute logic (-41 lines) |
| `iface_attributes.py` | Moved `client-ip-address`/`client-mac-address` to new `DEVICE_ATTRIBUTES_IFACE_CLIENT` list; removed `poe-out` from `DEVICE_ATTRIBUTES_IFACE_ETHER` |
| `switch_types.py` | Eliminated 4 duplicated attribute lists — now imports from `iface_attributes.py` (-66 lines) |
| `device_tracker.py` | Wireless attrs (`signal-strength`, `tx-ccq`, `tx/rx-rate`) only added for wireless/capsman hosts |
| `device_tracker_types.py` | Split `DEVICE_ATTRIBUTES_HOST_WIRELESS` from `DEVICE_ATTRIBUTES_HOST` |
| `tests/` | 10 new tests (SFP/copper exclusivity, skip_junk, poe-out conditional, client filtering, wireless tracker attrs); 472 total |

### Why

Entity attributes were polluted with ~1,300 meaningless defaults across 3 tested devices (rb4011, hapax3, hapac2/csr310). Root cause: `parse_api` adds all declared fields with defaults, then `copy_attrs` unconditionally includes them. Key examples:
- 16 SFP attributes (all "unknown") on every copper ethernet port
- `poe_out: "N/A"` on every non-PoE port
- `client_ip_address: "unknown"` on loopback, vlan, pppoe, wireguard, bonding interfaces
- `signal_strength`, `tx_ccq` on wired device tracker hosts

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 472 passed, 5 skipped | ✅ |

---

## CR-260325-mangle-interface-dedup — Include interface fields in mangle rule unique ID

**Date:** 2026-03-25
**Branch:** `fix/mangle-duplicate-interface`
**PR:** #40 (targeting dev)
**Status:** In Review

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Added `in-interface` and `out-interface` to mangle `uniq-id` formula and API query fields |
| `switch_types.py` | Added `in-interface` and `out-interface` to `DEVICE_ATTRIBUTES_MANGLE` |
| `tests/` | New test: `test_mangle_interface_differentiates_rules` |

### Why

Mangle rules differing only by `in-interface`/`out-interface` (e.g. MSS clamping for inbound vs outbound PPPoE) generated identical unique IDs, causing the duplicate detection to silently remove both rules.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 472 passed, 5 skipped | ✅ |

---

## CR-260324-arp-incomplete-filtering — Treat ARP "incomplete" as unreachable

**Date:** 2026-03-24
**Branch:** `claude/fix-device-tracker-incomplete-nYKrC`
**Status:** Released (v2.3.10)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | `_merge_arp_hosts()` now excludes both `"failed"` and `"incomplete"` ARP statuses from the detected set via `_ARP_UNREACHABLE_STATUSES` frozenset |
| `tests/test_coordinator.py` | Updated existing tests and added new test for `"incomplete"` status |
| `docs/decisions/ADR-001` | Updated to cover `"incomplete"` status alongside `"failed"` |

### Why

Devices with ARP status `"incomplete"` (ARP request sent, no reply received) were incorrectly shown as "home" in the device tracker. Only `"failed"` was being filtered. Both statuses indicate the device is unreachable and should result in `not_home`.

---

## CR-260322-port-upstream-frs — Port upstream feature requests (#310, #321, #334, #298)

**Date:** 2026-03-22
**Branch:** `feature/port-upstream-frs`
**PR:** (targeting dev)
**Status:** In Review

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | New `get_raw()` method for `/ip/firewall/raw` with dedup logic; new `get_container()` method for `/container` with running status derivation; enriched `get_dhcp_client()` with gateway, dns-server, dhcp-server, expires-after, comment; new option properties and capability detection |
| `switch.py` | New `MikrotikRawSwitch` class (enable/disable via set_value); new `MikrotikContainerSwitch` class (start/stop via execute) |
| `switch_types.py` | `DEVICE_ATTRIBUTES_RAW`, `DEVICE_ATTRIBUTES_CONTAINER`, 2 new switch entity descriptions |
| `sensor_types.py` | `DEVICE_ATTRIBUTES_DHCP_CLIENT`, 2 new sensor entity descriptions (dhcp_client_status, dhcp_client_address) |
| `button.py` | `async_refresh()` after script execution for environment variable updates |
| `const.py` | New config constants: `CONF_SENSOR_RAW`, `CONF_SENSOR_CONTAINER` |
| `config_flow.py` | New option toggles for RAW and Container in sensor_select step |
| `strings.json` / `en.json` | Translations for new options |
| `tests/` | 20 new tests (coordinator, switch, button, sensor) — 461 total |
| `docs/decisions/` | ADR-008: Upstream Feature Port |

### Why

Four upstream feature requests implemented to keep the fork current while upstream is quiet:
- tomaae#334: Container monitoring and control (RouterOS 7.4+)
- tomaae#310: Firewall RAW rule enable/disable switches
- tomaae#321: DHCP client sensors for WAN monitoring
- tomaae#298: Environment refresh after script execution

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | pending | ⏳ |
| Ruff format | pending | ⏳ |
| Tests | 461 passed, 5 skipped | ✅ |

---

## CR-260321-phase4-integration-tests — Entity-level integration tests for all platform types

**Date:** 2026-03-21
**Branch:** `feature/phase4-integration-tests`
**PR:** #31 (targeting dev)
**Status:** Merged

### What Changed

| Area | Change |
|------|--------|
| `tests/conftest.py` | Added `make_mock_coordinator()`, `make_mock_entity_description()`, `patch_coordinator_entity_init()` shared helpers |
| `tests/test_init.py` | New: 4 tests for `async_migrate_entry` (v1→v2, noop, data preservation) and `async_remove_config_entry_device` |
| `tests/test_entity.py` | Extended: 15 new tests for `MikrotikEntity` class (init, custom_name, unique_id, device_info, extra_state_attributes, `_handle_coordinator_update`) |
| `tests/test_sensor.py` | New: 7 tests for `MikrotikSensor` (native_value, native_unit_of_measurement, ClientTrafficSensor.custom_name) |
| `tests/test_binary_sensor.py` | New: 10 tests for binary sensor is_on, icon branches, PPP disabled guard, PortBinarySensor 3-state icon |
| `tests/test_switch.py` | New: 19 tests for 5 switch classes — turn_on/off, write access guard, CAPsMAN guard, PoE side-effects, NAT/Queue UID lookup, Kidcontrol resume/pause |
| `tests/test_button.py` | New: 3 tests for Button no-op, ScriptButton run_script, ApiEntryNotFound handling |
| `tests/test_device_tracker.py` | New: 12 tests for is_connected (tracking disabled, wireless, capsman, ARP timeout), state, extra_state_attributes |
| `tests/test_update.py` | Extended: 8 new tests for RouterOS/RouterBOARD install (with/without backup), version properties |
| `docs/ISSUES.md` | Updated ISS-260320-test-coverage with Phase 4 completion |

### Why

ISS-260320-test-coverage Phase 4: entity-level tests cover all 6 platform entity types and the MikrotikEntity base class. Previous phases covered helpers and coordinator data methods but the actual entity behaviour (properties, actions, state) was untested. 80 new tests bring total to 441.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 441 passed, 5 skipped | ✅ |

---

## CR-260321-complexity-reduction — Cognitive complexity reduction across coordinator, entity, apiparser

**Date:** 2026-03-21
**Branch:** `feature/complexity-reduction`
**PR:** #30 (targeting dev)
**Status:** Merged

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Extracted 11 helpers from `async_process_host()` (136→~10 each): `_merge_capsman_hosts`, `_merge_wireless_hosts`, `_merge_dhcp_hosts`, `_merge_arp_hosts`, `_recover_hass_hosts`, `_ensure_host_defaults`, `_update_host_availability`, `_update_host_address`, `_resolve_hostname`, `_dhcp_comment_for_host`, `_update_captive_portal` |
| `coordinator.py` | Extracted `_async_update_hwinfo` and `_run_if_enabled` from `_async_update_data()` (65→~15), plus optional sensor loop tables |
| `coordinator.py` | Extracted `_init_accounting_hosts`, `_classify_accounting_traffic`, `_check_accounting_threshold`, `_apply_accounting_throughput` from `process_accounting()` (48→~10 each) |
| `coordinator.py` | Extracted `_monitor_ethernet_port` with SFP/copper/PoE monitor val constants from `get_interface()` (27→~10) |
| `entity.py` | Split `_skip_sensor()` into `_skip_interface_traffic`, `_skip_binary_sensor`, `_skip_device_tracker`, `_skip_poe_sensor` (23→~5 each) |
| `switch.py` | Replaced inline attribute loops with shared `copy_attrs` from entity.py (21→~5) |
| `apiparser.py` | Extracted `_traverse_entry` helper with `_NOT_FOUND` sentinel, case-insensitive bool matching via frozensets (18→~8) |
| `coordinator.py` | Further extracted `_hostname_from_dns`, `_hostname_from_dhcp`, `_add_traffic_bytes` to bring two remaining functions under threshold |
| `coordinator.py` | Silent-failure fixes: username guard in `get_access`, debug logging on MAC lookup, ValueError guard on `_address_part_of_local_network` |
| `coordinator.py` | Restored independent `connected()` check between `get_wireless`/`get_wireless_hosts`; guarded `_apply_accounting_throughput` against zero `time_diff` |
| `tests/` | 58 new tests covering all extracted helpers (361 total, up from 303) |
| `docs/decisions/` | ADR-007: Cognitive Complexity Reduction via Helper Extraction |
| `docs/ISSUES.md` | Added ISS-260321-silent-failures tracking remaining audit findings |

### Why

ISS-260321-cognitive-complexity: SonarCloud quality target is ≤15 cognitive complexity per function. Seven of the worst offenders (totalling 358 complexity points) are now refactored into focused helpers, each well under the threshold. Silent-failure audit (pr-review-toolkit) identified 12 issues; 3 critical/high fixed, 8 pre-existing tracked.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 361 passed, 5 skipped | ✅ |

---

## CR-260320-tests-and-refactor — Test suite, devcontainer, CI/CD alignment, ruff migration

**Date:** 2026-03-20
**Branch:** `feature/tests-and-refactor`
**PR:** [#29](https://github.com/jnctech/homeassistant-mikrotik_router/pull/29)
**Status:** In Review (targeting dev)

### What Changed

| Area | Change |
|------|--------|
| `tests/` | 151+ tests across 7 files: apiparser (52), mikrotikapi (30), helper (13), coordinator (80), entity (30), update (8) |
| `.devcontainer/` | Python 3.13 devcontainer with pytest-homeassistant-custom-component, Ruff, Pylance |
| `.github/workflows/` | CI/CD aligned to gold standard: SHA-pinned actions, Ruff replaces Black+flake8, gitleaks, pip-audit, actionlint, dependency-review, scorecard added |
| `.github/dependabot.yml` | Dependabot configured for GitHub Actions and pip |
| `requirements_dev.txt` | New: all dev/test dependencies |
| `requirements_tests.txt` | Modernised from 2019-era pinned versions to match CI |
| `apiparser.py` | `type() == dict` → `isinstance(source, dict)` (E721) |
| `*.py` (14 files) | Ruff: remove 43 unused imports (F401), reformat 4 files |
| `docs/quality-gates.md` | Black/flake8 → Ruff references, local dev setup instructions |
| `docs/ISSUES.md` | Test coverage plan, refactor backlog, status updates |

### Why

1. Test coverage was ~11% — well below the 80% SonarCloud target
2. No local dev environment — tests could only run in CI
3. CI was using unpinned actions and legacy linters (Black+flake8)
4. Ruff migration tracked as ISS-260320-ruff-migration — now completed

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 151+ (CI pending) | ⏳ |

### Post-Deploy Actions

- [ ] Open in devcontainer and verify `pytest tests/ -v` passes
- [ ] Confirm CI passes on dev branch
- [ ] Measure coverage and compare against 80% target

---

## CR-260320-dispatcher-spam — Disable update_sensors dispatcher to fix log spam

**Date:** 2026-03-20
**Branch:** `fix/disable-dispatcher-spam-v2`
**PR:** [#26](https://github.com/jnctech/homeassistant-mikrotik_router/pull/26)
**Status:** Merged (v2.3.8)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Disable `async_dispatcher_send("update_sensors")` that caused "does not generate unique IDs" log errors every 30s |

### Why

The dispatcher re-enabled in v2.3.6 for new device discovery caused thousands of log errors because `_check_entity_exists()` doesn't guard against re-adding existing entities. Proper fix tracked as ISS-260320-new-device-discovery.

---

## CR-260320-arp-failed-filter — ARP failed-status filtering for device tracking

**Date:** 2026-03-20
**Branch:** `fix/arp-failed-filter-v2`
**PR:** [#23](https://github.com/jnctech/homeassistant-mikrotik_router/pull/23)
**Status:** Merged (v2.3.7)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Move ARP failed-status filtering from `get_arp()` to `async_process_host()` |

### Why

ARP entries with `status: failed` were causing devices to show as home when they were unreachable. Failed entries are now excluded from `arp_detected` but kept in `ds["arp"]` for bridge-interface lookups. Fixes [#17](https://github.com/jnctech/homeassistant-mikrotik_router/issues/17).

---

## CR-260320-ha-compliance-blocking-io — HA compliance: deadlocks, blocking I/O, options flow crash

**Date:** 2026-03-20
**Branch:** `fix/ha-compliance-blocking-io-deadlocks`
**PR:** [#19](https://github.com/jnctech/homeassistant-mikrotik_router/pull/19)
**Status:** Merged (v2.3.6)

### What Changed

| Area | Change |
|------|--------|
| `mikrotikapi.py` | Replace all manual `lock.acquire()`/`release()` with `with self.lock:` context managers — fixes critical deadlock in `run_script()` |
| `mikrotikapi.py` | Fix wrong `voluptuous.Optional` import → `list \| None`; fix return type `(bool, bool)` → `tuple[bool, bool]` |
| `config_flow.py` | Remove broken `__init__` from `OptionsFlowWithConfigEntry` subclass — fixes #470, #471 |
| `config_flow.py` | Wrap blocking `api.connect()` in `async_add_executor_job` |
| `switch.py` | Wrap all blocking `set_value`/`execute` calls in `async_add_executor_job` |
| `switch.py` | Remove dead sync `turn_on`/`turn_off` stubs |
| `button.py` | Wrap blocking `run_script` in `async_add_executor_job` |
| `update.py` | Wrap blocking `execute` calls in `async_add_executor_job` (RouterOS + RouterBOARD) |
| `entity.py` | Replace deprecated `default_name`/`default_manufacturer`/`default_model` with `name`/`manufacturer`/`model` |
| `strings.json` | Add missing `sensor_poe` translation entry |
| `CLAUDE.md` | New project CLAUDE.md with quality targets and linked standards |
| `docs/` | New: `ha-coding-standards.md`, `quality-gates.md`, `architecture.md`, `ISSUES.md`, `CHANGE-REGISTER.md` |

### Why

Multiple HA best-practice violations discovered during HACS compliance audit:
1. Options flow crash reported by users on HA 2025.12+ (GitHub #470, #471)
2. Blocking network I/O on the event loop freezing HA UI
3. Critical deadlock bug in `run_script()` that permanently freezes the integration
4. Deprecated APIs that will be removed in future HA releases

### Post-Deploy Actions

- [x] Validate options flow opens without error on HA
- [x] Toggle a switch and verify no UI freeze
- [x] Run a script button and verify no deadlock
- [ ] Comment on upstream issues #470, #471
