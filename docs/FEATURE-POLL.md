# Feature Poll — What MikroTik sensors do you want?

We've done a gap analysis of what this integration currently surfaces vs what it *could* surface from the RouterOS API. Before we start coding, we want to hear from you.

**How to vote:** Open a [new Discussion](https://github.com/jnctech/homeassistant-mikrotik_router/discussions) or comment on the pinned feature poll thread. Reference the item number (e.g. "B2 — WireGuard") and share your use case. Upvote existing comments with a thumbs-up reaction.

---

## Already Fetched — Easy Wins

These are data points the integration already collects from your router but doesn't expose as entities yet. Zero additional load on your router.

| # | Feature | What you'd get | Example use case |
|---|---------|---------------|------------------|
| A1 | **Firewall rule counters** | Byte/packet count per NAT, filter, mangle, raw rule | See which rules are actually active, detect brute-force attempts |
| A2 | **Interface queue drops** | Drop counter per interface | Alert on congestion, detect bandwidth bottlenecks |
| A3 | **Interface link-down counter** | Count of link flaps per port | Detect failing cables, unstable SFP modules, flapping PoE devices |
| A5 | **DHCP lease count** | Total active leases as a sensor | Track how many devices are on your network, detect DHCP pool exhaustion |
| A7 | **ARP table size** | Total ARP entries | Spot unexpected devices, detect network scans |
| A8 | **Queue actual throughput** | Real-time download/upload rate per queue | See actual bandwidth used vs limits in your QoS setup |
| A9 | **Wireless client signal strength** | Per-client RSSI as a sensor | WiFi health dashboards, "is the signal in the garage good enough?" |
| A10 | **Wireless client link rate** | Per-client TX/RX rate | Identify slow clients dragging down the AP |
| A11 | **Container running state** | Binary sensor per container | "Is my Pi-hole container actually running?" |
| A13 | **PPP connection details** | Caller-ID, encoding, address of active VPN users | Track who's connected to your VPN right now |
| A15 | **Captive portal stats** | Authorized/bypassed client counts | Monitor guest WiFi usage |

---

## New Data Sources — Medium Effort

These need new RouterOS API calls. They add a small amount to each polling cycle but unlock significant new capabilities.

### VPN & Remote Access

| # | Feature | What you'd get | Example use case |
|---|---------|---------------|------------------|
| B2 | **WireGuard VPN monitoring** | Tunnel up/down, peer connected, last handshake, TX/RX bytes, endpoint | "Is my remote site connected?", presence detection via VPN, alert on stale handshake |
| B12 | **PPPoE client status** | Connection state, uptime, assigned IP | Monitor ISP connection health, detect PPPoE drops |

### Network Awareness

| # | Feature | What you'd get | Example use case |
|---|---------|---------------|------------------|
| B1 | **Firewall address lists** | Enable/disable address list entries, entry count per list | Toggle ad-blocking lists, block/allow IPs from HA, geo-fence automation |
| B3 | **Network neighbors (LLDP/CDP/MNDP)** | Discovered neighbor devices | Detect when a new switch or AP appears on your network |
| B4 | **Route monitoring** | Active route count, default gateway status | Multi-WAN failover alerts: "WAN1 route disappeared, traffic on WAN2" — *voted; tracked as `ENH-260907-route-monitoring`* |
| B5 | **Interface IP addresses** | IP per interface as a sensor | WAN IP change detection, DDNS trigger, multi-WAN IP tracking |
| B11 | **Connection tracking count** | Active connections (TCP/UDP/ICMP breakdown) | Detect anomalies, alert on connection table near capacity |

### System & Security

| # | Feature | What you'd get | Example use case |
|---|---------|---------------|------------------|
| B7 | **MikroTik Cloud/DDNS** | Cloud hostname, status, public IP | External IP monitoring without a third-party DDNS service |
| B8 | **NTP sync status** | Synced/not synced, offset, stratum | Alert if router clock drifts (important for VPN certs, logging) |
| B9 | **Certificate expiry** | Cert name, expiry date, days remaining | Alert before HTTPS/VPN certificates expire |
| B13 | **Service status** | Enabled state of winbox, SSH, www, API, FTP | Security monitoring: "alert if FTP gets enabled" |
| B14 | **IP pool usage** | Used/total addresses per pool | DHCP pool exhaustion warning |

### Hardware-Specific

| # | Feature | What you'd get | Example use case |
|---|---------|---------------|------------------|
| B10 | **LTE modem stats** | RSSI, RSRP, RSRQ, SINR, carrier, connection state | LTE failover monitoring, signal quality dashboard for rural setups |
| B6 | **Scheduler status** | Next-run time, run-count per scheduled task | Monitor cron jobs, detect missed backup scripts |

---

## Advanced / Niche

Lower priority unless there's demand. Let us know if any of these matter to you.

| # | Feature | Notes |
|---|---------|-------|
| C1 | **IPsec tunnel status** | Site-to-site VPN monitoring |
| C4 | **IPv6 addresses** | Growing relevance as IPv6 adoption increases |
| C6 | **Disk usage** (ROS7) | Most routers have minimal storage |
| C9 | **License level** | Informational |
| C10 | **OpenVPN/SSTP server connections** | Being replaced by WireGuard |
| C13 | **System history / audit log** | Security-conscious setups |

---

## What's already covered

For reference, the integration currently provides:

- **System health** — CPU, memory, HDD, temperatures, voltages, fan speeds, PoE-in, UPS, GPS
- **Interface monitoring** — traffic (TX/RX), status, SFP details, PoE-out per port
- **Per-client traffic** — LAN/WAN TX/RX via Accounting (v6) or Kid Control (v7)
- **Firewall control** — enable/disable individual NAT, filter, mangle, RAW rules
- **Device tracking** — presence detection for wired, wireless, and CAPsMAN clients
- **Queue management** — enable/disable simple queues
- **PPP management** — enable/disable PPP secrets, connection status
- **Kid Control** — enable/disable/pause internet schedules
- **Containers** — status monitoring, start/stop
- **DHCP client** — WAN IP, gateway, DNS, lease expiry
- **Firmware updates** — check and install RouterOS and RouterBOARD updates
- **Scripts** — execute with immediate data refresh
- **Netwatch** — probe status tracking

Full technical details: [sensor-gap-analysis.md](sensor-gap-analysis.md)

---

## How we'll decide

1. **Community demand** — items with the most votes/discussion get prioritized
2. **Implementation complexity** — easy wins ship first
3. **Router load** — we won't add polling that degrades performance; new sources will be opt-in
4. **All new sensors are additive** — no breaking changes to existing entities

Have a use case we missed entirely? Tell us! Open a discussion or issue.
