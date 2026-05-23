# ADR-011: CAPsMAN AP-virtual interface — additive attribute, no source flip

**Date:** 2026-05-23
**Status:** Accepted

## Context

`device_tracker` entities for wireless clients are supposed to surface the AP-virtual interface (e.g. `Slaapkamer`, `Zolder`) so users can build automations on "which AP is this client on". In practice this rarely worked — issue [#68](https://github.com/jnctech/homeassistant-mikrotik_router/issues/68) (reporter @fuecy, RouterOS 7.21.4 + legacy CAPsMAN) reported the `interface` attribute showing only the bridge name.

Independent exploration of `coordinator.py` (2026-05-12 plan, file `handover-issue-68-atomic-bunny.md`) identified two false premises from an earlier feasibility note and one real bug:

1. **False premise:** later merges (DHCP/ARP/bridge) overwrite `interface` set by capsman. They don't — each later merge has a `source` skip guard, so once a host is claimed `source="capsman"`, its `interface` stays the AP name.
2. **False premise:** the bug is in merge ordering. It isn't — `_merge_capsman_hosts()` is called first in `async_process_host()`.
3. **Real bug:** `_merge_capsman_hosts()` early-continues when an existing host's `source != "capsman"`. Routers with persistent DHCP leases see DHCP/ARP claim hosts on every poll (because the lease is still current from the previous poll), so by the time capsman runs the next poll, the host is already claimed by DHCP. capsman skips, and the AP-virtual interface is **never recorded at all** for those hosts.

@fuecy confirmed on 2026-05-12: additive approach OK, RouterOS 7.21.4, `/caps-man/registration-table` is populated; `/interface/wifi/registration-table` returns empty (he's still running legacy CAPsMAN on a router whose firmware version would normally route the code to the new wifi endpoint — see "Known limitation" below).

## Decision

### 1. Add a new attribute `capsman-interface` to the host record

`capsman-interface` is **always** written by `_merge_capsman_hosts()` for any client appearing in `/caps-man/registration-table` (or `/interface/wifi/registration-table` on v7.13+ with the new WiFi package), **regardless of which source claimed the host first**.

`interface` and `source` remain owned by whichever merge claimed the host first — this preserves the semantics that existing automations may filter on. The new `capsman-interface` is the canonical source for "which AP is this client on".

### 2. Two-path `_merge_capsman_hosts()` logic

The existing single-path loop with `elif source != "capsman": continue` is replaced with two explicit paths via helpers:

- **New host** (`uid not in ds["host"]`) — `_write_capsman_claim()`: set `source="capsman"`, write `mac-address`, `interface`, `capsman-interface`, copy wireless metrics, update `available`/`last-seen`.
- **Existing host** (`uid in ds["host"]`) — `_write_capsman_overlay()`: write `capsman-interface` and copy wireless metrics (additive only). Update `available`/`last-seen` *only* if `source == "capsman"` (preserves the semantics that DHCP/ARP/bridge sources manage their own availability).

The `detected` set used by `_remove_undetected_hosts` is populated when the host *is* capsman-sourced — overlayed entries that DHCP claimed don't enter the capsman-detected set.

Helpers (`_write_capsman_claim`, `_write_capsman_overlay`, `_copy_capsman_metrics`) keep the main `_merge_capsman_hosts` function under the ≤15 complexity ceiling per ADR-007 (mechanically enforced via ruff C901 once ADR-010-claude-tooling-baseline merges to dev).

### 3. Dual-endpoint probe with fallback

`get_capsman_hosts()` probes endpoints in preference order and uses the first one that returns rows:

- **v7.13+:** `/interface/wifi/registration-table` first, `/caps-man/registration-table` as fallback.
- **v6 / v7 ≤ 12:** `/caps-man/registration-table` only (the wifi endpoint doesn't exist on these versions and would error if queried).

The fallback is necessary because some v7.13+ users (e.g. #68 reporter @fuecy on RouterOS 7.21.4) still run legacy CAPsMAN — their version-preferred endpoint returns empty while the legacy endpoint has data. Without the fallback, the new `capsman-interface` attribute wouldn't populate for them.

When the fallback fires, `_LOGGER.info` records the transition (`"CAPsMAN endpoint fallback: primary X returned no rows, using Y instead"`) so operators can confirm in their logs that the fix is doing the right thing on their router.

Helpers (`_capsman_endpoints_to_probe`, `_fetch_capsman_table`) keep `get_capsman_hosts` well under the ≤15 complexity ceiling.

### 4. Per-endpoint field lists in `get_capsman_hosts()`

The legacy `/caps-man/registration-table` endpoint (v6, v7 ≤ 12) returns a rich payload (RSSI, rates, uptime, bytes, packets, last IP, EAP identity). The new `/interface/wifi/registration-table` endpoint (v7.13+, new WiFi package) has an unverified field schema. v2.3.17 ships the **full payload extraction on the legacy path** and the **conservative 3-field extraction (`mac-address`, `interface`, `ssid`) on the new path** — v2.3.18 can extend the v7.13+ field list once a real payload is observed.

The `rx-signal` field on the legacy endpoint is renamed to `signal-strength` post-`parse_api` for cross-endpoint consistency with `/interface/wireless/registration-table` (which already uses `signal-strength`).

## Alternatives Considered

### A. Flip `interface` for capsman-claimed hosts and add a `bridge-interface` attribute
Rejected. Would change behaviour for users whose automations already filter on `interface == "<bridge>"`. The additive approach is strictly safer and matches what @fuecy explicitly approved.

### B. Change merge ordering so capsman always wins
Rejected. Existing `source` semantics are visible to users via the `source` attribute (some users filter on it). Changing the claim winner would break their automations.

### C. Single-endpoint selection by version (no fallback)
Considered and rejected during the design pass. The version check (v7.13+ → wifi, otherwise → caps-man) misroutes users like @fuecy who run legacy CAPsMAN on a v7.13+ firmware (their wifi endpoint is empty). v2.3.17 includes the dual-endpoint fallback (Decision §3 above) to handle this case in one shipment rather than deferring to v2.3.18.

### D. Add v7.13+ debug logging of raw rows for field-schema discovery
Plan called for this (`_LOGGER.debug("capsman v7.13 raw row: %s", row)`). Skipped in v2.3.17 because the field discovery only helps users who have data on the wifi endpoint, and the simpler path forward is asking volunteers to paste a `/rest/interface/wifi/registration-table` response on a follow-up issue.

## Consequences

### Positive

- Users get a stable, named attribute for "which AP is this client on", independent of merge timing.
- Existing automations relying on `interface` and `source` are unchanged.
- The `_merge_capsman_hosts` rewrite uses extracted helpers (per ADR-007), each under the ≤15 complexity gate. Future capsman field additions can extend `_copy_capsman_metrics` without touching the merge logic.

### Negative

- The new attribute appears on *every* device-tracker entity declaration's `DEVICE_ATTRIBUTES_HOST` list — non-capsman hosts simply won't have the key in their data and `copy_attrs` will omit it. Side effect: there is no protection if a non-wireless host ever ends up with a stray `capsman-interface` key (no current code path that does this, but worth noting).
- Dual-endpoint probing makes one extra API call per poll for v7.13+ users when the primary endpoint returns no rows — i.e. only for users in @fuecy's exact configuration. Once they upgrade to the new WiFi package, the fallback stops firing and the second query disappears. Cheap in practice (registration tables are small).

### Neutral

- `support_capsman` continues to gate the merge entirely; non-CAPsMAN routers see no change.
- `tx-rate-set`, `uptime`, `bytes`, `packets`, `last-ip`, `eap-identity` are stored in `ds["capsman_hosts"]` (post-PR) but not merged into `ds["host"]`. They're available for future feature work but not yet exposed as entities.
