# ADR-013 — Entity-naming disambiguation for colliding clients and DHCP servers

**Status:** Accepted — implemented on `feature/entity-naming` (CR-260608-entity-naming). Maintainer-approved after independent review (which caught the v7-path consumer, now incorporated).
**Date:** 2026-06-08
**Supersedes/relates:** `ENH-260608-entity-naming`. Gold quality-scale *entity-naming*.
**Numbering note:** ADR-012 = config-entry-runtime-data (on `dev`). This ADR takes **013** (lands first). The local `proto/fw-version-sot` prototype, previously noted to renumber to ADR-013, should now use **ADR-014**.

## Context

Distinct entities collapse to identical friendly names → Home Assistant disambiguates with `_2/_3/…` entity_id suffixes. Two families are affected. Both root causes were **verified live against the running v2.3.18 box** (recorder DB, 2026-06-08), which **corrected the prior brief's premise**.

### Family A — client device-trackers + client-traffic sensors

`device_tracker` (`device_tracker_types.py:54`, `name=""`) and the `client_traffic_*` sensors (`sensor_types.py:701+`) both derive their name from `host[uid]["host-name"]` — client-traffic inherits it directly (`coordinator.py:2736`). In `custom_name` (`entity.py:293-311`) the tracker takes the empty-name branch (`:311` → `data["host-name"]`); the traffic sensors take the compose branch (`:309` → `"{host-name} {name}"`).

**Live evidence (REFUTES the brief's "named after the interface"):**
```
device_tracker.lwip0    mac=AA:BB:CC:DD:EE:01  host_name="lwip0"  interface="bridge"  source=dhcp
device_tracker.lwip0_2  mac=AA:BB:CC:DD:EE:02  host_name="lwip0"  interface="bridge"  source=dhcp
… _3 AA:BB:CC:DD:EE:03, _4 AA:BB:CC:DD:EE:04, _5 AA:BB:CC:DD:EE:05, _6 AA:BB:CC:DD:EE:06
```
`host-name == "lwip0"` but `interface == "bridge"` — **not equal**. `"lwip0"` is the **DHCP hostname these devices report** (`lwIP` is the lightweight embedded TCP/IP stack; ESP8266/ESP32-class IoT devices default their hostname to `lwip0`). So this is a **non-unique reported hostname**, not interface-based naming. The coordinator already falls back to MAC (`_hostname_from_dhcp` → `return uid`, `coordinator.py:2593`) but only when `host-name == "unknown"` (`:2548`); a non-unique-but-present hostname slips through. The only stable distinguisher among the colliding hosts is the **MAC** (IP is dynamic; interface/source/host-name are identical).

### Family B — DHCP-server sensors

`dhcp_server_status` / `dhcp_server_lease_count` (`sensor_types.py:876/892`) have `data_name == data_reference == "name"`. The `entity.py:306` shortcut (`data[data_reference] == data[data_name]`) is therefore **always true** → collapses to the static label, dropping the distinguishing server name.

**Live evidence (CONFIRMS the brief):**
```
…dhcp_server    name="dhcp88" (bridge)  friendly="… RB4011… DHCP server"
…dhcp_server_2  name="dhcp20" (vlan20)  friendly="… RB4011… DHCP server"   ← same
…_3 dhcp30, _4 dhcp40, _5 dhcp99 — five distinct VLAN servers, identical friendly name
```
All five attach to the single `ha_group="System"` device, so (unlike per-interface entities) there is no device-level disambiguation. The distinct `name` (`dhcp88/20/30/40/99`) is the distinguisher and it is being dropped.

**Scope constraint (verified):** ~20 descriptors share `data_name == data_reference` (ppp, poe_out_*, traffic, queue, interface, environment, kidcontrol, dhcp_client, …). They rely on the `:306` shortcut and do **not** collide because each gets its own device. **Any fix to line 306 must be scoped to dhcp_server only**, or it renames dozens of entity types for every user.

## Decision

### A. Clients — disambiguate non-unique hostnames in the coordinator

At the **end of `async_process_host()`** (called at `coordinator.py:676`, *before* `_async_update_client_traffic()` at `:691`), after the host-resolution loop (`:2696-2707`), add a pass that:
1. Counts `host-name` occurrences across `self.ds["host"]`.
2. For each host whose `host-name` is shared by **more than one** host, set the display name to **`"{host-name} ({mac-address})"`** (maintainer's chosen format — keep the reported name, append the MAC to disambiguate).
3. Unique real hostnames are left unchanged. Empty/`unknown` already resolves to the MAC via the existing fallback — unchanged.

This fixes both client families with one change, at the source ("one owner per fact"). `device_tracker.lwip0` → `lwip0 (AA:BB:CC:DD:EE:01)`; its traffic sensors → `lwip0 (AA:BB:CC:DD:EE:01) LAN TX`, etc.

> **Insertion point is load-bearing (independent review catch).** `client_traffic` inherits `host-name` at **two** sites, gated by firmware in `_async_update_client_traffic` (`:761-767`): **v<7 → `process_accounting`/`_init_accounting_hosts`** (copy at `:2736`) and **v≥7 → `process_kid_control_devices`** (copy at `:2911`). The live v2.3.18/RouterOS-7 box uses the **`:2911`** path. The pass must therefore run at the end of `async_process_host` (before `:691`) so it precedes **both** copies — *not* inside `process_accounting`, which would silently miss every RouterOS-7 install. `device_tracker` reads `host[uid]` directly, so it is fixed regardless; only the traffic sensors depend on this ordering.

### B. DHCP servers — scoped opt-in to compose the name

Add a boolean to the entity description, e.g. `data_name_compose: bool = False`, designed **generally** (not dhcp-hardcoded): when `True`, `custom_name` skips the `:306` equality shortcut and always composes → `"{data[data_name]} {entity_description.name}"`. Set it **only** on `dhcp_server_status` and `dhcp_server_lease_count`. Result: `"dhcp88 DHCP server"` / `"dhcp88 DHCP server leases"`. No other descriptor is touched.

**Flag contract (must be explicit):** `data_name_compose` is evaluated *inside* the `if self.entity_description.name:` branch and only overrides the `:306` equality shortcut. The `data_name_comment` branch (`entity.py:302-303`) still takes precedence when set — the two are independent, and the dhcp_server descriptors carry no comment attribute, so the interaction is moot for the targets but is specified so a future consumer (see §Out of scope) isn't surprised.

## Consequences

**Non-breaking — the "don't break existing users" guarantee (verified):**
- `unique_id` is unchanged in both families — MAC-based for clients (`entity.py:316-317`, `data_reference="mac-address"`), name-based for DHCP (`data_reference="name"`). HA fixes `entity_id` at registry creation from `unique_id`; **existing entity_ids and the automations that reference them are untouched.**
- Only the **friendly name** updates live, and **new** entities (created after upgrade) get the improved entity_id slug. Existing `_2/_3` entity_ids persist until a user runs the cleanup service (out of scope here).
- No `unique_id` migration; no config-entry migration.

**Costs / risks:**
- Friendly names visibly change for affected entities (intended).
- The duplicate-detection is per-poll over the current host set — O(n) over hosts, negligible.
- A device that *starts* sharing a hostname mid-life gets the MAC-suffixed name on the next poll (correct, but the displayed name changes); a device whose duplicate-peer leaves keeps its suffixed name until it's the sole holder again. Acceptable and self-correcting.

## Implementation plan

1. `coordinator.py`: new `_disambiguate_duplicate_hostnames()` called at the **end of `async_process_host()`** (before `_async_update_client_traffic` at `:691`); mutates `host[uid]["host-name"]` to `"{host-name} ({mac})"` for shared names only. Runs after `_resolve_hostname`, so it sees the resolved value; raw host-name is re-read from the API each poll, so it re-derives cleanly. **Both** client_traffic copy sites then inherit it: `_init_accounting_hosts` (`:2736`, v<7) and `process_kid_control_devices` (`:2911`, v≥7).
2. `sensor_types.py` (and any other `*EntityDescription` dataclass that needs it): add `data_name_compose: bool = False`; set `True` on the two `dhcp_server_*` descriptors.
3. `entity.py` `custom_name`: honour `data_name_compose` (compose, bypassing the `:306` equality) — guarded so all other descriptors are unaffected; `data_name_comment` still wins per the flag contract above.

## Testing (behaviour, per the repo's test standards)

- **Clients:** given a host set with two hosts sharing `host-name="lwip0"` and distinct MACs, assert each renders `"lwip0 (<mac>)"` and the two names are distinct; a host with a unique hostname renders unchanged.
- **Empty/unknown hosts:** two hosts that both fall back to MAC (no DNS/DHCP name) render their distinct MACs and are **not** suffixed (they aren't "shared" — distinct MAC values → distinct names).
- **Client-traffic — BOTH firmware paths:** assert the disambiguated name flows into `client_traffic_*` via **`_init_accounting_hosts`** (v<7) **and** via **`process_kid_control_devices`** (v≥7 — the live box's path). A v7-path test is mandatory, not optional.
- **DHCP:** two `dhcp_server` rows with distinct `name` render distinct `"{name} DHCP server"`; assert an entity **without** `data_name_compose` (e.g. `queue`, `poe_out_status`, `ppp_secret`) is unchanged (scope guard).
- **unique_id invariance:** assert `unique_id` is identical before/after for all the above — explicitly including the **client** path (the dedup mutates `host-name`, but `unique_id` keys on `mac-address`, so it must stay stable).

Verify on the WSL/devbox runner under `python:3.13` **and** `python:3.14`.

## Out of scope (but mechanism-compatible) — netwatch naming (jnctech #70)

[jnctech #70](https://github.com/jnctech/homeassistant-mikrotik_router/issues/70) ("use netwatch names as device names") is the **same class of bug** — many netwatch entities collapse to one name because they share `comment`, and the user wants the distinct `name` field shown. It is **deliberately out of scope here** because it needs more than this ADR's flag:
- `get_netwatch` (`coordinator.py:~1542`) does **not** currently parse a `name` field — it would have to be added to the dataset.
- netwatch's descriptor uses `data_name_comment=True`, so the user's "use name, not comment" requires a **precedence decision** (name vs comment) that conflicts with the current comment-first behaviour.
- The collapse there fires via the **comment branch** (`entity.py:302-303`), not only the `:306` shortcut.

`data_name_compose` is therefore designed **generally** (§B) so that, in a follow-up PR, netwatch can adopt it (with `data_name="name"`) once `get_netwatch` provides `name` and the precedence is decided. Tracked separately; not delivered by this ADR.

### Related requests checked (no requirement missed)
- upstream tomaae **#130** (device-tracker id churn after re-add) — about `unique_id` stability, which this ADR leaves untouched. No regression.
- upstream **#306** (duplicate names in the *device*, e.g. "hAP ac³ hAP ac³") — device-registry layer, not `custom_name`. Out of scope, not claimed.
- upstream **#321** (expose DHCP client/relay/server *values*) — new sensors, orthogonal to naming. Not delivered here.

## Provenance
All facts cite code `file:line` on `dev` or live recorder-DB queries against the running v2.3.18 box (2026-06-08). The brief's "named after the interface" premise and the `host-name == interface` detector were both refuted by the live data and replaced with the non-unique-hostname model above.
