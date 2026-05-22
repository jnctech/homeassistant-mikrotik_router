# Data Schema — MikroTik Router HACS Integration

**Date:** 2026-03-25
**Purpose:** Documents every field stored in the coordinator's `self.ds` data store, its source, type, and whether it's surfaced to Home Assistant entities.

---

## Overview

The coordinator maintains state in `self.ds`, a dictionary with **38 top-level keys**. Most keys hold dict-of-dicts (keyed by entity identifier), while 7 are single-dict entries.

**Legend:**
- **Source:** `API` = direct from RouterOS, `Computed` = calculated by coordinator, `Merged` = combined from multiple sources
- **Surfaced:** Entity type that uses this field, or `unused` / `attr-only`
- Fields marked `unused` are fetched but never exposed — these are Category A gap candidates

---

## System Data (single-dict entries)

### `resource`
**API Path:** `/system/resource`
**Key:** Single dict

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| platform | str | API | `unused` |
| board-name | str | API | device info only |
| version | str | API | device info only |
| uptime | datetime | Computed | sensor `system_uptime` |
| cpu-load | str | API | sensor `system_cpu-load` |
| memory-usage | int | Computed (%) | sensor `system_memory-usage` |
| hdd-usage | int | Computed (%) | sensor `system_hdd-usage` |
| free-memory | int | API | `unused` (used in computation) |
| total-memory | int | API | `unused` (used in computation) |
| free-hdd-space | int | API | `unused` (used in computation) |
| total-hdd-space | int | API | `unused` (used in computation) |
| clients_wired | int | Computed | sensor `system_clients-wired` |
| clients_wireless | int | Computed | sensor `system_clients-wireless` |
| captive_authorized | int | Computed | sensor `system_captive-authorized` |

### `health`
**API Path:** `/system/health` (v6) or `/system/health` with name/value pairs (v7+)
**Key:** Single dict

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| temperature | int | API | sensor `system_temperature` |
| voltage | int | API | sensor `system_voltage` |
| cpu-temperature | int | API | sensor `system_cpu-temperature` |
| switch-temperature | int | API | sensor `system_switch-temperature` |
| board-temperature1 | int | API | sensor `system_board-temperature1` |
| phy-temperature | int | API | sensor `system_phy-temperature` |
| power-consumption | int | API | sensor `system_power-consumption` |
| poe-out-consumption | int | API | sensor `system_poe_out_consumption` |
| poe-in-voltage | int | API | sensor `system_poe_in_voltage` |
| poe-in-current | int | API | sensor `system_poe_in_current` |
| fan1-speed | int | API | sensor `system_fan1-speed` |
| fan2-speed | int | API | sensor `system_fan2-speed` |
| fan3-speed | int | API | sensor `system_fan3-speed` |
| fan4-speed | int | API | sensor `system_fan4-speed` |
| psu1-current | int | API | sensor `system_psu1_current` |
| psu1-voltage | int | API | sensor `system_psu1_voltage` |
| psu2-current | int | API | sensor `system_psu2_current` |
| psu2-voltage | int | API | sensor `system_psu2_voltage` |

*Note: v7+ returns health as name/value pairs in `health7`, then mapped into `health`.*

### `routerboard`
**API Path:** `/system/routerboard`
**Key:** Single dict

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| routerboard | bool | API | `unused` (capability check) |
| model | str | API | device info |
| serial-number | str | API | `unused` |
| current-firmware | str | API | update entity |
| upgrade-firmware | str | API | update entity |

### `fw-update`
**API Path:** `/system/package/update`
**Key:** Single dict

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| status | str | API | `unused` (internal check) |
| channel | str | API | `unused` |
| installed-version | str | API | update entity |
| latest-version | str | API | update entity |
| available | bool | Computed | update entity |

### `ups`
**API Path:** `/system/ups` + `/system/ups monitor`
**Key:** Single dict

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| name | str | API | `unused` |
| offline-time | str | API | `unused` |
| min-runtime | str | API | `unused` |
| alarm-setting | str | API | `unused` |
| model | str | API | `unused` |
| serial | str | API | `unused` |
| manufacture-date | str | API | `unused` |
| nominal-battery-voltage | str | API | `unused` |
| enabled | bool | API | capability check |
| on-line | bool | Monitor | binary_sensor `system_ups` |
| runtime-left | str | Monitor | **`unused` — attr defined but not surfaced** |
| battery-charge | int | Monitor | **`unused` — attr defined but not surfaced** |
| battery-voltage | float | Monitor | **`unused` — attr defined but not surfaced** |
| line-voltage | int | Monitor | **`unused` — attr defined but not surfaced** |
| load | int | Monitor | **`unused` — attr defined but not surfaced** |
| hid-self-test | str | Monitor | **`unused` — attr defined but not surfaced** |

*UPS has significant unused data — battery charge, runtime, load, voltage are all fetched but only exposed as binary_sensor attributes, not standalone sensors.*

### `gps`
**API Path:** `/system/gps` (monitor)
**Key:** Single dict

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| valid | bool | Monitor | attr-only |
| latitude | str | Monitor | sensor `system_gps-latitude` |
| longitude | str | Monitor | sensor `system_gps-longitude` |
| altitude | str | Monitor | attr-only |
| speed | str | Monitor | attr-only |
| destination-bearing | str | Monitor | attr-only |
| true-bearing | str | Monitor | attr-only |
| magnetic-bearing | str | Monitor | attr-only |
| satellites | int | Monitor | attr-only |
| fix-quality | int | Monitor | attr-only |
| horizontal-dilution | str | Monitor | attr-only |

---

## Network Interfaces

### `interface`
**API Path:** `/interface` + `/interface/ethernet` + monitor commands
**Key:** Dict of dicts, keyed by `default-name` or `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| default-name | str | API | attr |
| .id | str | API | internal |
| name | str | API | attr |
| type | str | API | attr |
| running | bool | API | binary_sensor |
| enabled | bool | Computed | switch |
| port-mac-address | str | API | attr |
| comment | str | API | attr |
| last-link-down-time | str | API | attr |
| last-link-up-time | str | API | attr |
| link-downs | int | API | **attr-only — not a sensor** |
| tx-queue-drop | int | API | **`unused`** |
| actual-mtu | int | API | attr |
| about | str | API | `unused` |
| rx / tx | float | Computed | sensor (traffic rate) |
| rx-current / tx-current | float | Computed | sensor (traffic total) |
| client-ip-address | str | Computed | attr |
| client-mac-address | str | Computed | attr |
| poe-out | str | API (ethernet) | switch/sensor |
| poe-out-status | str | Monitor | sensor |
| poe-out-voltage | float | Monitor | sensor |
| poe-out-current | float | Monitor | sensor |
| poe-out-power | float | Monitor | sensor |
| status | str | Monitor (ethernet) | attr |
| rate | str | Monitor (ethernet) | attr |
| full-duplex | bool | Monitor (ethernet) | attr |
| auto-negotiation | str | Monitor (ethernet) | attr |
| sfp-temperature | float | Monitor (SFP) | attr |
| sfp-supply-voltage | float | Monitor (SFP) | attr |
| sfp-tx-power | float | Monitor (SFP) | attr |
| sfp-rx-power | float | Monitor (SFP) | attr |
| sfp-module-present | bool | Monitor (SFP) | attr |
| *(+15 more SFP fields)* | varies | Monitor | attr |
| *(wireless fields merged)* | varies | from `wireless` | attr |

### `wireless`
**API Path:** `/interface/wifi` or `/interface/wifiwave2` or `/interface/wireless`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| ssid | str | API | attr |
| mode | str | API | attr |
| radio-name | str | API | attr |
| frequency | str | API | attr |
| band | str | API | attr |
| channel-width | str | API | attr |
| hide-ssid | bool | API | attr |
| *(+12 more wireless config fields)* | varies | API | attr |

### `wireless_hosts`
**API Path:** `/interface/[wifi]/registration-table`
**Key:** Dict of dicts, keyed by `mac-address`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| mac-address | str | API | internal |
| interface | str | API | host merging |
| ap | bool | API | `unused` |
| uptime | str | API | **`unused`** |
| signal-strength | str | API | host attr (via merge) |
| tx-ccq | str | API | host attr (via merge) |
| tx-rate | str | API | host attr (via merge) |
| rx-rate | str | API | host attr (via merge) |

### `bonding`
**API Path:** `/interface/bonding`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| name | str | API | internal |
| mac-address | str | API | internal |
| slaves | str | API | `unused` |
| mode | str | API | `unused` |

### `bridge_host`
**API Path:** `/interface/bridge/host`
**Key:** Dict of dicts, keyed by `mac-address`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| mac-address | str | API | internal |
| interface | str | API | internal |
| bridge | str | API | internal |
| enabled | bool | Computed | `unused` |

---

## IP / DHCP / ARP

### `arp`
**API Path:** `/ip/arp`
**Key:** Dict of dicts, keyed by `mac-address`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| mac-address | str | API | internal |
| address | str | API | host detection |
| interface | str | API | host detection |
| status | str | API | host availability |
| bridge | str | Computed | internal |

### `dhcp`
**API Path:** `/ip/dhcp-server/lease`
**Key:** Dict of dicts, keyed by `mac-address`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| mac-address | str | API | internal |
| address | str | API | host IP |
| host-name | str | API | host name |
| status | str | API | **`unused` as sensor** |
| last-seen | str | API | host tracking |
| server | str | API | internal |
| comment | str | API | **`unused`** |
| enabled | bool | Computed | `unused` |
| interface | str | Computed | host detection |

### `dhcp-server`
**API Path:** `/ip/dhcp-server`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| name | str | API | sensor ID |
| interface | str | API | attr |
| address-pool | str | API | attr |
| enabled | bool | API (reversed `disabled`) | attr |
| comment | str | API | attr |
| status | str | Computed | sensor `dhcp_server_status` |
| lease-count | int | Computed | sensor `dhcp_server_lease_count` |

*Added in v2.3.13: status derived from enabled flag, lease-count tallied from DHCP leases.*

### `dhcp-client`
**API Path:** `/ip/dhcp-client`
**Key:** Dict of dicts, keyed by `interface`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| interface | str | API | sensor ID |
| status | str | API | sensor |
| address | str | API | sensor |
| gateway | str | API | attr |
| dns-server | str | API | attr |
| dhcp-server | str | API | attr |
| expires-after | str | API | attr |
| comment | str | API | attr |

### `dhcp-network`
**API Path:** `/ip/dhcp-server/network`
**Key:** Dict of dicts, keyed by `address`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| address | str | API | internal |
| gateway | str | API | `unused` |
| netmask | str | API | `unused` |
| dns-server | str | API | `unused` |
| domain | str | API | `unused` |
| IPv4Network | object | Computed | internal (accounting) |

### `dns`
**API Path:** `/ip/dns/static`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| name | str | API | `unused` |
| address | str | API | `unused` |
| comment | str | API | `unused` |

*DNS static entries are fetched but completely unused — no entity references them.*

---

## Firewall Rules

### `nat`
**API Path:** `/ip/firewall/nat`
**Key:** Dict of dicts, keyed by `.id`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| .id | str | API | internal |
| chain | str | API | `unused` |
| action | str | API | `unused` |
| protocol | str | API | switch attr |
| dst-port | str | API | switch attr |
| in-interface | str | API | switch attr |
| to-addresses | str | API | switch attr |
| to-ports | str | API | switch attr |
| comment | str | API | switch attr |
| enabled | bool | Computed | switch |
| uniq-id | str | Computed | dedup |
| name | str | Computed | display |

*Same structure for `mangle`, `filter`, `raw` — see gap analysis for details.*

---

## Traffic Accounting

### `client_traffic`
**API Path:** `/ip/accounting/snapshot` (v6) or `/ip/kid-control/device` (v7+)
**Key:** Dict of dicts, keyed by `mac-address`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| address | str | Copied from host | attr |
| mac-address | str | Copied from host | attr |
| host-name | str | Copied from host | attr |
| authorized | bool | Computed | attr |
| bypassed | bool | Computed | attr |
| available | bool | Computed | internal |
| local_accounting | bool | Computed | internal |
| wan-tx | float | Computed (v6) | sensor |
| wan-rx | float | Computed (v6) | sensor |
| lan-tx | float | Computed (v6) | sensor |
| lan-rx | float | Computed (v6) | sensor |
| tx | float | Computed (v7) | sensor |
| rx | float | Computed (v7) | sensor |

---

## Services & Management

### `script`
**API Path:** `/system/script`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| name | str | API | button ID |
| last-started | str | API | attr |
| run-count | str | API | attr |

### `environment`
**API Path:** `/system/script/environment`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| name | str | API | sensor ID |
| value | str | API | sensor |

### `queue`
**API Path:** `/queue/simple`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| .id | str | API | internal |
| name | str | API | switch display |
| target | str | API | attr |
| comment | str | API | attr |
| enabled | bool | Computed | switch |
| download-rate | str | Computed | **attr-only — not a sensor** |
| upload-rate | str | Computed | **attr-only — not a sensor** |
| download-max-limit | str | Computed | **attr-only — not a sensor** |
| upload-max-limit | str | Computed | **attr-only — not a sensor** |
| *(+8 more computed queue fields)* | str | Computed | **attr-only — not sensors** |

### `kid-control`
**API Path:** `/ip/kid-control`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| name | str | API | switch display |
| rate-limit | str | API | attr |
| mon-sun | str | API | attr |
| comment | str | API | attr |
| blocked | bool | API | attr |
| paused | bool | API | switch |
| enabled | bool | Computed | switch |

### `ppp_secret`
**API Path:** `/ppp/secret` + `/ppp/active`
**Key:** Dict of dicts, keyed by `name`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| name | str | API | binary_sensor/switch ID |
| service | str | API | attr |
| profile | str | API | **`unused`** |
| comment | str | API | attr |
| enabled | bool | Computed | switch |
| connected | bool | Computed | binary_sensor |
| caller-id | str | Merged (active) | attr |
| address | str | Merged (active) | **`unused`** |
| encoding | str | Merged (active) | attr |

### `netwatch`
**API Path:** `/tool/netwatch`
**Key:** Dict of dicts, keyed by `host`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| host | str | API | binary_sensor ID |
| type | str | API | attr |
| interval | str | API | attr |
| port | str | API | attr |
| http-codes | str | API | attr |
| status | bool | API | binary_sensor |
| comment | str | API | attr |
| enabled | bool | Computed | internal |

### `container`
**API Path:** `/container`
**Key:** Dict of dicts, keyed by `.id`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| .id | str | API | internal |
| name | str | API | switch display |
| tag | str | API | **attr-only** |
| os | str | API | **attr-only** |
| arch | str | API | **attr-only** |
| interface | str | API | **attr-only** |
| root-dir | str | API | **attr-only** |
| mounts | str | API | `unused` |
| dns | str | API | `unused` |
| logging | str | API | `unused` |
| cmd | str | API | `unused` |
| entrypoint | str | API | `unused` |
| envlist | str | API | `unused` |
| hostname | str | API | `unused` |
| workdir | str | API | `unused` |
| comment | str | API | attr |
| status | str | API | internal |
| running | bool | Computed | switch |

### `host`
**API Path:** Composite (ARP + DHCP + wireless + capsman + hotspot)
**Key:** Dict of dicts, keyed by `mac-address`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| source | str | Computed | attr |
| mac-address | str | Merged | device_tracker ID |
| address | str | Merged | attr |
| interface | str | Merged (whichever source claimed first) | attr |
| capsman-interface | str | Merged (capsman) — **always** written if capsman saw the host, regardless of `source` | attr |
| host-name | str | Merged + resolved | device_tracker name |
| manufacturer | str | Computed (MAC lookup) | attr |
| available | bool | Computed | device_tracker state |
| last-seen | datetime | Computed | attr |
| signal-strength | str | Merged (wireless / capsman) | attr |
| tx-ccq | str | Merged (wireless) | attr |
| tx-rate | str | Merged (wireless / capsman) | attr |
| rx-rate | str | Merged (wireless / capsman) | attr |
| authorized | bool | Merged (hotspot) | attr |
| bypassed | bool | Merged (hotspot) | attr |

*Wireless detection (v2.3.13):* `_is_wireless_host()` determines if a host is wireless using three methods: (1) source is "capsman" or "wireless", (2) host interface matches a known wireless interface, (3) bridge host table maps the MAC to a wireless interface. This fixes wireless client counting on routers with empty registration tables (e.g. hAP ac2 with new WiFi package).

*CAPsMAN AP identity (v2.3.17, ADR-011):* `interface` and `source` are owned by whichever merge claimed the host first (often DHCP/ARP). `capsman-interface` is the canonical attribute for "which AP is this client on" — populated unconditionally from `/caps-man/registration-table` (or `/interface/wifi/registration-table` on v7.13+) for any client appearing in those tables, so automations don't need to know which merge won the source claim.

### `hostspot_host`
**API Path:** `/ip/hotspot/host`
**Key:** Dict of dicts, keyed by `mac-address`

| Field | Type | Source | Surfaced |
|-------|------|--------|----------|
| mac-address | str | API | internal |
| authorized | bool | API | host merge |
| bypassed | bool | API | `unused` |

---

## Unused / Internal Only

### `access`
**Type:** List of permission strings
**Used by:** Internal permission gating only

### `bridge`
**Type:** Dict of `{bridge_name: True}`
**Used by:** Internal ARP/interface lookups

### `host_hass`
**Type:** Dict of `{mac_address: entity_name}`
**Used by:** Host recovery from HA entity registry

### `packages`
**Type:** Temporary — not persisted in `self.ds`
**Used by:** Capability detection only

### `ppp_active`
**Type:** Dict of dicts — merged into `ppp_secret`
**Used by:** Internal enrichment only

### `bonding_slaves`
**Type:** Dict of dicts
**Used by:** Internal interface attribution only

---

## Key Findings for Gap Analysis

### Fetched and completely unused (no entity, no attribute):
1. `dns` — All fields unused
2. `interface.tx-queue-drop` — Fetched, never surfaced
3. `wireless_hosts.uptime` — Client uptime, never surfaced
4. `wireless_hosts.ap` — AP flag, never surfaced
5. `container` — 8 fields unused (mounts, dns, logging, cmd, entrypoint, envlist, hostname, workdir)
6. `ups` — 6 monitor fields unused as standalone sensors (runtime-left, battery-charge, battery-voltage, line-voltage, load, hid-self-test)
7. `routerboard.serial-number` — Never surfaced
8. `dhcp-network` — gateway, netmask, dns-server, domain all unused
9. `bonding` — slaves, mode unused
10. `ppp_secret.profile` — Never surfaced
11. `fw-update.channel` — Never surfaced

### Surfaced as attributes only (could be standalone sensors):
1. `interface.link-downs` — Link flap counter
2. `queue` — 12 computed rate/limit fields (attr-only)
3. `wireless_hosts` signal/rate — Only via host merge, not standalone sensors
4. GPS altitude, speed, satellites — attr-only
5. `ups` battery-charge, load, runtime-left — attr-only on binary_sensor
