# ADR-021: WireGuard peer sensors (B2) — per-peer handshake/connectivity, capability-gated and redacted

**Date:** 2026-09-07
**Status:** Accepted — design agreed with the maintainer 2026-09-07; implementation pending under `ENH-260703-wireguard-sensors` (FEATURE-POLL B2, operator-requested).

## Context

B2 ("WireGuard VPN monitoring") — surface per-peer state so users can alert on *"is my remote site connected?"*, do presence detection via VPN, or catch a stale tunnel. Today the integration surfaces WireGuard only at the **interface** level via the generic `/interface` handling (per-interface tx/rx + a connection binary_sensor, e.g. `wg-home`, `wg-us`). There is **no WireGuard-specific code** — confirmed by grep; peers are greenfield.

Live-fleet recon of `/interface/wireguard/peers` (2026-09-07, RB4011, fields shown non-sensitive):

| Peer | Interface | last-handshake | rx | tx | disabled |
|---|---|---|---|---|---|
| (peer A) | wg-home (server) | 53s | ~1.7 GiB | ~490 MiB | no |
| (peer B) | wg-us (client) | 1m28s | ~517 MiB | ~23 MiB | no |

Per-peer fields available: `interface`, `name` (ROS ≥ 7.15), `comment`, `last-handshake`, `rx`, `tx`, `disabled`, `responder`, `public-key`, `endpoint-address`/`-port`, `current-endpoint-address`/`-port`, `allowed-address`.

Facts that drive the design:

1. **`last-handshake` is a duration (age), not a timestamp.** RouterOS reports `"53s"`, `"1m28s"` — seconds since the last handshake, not an absolute time. Mirrors the LTE `session-uptime` case (ADR-019), which computed a TIMESTAMP from an age.
2. **WireGuard is connectionless.** There is no "connected" flag — a peer only handshakes when there is traffic (or on a keepalive interval if configured). "Connected" must be *derived* from handshake recency, and an idle-but-reachable peer with no keepalive can look down. This is inherent, not a bug.
3. **Peer identifiers are sensitive.** `public-key`, `endpoint-address`, `current-endpoint-address`, and `allowed-address` reveal identity and remote topology. `comment` is user-authored and can carry PII.
4. **No `support_wireguard` capability flag exists.** The flags at `coordinator.py:332-338` cover capsman/wireless/ppp/ups/gps/container/lte only.

Existing precedents (verified, `custom_components/mikrotik_router/`):

- **Dynamic table → entities + stable composite/uid:** netwatch (`coordinator.py:1721-1743`), and see ADR-020 for the `val_proc`-combine keying pattern.
- **Capability gate + conditional creation:** `support_lte = bool(self.api.query("/interface/lte"))` (`coordinator.py:563`); flags init `coordinator.py:332-338`.
- **Age → TIMESTAMP sensor:** LTE `session-uptime` (ADR-019).
- **Hidden-by-default identifier + redaction:** `lte_imei/imsi/iccid` use `entity_registry_enabled_default=False` (`sensor_types.py:236/249/262`) and are listed in `TO_REDACT` (`const.py:72,102-104`); diagnostics redacts via `async_redact_data(..., TO_REDACT)` (`diagnostics.py:18-22`).
- **unique_id formula:** `<inst>-<key>-slugify(row[data_reference])` (`entity.py:366`).

## Decision

### 1. Capability-gated conditional creation

- New `support_wireguard = bool(self.api.query("/interface/wireguard"))`, mirroring `support_lte` (init at `coordinator.py:332-338`, detect near `coordinator.py:563`).
- Non-WireGuard routers create **zero** peer entities (same conditional-creation guarantee that gave LTE 0 phantom entities on the non-LTE fleet).
- Gated by **both** the capability flag (creation) **and** a user opt-in option `CONF_SENSOR_WIREGUARD` (default `False`), mirroring the PoE/netwatch/route pattern (`const.py`, `option_sensor_*` at `coordinator.py:439-458`, `config_flow.py`). Rationale (operator decision 2026-09-07): peers are identifying, so surfacing them is an explicit opt-in even though poll cost is low. On a WG router, peer entities appear only when the option is enabled; on a non-WG router, nothing appears regardless.

### 2. Per-peer entities — `ha_group="WireGuard"`

- **binary_sensor: connected** — derived from `last-handshake` age < threshold (default **180 s**). The core "is the peer / remote site up" signal.
- **sensor: last-handshake (TIMESTAMP)** — computed `utcnow() − age` at poll time (LTE `session-uptime` precedent). A stable, graphable "when did it last handshake", rather than a value that churns every poll.
- **sensor: rx / tx per peer** — `data_size` GB, `total_increasing`, like interface totals. (See Open Question 3.)
- **Attributes:** `interface`, `responder`, `name`/`comment`, and (redacted in diagnostics) `current-endpoint-address`, `allowed-address`.
- **public-key:** not a default entity. It is the keying field; if surfaced at all, a disabled-by-default sensor (`entity_registry_enabled_default=False`) and in `TO_REDACT` — the LTE IMEI treatment.

Naming precedence (ADR-018 `data_name_prefer`): peer `name` → `comment` → a truncated public-key fingerprint.

### 3. Stable keying

- Key peers by **`public-key`** — globally unique and stable across reboots (unlike `.id`). `unique_id = <inst>-<key>-slugify(public-key)` via the generic formula (`entity.py:366`). New entities, so **no migration**.
- Do **not** key on `.id` (unstable) or `name` (absent on ROS < 7.15, not guaranteed unique).
- The raw public-key is used only for identity/uid — never surfaced as an enabled state/attribute (see §2).

### 4. "Connected" heuristic

- `connected = (now − last-handshake) < 180 s`, hardcoded as a named constant (e.g. `WIREGUARD_STALE_SECONDS = 180`; operator decision 2026-09-07). WireGuard rekeys roughly every 2 min under traffic; 180 s is the common "up" window. Promote to an option later if users ask.
- **Never-handshaked peer:** `last-handshake` absent → `connected = off`, timestamp = `None` (the `.get()` unknown-not-stale base-class fix from #120 already handles the missing field).
- **Documented caveat:** an idle peer without a keepalive can read "disconnected" though reachable — inherent to WireGuard's connectionless model.

### 5. Redaction

- Add to `TO_REDACT` (`const.py:72`): `public-key`, `endpoint-address`, `current-endpoint-address`, `allowed-address`. Diagnostics already redacts the coordinator data dict through `TO_REDACT`, so this covers dumps automatically.
- `comment` is user-authored and user-visible by choice (it may be used as the display name); treated like other comment fields — not auto-redacted, but flagged here as a possible PII carrier.

## Alternatives Considered

- **A. Expose `last-handshake` as a duration (seconds-ago) sensor.** Rejected — a relative value churns every poll and graphs poorly; a computed TIMESTAMP is stable.
- **B. All peer fields as attributes on one sensor.** Rejected — same rationale as ADR-019: discrete sensors give per-field history and alerting.
- **C. Key on `.id` or `name`.** Rejected — `.id` unstable; `name` optional (ROS < 7.15) and not guaranteed unique.
- **D. Always fetch (no capability gate).** Rejected — non-WireGuard routers would pay the poll and could get phantom entities; conditional creation (LTE precedent) avoids both.
- **E. Expose `public-key` as an enabled sensor.** Rejected — identifying; hidden-by-default + redacted (LTE IMEI precedent).

## Consequences

**Positive:** remote-site up/down alerts, VPN-presence automations, per-peer transfer; correct conditional creation (0 entities on non-WG routers); reuses LTE (age→timestamp, hidden+redact) and netwatch (dynamic table) precedents — low structural risk.

**Negative:** the "connected" signal is threshold-based and can false-negative on idle keepalive-less peers (inherent to WireGuard); peer `comment` may carry PII if the user surfaces it as a name.

**Neutral:** new `support_wireguard` flag, new `ha_group="WireGuard"`, `TO_REDACT` additions.

## Test Plan

- **Unit:** `get_wireguard_peers()` parse (age→timestamp, connected threshold, never-handshaked → off/None), public-key keying, and the `support_wireguard` gate producing no phantom entities on a non-WG router. ADR-014 golden entity tests for the binary_sensor + timestamp + rx/tx sensors.
- **Live validation (per `docs/release-validation.md`):** RB4011 (two peers across a server `wg-home` and a client `wg-us`); confirm `connected` flips when a peer idles past the threshold; verify `public-key`/endpoints are redacted in a diagnostics dump; verify a non-WG device (CRS310) creates zero peer entities.

## Decisions (resolved 2026-09-07 with the maintainer)

1. **Gating — capability flag + opt-in option.** Both `support_wireguard` (creation) **and** a user option `CONF_SENSOR_WIREGUARD` (default off). Peers are identifying, so surfacing them is explicit opt-in.
2. **"Connected" threshold — hardcoded 180 s** named constant in v1; promote to an option later if asked.
3. **v1 sensors — the full set:** `connected` binary_sensor + `last-handshake` TIMESTAMP + per-peer rx/tx.

## Implementation checklist (from the code map — see `ENH-260703`)

1. `const.py` — `CONF_SENSOR_WIREGUARD` / `DEFAULT_SENSOR_WIREGUARD = False`; `WIREGUARD_STALE_SECONDS = 180`; add `public-key`, `endpoint-address`, `current-endpoint-address`, `allowed-address` to `TO_REDACT`.
2. `coordinator.py` — `support_wireguard` flag init (`:332-338`) + detect `bool(query("/interface/wireguard"))` (near `:563`); `option_sensor_wireguard` property; `"wireguard_peers": {}` in `self.ds`; `get_wireguard_peers()` getter (path `/interface/wireguard/peers`, `key="public-key"`, age→timestamp for `last-handshake`, derive `connected`); register in the gated getter list gated on `support_wireguard and option_sensor_wireguard`; add to `_ENTITY_UID_PATHS`.
3. `binary_sensor_types.py` — per-peer `connected` description (`data_path="wireguard_peers"`, `data_reference="public-key"`, `DEVICE_ATTRIBUTES_WIREGUARD_PEER`).
4. `sensor_types.py` — `last-handshake` (TIMESTAMP), rx, tx (data_size / total_increasing); public-key sensor `entity_registry_enabled_default=False` if surfaced at all.
5. `entity.py` — `_skip_*` branch gating the peer group on `CONF_SENSOR_WIREGUARD`.
6. `config_flow.py` — `vol.Optional(CONF_SENSOR_WIREGUARD, ...)` toggle.
7. `strings.json` + `translations/*.json` (29 locales) — the new option label/description.
8. Tests — unit (`get_wireguard_peers` parse, age→timestamp, connected threshold, never-handshaked → off/None, `support_wireguard` gate → no phantom entities) + ADR-014 goldens; live validation on RB4011 (2 peers) + a non-WG device (0 entities) + diagnostics redaction check.
