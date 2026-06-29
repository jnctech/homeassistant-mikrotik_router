# ADR-017 — PoE-out energy accumulation (measured + nameplate estimate)

**Status:** Accepted — implemented on `feature/poe-energy-sensors` (CR-260614-poe-energy-sensors). Ships beta-gated as `v2.3.20-beta.1` for live validation on metering hardware.
**Date:** 2026-06-14
**Supersedes/relates:** `ENH-260509-poe-energy` (#59). G0 design panel 2026-06-14.
**Numbering note:** ADR-014 is the highest on disk. **ADR-015** is reserved (librouteros salvage renumber) and **ADR-016** is reserved (coordinator decomposition) per `docs/ISSUES.md`. This feature therefore takes **017**.

## Context

[#59](https://github.com/jnctech/homeassistant-mikrotik_router/issues/59) (@Dillton) asks for native PoE-out **energy** (kWh) sensors for the HA Energy Dashboard so users don't hand-build Integration/Utility-Meter helpers. RouterOS exposes only **instantaneous** PoE-out power (`/interface/ethernet/poe monitor` → `poe-out-power`, W), no energy accumulator — so energy must be integrated in-integration.

Two hardware realities, both **verified live 2026-06-14**:
- **Metering hardware** reports a real `poe-out-power` per port (e.g. @Dillton's box). Here energy = trapezoidal integral of the measured power.
- **Non-metering hardware** powers a device but reports no power: the maintainer's hAP ax3 ether1 is `poe-out-status: powered-on` with **no** `poe-out-power/voltage/current` fields at all (`/interface/ethernet/poe/monitor [find] once`). For these, the only attribution is a **nameplate estimate** of the downstream device — identifiable via MikroTik Neighbor Discovery (`/ip/neighbor` → `board`; ether1 → `RBD52G-5HacD2HnD` = hAP ac²). Multi-neighbour ports (e.g. ether2 → rb4011 + CRS310) are **not** attributable.

The maintainer cannot self-validate accuracy (null PoE power), hence the beta gate on reporter hardware.

## Decision

### 1. Ownership — entity owns the durable total; coordinator emits per-poll deltas
Entities are created **after** the first coordinator poll (`entity.py:_run_entity_setup_loop`), so a coordinator-held running total would advance from 0 before any RestoreSensor could seed it — losing energy on every restart. Therefore:
- The **coordinator** holds only transient `self._poe_energy_last_power[uid]` (W) and writes a per-poll increment `ds["interface"][uid]["poe-out-energy-delta-wh"]` (Wh), plus a device-total delta into `ds["resource"]`.
- The **entity** (`MikrotikPoEEnergySensor(MikrotikSensor, RestoreSensor)`) owns the durable `_accumulated_kwh`, restores it on `async_added_to_hass` via `async_get_last_sensor_data()`, and adds each poll's delta. No state is ever written back into the coordinator.

### 2. Integration — trapezoid over the configured scan interval
`delta_wh = max(0.0, (p_now + p_prev) / 2 * interval / 3600)`, `interval = option_scan_interval.seconds` — mirroring `_calculate_interface_traffic` (`coordinator.py`). Using the **configured** interval (not measured wall-clock elapsed) means a missed/late poll or a restart can never integrate a phantom area: no `last_ts` state, nothing to survive restarts. The first sample of a port (no prev) and any `None` power contribute **0** and clear the prev sample, so energy is never integrated across an unpowered gap.

### 3. Monotonicity — `total_increasing` proven non-decreasing
Both the coordinator step and the entity accumulation clamp the increment `>= 0`, and the entity only ever does `_accumulated_kwh += increment`, so the exposed value cannot decrease — a port going `None`→present, a clock-skew negative dt, or a restart (first post-restart delta is 0) never produce a backward step that HA would read as a meter reset.

### 4. Device-total — sum of per-poll deltas, as its own RestoreSensor
RouterOS exposes no aggregate PoE energy register `[UNVERIFIED — Dillton]`, so the device total is the sum of per-port increments accumulated by a second RestoreSensor (`MikrotikPoEEnergyTotalSensor`, no-uid, `data_path="resource"`). It accumulates the **same delta source** as the per-port sensors (not `sum(entity.native_value)`), so total and per-port stay consistent across restarts. The resource delta is `None` (not `0.0`) when no port has attributable energy, so the total is not created on PoE-enabled routers with no PoE-out load.

### 5. Measured vs estimated — labelled, never conflated
`_resolve_poe_power` returns `(watts, source, model)`: measured `poe-out-power` when present; else, for a `powered-on` port with **exactly one** neighbour whose `board` is in `_POE_DEVICE_NAMEPLATE`, the nameplate watts (`source="estimated"`, `model=board`); else `(None, None, None)` (null-not-guess — ambiguous/unknown ports get no sensor). The entity surfaces `power_source` (+ `estimated_from_model`) as attributes. Nameplate values are the vendor datasheet **maximum** (an upper bound; real draw is lower), each entry citing its source — estimated energy is explicitly coarse.

### 6. entity_category = None
The energy descriptors omit `entity_category` (existing PoE sensors are `DIAGNOSTIC`) so they are user-facing and selectable as Energy-Dashboard sources. Whether a `DIAGNOSTIC` category disqualifies an entity from the Energy-Dashboard picker is an HA-frontend behaviour **not verifiable in this repo** — `None` is the safe default; confirmed-on-live is a beta task.

### 7. Opt-in reuses `CONF_SENSOR_POE`
No new toggle — energy is meaningless without PoE monitoring. Neighbour discovery (`get_neighbor`) and accumulation only run when `option_sensor_poe` is set.

## Consequences
- New `unique_id`s only (`poe_out_energy-<port>`, `poe_out_energy_total`); no migration; existing entities/automations untouched.
- New net pattern for the repo (RestoreSensor; only `MikrotikSwitch` used `RestoreEntity` before).
- `_handle_coordinator_update` accumulates **before** `super()` writes HA state (the base couples refresh+write); the duplicated data lookup is the deliberate cost of correct ordering (deferring it past `super()` would record a one-poll-stale total).
- A failed `/ip/neighbor` query retains the prior neighbour map (no estimate-baseline reset on a transient disconnect); a non-numeric `poe-out-power` null-not-guesses rather than crashing the poll.

## Residual risks (only reporter metering hardware closes)
Energy-Dashboard pickability with `entity_category=None`; trapezoidal accuracy vs a true inline meter; restore correctness across a real HA restart; device-total fidelity; and **nameplate accuracy** (datasheet max ≠ actual draw — an upper-bound estimate, labelled as such).
