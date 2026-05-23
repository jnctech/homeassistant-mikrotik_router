# MikroTik Router Integration for Home Assistant

![GitHub release (latest by date)](https://img.shields.io/github/v/release/jnctech/homeassistant-mikrotik_router?style=plastic)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=plastic)](https://github.com/hacs/integration)
![Project Stage](https://img.shields.io/badge/project%20stage-Production%20Ready-green.svg?style=plastic)
![GitHub all releases](https://img.shields.io/github/downloads/jnctech/homeassistant-mikrotik_router/total?style=plastic)

[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=coverage)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)

Monitor and control your entire MikroTik network from Home Assistant. This HACS custom integration connects to MikroTik routers, switches and access points running RouterOS v6 or v7 via the RouterOS API — surfacing system health, interface status, PoE monitoring, traffic sensors, wireless client counts, DHCP server monitoring, firewall rule control, network device tracking, firmware updates and more as native Home Assistant entities.

**Works with:** RB4011, RB5009, hAP ac2, hAP ax3, CRS switches, CCR routers, hEX, and any MikroTik device with the RouterOS API enabled. Tested on RouterOS 7.13 through 7.22.

> **[Vote on upcoming features](https://github.com/jnctech/homeassistant-mikrotik_router/discussions/48)** — WireGuard VPN monitoring, firewall address lists, LTE modem stats, certificate expiry alerts, and more. Tell us what you need.

> **This is a community-maintained fork of [tomaae/homeassistant-mikrotik_router](https://github.com/tomaae/homeassistant-mikrotik_router).** The original author built an incredible integration that many of us rely on daily. This fork exists to keep things running and ship bug fixes while the upstream repo is quiet. We're happy to contribute fixes back anytime.

---

## What's New — v2.3.17

**CAPsMAN AP-virtual interface surfaced on device trackers** — When a wireless client is also claimed by a DHCP/ARP/bridge merge (which happens whenever DHCP leases persist across polls), the `interface` attribute previously held the bridge name, not the AP-virtual interface. v2.3.17 adds a new additive `capsman-interface` attribute populated *unconditionally* from `/caps-man/registration-table` (or `/interface/wifi/registration-table` on v7.13+), so you can identify which AP a client is connected to (e.g. `Slaapkamer`, `Zolder`) regardless of which merge claimed the host first. The endpoint selection now also has a fallback: v7.13+ users still running legacy CAPsMAN (where the new wifi endpoint returns empty) automatically fall back to the legacy `/caps-man/` endpoint — fixes the specific case reported in [#68](https://github.com/jnctech/homeassistant-mikrotik_router/issues/68) where the version-based selection misrouted. Existing `interface` and `source` semantics are unchanged — automations that filter on those keys keep working. See [ADR-011](docs/decisions/ADR-011-capsman-attributes.md).

## v2.3.16

**Concurrency fix for rapid switch toggles** — `set_value()` and `execute()` in `mikrotikapi.py` were iterating the librouteros response object (which performs additional socket reads) **outside** the API lock. Under workloads that toggle switches rapidly, this could race with the 30s coordinator poll and corrupt the librouteros sentence stream, triggering `ValueError: not enough values to unpack` followed by a full coordinator disconnect. Both methods now hold the lock for the entire response lifecycle, matching the pattern `run_script()` was already using. Addresses [#64](https://github.com/jnctech/homeassistant-mikrotik_router/issues/64).

> **HA 2026.5.0 compatibility:** This release was prompted by a report against HA 2026.5.0 ([#64](https://github.com/jnctech/homeassistant-mikrotik_router/issues/64)). The integration has not yet been formally validated against 2026.5.0 — testing is planned. The underlying race fixed in this release was pre-existing and unrelated to v2.3.15; what changed in 2026.5.0 specifically that surfaced it is still being investigated (HA has been on Python 3.14 since [2026.3](https://www.home-assistant.io/blog/2026/03/04/release-20263/#running-on-python-314-) without prior reports of this race). See `docs/ISSUES.md` (`ISS-260509-ha-2026.5-untested`).

## v2.3.15

**Two reported bugs fixed:**
- **UPS package installed but no UPS configured no longer breaks the integration** — On routers with the UPS package enabled but `/system/ups` empty, the integration was issuing a `monitor` query that RouterOS rejected with "no such item", causing a full coordinator disconnect ("Mikrotik Disconnected"). Addresses [#61](https://github.com/jnctech/homeassistant-mikrotik_router/issues/61).
- **PoE out current value corrected** — The sensor was declared in amperes while RouterOS reports the value in milliamperes, causing displayed values to be 1000× too large (e.g. `1234.56 mA` for a ~25 mA load). Addresses [#60](https://github.com/jnctech/homeassistant-mikrotik_router/issues/60).

## v2.3.14

**librouteros 4.x hotfix** — Pin `librouteros<4.0` in `manifest.json`. Version 4.0.1 of librouteros renamed `connect()`'s `login_methods` kwarg to `login_method`, breaking every install that auto-upgraded. Addresses [#55](https://github.com/jnctech/homeassistant-mikrotik_router/issues/55) and [#56](https://github.com/jnctech/homeassistant-mikrotik_router/issues/56). Proper 4.x migration will ship in a future release.

## v2.3.13

**Wireless client detection fix** — Wireless clients on routers with empty WiFi registration tables (e.g. hAP ac2 with the new WiFi package) are now correctly detected via bridge host table lookup. The `clients_wireless` and `clients_wired` counters are accurate for these devices.

**DHCP server sensors** — Two new sensors per DHCP server:
- `dhcp_server_status` — shows "running" or "disabled"
- `dhcp_server_lease_count` — real-time count of active DHCP leases
- Both include attributes: interface, address-pool, enabled, comment

**Documentation** — Added comprehensive data store schema (`docs/data-schema.md`), sensor gap analysis, and community feature poll.

<details>
<summary>Previous: v2.3.12 — Faster startup, cleanup services</summary>

**Faster startup** — The integration no longer blocks Home Assistant startup by sequentially pinging every tracked host. First-run host availability now uses the ARP table for instant results, with pings starting on the next 10-second tracker cycle. MAC vendor lookups are also parallelised instead of running one-by-one.

**Entity cleanup services** — Two new service actions available in Developer Tools > Services:
- `mikrotik_router.cleanup_entities` — removes orphaned entities that no longer have backing router data (deleted interfaces, old firewall rules)
- `mikrotik_router.cleanup_stale_hosts` — reports or removes stale device tracker entities for away hosts (dry_run mode by default)

**Bug fixes:**
- Fixed chained comparison bug that could skip firmware v7+ client traffic processing
- Fixed `voluptuous.Optional` incorrectly used as a type hint in API parser
- All `datetime.now()` calls replaced with timezone-aware equivalents (HA coding standards)
- `get_system_resource` now properly guarded against disconnected API
</details>

<details>
<summary>Previous: v2.3.11 — Attribute cleanup</summary>

**Attribute cleanup** — Entity attributes now only show information relevant to each port type. Previously, all ethernet ports displayed SFP diagnostics, PoE status, and client tracking fields regardless of hardware capability. Now:

| Attribute type | Before | After |
|----------------|--------|-------|
| SFP diagnostics | Shown on all ethernet ports | Only SFP ports |
| Link rate & duplex | Only copper ports | Both copper and SFP ports |
| PoE status | Shown as "N/A" on non-PoE ports | Only PoE-capable ports |
| Client IP/MAC | Shown as "unknown" on all interfaces | Only when a client is connected |
| Wireless metrics | Shown on all tracked devices | Only wireless/CAPsMAN clients |

**Mangle fix** — Rules differing only by `in-interface`/`out-interface` (e.g. MSS clamping for inbound vs outbound PPPoE) were silently removed as duplicates. Interface fields are now included in the rule unique ID.

</details>

<details>
<summary>Previous: v2.3.10 — Device tracker fix</summary>

**Device tracker fix** — ARP entries with `"incomplete"` status were incorrectly treated as reachable, causing devices to show as "home" when they were actually unreachable. Both `"failed"` and `"incomplete"` ARP statuses are now filtered. See [ADR-001](docs/decisions/ADR-001-arp-failed-filtering.md).

</details>

<details>
<summary>Previous: v2.3.9 — Upstream feature ports</summary>

Four upstream feature requests implemented.

| Feature | Detail | Upstream |
|---------|--------|----------|
| **Firewall RAW switches** | Enable/disable individual `/ip/firewall/raw` rules. Opt-in via integration options. | [#310](https://github.com/tomaae/homeassistant-mikrotik_router/issues/310) |
| **Container monitoring** | Monitor status and start/stop MikroTik containers (RouterOS 7.4+). Requires container package. Opt-in via integration options. | [#334](https://github.com/tomaae/homeassistant-mikrotik_router/issues/334) |
| **DHCP client sensors** | WAN IP, gateway, DNS server, DHCP server, lease expiry per DHCP client interface. Always-on. | [#321](https://github.com/tomaae/homeassistant-mikrotik_router/issues/321) |
| **Script env refresh** | Coordinator refreshes immediately after script button press — environment variables update without waiting for next poll. | [#298](https://github.com/tomaae/homeassistant-mikrotik_router/issues/298) |

Also includes: cognitive complexity reduction (ADR-007), 461 automated tests, ruff migration, and CI/CD improvements from v2.3.8 dev work.

</details>

<details>
<summary>Previous: v2.3.8 — Bug fixes</summary>

The v2.3.6–v2.3.8 releases fix critical bugs and align with HA best practices. **Install v2.3.8** — it includes all fixes from v2.3.6 and v2.3.7 plus a patch for log spam introduced in v2.3.6.

### Fixes in v2.3.6–v2.3.8

| Fix | Version | Detail |
|-----|---------|--------|
| **Options flow crash on HA 2025.12+** | v2.3.6 | Config panel now works on modern HA versions ([upstream #470](https://github.com/tomaae/homeassistant-mikrotik_router/issues/470), [#471](https://github.com/tomaae/homeassistant-mikrotik_router/issues/471)) |
| **Deadlock in `run_script()`** | v2.3.6 | Lock was never released when script not found — permanently froze the integration |
| **Blocking I/O on event loop** | v2.3.6 | Switch toggles, button presses, firmware updates no longer freeze the HA UI |
| **False "home" device tracking** | v2.3.7 | ARP entries with `status: failed` no longer cause devices to show as home ([#17](https://github.com/jnctech/homeassistant-mikrotik_router/issues/17)) |
| **Deprecated `DeviceInfo` params** | v2.3.6 | Updated to current HA API (`name`, `manufacturer`, `model`) |
| **Duplicate entity log spam** | v2.3.8 | Fixed "does not generate unique IDs" errors flooding the log every 30s |

### Previous releases

<details>
<summary>v2.3.5 — Python compatibility</summary>

| Fix | Detail |
|-----|--------|
| **Python 3.12 compatibility** | Replaced deprecated `datetime.utcfromtimestamp()` with `datetime.fromtimestamp(ts, tz=UTC)` |
| **Removed `pytz` dependency** | Replaced with stdlib `datetime.timezone.utc` — no behavioural change |

</details>

<details>
<summary>v2.3.4 — Reliability patch</summary>

| Fix | Detail |
|-----|--------|
| **Crash on empty accounting query** | No longer crashes when `/ip/accounting` returns no data |
| **Firmware version parse** | Handles RouterOS versions without a minor segment |
| **Host manufacturer lookup** | Exception during MAC OUI lookup no longer propagates |

</details>

</details>

---

## v2.3.3 — PoE Monitoring & Core Bug Fixes

The [v2.3.3](https://github.com/jnctech/homeassistant-mikrotik_router/releases/tag/v2.3.3) release is the first stable release of this community fork. It adds a major new feature and fixes several long-standing bugs reported against the upstream integration.

### New feature: PoE monitoring

Monitor Power over Ethernet status and power metrics for each PoE-capable port on your MikroTik switch or router directly in Home Assistant. Enable **PoE port sensors** under **Settings → Devices & Services → Mikrotik Router → Configure**.

| Sensor | Description | Hardware |
|--------|-------------|----------|
| PoE out status | Port operational state (`powered-on`, `waiting-for-load`, `overload`, etc.) | All PoE ports |
| PoE out voltage | Output voltage to connected device | Full monitoring hardware (CRS/CSS/hEX PoE) |
| PoE out current | Output current to connected device | Full monitoring hardware (CRS/CSS/hEX PoE) |
| PoE out power | Power consumed by connected device | Full monitoring hardware (CRS/CSS/hEX PoE) |

Voltage, current and power sensors are **automatically hidden** on passive-PoE hardware that does not report measurements (e.g. hAP ax3 ether1). Only `poe-out-status` appears on those ports.

### Bug fixes in v2.3.3 (also included in v2.3.4+)

| Fix | Detail |
|-----|--------|
| **Error 500 on Configure** | Fixed for HA 2025.12+ — `OptionsFlow` compatibility with the new framework ([#464](https://github.com/tomaae/homeassistant-mikrotik_router/issues/464)) |
| **Integration crash on non-wireless routers** | RB4011, RB5009, CCR series no longer fail on startup when wireless package is absent ([#433](https://github.com/tomaae/homeassistant-mikrotik_router/issues/433)) |
| **Wired client count always 0** | ARP/DHCP hosts now correctly marked available — wired client counter works ([upstream #468](https://github.com/tomaae/homeassistant-mikrotik_router/issues/468)) |
| **Wireless client count** | Correct client count on hAP ac2 and compatible devices ([upstream #421](https://github.com/tomaae/homeassistant-mikrotik_router/issues/421)) |
| **Temperature sensors ignore Fahrenheit preference** | Sensors now respect the HA unit preference ([#230](https://github.com/tomaae/homeassistant-mikrotik_router/issues/230)) |
| PoE measurement sensors showing 0 on passive PoE ports | Voltage/current/power sensors now hidden when hardware does not report measurements |
| RouterOS 7 WiFi package detection | Supports `wifiwave2`, `wifi`, `wifi-qcom`, `wifi-qcom-ac` |

### Install via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jnctech&repository=homeassistant-mikrotik_router&category=integration)

Or manually:

1. In HACS, add this repo as a custom repository (if not already):
   - HACS > Integrations > 3-dot menu > Custom repositories
   - URL: `https://github.com/jnctech/homeassistant-mikrotik_router`
   - Category: Integration
2. Install **Mikrotik Router** from HACS
3. Restart Home Assistant

### Switching from the upstream fork

If you are currently on `tomaae/homeassistant-mikrotik_router` and seeing **Error 500 on Configure**, **Internal Server Error**, or **crashes on startup** since updating Home Assistant:

1. Remove `tomaae/homeassistant-mikrotik_router` from HACS custom repositories
2. Add `https://github.com/jnctech/homeassistant-mikrotik_router` as a custom repository in HACS
3. Install **Mikrotik Router** from HACS and restart Home Assistant

Your existing configuration and entities are preserved — no reconfiguration needed.

---

![Mikrotik Logo](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/header.png)

## Feature Highlights

- **System health** — CPU, memory, HDD, temperatures, voltages, fan speeds, PoE-in, UPS, GPS
- **Interface monitoring** — enable/disable, SFP diagnostics, RX/TX traffic, link status, connected client IP/MAC
- **PoE monitoring** — per-port status, voltage, current and power for PoE-capable switches and routers
- **Firewall control** — enable/disable individual NAT, filter, mangle, and RAW rules
- **Device tracking** — presence detection for wired, wireless, CAPsMAN, and bridged AP clients (hAP ac2, etc.)
- **DHCP server monitoring** — per-server status and active lease count
- **DHCP client sensors** — WAN IP, gateway, DNS server, lease expiry per DHCP client interface
- **Container management** — monitor status and start/stop MikroTik containers (RouterOS 7.4+)
- **Client traffic** — per-client RX/TX bandwidth via Accounting (v6) or Kid Control (v7)
- **Queue management** — enable/disable simple queues with bandwidth monitoring
- **PPP management** — monitor and control PPP secrets and connections
- **Kid Control** — enable/disable/pause internet schedules
- **Firmware updates** — check and install RouterOS and RouterBOARD updates from HA
- **Scripts** — execute RouterOS scripts with immediate environment variable refresh
- **Netwatch** — probe status tracking
- **Entity cleanup** — services to remove orphaned entities and stale device trackers
- **Multiple devices** — monitor several MikroTik routers, switches and APs simultaneously

### Coming Soon — [Vote Here](https://github.com/jnctech/homeassistant-mikrotik_router/discussions/48)

| Feature | Status |
|---------|--------|
| WireGuard VPN tunnel and peer monitoring | Planned — high demand |
| Firewall address list management (toggle entries from HA) | Planned — high demand |
| Interface IP address tracking (WAN IP change detection) | Planned |
| Certificate expiry alerts | Planned |
| LTE modem signal stats (RSSI, RSRP, SINR) | Planned — hardware-specific |
| Wireless client signal strength as standalone sensors | Planned |
| Firewall rule byte/packet counters | Planned |
| Connection tracking stats | Planned |

For the full analysis, see the [Sensor Gap Analysis](docs/sensor-gap-analysis.md).

---

# Features

## Interfaces
Monitor and control status on each MikroTik interface — LAN, WLAN, physical and virtual.

![Interface Info](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface.png)
![Interface Switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface_switch.png)
![Interface Sensor](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface_sensor.png)

## PoE Monitoring *(v2.3.3+)*
Monitor Power over Ethernet (PoE) status and power metrics for each PoE-capable port on your MikroTik switch or router directly in Home Assistant.

More information about PoE-Out can be found on the [MikroTik support page](https://help.mikrotik.com/docs/display/ROS/PoE-Out).

### Compatible hardware
PoE-Out sensors are available on MikroTik devices with managed PoE-Out ports, including (but not limited to):

- **CRS series** managed switches: CRS106, CRS112, CRS210, CRS212, CRS226, CRS317, CRS328, CRS354, **CRS310-8G+2S+IN**
- **CSS series** with PoE: CSS106, CSS326, CSS610
- **RB series** with PoE-Out: RB260, RB2011, RB3011, RB4011, RB5009
- **hEX PoE**, **hEX PoE lite**
- Any RouterOS device where `/interface/ethernet/poe` returns data

#### Two tiers of PoE-Out monitoring

| Tier | Hardware examples | Sensors available |
|------|-------------------|-------------------|
| **Full monitoring** | CRS series managed switches, CSS series, hEX PoE | Status + voltage + current + power |
| **Status only** | hAP ax3 ether1 (passive 24 V PoE), some RB series ports | Status only |

On **status-only** ports the voltage, current and power sensors are automatically hidden because the hardware does not report those measurements. Only `poe-out-status` will appear.

To confirm your device capability, run in RouterOS terminal:
```
/interface ethernet poe monitor ether1 once
```

### PoE-Out sensors (per port)
Enable **PoE port sensors** in the integration options to add the following diagnostic sensors for each PoE-capable ethernet port:

| Sensor | Description | Example values | Hardware requirement |
|--------|-------------|----------------|---------------------|
| PoE out status | Current PoE port operational state | `powered-on`, `waiting-for-load`, `short-circuit`, `overload`, `voltage-too-low`, `off` | All PoE ports |
| PoE out voltage | Output voltage to the connected device | 48.0 V | Full monitoring only |
| PoE out current | Output current to the connected device | 120 mA | Full monitoring only |
| PoE out power | Power consumed by the connected device | 5.76 W | Full monitoring only |

> **Note:** PoE port sensors are opt-in. Enable them under **Settings → Devices & Services → Mikrotik Router → Configure → PoE port sensors**. Voltage, current and power sensors are automatically hidden on hardware that does not report those measurements. Implements [upstream feature request #259](https://github.com/tomaae/homeassistant-mikrotik_router/issues/259).

### PoE-In sensors (system)
For MikroTik devices powered via PoE, the following sensors appear automatically under the System device when the hardware reports them — no opt-in required:

| Sensor | Description |
|--------|-------------|
| PoE in voltage | Input voltage supplied to the device via PoE |
| PoE in current | Input current supplied to the device via PoE |

Example devices with PoE-In:
- **CRS310-8G+2S+IN** — management port accepts 802.3af/at (standard PoE) and passive PoE 18–57 V DC

PoE-In sensors only appear if your device exposes these values via `/system/health`. Not all PoE-powered devices support this command (e.g. hAP ac2 returns `bad command name health`). Verify with `/system health print` in RouterOS terminal.

## NAT
Monitor and control individual NAT rules.

More information about NAT rules can be found on [Mikrotik support page](https://help.mikrotik.com/docs/display/ROS/NAT).

![NAT switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/nat.png)

## Mangle
Monitor and control individual Mangle rules.

More information about Mangle rules can be found on [Mikrotik support page](https://help.mikrotik.com/docs/display/ROS/Mangle).

![Mangle switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/mangle_switch.png)

## Firewall RAW Rules *(new)*
Enable/disable individual firewall RAW rules — the same control you have for NAT, Mangle and Filter, now extended to `/ip/firewall/raw`. Dynamic and jump rules are automatically excluded. Each rule exposes chain, action, protocol, src/dst addresses and ports as attributes.

Enable **Firewall RAW switches** in the integration options.

More information about RAW rules can be found on the [MikroTik support page](https://help.mikrotik.com/docs/display/ROS/RAW).

> Implements [upstream feature request #310](https://github.com/tomaae/homeassistant-mikrotik_router/issues/310).

## Containers *(new)*
Monitor and control MikroTik containers (RouterOS 7.4+). Each container appears as:
- **Status sensor** — shows `running`, `stopped`, or `error` with attributes (image tag, OS, arch, interface, root-dir, mounts, DNS, cmd, entrypoint)
- **Start/stop switch** — toggle containers on and off, usable in automations

The container package must be installed and enabled on your router. Enable **Container sensors and switches** in the integration options.

More information about containers can be found on the [MikroTik support page](https://help.mikrotik.com/docs/display/ROS/Container).

> Implements [upstream feature request #334](https://github.com/tomaae/homeassistant-mikrotik_router/issues/334).

## DHCP Client *(new)*
Monitor DHCP client status on each interface (typically WAN). Two sensors per DHCP client interface:
- **DHCP status** — `bound`, `searching`, `stopped`, etc.
- **DHCP address** — the current IP address assigned by the ISP/upstream

Each sensor exposes gateway, DNS server, DHCP server address, lease expiry (`expires-after`), and comment as attributes. Useful for WAN IP change detection, multi-WAN failover awareness, and ISP DNS drift monitoring.

DHCP client sensors appear automatically for each interface that has a DHCP client configured — no opt-in required.

> Implements [upstream feature request #321](https://github.com/tomaae/homeassistant-mikrotik_router/issues/321).

## Simple Queue
Control simple queues.

More information about simple queues can be found on [Mikrotik support page](https://help.mikrotik.com/docs/display/ROS/Queues#heading-SimpleQueue).

NOTE: FastTracked packets are not processed by Simple Queues.

![Queue switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/queue_switch.png)


## PPP
Control and monitor PPP users.

![PPP switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/ppp_switch.png)
![PPP tracker](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/ppp_tracker.png)

## Host Tracking
Track availability of all network devices. All devices visible to the MikroTik device can be tracked, including LAN connected devices and both Wireless and CAPsMAN clients.

![Host tracker](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/host_tracker.png)

## Netwatch Tracking
Track netwatch probe status.

![Netwatch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/netwatch_tracker.png)

## Scripts
Execute MikroTik Router scripts from Home Assistant via automatically created buttons.

After a script executes, all sensor data (including environment variables) is refreshed immediately — no need to wait for the next polling cycle. This makes script → read-environment-variable automations reliable.

> Environment variable refresh implements [upstream feature request #298](https://github.com/tomaae/homeassistant-mikrotik_router/issues/298).

![Script Switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/script_switch.png)

## Kid Control
Monitor and control Kid Control internet schedules.

![Kid Control Enable](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/kidcontrol_switch.png)
![Kid Control Pause](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/kidcontrol_pause_switch.png)

## Client Traffic

### Client Traffic for RouterOS v6
Monitor per-IP throughput based on MikroTik Accounting (Winbox: IP → Accounting).

Set the threshold to a reasonable value — max is 8192. FastTracked packets are not counted.

More information: [MikroTik Accounting](https://wiki.mikrotik.com/wiki/Manual:IP/Accounting).

### Client Traffic for RouterOS v7+
In RouterOS v7 the Accounting feature is deprecated. Use Kid Control Devices instead (IP → Kid Control → Devices). Requires at least one Kid entry to be defined — a dummy entry works:

```
/ip kid-control add name=Monitor mon=0s-1d tue=0s-1d wed=0s-1d thu=0s-1d fri=0s-1d sat=0s-1d sun=0s-1d
```

![Accounting sensor](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/accounting_sensor.png)

## UPS sensor
Monitor your UPS.

![UPS sensor](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/ups.png)

## GPS sensors
Monitor GPS coordinates.

![GPS sensor](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/gps.png)

## Update sensor
Check and update RouterOS and RouterBOARD firmware directly from Home Assistant.

![RouterOS update](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/routeros_update.png)
![Firmware update](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/firmware_update.png)

---

# Install Integration

This integration is distributed using [HACS](https://hacs.xyz/).

**Minimum requirements:**
- RouterOS v6.43 or v7.1+
- Home Assistant 2024.3.0+

## Setup

1. Create a dedicated Home Assistant user on your MikroTik device with these permissions:
   - `read, write, api, reboot, policy, test`
   - `read` and `api` are mandatory; lower permissions will limit functionality
   - System health sensors require `write` and `reboot` (MikroTik limitation)
2. For script execution, the script itself needs only `read, write` — or check "Don't Require Permissions"
3. Add the integration: **Settings → Devices & Services → Add Integration → Mikrotik Router**

> Do not confuse "Mikrotik Router" with the built-in Home Assistant "Mikrotik" integration. If you don't see it, clear your browser cache.

![Add Integration](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/setup_integration.png)

## Configuration options

![Integration options](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_options.png)

- **Scan interval** — poll frequency in seconds (HA reload required after change)
- **Unit of measurement** — traffic sensor units: bps, Kbps, Mbps, B/s, KB/s, MB/s
- **Show client MAC and IP on interfaces** — display connected device info per port
- **Track network devices timeout** — mark tracked devices away after this period
- **Zone for device tracker** — assign new tracked devices to a Home Assistant zone

![Integration sensors](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_options_sensors.png)

---

# Known Issues & Workarounds

## Wireless clients count (hAP ax2, hAP ax3, Audience, RouterOS 7 WiFi package)

**Affected devices:** hAP ax2, hAP ax3, Audience, and devices using the newer **WiFi package** (not the legacy **Wireless package**).

**What's happening:** Devices running the newer WiFi package (802.11ax/WiFi 6 hardware) use `/interface/wifi` API endpoints instead of the legacy `/interface/wireless`. The `sensor.*_wireless_clients_api` sensor works correctly on legacy Wireless package devices (confirmed on hAP ac2). Devices on the newer WiFi package may report 0.

**Workaround — use Kid Control for device tracking:**

1. SSH or open a terminal to your MikroTik router
2. Create a dummy Kid Control entry:
```
/ip kid-control add name=Monitor mon=0s-1d tue=0s-1d wed=0s-1d thu=0s-1d fri=0s-1d sat=0s-1d sun=0s-1d
```
3. In integration options, enable **"Track network devices"**
4. Reload the integration

This provides device presence detection and per-client traffic stats regardless of WiFi package version.

**Status:** Native support for the new WiFi package API is planned ([upstream #421](https://github.com/tomaae/homeassistant-mikrotik_router/issues/421)).

## Integration crashes on routers without wireless package (RB4011, RB5009, CCR series)

**Affected devices:** RB4011, RB5009, CCR1009, CCR1016, CCR1036, CCR2004, CCR2116, and any MikroTik router where the wireless package is absent.

**Status:** Fixed in v2.3.3. The fix checks which WiFi packages are installed before querying wireless endpoints. ([upstream #433](https://github.com/tomaae/homeassistant-mikrotik_router/issues/433))

## Temperature sensors always show Celsius, ignore Fahrenheit preference

**Affected users:** Home Assistant instances configured for imperial/Fahrenheit units.

**Status:** Fixed in v2.3.3. Temperature sensors now respect HA unit preferences and auto-convert. ([upstream #230](https://github.com/tomaae/homeassistant-mikrotik_router/issues/230))

---

# Development

## Translation
To help with translation, [log in to Lokalise with GitHub](https://lokalise.com/login/) then [join the Mikrotik Router project](https://app.lokalise.com/public/581188395e9778a6060128.17699416/).

To request a new language, [open a Feature request](https://github.com/tomaae/homeassistant-mikrotik_router/issues/new?labels=enhancement&title=%5BLokalise%5D%20Add%20new%20translations%20language).

## Diagnostics
Download diagnostics data for investigation:

![Diagnostics](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/diagnostics.png)

## Enabling debug logging
Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.mikrotik_router: debug
```
