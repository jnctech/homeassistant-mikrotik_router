# ADR-019: LTE modem sensors (B10)

**Date:** 2026-06-04
**Status:** Accepted — merged to `dev` via PR [#116](https://github.com/jnctech/homeassistant-mikrotik_router/pull/116) (@zvldz); ships beta-first (`v2.3.21-beta.1`).

## Context

`sensor-gap-analysis.md` / `FEATURE-POLL.md` item **B10** — LTE modem stats — is rated **Very High** ("LTE failover monitoring is a top request for rural/backup internet users"), and upstream tomaae issue **#249** (26 comments) requests the same. No implementation exists upstream or in any fork as of 2026-06-04.

RouterOS exposes the data on devices with an LTE interface:
- `/interface/lte/monitor <id> once` — live signal/network/identity (rssi, rsrp, rsrq, sinr, cqi, current-operator, data-class, primary-band, cell ids, status, imei/imsi/iccid, model, revision).
- `/interface/lte/firmware-upgrade <id>` (read-only, no upgrade param) — modem firmware `installed`/`latest`/`status`.

Captured live on a Chateau S53UG (modem EG18-EA) on a live LTE network. Relevant **only if the router has an LTE interface**.

## Decision

### 1. Two coordinator methods, distinct cadence
- **`get_lte_signal()`** — regular poll cycle: `/interface/lte` → `.id` → `/interface/lte/monitor` once → `ds["lte"]`.
- **`get_lte_firmware()`** — hwinfo cycle (4h): `/interface/lte/firmware-upgrade` (read-only) → `ds["lte_firmware"]`.
- **`support_lte`** detected in `get_capabilities()` via `bool(api.query("/interface/lte"))`; both methods gated with `_run_if_enabled(requires=self.support_lte)`.
- *Rationale:* signal drifts over minutes (rssi −76→−79 per session), stable second-to-second → ~1-min poll is enough; firmware is static → 4h; avoid hammering the modem.

### 2. Entities (`ha_group="LTE"`)
- **Signal sensors** (primary, `state_class=measurement`): RSSI, RSRP (`signal_strength`, dBm); RSRQ, SINR (`signal_strength`, dB); CQI (index).
- **Operator** (diagnostic, text) with `data_attributes_list`: data-class, primary-band, current-cellid, enb-id, phy-cellid, sector-id, dl-modulation, mcs, ri, model.
- **Session uptime** (diagnostic, `device_class: timestamp` — session-start time = now − parsed uptime, via `_parse_uptime_to_seconds` + drift-guard, like system uptime).
- **Modem firmware** (diagnostic, text) + attrs latest/status/available.
- **binary_sensor Connection** (`connectivity`, from `status == "running"`).
- **IMEI / IMSI / ICCID** — collected always, exposed as diagnostic sensors with `entity_registry_enabled_default=False` (user opt-in; identifiers are PII-ish, not hidden from collection).

### 3. Conditional creation
No LTE interface → `support_lte=False` → `ds["lte"]`/`ds["lte_firmware"]` stay `{}` → entities not created (existing `entity.py` rule: singular sensor created only if `ds[path].get(attr) is not None`).

## Alternatives Considered

### A. All fields as attributes on a single sensor
Rejected — signal metrics must be standalone sensors to be graphable / get long-term statistics.

### B. Expose IMEI/IMSI/ICCID as regular enabled sensors
Rejected — identifiers are PII-ish; collect them but ship `entity_registry_enabled_default=False`.

### C. Single cadence (all signal+firmware in one cycle)
Rejected — firmware is static (1-min polling wasteful + hits modem), signal is dynamic (4h too coarse).

### D. Gate behind an `option_sensor_lte` toggle
Deferred — conditional creation already prevents noise on non-LTE routers; a toggle can be added later if users want explicit opt-out.

### E. Parse `primary-band` into a discrete band-number sensor
Deferred — raw string (`B40@20Mhz earfcn:… phy-cellid:…`) is simpler; can refine later.

## Consequences

### Positive
- Closes B10 (top community request, upstream #249).
- Graphable signal quality + carrier/connection visibility; modem firmware version.
- Zero footprint on non-LTE routers (conditional creation).

### Negative
- Adds entities on LTE routers; `monitor` command polled every cycle (mitigated: read-only, ~1-min cadence).

### Neutral
- Modem-firmware sensor reuses a previously prototyped approach (`get_lte_firmware`), now folded into this feature.

## Test Plan
- `tests/test_coordinator.py`: `FakeMikrotikAPI` canned responses for `/interface/lte` + `monitor` + `firmware-upgrade` → call `get_lte_signal()`/`get_lte_firmware()` → assert `ds["lte"]`/`ds["lte_firmware"]` fields.
- **No-LTE case:** empty `/interface/lte` → `support_lte=False` → `ds` stays empty → no entities created.
- Per `ha-coding-standards.md`: blocking API calls via executor; lock used as context manager.
