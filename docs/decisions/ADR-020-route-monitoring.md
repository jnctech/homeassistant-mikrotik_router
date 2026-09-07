# ADR-020: Route monitoring (B4) — per-routing-table default-route reachability, bounded by design

**Date:** 2026-09-07
**Status:** Accepted — design agreed with the maintainer 2026-09-07; implementation pending under `ENH-260907-route-monitoring` (FEATURE-POLL B4, user-voted).

## Context

B4 ("route monitoring") was voted for in the feature poll: users want multi-WAN failover awareness — *"WAN1's default route disappeared, traffic is on WAN2"* — surfaced as Home Assistant entities they can alert on.

Live-fleet recon of `/ip/route` (2026-09-07) sets the constraints:

| Device | Total routes | Default routes (`0.0.0.0/0`) | Routing tables |
|---|---|---|---|
| RB4011 | 16 | 1 in `main` + policy defaults | **2** (`main`, `wg_us`) |
| CRS310 | 8 | **2** | 1 |
| hAP ax³ | 5 | 1 | 1 |
| hAP ac² | 2 | 1 | 1 |

Three facts drive the design:

1. **Policy routing is real.** RB4011 runs a `main` default via `pppoe-out1` *and* a separate `wg_us` routing-table with its own static default via `wg-us` plus a **blackhole kill-switch** route (distance 10). A single global "the default gateway" sensor would be wrong here.
2. **Multiple defaults are normal even on simple gear.** CRS310 has two `0.0.0.0/0` routes (dual-uplink / ECMP). "Default route" is a *set*, not a scalar.
3. **Route tables can be unbounded.** Typical gear has 2–16 routes, but a router running BGP/OSPF can hold 100k+. Any design that creates one entity per route row is a non-starter.

Two RouterOS/data facts:

- **`.id` (`*N` handles) is unstable** — reassigned across reboots and route churn. Entities must not key on it.
- Fields available per route: `dst-address`, `routing-table`, `gateway`, `immediate-gw`, `distance`, `scope`, `active`, `dynamic`/`static`/`connect`/`dhcp`/`vpn` flags, `blackhole`, `comment`.

Existing code precedents (verified, `custom_components/mikrotik_router/`):

- **Dynamic table → binary_sensor:** netwatch (`coordinator.py:1721-1743` fetch, `binary_sensor_types.py:144-161` description, generic per-row loop `entity.py:228-244`).
- **Dynamic table → value sensor:** `dhcp_server_lease_count` (`sensor_types.py:1102-1118`).
- **Stable composite UID without `.id`:** `get_nat` / `get_mangle` build a synthetic `uniq-id` from multiple row fields via the `val_proc` "combine" mechanism (`coordinator.py:1355-1382`). This is the pattern route keying should reuse.
- **Option gate:** `CONF_SENSOR_POE` / `CONF_SENSOR_NETWATCH` (`const.py:63-66`), read as `option_sensor_*` (`coordinator.py:439-458`), gating both the fetch (`coordinator.py:745-754`) and entity creation (`entity.py:141-142`).
- **unique_id formula:** `<inst>-<key>-slugify(row[data_reference])` (`entity.py:366`).

## Decision

### 1. Scope — bounded by default, never one entity per route

- v1 default surface = **default routes only** (`0.0.0.0/0` and `::/0`). This is the failover-relevant set and stays tiny even on a full-table router.
- The full route table is **never** enumerated as entities. This is the entity-explosion guard.
- A user watch-list for specific non-default destinations is a **v2** extension, out of scope here.

### 2. Entities — `ha_group="Routing"`

- **binary_sensor per default route** — the RouterOS `active` flag → `on`/`off`. This is the core failover signal. Attributes: `gateway`, `immediate-gw`, `distance`, `routing-table`, `dynamic`/`static`, `blackhole`, `comment`.
- **sensor: active default-route count per routing-table** — for "how many WAN defaults are up" automations. Confirmed in v1 alongside the binary_sensors (operator decision 2026-09-07).

Naming follows the ADR-018 precedent (`data_name_prefer`): route `comment` when set, else a composed `"{routing-table} via {gateway}"`.

### 3. Data fetch + gate

- New `get_route()` getter, path `/ip/route`, registered in the gated getter list (`coordinator.py:745-754`).
- Gate: new user option `CONF_SENSOR_ROUTE` (default `False`) — opt-in, mirroring PoE/netwatch. No hardware `support_*` flag (every router has `/ip/route`), but the option gate is **mandatory** because a full-table fetch is expensive.
- **Bound the fetch — client-side filter.** The API wrapper (`mikrotikapi.py:162-192`) fetches the whole table (`list(connection.path(path))`) and exposes no server-side `where`/proplist filter. So `get_route()` filters to default routes **client-side** immediately after the fetch, so the coordinator dict and entities only ever hold default routes. This still transfers the full table over the API on a BGP/OSPF router, but the opt-in gate means those users simply don't enable it. A server-side `.select(where=...)` filter in the wrapper is a possible future optimization, out of scope for v1.

### 4. Stable keying (the crux)

- Do **not** set `key=".id"` or `data_reference=".id"`.
- Build a synthetic composite UID from **`routing-table` + `dst-address` + `gateway` + `distance`** via the `val_proc` "combine" mechanism (`coordinator.py:1355-1382`), exactly as `get_nat`/`get_mangle` do. Both the getter `key=` and the description `data_reference=` point at that composite.
- `distance` is in the key to distinguish a primary default from a same-table backup/blackhole (RB4011's `wg_us` has a distance-1 gateway default and a distance-10 blackhole; they also differ by `gateway`, but including `distance` is belt-and-suspenders for ECMP/backup pairs).

### 5. Redaction

- On the user's own HA, entity state/attributes carrying gateway IPs are the user's own data — fine.
- The redaction obligation is for **committed artifacts**: this ADR and any docs use interface-name examples only, never real gateway IPs (the `homelab-leak` gate enforces this). Diagnostics output must redact gateway IP addresses the same way other addresses are redacted — confirm against the existing diagnostics redaction before implementing.

## Alternatives Considered

- **A. One entity per route (full table).** Rejected — entity explosion on BGP/OSPF (100k+ rows).
- **B. Single global "default gateway" sensor.** Rejected — wrong under policy routing; RB4011 and CRS310 both disprove the single-default assumption.
- **C. Key on `.id`.** Rejected — unstable; entity churn on every reboot/route change.
- **D. Always-on (no option gate).** Rejected — unbounded `/ip/route` poll cost on full-table routers.
- **E. Surface only a count sensor, no per-route binary_sensors.** Rejected for v1 core — a count tells you *how many* defaults are up but not *which* WAN dropped; the per-route binary_sensor is the actionable failover signal.

## Consequences

**Positive:** multi-WAN / failover automations; correct under policy routing and ECMP; cost bounded by the default-routes-only scope + opt-in gate; reuses existing dynamic-table and composite-key precedents (low structural risk).

**Negative:** v1 covers default routes only (non-default watch-list deferred to v2); comment-based naming is only as good as the user's route comments; adds a config-flow option requiring translation across the 29 locale files.

**Neutral:** new `ha_group="Routing"` device grouping; one new option key.

## Test Plan

- **Unit:** `get_route()` parses default routes, builds the stable composite UID, and handles the multi-table + blackhole + ECMP (2-default) cases. Golden entity tests (ADR-014) for the binary_sensor and the count sensor.
- **Live validation (per `docs/release-validation.md`):** RB4011 (policy routing: `main` + `wg_us`, blackhole), CRS310 (2 defaults), and a single-table device. Failover check: disable/withdraw a default route → its binary_sensor flips `off` and the count decrements within one poll.

## Decisions (resolved 2026-09-07 with operator)

1. **v1 entity set — binary_sensors + count.** Per-default-route `binary_sensor` (the failover signal) **plus** an active-default-count `sensor` per routing-table. (Open Questions 1 + 4.)
2. **Fetch bounding — client-side filter.** The API wrapper has no server-side filter (`mikrotikapi.py:162-192` materializes the full table), so `get_route()` filters to default routes client-side; the coordinator dict and entities only ever hold default routes. Server-side filtering is a future wrapper optimization, out of scope for v1.
3. **Non-default watch-list — deferred to v2.** v1 is default-routes-only. A "monitor these destinations" option is a follow-up once the failover core is validated.
4. **Rollup granularity — per-route + per-table count**, as in decision 1.

## Implementation checklist (from the code map — see `ENH-260907`)

1. `const.py` — `CONF_SENSOR_ROUTE` / `DEFAULT_SENSOR_ROUTE = False`.
2. `coordinator.py` — `"route": {}` in `self.ds`; `option_sensor_route` property; `get_route()` (path `/ip/route`, client-side default-route filter, composite UID via the `val_proc` combine of `routing-table`+`dst-address`+`gateway`+`distance`); register in the gated getter list; add `"route"` to `_ENTITY_UID_PATHS`.
3. `binary_sensor_types.py` — per-default-route description (`data_path="route"`, `data_attribute="active"`, `data_reference=<composite>`, `DEVICE_ATTRIBUTES_ROUTE`).
4. `sensor_types.py` — active-default-count-per-table description.
5. `entity.py` — `_skip_*` branch gating the route group on `CONF_SENSOR_ROUTE`.
6. `config_flow.py` — `vol.Optional(CONF_SENSOR_ROUTE, ...)` toggle.
7. `strings.json` + `translations/*.json` (29 locales) — the new option label/description.
8. Diagnostics — confirm gateway IP redaction.
9. Tests — unit (`get_route` parse + composite UID + multi-table/blackhole/ECMP) and ADR-014 golden entity tests; live validation on RB4011 (policy routing), CRS310 (2 defaults), single-table device.
