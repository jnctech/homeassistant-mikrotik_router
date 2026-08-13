Monitor and control your MikroTik router from Home Assistant.

**Community-maintained fork** with active bug fixes for HA 2025.12+ compatibility, RouterOS 7 support, and more.

[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=coverage)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)

![Mikrotik Logo](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/header.png)

### What's new in v2.3.21-beta.2
Adds a recovery fix to the open v2.3.21 beta cycle; everything in beta.1 below still applies.
- **Self-recovery after a transient API outage** — if the RouterOS API dropped (gateway reboot, path outage, PoE toggle), entities could stay `unavailable` until you reloaded the config entry, worst case ~4h. Each poll now attempts a reconnect. Bad credentials still raise a reauth prompt rather than retrying forever. Thanks @sappsys (#123).

### What's new in v2.3.21-beta.1
Beta: **LTE modem sensors** + an integration-wide entity-reliability fix. LTE is beta-gated on contributor hardware; the fix was live-validated with no regressions.
- **LTE modem sensors** — signal (RSSI/RSRP/RSRQ/SINR/CQI), operator, connection, session uptime, and modem firmware for routers with an `/interface/lte`. Conditional on LTE hardware. IMEI/IMSI/ICCID collected but disabled by default + redacted. Thanks @zvldz for the implementation + live validation on a MikroTik Chateau. Implements tomaae #249. See ADR-019.
- **`unknown` instead of stale** — when a source stops reporting mid-session, the sensor reads `unknown` rather than keeping its last value. Integration-wide.

### What's new in v2.3.20
Stable release rolling up the v2.3.20 beta cycle. Both new features were validated live — PoE-out energy on real metering hardware (#59, thanks @Dillton) and netwatch naming on a multi-entry deployment (#70, thanks @L2jLiga).
- **PoE energy for the Energy Dashboard** — per-port energy sensors (kWh, `total_increasing`) + a device total, restart-persistent. Enable the existing PoE sensors option. Addresses #59.
- **Estimated energy on non-metering hardware** — where a PoE-out port powers a device that has no wattage reading, energy is estimated from the device's datasheet rating (via Neighbor Discovery) and labelled `power_source: estimated` — a coarse upper bound, not a measurement.
- **Netwatch entities named by their netwatch `name`** — if you set a distinct `name` on each netwatch entry, that name is now shown in Home Assistant instead of a shared `comment`, so entries that share a comment are no longer indistinguishable. Entries with no name keep showing their comment (or "Netwatch" if neither is set). Your entity IDs and automations are unchanged. Addresses #70.
- **Correct librouteros `login_method` handling** (`ISS-260417`) + HA deprecation cleanup (device_tracker `ScannerEntity`, config-flow reload).

### What's new in v2.3.19
Stable release rolling up the read-only and quality-scale fixes since v2.3.18. Validated live against a multi-device RouterOS deployment before tagging.
- **Read-only users now get wireless / CAPsMAN / PPP data** — on RouterOS 7.x, an HA user without write/policy/reboot rights previously saw zero wireless clients. The firmware version is now read from `/system/resource`, so capability detection works without granting write access. Thanks to @ahharvey for the fix and wifi-qcom testing. Addresses #82.
- **Reauthentication flow** — if your router credentials change, re-enter them via the normal Home Assistant reauth prompt instead of deleting and re-adding the integration.
- **Cleaner entity names** — distinct device-trackers and per-VLAN DHCP-server sensors no longer collide into `_2`/`_3` names (e.g. several devices all reporting the hostname `lwip0`). `unique_id`s are unchanged, so existing entity IDs and automations are preserved.
- **Environment sensors no longer get stuck `unavailable`** — empty or transient RouterOS global script variables (e.g. `defconfMode`, cleared on reboot) no longer create empty-state or orphaned entities.
- **HA Quality Scale: Silver** — Bronze + Silver tiers met and declared (typed runtime-data, per-platform parallel updates, reauthentication).
- **More diagnosable firmware detection** — version-gated polling paths now log at debug instead of silently doing nothing while the firmware version is briefly unknown.
- **Quality & process** — documented release validation (CI test suite + live per-sensor-class cross-check against real RouterOS hardware) and review gates (multi-agent audit panels + specialized passes).
- Internal: test-suite hardening and CI resilience.

### What's new in v2.3.18
- **CAPsMAN now works on legacy-wireless routers** — RouterOS 7.13+ devices still running the legacy `wireless` package weren't detecting CAPsMAN wireless clients. Fixed. Addresses #68.
- **See which AP a wireless client is on** — new `capsman-interface` attribute on device trackers (e.g. `Slaapkamer`), useful for per-room automations. Works even when DHCP/ARP claimed the host first. Existing `interface` / `source` attributes unchanged.
- Thanks to @fuecy for the diagnostics and clean-install testing.

### v2.3.16
- **API concurrency fix** — `set_value`/`execute` now hold the API lock around the librouteros response iteration, preventing a race with the 30s coordinator poll that could disconnect the integration on rapid switch toggles. Addresses #64.
- **HA 2026.5.0 / Python 3.14 not yet validated** — testing planned; see `docs/ISSUES.md`.

### v2.3.15
- **UPS without configured device no longer breaks the integration** — `/system/ups` empty path stopped triggering "Mikrotik Disconnected". Addresses #61.
- **PoE out current value corrected** — Native unit was AMPERE while RouterOS reports mA, causing values 1000× too large. Now declared as MILLIAMPERE. Addresses #60.

### v2.3.14
- **Hotfix** — Pin `librouteros<4.0` to prevent integration failure after librouteros 4.0.1 release (`connect()` kwarg rename). Addresses #55 and #56.

### v2.3.13
- **Wireless client detection fix** — Clients on routers with empty WiFi registration tables (e.g. hAP ac2) now correctly detected as wireless via bridge host table lookup
- **DHCP server sensors** — New status and lease count sensors per DHCP server instance
- **Documentation** — Comprehensive data store schema, sensor gap analysis, and community feature poll

### v2.3.12
- **Faster startup** — No longer blocks HA startup by pinging every tracked host sequentially; uses ARP table for instant first-run availability
- **Parallel MAC lookups** — Vendor resolution now runs concurrently instead of one-by-one
- **Entity cleanup services** — `cleanup_entities` removes orphaned entities; `cleanup_stale_hosts` reports/removes stale device trackers
- **Bug fixes** — Firmware v7+ client traffic comparison fix, timezone-aware datetimes, API parser type hint fix

### v2.3.11
- **Attribute cleanup** — Entity attributes now only show information relevant to each port type (SFP diagnostics on SFP ports only, PoE on PoE-capable ports only, wireless metrics on wireless clients only)
- **Mangle fix** — Rules differing only by interface were silently dropped as duplicates

### v2.3.10
- **Device tracker fix** — ARP `"incomplete"` status no longer falsely shows devices as "home" ([PR #38](https://github.com/jnctech/homeassistant-mikrotik_router/pull/38))

### v2.3.9
- **Firewall RAW switches** — enable/disable individual RAW rules ([upstream #310](https://github.com/tomaae/homeassistant-mikrotik_router/issues/310))
- **Container monitoring** — monitor and start/stop MikroTik containers, RouterOS 7.4+ ([upstream #334](https://github.com/tomaae/homeassistant-mikrotik_router/issues/334))
- **DHCP client sensors** — WAN IP, gateway, DNS, lease expiry per interface ([upstream #321](https://github.com/tomaae/homeassistant-mikrotik_router/issues/321))
- **Script env refresh** — environment variables update immediately after script execution ([upstream #298](https://github.com/tomaae/homeassistant-mikrotik_router/issues/298))

### v2.3.8
- **Device tracking fix** — disabled duplicate entity registration that caused thousands of "does not generate unique IDs" log errors every 30s
- **ARP filtering** — failed ARP entries no longer cause false "home" status ([#17](https://github.com/jnctech/homeassistant-mikrotik_router/issues/17))

### v2.3.7
- **ARP failed-status filtering** moved to `async_process_host()` for correct bridge-interface lookups

### v2.3.6
- **Options flow crash fixed** — config panel now works on HA 2025.12+ ([upstream #470](https://github.com/tomaae/homeassistant-mikrotik_router/issues/470), [#471](https://github.com/tomaae/homeassistant-mikrotik_router/issues/471))
- **Deadlock fix** — `run_script()` lock leak permanently freezing the integration is resolved
- **Blocking I/O eliminated** — switch toggles, button presses, and firmware updates no longer freeze the HA UI
- **Deprecated API cleanup** — updated `DeviceInfo` params and added missing PoE translation

### Features
 * Interfaces: enable/disable, SFP info, PoE-Out control & power monitoring, RX/TX traffic, device presence
 * NAT / Mangle / Filter / RAW / Simple Queue rule switches
 * Container monitoring and control (RouterOS 7.4+)
 * DHCP client sensors (WAN IP, gateway, DNS, lease expiry)
 * PPP user monitoring and control
 * Kid Control
 * Client traffic monitoring (Accounting on v6, Kid Control Devices on v7+)
 * Device tracker for all network hosts
 * System sensors (CPU, Memory, HDD, Temperature, Voltage, Fan speed)
 * RouterOS and firmware update sensors
 * Script execution
 * Environment variables
 * GPS and UPS monitoring
 * Configurable scan interval and traffic units

## Links
- [Documentation](https://github.com/jnctech/homeassistant-mikrotik_router/tree/master)
- [Configuration](https://github.com/jnctech/homeassistant-mikrotik_router/tree/master#setup-integration)
- [Report a Bug](https://github.com/jnctech/homeassistant-mikrotik_router/issues/new?labels=bug&template=bug_report.md&title=%5BBug%5D)
- [Suggest an idea](https://github.com/jnctech/homeassistant-mikrotik_router/issues/new?labels=enhancement&template=feature_request.md&title=%5BFeature%5D)
- [Upstream repo](https://github.com/tomaae/homeassistant-mikrotik_router) (original by tomaae)
