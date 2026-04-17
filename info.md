Monitor and control your MikroTik router from Home Assistant.

**Community-maintained fork** with active bug fixes for HA 2025.12+ compatibility, RouterOS 7 support, and more.

[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=jnctech_homeassistant-mikrotik_router&metric=coverage)](https://sonarcloud.io/summary/new_code?id=jnctech_homeassistant-mikrotik_router)

![Mikrotik Logo](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/header.png)

### What's new in v2.3.14
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
