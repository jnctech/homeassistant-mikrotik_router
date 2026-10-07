# ADR-NEXT: Per-router identity for dummy-MAC virtual interfaces

**Date:** 2026-08-14
**Status:** Proposed
**Numbering note:** Maintainer will number at merge (planned ADR-023; #145 took 022). 015/016 remain reserved.

## Context

Interface entities use `ha_connection=CONNECTION_NETWORK_MAC` with `ha_connection_value=data__port-mac-address`. For virtual interfaces (`default-name == ""`) the coordinator previously set `port-mac-address` to `{mac}-{ifname}`.

RouterOS `lo` always reports an all-zero MAC. Some tunnels report an empty MAC. Every router therefore produced the same connection token (`{all-zero-mac}-lo`, `-wireguard1`, …). Home Assistant's device registry merges on `connections`, so multiple MikroTik config entries collapsed those interfaces onto one device. `via_device` then followed whichever router last wrote the entry.

Real ethernet/wifi MACs are already unique and are not in scope.

## Decision

1. **Coordinator.** For virtual interfaces whose MAC is empty or all-zero, set `port-mac-address` to `{serial}-{ifname}`. Virtual interfaces that do have a hardware MAC keep `{mac}-{ifname}`. When `serial-number` is a CHR/x86 placeholder (`""` / `"N/A"` / `"unknown"`), use `config_entry.entry_id` as the prefix so interface devices do not collide across CHR entries.
2. **Entity `device_info`.** If the connection type is `CONNECTION_NETWORK_MAC` and the value is either already `{identity}-…` or not a real 12-hex MAC, register `(DOMAIN, {identity}-{ifname})` as both `identifiers` and `connections` instead of a MAC connection. Prefer the identity prefix check over hex sniffing so hex-shaped serials stay deterministic. `via_device` remains `(DOMAIN, serial)`.
3. **Do not double-prefix.** When the coordinator has already produced `{identity}-{ifname}`, the entity uses that token as-is.
4. **Leave unique_ids unchanged.** Entity unique_ids already include the config-entry name plus interface name; this is a device-registry identity fix only.

## Alternatives Considered

- **Serial in identifiers only, keep the shared MAC connection.** HA still merges on `connections`, so the collision remains.
- **Skip `lo` / tunnel entities.** Hides the bug rather than fixing identity; users who want those sensors still collide.
- **HA device-registry cleanup / migration.** Existing merged devices are sticky; on modern HA a reload rebinds entities to the new per-router device, and the leftover merged device can then be deleted from its device page.

## Consequences

- Each router's `lo` (and empty-MAC tunnels) becomes its own device, `via` the parent router.
- After upgrade: reload the integration (entities rebind automatically); then delete any leftover merged `lo`/tunnel device from its device page.
- CHR/x86 parent devices that share `(DOMAIN, "N/A")` remain a pre-existing collision; this ADR only de-collides their interface devices via `entry_id` fallback. Full CHR parent identity is out of scope.
- Diagnostics still redact serials (`TO_REDACT`); the new connection token is an internal registry key, not a new user-facing unique_id.
