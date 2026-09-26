# ADR-022: Live interface rates (monitor-traffic) + wifi-type fixes

**Date:** 2026-09-19
**Status:** Accepted — implementation under `feature/wifi-throughput` (throughput feature request, operator-reported on hAP be³).

## Context

The integration already exposes per-interface TX/RX sensors (`traffic_tx` /
`traffic_rx`, B/s) computed as a byte-counter delta over the scan interval
(`_calculate_interface_traffic`), plus TX/RX totals. Three gaps were verified
against a live hAP be³ Media (ROS 7.25beta5, `wifi-qcom-be` package):

1. **Live rate missing.** The delta is a 30 s average (and reads 0 on the first
   poll). RouterOS offers live rates via `/interface monitor-traffic
   interface=<name> once=yes` (`rx/tx-bits-per-second`, packets/drops/errors
   per second) — verified read-only on the be³ (ether1 ~277 kbit/s rx /
   ~318 kbit/s tx at probe time, wifi1 near idle). The integration never
   queries it.
2. **wifi package variants unrecognised.** `_has_wifi_package()` knows only
   `wifi`, `wifi-qcom`, `wifi-qcom-ac`. On `wifi-qcom-be` (and
   `wifi-mediatek`) hardware only the version heuristic (>= 7.13) selects the
   `wifi` module — fragile, and wrong the moment a legacy `wireless` package
   is also present on 7.13+ gear.
3. **wifi registration-table schema unmapped.** `get_wireless_hosts()` parses
   the legacy `wireless` schema (`signal-strength`, `tx-ccq`). The `wifi`
   registration table reports `signal`, `tx-rate`/`rx-rate`,
   `tx-bits-per-second`/`rx-bits-per-second`, `bytes`, `band` — so per-client
   signal/rate data is dropped on wifi hardware. `entity.py` likewise handles
   only type `ether`/`wlan`, leaving type `wifi` without wireless attributes
   or binary-sensor skip treatment.

Existing precedents (verified, `custom_components/mikrotik_router/`):

- **Opt-in option + fetch gate:** `CONF_SENSOR_ROUTE` / `option_sensor_route`
  (`const.py`, `coordinator.py`), gating both the fetch and entity creation
  (`entity.py`), no `support_*` flag when every router has the source (ADR-020 §3).
- **Null-not-guess + stale-clear + DEBUG log:** `get_ups()` pattern
  (CONTRIBUTING §1–3).
- **Per-port monitor with `once=yes`:** `_monitor_ethernet_port()`
  (`coordinator.py`), one `monitor … once: True` call per port.

## Decision

### 1. Live-rate sensors — opt-in, interface-merged, bit/s

- New option `CONF_SENSOR_LIVE_TRAFFIC` (`sensor_live_traffic`, default
  `False`) in `const.py`, `config_flow.py`, `strings.json`,
  `translations/en.json`, with `option_sensor_live_traffic` on the coordinator.
- New `get_interface_live_traffic()` getter: one `/interface`
  `monitor-traffic … once: True` call per non-bridge interface, merging
  `rx-live`/`tx-live` (bit/s) plus `rx/tx-packets-per-second`,
  `rx/tx-drops-per-second`, `rx/tx-errors-per-second` into the existing
  `ds["interface"]` rows (defaults `None` via `ensure_vals`). Registered in
  `_async_update_data` via `_run_if_enabled(…, requires=option)` so the poll
  cost (one ~50–200 ms call per interface) is paid only when opted in.
- New `traffic_tx_live` / `traffic_rx_live` sensor descriptions
  (`SensorDeviceClass.DATA_RATE`, `MEASUREMENT`, bit/s native, kbit/s
  suggested) with `func="MikrotikInterfaceTrafficSensor"`, so the existing
  bridge-skip applies; `_skip_interface_traffic()` gates them on the new
  option instead of `sensor_port_traffic`. Units deliberately differ from the
  averaged sensors (bit/s live vs B/s average) — they answer different
  questions ("what is the rate right now" vs "what was the interval mean").
- Null-not-guess: absent/empty/non-numeric monitor fields → `None`
  (`_to_float_or_none`), so sensors read `unknown`, never stale or fabricated.
  No-data per interface clears that interface's live fields to `None` and logs
  at DEBUG.

### 2. wifi-type fixes (same PR — one reviewable throughput story)

- `_has_wifi_package()`: recognise `wifi-qcom-be` and `wifi-mediatek`
  explicitly; version heuristic and legacy-`wireless` precedence unchanged.
- `get_wireless_hosts()`: also parse the wifi-schema fields (`signal`,
  `tx-bits-per-second`, `rx-bits-per-second`, `bytes`, `band`); alias `signal`
  onto `signal-strength` when the legacy field is absent. No-data clears
  `ds["wireless_hosts"]` to `{}` with a DEBUG log (stale-clear).
- `entity.py`: treat type `wifi` like `wlan` for wireless attributes and for
  the port binary-sensor skip.

### 3. Non-goals

- No per-client WLAN throughput sensors (registration-table bps per MAC) —
  future work behind the client-traffic option.
- No `wifi-monitor` (peers/channel/tx-power) or `ethernet-monitor` summoning
  beyond the existing `_monitor_ethernet_port()` — link rate/status already
  covered there.
- No README/register/CHANGELOG touches — maintainer-owned at merge
  (CONTRIBUTING).

## Alternatives Considered

- **A. Reuse the averaged TX/RX sensors only (document the opt-in).**
  Rejected — the 30 s mean cannot answer "current rate", reads 0 on first
  poll, and gives no pps/drops/errors signal.
- **B. Separate `interface_live` dataset keyed by name.** Rejected — merging
  into `ds["interface"]` reuses the entity keying, bridge-skip, and attribute
  machinery with no migration and no new UID space.
- **C. Always-on live polling (no opt-in).** Rejected — one monitor call per
  interface per poll is a real cost on port-dense routers; opt-in mirrors the
  PoE/netwatch/route pattern.
- **D. Separate PRs for wifi-fix vs live sensors.** Considered; kept as one PR
  because both halves are small, share the ADR/tests, and tell one reviewable
  story ("throughput on wifi-qcom-be hardware").

## Consequences

**Positive:** live per-port rates (ether + wifi + veth) on any RouterOS;
wifi-qcom-be/mtk hardware correctly detected; wifi registration signal/rates
no longer dropped; `wifi`-type interfaces get wireless attributes.

**Negative:** one extra API call per interface per poll while enabled —
documented; users on large switches should weigh scan-interval cost.

**Neutral:** new `sensor_live_traffic` option (default off → zero new entities
unless enabled); new live fields default `None` (no phantom values).
