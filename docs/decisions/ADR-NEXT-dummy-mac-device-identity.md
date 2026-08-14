# ADR-NEXT: Per-router identity for dummy-MAC virtual interfaces

**Date:** 2026-08-14
**Status:** Proposed
**Numbering note:** Next unused on `dev` is 020; 015/016 remain reserved. File as `ADR-NEXT` for maintainer numbering at merge.

## Context

Interface entities use `ha_connection=CONNECTION_NETWORK_MAC` with `ha_connection_value=data__port-mac-address`. For virtual interfaces (`default-name == ""`) the coordinator previously set `port-mac-address` to `{mac}-{ifname}`.

RouterOS `lo` always reports an all-zero MAC. Some tunnels report an empty MAC. Every router therefore produced the same connection token (`{all-zero-mac}-lo`, `-wireguard1`, …). Home Assistant's device registry merges on `connections`, so multiple MikroTik config entries collapsed those interfaces onto one device. `via_device` then followed whichever router last wrote the entry.

Real ethernet/wifi MACs are already unique and are not in scope.

## Decision

1. **Coordinator.** For virtual interfaces whose MAC is empty or all-zero, set `port-mac-address` to `{serial}-{ifname}`. Virtual interfaces that do have a hardware MAC keep `{mac}-{ifname}`.
2. **Entity `device_info`.** If the connection type is `CONNECTION_NETWORK_MAC` but the value is not a real 12-hex MAC, register `(DOMAIN, {serial}-{ifname})` as both `identifiers` and `connections` instead of a MAC connection. `via_device` remains `(DOMAIN, serial)`.
3. **Do not double-prefix.** When the coordinator has already produced `{serial}-{ifname}`, the entity uses that token as-is.
4. **Leave unique_ids unchanged.** Entity unique_ids already include the config-entry name plus interface name; this is a device-registry identity fix only.

## Alternatives Considered

- **Serial in identifiers only, keep the shared MAC connection.** HA still merges on `connections`, so the collision remains.
- **Skip `lo` / tunnel entities.** Hides the bug rather than fixing identity; users who want those sensors still collide.
- **HA device-registry cleanup / migration.** Existing merged devices are sticky and may need a one-time remove+reload; that is an operator step, not a data-format migration, and is documented on the PR rather than automated here.

## Consequences

- Each router's `lo` (and empty-MAC tunnels) becomes its own device, `via` the parent router.
- Already-merged registry devices will not split on upgrade until the merged device (or its all-zero-MAC `lo` connection) is removed and the integration reloads.
- Diagnostics still redact serials (`TO_REDACT`); the new connection token is an internal registry key, not a new user-facing unique_id.
