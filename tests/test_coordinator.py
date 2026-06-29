"""Unit tests for Mikrotik Router coordinator and apiparser logic."""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mikrotik_router.apiparser import (
    parse_api,
    utc_from_timestamp as apiparser_utc_from_timestamp,
)
from custom_components.mikrotik_router.coordinator import (
    MikrotikCoordinator,
    _parse_uptime_to_seconds,
    as_local,
    utc_from_timestamp,
)
from custom_components.mikrotik_router.const import (
    CONF_SCAN_INTERVAL,
    CONF_SENSOR_CLIENT_TRAFFIC,
    CONF_SENSOR_POE,
    CONF_SENSOR_PORT_TRAFFIC,
    CONF_TRACK_IFACE_CLIENTS,
    DEFAULT_SENSOR_POE,
    DEFAULT_SENSOR_PORT_TRAFFIC,
)

from .conftest import MockMikrotikAPI

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_coordinator(options=None, api_responses=None, major_fw_version=6):
    """Build a minimal MikrotikCoordinator without triggering __init__."""
    coordinator = object.__new__(MikrotikCoordinator)

    coordinator.ds = {
        "access": ["write", "policy", "reboot", "test"],
        "routerboard": {},
        "resource": {},
        "health": {},
        "health7": {},
        "interface": {},
        "bonding": {},
        "bonding_slaves": {},
        "bridge": {},
        "bridge_host": {},
        "arp": {},
        "nat": {},
        "kid-control": {},
        "mangle": {},
        "filter": {},
        "ppp_secret": {},
        "ppp_active": {},
        "fw-update": {},
        "script": {},
        "queue": {},
        "dns": {},
        "dhcp-server": {},
        "dhcp-client": {},
        "dhcp-network": {},
        "dhcp": {},
        "capsman_hosts": {},
        "wireless": {},
        "wireless_hosts": {},
        "host": {},
        "host_hass": {},
        "hostspot_host": {},
        "client_traffic": {},
        "environment": {},
        "ups": {},
        "gps": {},
        "netwatch": {},
        "raw": {},
        "container": {},
    }

    coordinator.major_fw_version = major_fw_version
    coordinator.minor_fw_version = 0
    coordinator.api = MockMikrotikAPI(responses=api_responses or {})
    coordinator._known_uids = {}

    cfg = MagicMock()
    cfg.options = options or {}
    coordinator.config_entry = cfg

    return coordinator


# ---------------------------------------------------------------------------
# Group A: parse_api() — pure function tests
# ---------------------------------------------------------------------------


def test_parse_api_no_source_returns_data_unchanged():
    """parse_api with no source and empty vals returns data as-is."""
    data = {"existing": "value"}
    result = parse_api(data=data, source=None, vals=[])
    assert result == {"existing": "value"}


def test_parse_api_no_source_fills_defaults():
    """parse_api with no source and no key fills defaults into data dict."""
    data = {}
    result = parse_api(
        data=data,
        source=None,
        vals=[
            {"name": "temperature", "default": 0},
            {"name": "voltage", "default": 0},
        ],
    )
    assert result["temperature"] == 0
    assert result["voltage"] == 0


def test_parse_api_key_creates_keyed_entry():
    """parse_api with key= creates a keyed entry from source list."""
    data = {}
    source = [{"name": "ether1", "type": "ether", "mac-address": "AA:BB:CC:DD:EE:FF"}]
    result = parse_api(
        data=data,
        source=source,
        key="name",
        vals=[
            {"name": "name"},
            {"name": "type", "default": "unknown"},
        ],
    )
    assert "ether1" in result
    assert result["ether1"]["type"] == "ether"


def test_parse_api_key_search_merges_into_existing_entry():
    """parse_api with key_search= merges data into existing entry by name lookup."""
    data = {
        "uid-abc": {
            "name": "ether1",
            "type": "ether",
            "poe-out": "auto-on",
        }
    }
    source = [
        {
            "name": "ether1",
            "poe-out-status": "powered-on",
            "poe-out-voltage": 24.2,
            "poe-out-current": 0.5,
            "poe-out-power": 12.1,
        }
    ]
    result = parse_api(
        data=data,
        source=source,
        key_search="name",
        vals=[
            {"name": "poe-out-status", "default": "unknown"},
            {"name": "poe-out-voltage", "default": 0},
            {"name": "poe-out-current", "default": 0},
            {"name": "poe-out-power", "default": 0},
        ],
    )
    assert result["uid-abc"]["poe-out-status"] == "powered-on"
    assert result["uid-abc"]["poe-out-voltage"] == pytest.approx(24.2)
    assert result["uid-abc"]["poe-out-current"] == pytest.approx(0.5)
    assert result["uid-abc"]["poe-out-power"] == pytest.approx(12.1)


def test_parse_api_default_used_when_field_missing():
    """parse_api uses default value when a field is absent from source entry."""
    data = {}
    source = [{"name": "ether1"}]
    result = parse_api(
        data=data,
        source=source,
        key="name",
        vals=[
            {"name": "name"},
            {"name": "poe-out", "default": "N/A"},
        ],
    )
    assert result["ether1"]["poe-out"] == "N/A"


def test_parse_api_ensure_vals_adds_missing_keys():
    """parse_api ensure_vals adds keys not present in the existing data."""
    data = {}
    source = [{"name": "ether1", "type": "ether"}]
    result = parse_api(
        data=data,
        source=source,
        key="name",
        vals=[{"name": "name"}, {"name": "type"}],
        ensure_vals=[
            {"name": "rx-previous", "default": 0.0},
            {"name": "tx-previous", "default": 0.0},
        ],
    )
    assert result["ether1"]["rx-previous"] == pytest.approx(0.0)
    assert result["ether1"]["tx-previous"] == pytest.approx(0.0)


def test_parse_api_skip_filters_entries():
    """parse_api skip= skips entries matching skip conditions."""
    data = {}
    source = [
        {"name": "ether1", "type": "ether"},
        {"name": "bridge1", "type": "bridge"},
    ]
    result = parse_api(
        data=data,
        source=source,
        key="name",
        vals=[{"name": "name"}, {"name": "type"}],
        skip=[{"name": "type", "value": "bridge"}],
    )
    assert "ether1" in result
    assert "bridge1" not in result


# ---------------------------------------------------------------------------
# Group B: get_system_health()
# ---------------------------------------------------------------------------


def test_health_access_check_blocks_when_missing_write():
    """get_system_health returns early (no API call) when 'write' not in access."""
    coordinator = make_coordinator(major_fw_version=6)
    coordinator.ds["access"] = ["read", "policy"]
    coordinator.ds["health"] = {}

    coordinator.get_system_health()

    assert coordinator.ds["health"] == {}


def test_health_fw6_populates_poe_in_keys():
    """FW v6: health response with poe-in fields is merged into ds['health']."""
    coordinator = make_coordinator(
        major_fw_version=6,
        api_responses={
            "/system/health": [
                {
                    "temperature": 45,
                    "voltage": 12.0,
                    "poe-in-voltage": 48.1,
                    "poe-in-current": 220,
                }
            ]
        },
    )

    coordinator.get_system_health()

    assert coordinator.ds["health"]["poe-in-voltage"] == pytest.approx(48.1)
    assert coordinator.ds["health"]["poe-in-current"] == 220
    assert coordinator.ds["health"]["temperature"] == 45


def test_health_fw6_missing_poe_in_uses_defaults():
    """FW v6: health response without poe-in fields uses default 0."""
    coordinator = make_coordinator(
        major_fw_version=6,
        api_responses={
            "/system/health": [
                {
                    "temperature": 55,
                    "voltage": 12.1,
                }
            ]
        },
    )

    coordinator.get_system_health()

    assert coordinator.ds["health"]["poe-in-voltage"] == 0
    assert coordinator.ds["health"]["poe-in-current"] == 0


def test_health_fw7_flattens_name_value_pairs():
    """FW v7: name/value pair format is flattened into ds['health']."""
    coordinator = make_coordinator(
        major_fw_version=7,
        api_responses={
            "/system/health": [
                {"name": "temperature", "value": 50},
                {"name": "voltage", "value": 12.1},
                {"name": "poe-in-voltage", "value": 48.0},
            ]
        },
    )

    coordinator.get_system_health()

    assert coordinator.ds["health"]["temperature"] == 50
    assert coordinator.ds["health"]["voltage"] == pytest.approx(12.1)
    assert coordinator.ds["health"]["poe-in-voltage"] == pytest.approx(48.0)


def test_health_v0_unknown_skips_and_logs(caplog):
    """FW version 0 (unknown): system health is skipped, not silently no-op'd."""
    coordinator = make_coordinator(major_fw_version=0)
    coordinator.host = "10.0.0.1"

    with caplog.at_level(logging.DEBUG):
        coordinator.get_system_health()

    assert coordinator.ds["health"] == {}
    assert coordinator.ds["health7"] == {}
    assert "skipping system health" in caplog.text


# ---------------------------------------------------------------------------
# Group C: option_sensor_poe property + PoE parse_api merge
# ---------------------------------------------------------------------------


def test_option_sensor_poe_true_when_enabled():
    """option_sensor_poe returns True when CONF_SENSOR_POE is set in options."""
    coordinator = make_coordinator(options={CONF_SENSOR_POE: True})
    assert coordinator.option_sensor_poe is True


def test_option_sensor_poe_false_when_disabled():
    """option_sensor_poe returns False when CONF_SENSOR_POE is False."""
    coordinator = make_coordinator(options={CONF_SENSOR_POE: False})
    assert coordinator.option_sensor_poe is False


def test_option_sensor_poe_default_when_not_set():
    """option_sensor_poe uses DEFAULT_SENSOR_POE when option not in config."""
    coordinator = make_coordinator(options={})
    assert coordinator.option_sensor_poe == DEFAULT_SENSOR_POE


def test_poe_monitor_merges_all_four_fields():
    """parse_api with PoE monitor source merges all 4 poe-out fields into interface."""
    data = {
        "ether1": {
            "name": "ether1",
            "type": "ether",
            "poe-out": "auto-on",
        }
    }
    source = [
        {
            "name": "ether1",
            "poe-out-status": "powered-on",
            "poe-out-voltage": 24.5,
            "poe-out-current": 310,
            "poe-out-power": 7.6,
        }
    ]
    result = parse_api(
        data=data,
        source=source,
        key_search="name",
        vals=[
            {"name": "poe-out-status", "default": "unknown"},
            {"name": "poe-out-voltage", "default": 0},
            {"name": "poe-out-current", "default": 0},
            {"name": "poe-out-power", "default": 0},
        ],
    )
    assert result["ether1"]["poe-out-status"] == "powered-on"
    assert result["ether1"]["poe-out-voltage"] == pytest.approx(24.5)
    assert result["ether1"]["poe-out-current"] == 310
    assert result["ether1"]["poe-out-power"] == pytest.approx(7.6)


def test_poe_monitor_uses_none_defaults_for_missing_fields():
    """parse_api with partial PoE monitor response uses None defaults for missing fields.

    This mirrors the real coordinator behaviour: if the hardware doesn't return
    poe-out-voltage/current/power, they default to None so _skip_sensor() can
    hide those sensors on passive-PoE hardware (e.g. hAP ax3).
    """
    data = {
        "ether1": {
            "name": "ether1",
            "type": "ether",
            "poe-out": "auto-on",
        }
    }
    source = [{"name": "ether1", "poe-out-status": "waiting-for-load"}]
    result = parse_api(
        data=data,
        source=source,
        key_search="name",
        vals=[
            {"name": "poe-out-status", "default": "unknown"},
            {"name": "poe-out-voltage", "default": None},
            {"name": "poe-out-current", "default": None},
            {"name": "poe-out-power", "default": None},
        ],
    )
    assert result["ether1"]["poe-out-status"] == "waiting-for-load"
    assert result["ether1"]["poe-out-voltage"] is None
    assert result["ether1"]["poe-out-current"] is None
    assert result["ether1"]["poe-out-power"] is None


# ---------------------------------------------------------------------------
# Group D: async_process_host() — wired client availability
# ---------------------------------------------------------------------------


def make_coordinator_for_host(arp_entries=None, dhcp_entries=None, host_entries=None):
    """Build a coordinator pre-configured for async_process_host() testing."""
    coordinator = make_coordinator()

    # Required attributes for async_process_host
    coordinator.support_capsman = False
    coordinator.support_wireless = False
    # option_sensor_client_captive is a @property reading from config_entry.options;
    # make_coordinator() sets options={} so it defaults to DEFAULT_SENSOR_CLIENT_CAPTIVE=False
    coordinator.host_hass_recovered = True  # skip HA registry recovery

    mac_lookup = MagicMock()
    mac_lookup.lookup = AsyncMock(return_value="Vendor")
    coordinator.async_mac_lookup = mac_lookup

    coordinator.ds["arp"] = arp_entries or {}
    coordinator.ds["dhcp"] = dhcp_entries or {}
    coordinator.ds["host"] = host_entries or {}
    coordinator.ds["resource"] = {"clients_wired": 0, "clients_wireless": 0}
    coordinator.ds["capsman_hosts"] = {}
    coordinator.ds["wireless_hosts"] = {}
    coordinator.ds["dns"] = {}
    coordinator.ds["hostspot_host"] = {}

    return coordinator


# ---------------------------------------------------------------------------
# _disambiguate_duplicate_hostnames (ADR-013)
# ---------------------------------------------------------------------------


def _host(mac, host_name, address="192.168.88.1"):
    return {"mac-address": mac, "host-name": host_name, "address": address}


def test_disambiguate_appends_mac_for_shared_hostname():
    """Distinct MACs reporting the same host-name (e.g. lwIP 'lwip0') get the MAC
    appended, yielding distinct, stable display names."""
    coord = make_coordinator()
    coord.ds["host"] = {
        "B0:F8:93:DE:60:AD": _host("B0:F8:93:DE:60:AD", "lwip0"),
        "C0:F8:53:9C:E6:E3": _host("C0:F8:53:9C:E6:E3", "lwip0"),
    }
    coord._disambiguate_duplicate_hostnames()
    names = [v["host-name"] for v in coord.ds["host"].values()]
    assert names == ["lwip0 (B0:F8:93:DE:60:AD)", "lwip0 (C0:F8:53:9C:E6:E3)"]
    assert len(set(names)) == 2  # distinct


def test_disambiguate_leaves_unique_hostname_unchanged():
    coord = make_coordinator()
    coord.ds["host"] = {
        "AA:BB:CC:00:00:01": _host("AA:BB:CC:00:00:01", "mypc"),
        "AA:BB:CC:00:00:02": _host("AA:BB:CC:00:00:02", "lwip0"),
        "AA:BB:CC:00:00:03": _host("AA:BB:CC:00:00:03", "lwip0"),
    }
    coord._disambiguate_duplicate_hostnames()
    assert coord.ds["host"]["AA:BB:CC:00:00:01"]["host-name"] == "mypc"  # unique → untouched
    assert coord.ds["host"]["AA:BB:CC:00:00:02"]["host-name"] == "lwip0 (AA:BB:CC:00:00:02)"


def test_disambiguate_distinct_mac_fallbacks_not_suffixed():
    """Two hosts that fell back to their own MAC have distinct host-names already,
    so they are not 'shared' and must not be double-suffixed."""
    coord = make_coordinator()
    coord.ds["host"] = {
        "AA:BB:CC:00:00:01": _host("AA:BB:CC:00:00:01", "AA:BB:CC:00:00:01"),
        "AA:BB:CC:00:00:02": _host("AA:BB:CC:00:00:02", "AA:BB:CC:00:00:02"),
    }
    coord._disambiguate_duplicate_hostnames()
    assert coord.ds["host"]["AA:BB:CC:00:00:01"]["host-name"] == "AA:BB:CC:00:00:01"
    assert coord.ds["host"]["AA:BB:CC:00:00:02"]["host-name"] == "AA:BB:CC:00:00:02"


def test_disambiguate_skips_unknown_mac():
    """A shared host-name with no usable MAC cannot be disambiguated → left as-is."""
    coord = make_coordinator()
    coord.ds["host"] = {
        "h1": {"mac-address": "unknown", "host-name": "lwip0", "address": "x"},
        "h2": {"mac-address": "unknown", "host-name": "lwip0", "address": "y"},
    }
    coord._disambiguate_duplicate_hostnames()
    assert coord.ds["host"]["h1"]["host-name"] == "lwip0"
    assert coord.ds["host"]["h2"]["host-name"] == "lwip0"


def test_disambiguate_is_idempotent():
    """Re-running must not append the MAC twice (suffixed names are unique → count 1)."""
    coord = make_coordinator()
    coord.ds["host"] = {
        "B0:F8:93:DE:60:AD": _host("B0:F8:93:DE:60:AD", "lwip0"),
        "C0:F8:53:9C:E6:E3": _host("C0:F8:53:9C:E6:E3", "lwip0"),
    }
    coord._disambiguate_duplicate_hostnames()
    coord._disambiguate_duplicate_hostnames()
    assert coord.ds["host"]["B0:F8:93:DE:60:AD"]["host-name"] == "lwip0 (B0:F8:93:DE:60:AD)"


def test_disambiguated_name_propagates_to_client_traffic_fw_lt7():
    """fw<7 path: _init_accounting_hosts copies the disambiguated host-name."""
    coord = make_coordinator(major_fw_version=6)
    coord.ds["host"] = {
        "B0:F8:93:DE:60:AD": {
            "mac-address": "B0:F8:93:DE:60:AD",
            "host-name": "lwip0 (B0:F8:93:DE:60:AD)",
            "address": "192.168.88.71",
        }
    }
    coord.ds["client_traffic"] = {}
    coord._init_accounting_hosts()
    assert coord.ds["client_traffic"]["B0:F8:93:DE:60:AD"]["host-name"] == "lwip0 (B0:F8:93:DE:60:AD)"


def test_disambiguated_name_propagates_to_client_traffic_fw_ge7():
    """fw>=7 path (the live RouterOS-7 path): process_kid_control_devices copies it."""
    coord = make_coordinator(major_fw_version=7)
    coord.ds["host"] = {
        "B0:F8:93:DE:60:AD": {
            "mac-address": "B0:F8:93:DE:60:AD",
            "host-name": "lwip0 (B0:F8:93:DE:60:AD)",
            "address": "192.168.88.71",
        }
    }
    coord.ds["client_traffic"] = {}
    coord.notified_flags = []
    coord.api.query = MagicMock(return_value=[])  # no kid-control data → early return after copy
    coord.api.take_client_traffic_snapshot = MagicMock(return_value=0)
    coord.process_kid_control_devices()
    assert coord.ds["client_traffic"]["B0:F8:93:DE:60:AD"]["host-name"] == "lwip0 (B0:F8:93:DE:60:AD)"


@pytest.mark.asyncio
async def test_arp_host_becomes_available():
    """ARP host present in current ARP table is marked available=True."""
    coordinator = make_coordinator_for_host(
        arp_entries={
            "AA:BB:CC:DD:EE:01": {
                "mac-address": "AA:BB:CC:DD:EE:01",
                "address": "192.168.1.10",
                "interface": "ether1",
            }
        }
    )

    await coordinator.async_process_host()

    host = coordinator.ds["host"]["AA:BB:CC:DD:EE:01"]
    assert host["available"] is True
    assert host["last-seen"] is not False


@pytest.mark.asyncio
async def test_arp_host_becomes_unavailable_when_not_in_arp():
    """ARP host previously tracked but absent from current ARP table is unavailable."""
    coordinator = make_coordinator_for_host(
        arp_entries={},  # empty — device left the network
        host_entries={
            "AA:BB:CC:DD:EE:02": {
                "source": "arp",
                "mac-address": "AA:BB:CC:DD:EE:02",
                "address": "192.168.1.11",
                "interface": "ether1",
                "host-name": "mypc",
                "manufacturer": "Vendor",
                "last-seen": False,
                "available": True,  # was available before
            }
        },
    )

    await coordinator.async_process_host()

    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:02"]["available"] is False


@pytest.mark.asyncio
async def test_dhcp_host_available_when_in_arp():
    """DHCP-sourced host is available when its MAC appears in the current ARP table."""
    mac = "AA:BB:CC:DD:EE:03"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac: {
                "mac-address": mac,
                "address": "192.168.1.12",
                "interface": "ether2",
            }
        },
        dhcp_entries={
            mac: {
                "enabled": True,
                "mac-address": mac,
                "address": "192.168.1.12",
                "interface": "ether2",
                "host-name": "laptop",
                "comment": "",
            }
        },
    )

    await coordinator.async_process_host()

    host = coordinator.ds["host"][mac]
    assert host["available"] is True


@pytest.mark.asyncio
async def test_dhcp_host_unavailable_when_not_in_arp():
    """DHCP host with a valid lease but absent from ARP table is unavailable."""
    mac = "AA:BB:CC:DD:EE:04"
    coordinator = make_coordinator_for_host(
        arp_entries={},  # not in ARP
        dhcp_entries={
            mac: {
                "enabled": True,
                "mac-address": mac,
                "address": "192.168.1.13",
                "interface": "ether2",
                "host-name": "phone",
                "comment": "",
            }
        },
    )

    await coordinator.async_process_host()

    host = coordinator.ds["host"][mac]
    assert host["available"] is False


@pytest.mark.asyncio
async def test_clients_wired_count_increments_for_arp_hosts():
    """clients_wired increments once per available ARP host."""
    coordinator = make_coordinator_for_host(
        arp_entries={
            "AA:BB:CC:DD:EE:05": {
                "mac-address": "AA:BB:CC:DD:EE:05",
                "address": "192.168.1.20",
                "interface": "ether1",
            },
            "AA:BB:CC:DD:EE:06": {
                "mac-address": "AA:BB:CC:DD:EE:06",
                "address": "192.168.1.21",
                "interface": "ether1",
            },
        }
    )

    await coordinator.async_process_host()

    assert coordinator.ds["resource"]["clients_wired"] == 2
    assert coordinator.ds["resource"]["clients_wireless"] == 0


@pytest.mark.asyncio
async def test_wireless_host_not_counted_as_wired():
    """Wireless-sourced host is never counted as a wired client."""
    mac = "AA:BB:CC:DD:EE:07"
    coordinator = make_coordinator_for_host(
        host_entries={
            mac: {
                "source": "wireless",
                "mac-address": mac,
                "address": "192.168.1.30",
                "interface": "wlan1",
                "host-name": "tablet",
                "manufacturer": "Vendor",
                "last-seen": False,
                "available": True,
                "signal-strength": -65,
                "tx-ccq": 90,
                "tx-rate": "54Mbps",
                "rx-rate": "54Mbps",
            }
        }
    )
    coordinator.support_wireless = True
    coordinator.ds["wireless_hosts"] = {
        mac: {
            "mac-address": mac,
            "interface": "wlan1",
            "ap": False,
            "signal-strength": -65,
            "tx-ccq": 90,
            "tx-rate": "54Mbps",
            "rx-rate": "54Mbps",
        }
    }

    await coordinator.async_process_host()

    assert coordinator.ds["resource"]["clients_wired"] == 0
    assert coordinator.ds["resource"]["clients_wireless"] == 1


@pytest.mark.asyncio
async def test_arp_failed_status_not_detected_but_host_created():
    """ARP entry with status 'failed' is NOT counted in arp_detected (#17).

    The host entry IS still created (so it appears in the UI as 'away'),
    but it is not marked available.  The failed entry stays in ds['arp']
    so the tracker coordinator can still look up bridge interfaces.
    """
    mac = "AA:BB:CC:DD:EE:F1"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac: {
                "mac-address": mac,
                "address": "192.168.1.50",
                "interface": "ether1",
                "status": "failed",
                "bridge": "bridge",
            }
        }
    )

    await coordinator.async_process_host()

    # Host entry created (visible in UI) but marked unavailable
    assert mac in coordinator.ds["host"]
    assert coordinator.ds["host"][mac]["available"] is False

    # Failed entry kept in ds["arp"] for bridge lookups
    assert mac in coordinator.ds["arp"]
    assert coordinator.ds["arp"][mac]["bridge"] == "bridge"


@pytest.mark.asyncio
async def test_arp_reachable_status_detected():
    """ARP entry with non-failed status is counted as detected and available."""
    mac = "AA:BB:CC:DD:EE:F2"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac: {
                "mac-address": mac,
                "address": "192.168.1.51",
                "interface": "ether1",
                "status": "reachable",
            }
        }
    )

    await coordinator.async_process_host()

    assert coordinator.ds["host"][mac]["available"] is True
    assert coordinator.ds["host"][mac]["last-seen"] is not False


@pytest.mark.asyncio
async def test_arp_empty_status_detected():
    """ARP entry with empty/missing status (static entry) is detected and available."""
    mac = "AA:BB:CC:DD:EE:F3"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac: {
                "mac-address": mac,
                "address": "192.168.1.52",
                "interface": "ether1",
                "status": "",
            }
        }
    )

    await coordinator.async_process_host()

    assert coordinator.ds["host"][mac]["available"] is True


@pytest.mark.asyncio
async def test_mixed_arp_statuses_only_unreachable_excluded():
    """Only 'failed'/'incomplete' ARP entries are excluded; others are detected."""
    mac_ok = "AA:BB:CC:DD:EE:A1"
    mac_failed = "AA:BB:CC:DD:EE:A2"
    mac_incomplete = "AA:BB:CC:DD:EE:A3"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac_ok: {
                "mac-address": mac_ok,
                "address": "192.168.1.60",
                "interface": "ether1",
                "status": "stale",
            },
            mac_failed: {
                "mac-address": mac_failed,
                "address": "192.168.1.61",
                "interface": "ether1",
                "status": "failed",
            },
            mac_incomplete: {
                "mac-address": mac_incomplete,
                "address": "192.168.1.62",
                "interface": "ether1",
                "status": "incomplete",
            },
        }
    )

    await coordinator.async_process_host()

    assert coordinator.ds["host"][mac_ok]["available"] is True
    assert coordinator.ds["host"][mac_failed]["available"] is False
    assert coordinator.ds["host"][mac_incomplete]["available"] is False


@pytest.mark.asyncio
async def test_arp_incomplete_status_not_detected_but_host_created():
    """ARP entry with status 'incomplete' is NOT counted as detected.

    'incomplete' means the router sent an ARP request but received no reply —
    the device is unreachable, same as 'failed'.
    """
    mac = "AA:BB:CC:DD:EE:F4"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac: {
                "mac-address": mac,
                "address": "192.168.1.53",
                "interface": "ether1",
                "status": "incomplete",
                "bridge": "bridge",
            }
        }
    )

    await coordinator.async_process_host()

    # Host entry created (visible in UI) but marked unavailable
    assert mac in coordinator.ds["host"]
    assert coordinator.ds["host"][mac]["available"] is False

    # Entry kept in ds["arp"] for bridge lookups
    assert mac in coordinator.ds["arp"]
    assert coordinator.ds["arp"][mac]["bridge"] == "bridge"


# ---------------------------------------------------------------------------
# Group E: bug-fix regression tests
# ---------------------------------------------------------------------------


def test_get_accounting_uid_by_ip_uses_equality_not_identity():
    """_get_accounting_uid_by_ip returns correct MAC using == not 'is'.

    Regression test for the 'is' vs '==' string comparison fix.
    String interning means 'is' works for short literals but fails for
    dynamically built strings — == is always correct.
    """
    coordinator = make_coordinator()
    coordinator.ds["client_traffic"] = {
        "AA:BB:CC:DD:EE:01": {"address": "192.168.1.10"},
        "AA:BB:CC:DD:EE:02": {"address": "192.168.1.20"},
    }

    # Build IP as a non-interned string to ensure 'is' would fail
    target_ip = "192.168.1." + "20"
    result = coordinator._get_accounting_uid_by_ip(target_ip)

    assert result == "AA:BB:CC:DD:EE:02"


@pytest.mark.asyncio
async def test_mac_lookup_cancelled_error_propagates():
    """asyncio.CancelledError from mac lookup is re-raised, not swallowed.

    Regression test for the bare except swallowing CancelledError fix.
    """
    import asyncio

    coordinator = make_coordinator_for_host(
        arp_entries={
            "AA:BB:CC:DD:EE:FF": {
                "mac-address": "AA:BB:CC:DD:EE:FF",
                "address": "192.168.1.99",
                "interface": "ether1",
            }
        }
    )

    async def raise_cancelled(_mac):
        raise asyncio.CancelledError()

    coordinator.async_mac_lookup.lookup = raise_cancelled

    with pytest.raises(asyncio.CancelledError):
        await coordinator.async_process_host()


def _host_entry(mac, address="192.168.1.10", manufacturer="detect"):
    """Build a minimal host entry for manufacturer resolution tests."""
    return {
        "mac-address": mac,
        "address": address,
        "interface": "ether1",
        "host-name": "test",
        "source": "arp",
        "manufacturer": manufacturer,
        "last-seen": False,
        "available": False,
    }


@pytest.mark.asyncio
async def test_resolve_manufacturer_error_sets_empty_string():
    """When mac_lookup.lookup raises, manufacturer is set to '' not left as 'detect'."""
    mac = "AA:BB:CC:DD:EE:FF"
    coordinator = make_coordinator_for_host(
        arp_entries={mac: {"mac-address": mac, "address": "192.168.1.10", "interface": "ether1"}},
        host_entries={mac: _host_entry(mac)},
    )

    coordinator.async_mac_lookup.lookup = AsyncMock(side_effect=OSError("lookup DB unavailable"))

    await coordinator.async_process_host()

    assert coordinator.ds["host"][mac]["manufacturer"] == ""


@pytest.mark.asyncio
async def test_resolve_manufacturer_concurrent_partial_failure():
    """One MAC lookup failure does not affect other concurrent lookups."""
    mac1, mac2 = "AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac1: {
                "mac-address": mac1,
                "address": "192.168.1.10",
                "interface": "ether1",
            },
            mac2: {
                "mac-address": mac2,
                "address": "192.168.1.11",
                "interface": "ether1",
            },
        },
        host_entries={
            mac1: _host_entry(mac1, "192.168.1.10"),
            mac2: _host_entry(mac2, "192.168.1.11"),
        },
    )

    async def selective_lookup(mac):
        if mac == mac1:
            raise OSError("lookup failed")
        return "GoodVendor"

    coordinator.async_mac_lookup.lookup = selective_lookup

    await coordinator.async_process_host()

    assert coordinator.ds["host"][mac1]["manufacturer"] == ""
    assert coordinator.ds["host"][mac2]["manufacturer"] == "GoodVendor"


@pytest.mark.asyncio
async def test_resolve_manufacturer_parallel_success():
    """Multiple MAC lookups resolve concurrently via asyncio.gather."""
    mac1, mac2 = "AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac1: {
                "mac-address": mac1,
                "address": "192.168.1.10",
                "interface": "ether1",
            },
            mac2: {
                "mac-address": mac2,
                "address": "192.168.1.11",
                "interface": "ether1",
            },
        },
        host_entries={
            mac1: _host_entry(mac1, "192.168.1.10"),
            mac2: _host_entry(mac2, "192.168.1.11"),
        },
    )

    async def vendor_by_mac(mac):
        return {mac1: "VendorA", mac2: "VendorB"}[mac]

    coordinator.async_mac_lookup.lookup = vendor_by_mac

    await coordinator.async_process_host()

    assert coordinator.ds["host"][mac1]["manufacturer"] == "VendorA"
    assert coordinator.ds["host"][mac2]["manufacturer"] == "VendorB"


@pytest.mark.asyncio
async def test_resolve_manufacturer_unknown_mac_skips_lookup():
    """Hosts with mac-address='unknown' skip lookup and get manufacturer=''."""
    coordinator = make_coordinator_for_host(
        host_entries={
            "AA:BB:CC:DD:EE:FF": _host_entry("unknown"),
        },
    )

    await coordinator.async_process_host()

    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:FF"]["manufacturer"] == ""
    coordinator.async_mac_lookup.lookup.assert_not_called()


# ---------------------------------------------------------------------------
# utc_from_timestamp and as_local tests
# ---------------------------------------------------------------------------


def test_utc_from_timestamp_returns_utc_aware_datetime():
    """utc_from_timestamp produces a UTC-aware datetime from a Unix timestamp."""
    result = utc_from_timestamp(0)
    assert result == datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert result.tzinfo is timezone.utc


def test_utc_from_timestamp_apiparser_matches_coordinator():
    """Both apiparser and coordinator produce identical results."""
    ts = 1_700_000_000.0
    assert apiparser_utc_from_timestamp(ts) == utc_from_timestamp(ts)


def test_as_local_returns_naive_datetime_unchanged_when_no_tz_configured():
    """as_local returns naive datetime unchanged when DEFAULT_TIME_ZONE is None."""
    naive = datetime(2024, 1, 15, 12, 0, 0)
    result = as_local(naive)
    assert result == naive


def test_as_local_attaches_utc_to_naive_datetime_when_tz_configured(monkeypatch):
    """as_local attaches UTC tzinfo to naive datetime when DEFAULT_TIME_ZONE is set."""
    import custom_components.mikrotik_router.coordinator as coord_module

    monkeypatch.setattr(coord_module, "DEFAULT_TIME_ZONE", timezone.utc)
    naive = datetime(2024, 1, 15, 12, 0, 0)
    result = as_local(naive)
    assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# Group F: get_arp — ARP table processing and failed entry filtering
# ---------------------------------------------------------------------------


def test_get_arp_keeps_failed_entries_for_bridge_lookups():
    """ARP entries with status 'failed' are kept in ds['arp'] per ADR-001.

    Failed entries are excluded from availability in async_process_host(),
    not in get_arp(). They must remain for bridge-interface resolution.
    """
    coordinator = make_coordinator(
        api_responses={
            "/ip/arp": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "10.0.0.1",
                    "interface": "ether1",
                    "status": "",
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:02",
                    "address": "10.0.0.2",
                    "interface": "ether1",
                    "status": "failed",
                },
            ]
        }
    )
    coordinator.ds["bridge"] = {}
    coordinator.ds["bridge_host"] = {}
    coordinator.ds["dhcp-client"] = {}
    coordinator.get_arp()
    assert "AA:BB:CC:DD:EE:01" in coordinator.ds["arp"]
    assert "AA:BB:CC:DD:EE:02" in coordinator.ds["arp"]


def test_get_arp_keeps_entries_without_status():
    """ARP entries without a status field (or empty status) should be kept."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/arp": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "10.0.0.1",
                    "interface": "ether1",
                },
            ]
        }
    )
    coordinator.ds["bridge"] = {}
    coordinator.ds["bridge_host"] = {}
    coordinator.ds["dhcp-client"] = {}
    coordinator.get_arp()
    assert "AA:BB:CC:DD:EE:01" in coordinator.ds["arp"]


def test_get_arp_removes_dhcp_client_interfaces():
    """ARP entries on DHCP client interfaces should be excluded."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/arp": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "10.0.0.1",
                    "interface": "ether1-wan",
                    "status": "",
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:02",
                    "address": "10.0.0.2",
                    "interface": "ether2",
                    "status": "",
                },
            ]
        }
    )
    coordinator.ds["bridge"] = {}
    coordinator.ds["bridge_host"] = {}
    coordinator.ds["dhcp-client"] = {"ether1-wan": {"interface": "ether1-wan"}}
    coordinator.get_arp()
    assert "AA:BB:CC:DD:EE:01" not in coordinator.ds["arp"]
    assert "AA:BB:CC:DD:EE:02" in coordinator.ds["arp"]


def test_get_arp_resolves_bridge_interface():
    """ARP entries on bridge interfaces get bridge field set and real port resolved."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/arp": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "10.0.0.1",
                    "interface": "bridge",
                    "status": "",
                },
            ]
        }
    )
    coordinator.ds["bridge"] = {"bridge": {"name": "bridge"}}
    coordinator.ds["bridge_host"] = {"AA:BB:CC:DD:EE:01": {"interface": "ether3"}}
    coordinator.ds["dhcp-client"] = {}
    coordinator.get_arp()
    entry = coordinator.ds["arp"]["AA:BB:CC:DD:EE:01"]
    assert entry["bridge"] == "bridge"
    assert entry["interface"] == "ether3"


# ---------------------------------------------------------------------------
# Group G: get_dns — static DNS processing
# ---------------------------------------------------------------------------


def test_get_dns_parses_entries():
    """Static DNS entries are parsed with name, address, comment."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dns/static": [
                {
                    "name": "router.lan",
                    "address": "10.0.0.1",
                    "comment": "Main Router",
                },
            ]
        }
    )
    coordinator.get_dns()
    assert "router.lan" in coordinator.ds["dns"]
    assert coordinator.ds["dns"]["router.lan"]["address"] == "10.0.0.1"
    assert coordinator.ds["dns"]["router.lan"]["comment"] == "Main Router"


def test_get_dns_comment_converted_to_string():
    """DNS comment field is always converted to string."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dns/static": [
                {"name": "test.lan", "address": "10.0.0.2", "comment": 12345},
            ]
        }
    )
    coordinator.get_dns()
    assert coordinator.ds["dns"]["test.lan"]["comment"] == "12345"


# ---------------------------------------------------------------------------
# Group H: coordinator option properties
# ---------------------------------------------------------------------------


def test_option_sensor_port_traffic_enabled():
    coordinator = make_coordinator(options={CONF_SENSOR_PORT_TRAFFIC: True})
    assert coordinator.option_sensor_port_traffic is True


def test_option_sensor_port_traffic_default():
    coordinator = make_coordinator(options={})
    assert coordinator.option_sensor_port_traffic == DEFAULT_SENSOR_PORT_TRAFFIC


def test_option_sensor_poe_enabled():
    coordinator = make_coordinator(options={CONF_SENSOR_POE: True})
    assert coordinator.option_sensor_poe is True


def test_option_sensor_poe_default():
    coordinator = make_coordinator(options={})
    assert coordinator.option_sensor_poe == DEFAULT_SENSOR_POE


# ---------------------------------------------------------------------------
# Group I: set_value and execute wrappers
# ---------------------------------------------------------------------------


def test_set_value_delegates_to_api():
    """Coordinator.set_value passes through to api.set_value."""
    coordinator = make_coordinator()
    coordinator.api.set_value = MagicMock(return_value=True)
    result = coordinator.set_value("/interface", "name", "ether1", "disabled", True)
    coordinator.api.set_value.assert_called_once_with("/interface", "name", "ether1", "disabled", True)
    assert result is True


def test_execute_delegates_to_api():
    """Coordinator.execute passes through to api.execute."""
    coordinator = make_coordinator()
    coordinator.api.execute = MagicMock(return_value=True)
    result = coordinator.execute("/system", "reboot", None, None)
    coordinator.api.execute.assert_called_once_with("/system", "reboot", None, None, None)
    assert result is True


# ---------------------------------------------------------------------------
# _parse_uptime_to_seconds helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uptime_str, expected",
    [
        ("1w2d3h4m5s", 788645),
        ("5s", 5),
        ("3m", 180),
        ("2h", 7200),
        ("1d", 86400),
        ("1w", 604800),
        ("", 0),
        ("unknown", 0),
        ("1d12h30m", 131400),
    ],
)
def test_parse_uptime_to_seconds(uptime_str, expected):
    """_parse_uptime_to_seconds converts MikroTik uptime strings correctly."""
    assert _parse_uptime_to_seconds(uptime_str) == expected


# ---------------------------------------------------------------------------
# Group J: get_system_resource() — CPU, memory, uptime, storage
# ---------------------------------------------------------------------------


def test_system_resource_uptime_parsing():
    """Uptime string '1w2d3h4m5s' is parsed to correct epoch seconds."""
    coordinator = make_coordinator(
        api_responses={
            "/system/resource": [
                {
                    "uptime": "1w2d3h4m5s",
                    "cpu-load": 15,
                    "free-memory": 500000,
                    "total-memory": 1000000,
                    "free-hdd-space": 8000000,
                    "total-hdd-space": 16000000,
                    "platform": "MikroTik",
                    "board-name": "RB4011",
                    "version": "7.16.2",
                }
            ]
        }
    )
    coordinator.rebootcheck = 999999
    coordinator.host = "10.0.0.1"
    coordinator.get_system_resource()

    expected = 1 * 604800 + 2 * 86400 + 3 * 3600 + 4 * 60 + 5
    assert coordinator.ds["resource"]["uptime_epoch"] == expected


def test_system_resource_uptime_seconds_only():
    """Uptime '45s' parses correctly."""
    coordinator = make_coordinator(
        api_responses={
            "/system/resource": [
                {
                    "uptime": "45s",
                    "cpu-load": 5,
                    "free-memory": 100,
                    "total-memory": 200,
                    "free-hdd-space": 100,
                    "total-hdd-space": 200,
                }
            ]
        }
    )
    coordinator.rebootcheck = 999999
    coordinator.host = "10.0.0.1"
    coordinator.get_system_resource()
    assert coordinator.ds["resource"]["uptime_epoch"] == 45


def test_system_resource_memory_usage():
    """Memory usage percentage calculated correctly."""
    coordinator = make_coordinator(
        api_responses={
            "/system/resource": [
                {
                    "uptime": "1h",
                    "cpu-load": 10,
                    "free-memory": 256000000,
                    "total-memory": 1024000000,
                    "free-hdd-space": 100,
                    "total-hdd-space": 200,
                }
            ]
        }
    )
    coordinator.rebootcheck = 999999
    coordinator.host = "10.0.0.1"
    coordinator.get_system_resource()
    assert coordinator.ds["resource"]["memory-usage"] == 75


def test_system_resource_zero_memory_returns_unknown():
    """Zero total memory → memory-usage is 'unknown'."""
    coordinator = make_coordinator(
        api_responses={
            "/system/resource": [
                {
                    "uptime": "1m",
                    "cpu-load": 0,
                    "free-memory": 0,
                    "total-memory": 0,
                    "free-hdd-space": 0,
                    "total-hdd-space": 0,
                }
            ]
        }
    )
    coordinator.rebootcheck = 999999
    coordinator.host = "10.0.0.1"
    coordinator.get_system_resource()
    assert coordinator.ds["resource"]["memory-usage"] == "unknown"
    assert coordinator.ds["resource"]["hdd-usage"] == "unknown"


def test_system_resource_hdd_usage():
    """HDD usage percentage calculated correctly."""
    coordinator = make_coordinator(
        api_responses={
            "/system/resource": [
                {
                    "uptime": "1h",
                    "cpu-load": 5,
                    "free-memory": 100,
                    "total-memory": 200,
                    "free-hdd-space": 4000000,
                    "total-hdd-space": 16000000,
                }
            ]
        }
    )
    coordinator.rebootcheck = 999999
    coordinator.host = "10.0.0.1"
    coordinator.get_system_resource()
    assert coordinator.ds["resource"]["hdd-usage"] == 75


def test_system_resource_reboot_detection():
    """When uptime_epoch < rebootcheck, get_firmware_update is called."""
    coordinator = make_coordinator(
        api_responses={
            "/system/resource": [
                {
                    "uptime": "30s",
                    "cpu-load": 5,
                    "free-memory": 100,
                    "total-memory": 200,
                    "free-hdd-space": 100,
                    "total-hdd-space": 200,
                }
            ]
        }
    )
    coordinator.rebootcheck = 99999  # much larger than 30s
    coordinator.host = "10.0.0.1"
    coordinator.get_firmware_update = MagicMock()
    coordinator.get_system_resource()
    coordinator.get_firmware_update.assert_called_once()


def test_system_resource_no_reboot_if_uptime_grows():
    """Normal operation: uptime grows, no reboot detection."""
    coordinator = make_coordinator(
        api_responses={
            "/system/resource": [
                {
                    "uptime": "2h",
                    "cpu-load": 5,
                    "free-memory": 100,
                    "total-memory": 200,
                    "free-hdd-space": 100,
                    "total-hdd-space": 200,
                }
            ]
        }
    )
    coordinator.rebootcheck = 3600  # 1 hour — less than 2h
    coordinator.host = "10.0.0.1"
    coordinator.get_firmware_update = MagicMock()
    coordinator.get_system_resource()
    coordinator.get_firmware_update.assert_not_called()


# ---------------------------------------------------------------------------
# Group K: get_firmware_update() — version parsing, access control
# ---------------------------------------------------------------------------


def test_firmware_update_available():
    """Firmware update detected when status matches."""
    coordinator = make_coordinator(
        api_responses={
            "/system/package/update": [
                {
                    "status": "New version is available",
                    "channel": "stable",
                    "installed-version": "7.16.1",
                    "latest-version": "7.16.2",
                }
            ]
        }
    )
    coordinator.host = "10.0.0.1"
    coordinator.execute = MagicMock()
    coordinator.get_firmware_update()
    assert coordinator.ds["fw-update"]["available"] is True
    assert coordinator.major_fw_version == 7
    assert coordinator.minor_fw_version == 16


def test_firmware_update_not_available():
    """No update when status is different."""
    coordinator = make_coordinator(
        api_responses={
            "/system/package/update": [
                {
                    "status": "System is already up to date",
                    "channel": "stable",
                    "installed-version": "7.16.2",
                    "latest-version": "7.16.2",
                }
            ]
        }
    )
    coordinator.host = "10.0.0.1"
    coordinator.execute = MagicMock()
    coordinator.get_firmware_update()
    assert coordinator.ds["fw-update"]["available"] is False


def test_firmware_update_blocked_without_access():
    """Firmware check skipped if missing write/policy/reboot access."""
    coordinator = make_coordinator(
        api_responses={
            "/system/package/update": [
                {
                    "status": "New version is available",
                    "installed-version": "7.16.2",
                    "latest-version": "7.17.0",
                }
            ]
        }
    )
    coordinator.ds["access"] = ["read"]  # missing write, policy, reboot
    coordinator.host = "10.0.0.1"
    coordinator.execute = MagicMock()
    coordinator.get_firmware_update()
    coordinator.execute.assert_not_called()
    assert coordinator.ds["fw-update"] == {}


def test_firmware_version_parsing_v6():
    """Version string '6.49' parsed as major=6, minor=49."""
    coordinator = make_coordinator(
        api_responses={
            "/system/package/update": [
                {
                    "status": "System is already up to date",
                    "installed-version": "6.49.10",
                    "latest-version": "6.49.10",
                }
            ]
        }
    )
    coordinator.host = "10.0.0.1"
    coordinator.execute = MagicMock()
    coordinator.get_firmware_update()
    assert coordinator.major_fw_version == 6
    assert coordinator.minor_fw_version == 49


# ---------------------------------------------------------------------------
# Group L: get_nat() — NAT rule parsing and deduplication
# ---------------------------------------------------------------------------


def test_nat_basic_rule():
    """Basic dst-nat rule is parsed correctly."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/nat": [
                {
                    ".id": "*1",
                    "chain": "dstnat",
                    "action": "dst-nat",
                    "protocol": "tcp",
                    "dst-port": "8080",
                    "in-interface": "ether1",
                    "to-addresses": "192.168.1.100",
                    "to-ports": "80",
                    "comment": "Web server",
                    "disabled": False,
                }
            ]
        }
    )
    coordinator.nat_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_nat()
    assert "*1" in coordinator.ds["nat"]
    rule = coordinator.ds["nat"]["*1"]
    assert rule["action"] == "dst-nat"
    assert rule["protocol"] == "tcp"
    assert rule["enabled"] is True
    assert rule["name"] == "tcp:8080"


def test_nat_filters_non_dst_nat():
    """Only dst-nat rules are kept; masquerade is filtered out."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/nat": [
                {
                    ".id": "*1",
                    "chain": "srcnat",
                    "action": "masquerade",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "dstnat",
                    "action": "dst-nat",
                    "protocol": "tcp",
                    "dst-port": "443",
                    "to-addresses": "192.168.1.1",
                    "to-ports": "443",
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.nat_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_nat()
    assert "*1" not in coordinator.ds["nat"]
    assert "*2" in coordinator.ds["nat"]


def test_nat_duplicate_removal():
    """Duplicate NAT rules (same uniq-id) are both removed."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/nat": [
                {
                    ".id": "*1",
                    "chain": "dstnat",
                    "action": "dst-nat",
                    "protocol": "tcp",
                    "dst-port": "80",
                    "in-interface": "ether1",
                    "to-addresses": "192.168.1.1",
                    "to-ports": "80",
                    "comment": "Rule A",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "dstnat",
                    "action": "dst-nat",
                    "protocol": "tcp",
                    "dst-port": "80",
                    "in-interface": "ether1",
                    "to-addresses": "192.168.1.1",
                    "to-ports": "80",
                    "comment": "Rule B",
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.nat_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_nat()
    assert len(coordinator.ds["nat"]) == 0


def test_nat_comment_converted_to_string():
    """NAT comment field is always converted to string."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/nat": [
                {
                    ".id": "*1",
                    "chain": "dstnat",
                    "action": "dst-nat",
                    "protocol": "tcp",
                    "dst-port": "22",
                    "to-addresses": "10.0.0.2",
                    "to-ports": "22",
                    "comment": 12345,
                    "disabled": False,
                }
            ]
        }
    )
    coordinator.nat_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_nat()
    assert coordinator.ds["nat"]["*1"]["comment"] == "12345"


# ---------------------------------------------------------------------------
# Group M: get_mangle() — mangle rule parsing
# ---------------------------------------------------------------------------


def test_mangle_basic_rule():
    """Basic mangle rule is parsed."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/mangle": [
                {
                    ".id": "*1",
                    "chain": "prerouting",
                    "action": "mark-routing",
                    "protocol": "tcp",
                    "dst-port": "443",
                    "comment": "HTTPS routing",
                    "disabled": False,
                }
            ]
        }
    )
    coordinator.mangle_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_mangle()
    assert "*1" in coordinator.ds["mangle"]
    assert coordinator.ds["mangle"]["*1"]["action"] == "mark-routing"


def test_mangle_skips_dynamic_and_jump():
    """Dynamic rules and 'jump' actions are excluded."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/mangle": [
                {
                    ".id": "*1",
                    "chain": "prerouting",
                    "action": "jump",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "prerouting",
                    "action": "mark-routing",
                    "dynamic": True,
                    "disabled": False,
                },
                {
                    ".id": "*3",
                    "chain": "prerouting",
                    "action": "mark-routing",
                    "protocol": "udp",
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.mangle_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_mangle()
    assert "*1" not in coordinator.ds["mangle"]
    assert "*2" not in coordinator.ds["mangle"]
    assert "*3" in coordinator.ds["mangle"]


def test_mangle_duplicate_removal():
    """Duplicate mangle rules are both removed."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/mangle": [
                {
                    ".id": "*1",
                    "chain": "prerouting",
                    "action": "mark-routing",
                    "protocol": "tcp",
                    "dst-port": "80",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "prerouting",
                    "action": "mark-routing",
                    "protocol": "tcp",
                    "dst-port": "80",
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.mangle_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_mangle()
    assert len(coordinator.ds["mangle"]) == 0


def test_mangle_interface_differentiates_rules():
    """Rules with same chain/action/protocol but different interfaces are not duplicates."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/mangle": [
                {
                    ".id": "*1",
                    "chain": "forward",
                    "action": "change MSS",
                    "protocol": "tcp",
                    "in-interface": "pppoe-out1",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "forward",
                    "action": "change MSS",
                    "protocol": "tcp",
                    "out-interface": "pppoe-out1",
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.mangle_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_mangle()
    assert len(coordinator.ds["mangle"]) == 2
    assert "*1" in coordinator.ds["mangle"]
    assert "*2" in coordinator.ds["mangle"]
    assert coordinator.ds["mangle"]["*1"]["in-interface"] == "pppoe-out1"
    assert coordinator.ds["mangle"]["*2"]["out-interface"] == "pppoe-out1"


# ---------------------------------------------------------------------------
# Group N: get_filter() — filter rule parsing
# ---------------------------------------------------------------------------


def test_filter_basic_rule():
    """Basic filter rule is parsed."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/filter": [
                {
                    ".id": "*1",
                    "chain": "forward",
                    "action": "drop",
                    "protocol": "tcp",
                    "dst-port": "445",
                    "comment": "Block SMB",
                    "disabled": False,
                }
            ]
        }
    )
    coordinator.filter_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_filter()
    assert "*1" in coordinator.ds["filter"]
    assert coordinator.ds["filter"]["*1"]["action"] == "drop"
    assert coordinator.ds["filter"]["*1"]["enabled"] is True


def test_filter_skips_dynamic_and_jump():
    """Dynamic rules and 'jump' actions are excluded from filter."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/filter": [
                {
                    ".id": "*1",
                    "chain": "forward",
                    "action": "jump",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "input",
                    "action": "accept",
                    "dynamic": True,
                    "disabled": False,
                },
                {
                    ".id": "*3",
                    "chain": "forward",
                    "action": "accept",
                    "protocol": "icmp",
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.filter_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_filter()
    assert "*1" not in coordinator.ds["filter"]
    assert "*2" not in coordinator.ds["filter"]
    assert "*3" in coordinator.ds["filter"]


def test_filter_duplicate_removal():
    """Duplicate filter rules are both removed."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/filter": [
                {
                    ".id": "*1",
                    "chain": "forward",
                    "action": "drop",
                    "protocol": "tcp",
                    "dst-port": "445",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "forward",
                    "action": "drop",
                    "protocol": "tcp",
                    "dst-port": "445",
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.filter_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_filter()
    assert len(coordinator.ds["filter"]) == 0


def test_filter_disabled_reversed_default_true():
    """Filter enabled defaults to True when disabled field is absent."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/filter": [
                {
                    ".id": "*1",
                    "chain": "forward",
                    "action": "accept",
                }
            ]
        }
    )
    coordinator.filter_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_filter()
    assert coordinator.ds["filter"]["*1"]["enabled"] is True


# ---------------------------------------------------------------------------
# Group O: get_interface() — interface discovery & traffic calculation
# ---------------------------------------------------------------------------


def test_interface_basic_parsing():
    """Basic interface entry is parsed with correct fields."""
    coordinator = make_coordinator(
        options={CONF_SENSOR_PORT_TRAFFIC: False},
        api_responses={
            "/interface": [
                {
                    "default-name": "ether1",
                    ".id": "*1",
                    "name": "ether1",
                    "type": "ether",
                    "running": True,
                    "disabled": False,
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "rx-byte": 1000,
                    "tx-byte": 2000,
                }
            ],
            "/interface/ethernet": [],
        },
    )
    coordinator.get_interface()
    assert "ether1" in coordinator.ds["interface"]
    iface = coordinator.ds["interface"]["ether1"]
    assert iface["type"] == "ether"
    assert iface["enabled"] is True
    assert iface["running"] is True
    assert iface["port-mac-address"] == "AA:BB:CC:DD:EE:01"


def test_interface_bridge_type_skipped():
    """Bridge-type interfaces are excluded."""
    coordinator = make_coordinator(
        options={CONF_SENSOR_PORT_TRAFFIC: False},
        api_responses={
            "/interface": [
                {
                    "default-name": "bridge1",
                    ".id": "*1",
                    "name": "bridge1",
                    "type": "bridge",
                    "disabled": False,
                    "mac-address": "AA:BB:CC:DD:EE:01",
                },
                {
                    "default-name": "ether1",
                    ".id": "*2",
                    "name": "ether1",
                    "type": "ether",
                    "disabled": False,
                    "mac-address": "AA:BB:CC:DD:EE:02",
                },
            ],
            "/interface/ethernet": [],
        },
    )
    coordinator.get_interface()
    assert "bridge1" not in coordinator.ds["interface"]
    assert "ether1" in coordinator.ds["interface"]


def test_interface_traffic_calculation():
    """Traffic delta is calculated per second when enabled."""
    coordinator = make_coordinator(
        options={CONF_SENSOR_PORT_TRAFFIC: True, CONF_SCAN_INTERVAL: 30},
        api_responses={
            "/interface": [
                {
                    "default-name": "ether1",
                    ".id": "*1",
                    "name": "ether1",
                    "type": "ether",
                    "disabled": False,
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "rx-byte": 6000,
                    "tx-byte": 9000,
                }
            ],
            "/interface/ethernet": [],
        },
    )
    # Seed previous values (must be non-zero; 0.0 is falsy and triggers first-run logic)
    coordinator.ds["interface"]["ether1"] = {
        "rx-previous": 3000.0,
        "tx-previous": 3000.0,
        "rx": 0.0,
        "tx": 0.0,
    }
    coordinator.get_interface()
    iface = coordinator.ds["interface"]["ether1"]
    # (6000 - 3000) / 30 = 100 bytes/s
    assert iface["rx"] == 100
    # (9000 - 3000) / 30 = 200 bytes/s
    assert iface["tx"] == 200
    assert iface["rx-total"] == 6000
    assert iface["tx-total"] == 9000


def test_interface_traffic_first_run_zero_delta():
    """First run with no previous values → delta is 0."""
    coordinator = make_coordinator(
        options={CONF_SENSOR_PORT_TRAFFIC: True, CONF_SCAN_INTERVAL: 30},
        api_responses={
            "/interface": [
                {
                    "default-name": "ether1",
                    ".id": "*1",
                    "name": "ether1",
                    "type": "ether",
                    "disabled": False,
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "rx-byte": 5000,
                    "tx-byte": 10000,
                }
            ],
            "/interface/ethernet": [],
        },
    )
    coordinator.get_interface()
    iface = coordinator.ds["interface"]["ether1"]
    # First run: previous is 0 → delta is current-0 but previous defaults to current
    # because `previous_tx = vals["tx-previous"] or current_tx`
    assert iface["rx"] == 0
    assert iface["tx"] == 0


def test_interface_virtual_interface_naming():
    """Virtual interface without default-name uses name as key via key_secondary."""
    coordinator = make_coordinator(
        options={CONF_SENSOR_PORT_TRAFFIC: False},
        api_responses={
            "/interface": [
                {
                    ".id": "*1",
                    "name": "vlan100",
                    "type": "vlan",
                    "disabled": False,
                    "mac-address": "AA:BB:CC:DD:EE:01",
                }
            ],
            "/interface/ethernet": [],
        },
    )
    coordinator.get_interface()
    assert "vlan100" in coordinator.ds["interface"]
    iface = coordinator.ds["interface"]["vlan100"]
    assert iface["default-name"] == "vlan100"
    assert "vlan100" in iface["port-mac-address"]


def test_interface_bonding_detected():
    """Bonding interfaces populate bonding and bonding_slaves dicts."""
    coordinator = make_coordinator(
        options={CONF_SENSOR_PORT_TRAFFIC: False},
        api_responses={
            "/interface": [
                {
                    "default-name": "ether1",
                    ".id": "*1",
                    "name": "ether1",
                    "type": "ether",
                    "disabled": False,
                    "mac-address": "AA:BB:CC:DD:EE:01",
                },
                {
                    ".id": "*2",
                    "name": "bond1",
                    "type": "bond",
                    "disabled": False,
                    "mac-address": "AA:BB:CC:DD:EE:02",
                },
            ],
            "/interface/ethernet": [],
            "/interface/bonding": [
                {
                    "name": "bond1",
                    "mac-address": "AA:BB:CC:DD:EE:02",
                    "slaves": "ether1,ether2",
                    "mode": "802.3ad",
                }
            ],
        },
    )
    coordinator.get_interface()
    assert "bond1" in coordinator.ds["bonding"]
    assert "ether1" in coordinator.ds["bonding_slaves"]
    assert "ether2" in coordinator.ds["bonding_slaves"]
    assert coordinator.ds["bonding_slaves"]["ether1"]["master"] == "bond1"


# ---------------------------------------------------------------------------
# Group P: get_dhcp() — DHCP lease parsing
# ---------------------------------------------------------------------------


def test_dhcp_basic_lease():
    """Basic DHCP lease is parsed correctly."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.100",
                    "host-name": "desktop-pc",
                    "status": "bound",
                    "server": "dhcp1",
                    "disabled": False,
                }
            ],
            "/ip/dhcp-server": [
                {"name": "dhcp1", "interface": "bridge1"},
            ],
        }
    )
    coordinator.get_dhcp()
    mac = "AA:BB:CC:DD:EE:01"
    assert mac in coordinator.ds["dhcp"]
    lease = coordinator.ds["dhcp"][mac]
    assert lease["address"] == "192.168.1.100"
    assert lease["host-name"] == "desktop-pc"
    assert lease["interface"] == "bridge1"


def test_dhcp_active_address_override():
    """Active address used when different from static address."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.100",
                    "active-address": "192.168.1.200",
                    "host-name": "pc",
                    "server": "dhcp1",
                    "disabled": False,
                }
            ],
            "/ip/dhcp-server": [
                {"name": "dhcp1", "interface": "bridge1"},
            ],
        }
    )
    coordinator.get_dhcp()
    assert coordinator.ds["dhcp"]["AA:BB:CC:DD:EE:01"]["address"] == "192.168.1.200"


def test_dhcp_invalid_ip_set_to_unknown():
    """Invalid IP address in lease → set to 'unknown'."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "not-an-ip",
                    "host-name": "pc",
                    "server": "dhcp1",
                    "disabled": False,
                }
            ],
            "/ip/dhcp-server": [
                {"name": "dhcp1", "interface": "bridge1"},
            ],
        }
    )
    coordinator.get_dhcp()
    assert coordinator.ds["dhcp"]["AA:BB:CC:DD:EE:01"]["address"] == "unknown"


def test_dhcp_active_mac_override():
    """Active MAC updates the mac-address field inside the existing entry."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "active-mac-address": "AA:BB:CC:DD:EE:02",
                    "address": "192.168.1.100",
                    "host-name": "pc",
                    "server": "dhcp1",
                    "disabled": False,
                }
            ],
            "/ip/dhcp-server": [
                {"name": "dhcp1", "interface": "bridge1"},
            ],
        }
    )
    coordinator.get_dhcp()
    # Dict key stays as original mac, but mac-address value is updated
    assert "AA:BB:CC:DD:EE:01" in coordinator.ds["dhcp"]
    assert coordinator.ds["dhcp"]["AA:BB:CC:DD:EE:01"]["mac-address"] == "AA:BB:CC:DD:EE:02"


def test_dhcp_interface_from_arp_fallback():
    """Interface resolved from ARP when DHCP server not found."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.100",
                    "host-name": "pc",
                    "server": "unknown-server",
                    "disabled": False,
                }
            ],
            "/ip/dhcp-server": [],
        }
    )
    coordinator.ds["arp"]["AA:BB:CC:DD:EE:01"] = {
        "interface": "ether1",
        "bridge": "unknown",
    }
    coordinator.get_dhcp()
    assert coordinator.ds["dhcp"]["AA:BB:CC:DD:EE:01"]["interface"] == "ether1"


def test_dhcp_interface_from_arp_bridge():
    """Interface resolved from ARP bridge when available."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.100",
                    "host-name": "pc",
                    "server": "unknown-server",
                    "disabled": False,
                }
            ],
            "/ip/dhcp-server": [],
        }
    )
    coordinator.ds["arp"]["AA:BB:CC:DD:EE:01"] = {
        "interface": "ether1",
        "bridge": "bridge1",
    }
    coordinator.get_dhcp()
    assert coordinator.ds["dhcp"]["AA:BB:CC:DD:EE:01"]["interface"] == "bridge1"


def test_dhcp_server_queried_on_demand():
    """DHCP server is queried only when server not in cache."""
    call_count = 0

    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.100",
                    "server": "dhcp1",
                    "disabled": False,
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:02",
                    "address": "192.168.1.101",
                    "server": "dhcp1",
                    "disabled": False,
                },
            ],
            "/ip/dhcp-server": [
                {"name": "dhcp1", "interface": "bridge1"},
            ],
        }
    )
    original_get_dhcp_server = coordinator.get_dhcp_server

    def counting_get_dhcp_server():
        nonlocal call_count
        call_count += 1
        original_get_dhcp_server()

    coordinator.get_dhcp_server = counting_get_dhcp_server
    coordinator.get_dhcp()
    # Should be called exactly once (first lease triggers it, second reuses cache)
    assert call_count == 1


def test_dhcp_comment_converted_to_string():
    """DHCP comment field is always converted to string."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.100",
                    "server": "dhcp1",
                    "comment": 42,
                    "disabled": False,
                }
            ],
            "/ip/dhcp-server": [
                {"name": "dhcp1", "interface": "bridge1"},
            ],
        }
    )
    coordinator.get_dhcp()
    assert coordinator.ds["dhcp"]["AA:BB:CC:DD:EE:01"]["comment"] == "42"


# ---------------------------------------------------------------------------
# Group Q: get_dhcp_network() — DHCP network / IPv4Network creation
# ---------------------------------------------------------------------------


def test_dhcp_network_creates_ipv4_network():
    """DHCP network creates IPv4Network object from CIDR address."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/network": [
                {
                    "address": "192.168.1.0/24",
                    "gateway": "192.168.1.1",
                }
            ]
        }
    )
    coordinator.get_dhcp_network()
    from ipaddress import IPv4Network

    net = coordinator.ds["dhcp-network"]["192.168.1.0/24"]
    assert isinstance(net["IPv4Network"], IPv4Network)
    assert str(net["IPv4Network"]) == "192.168.1.0/24"


# ---------------------------------------------------------------------------
# Group R: get_access() — user access rights
# ---------------------------------------------------------------------------


def test_access_rights_parsed():
    """Access rights are extracted from user group policy."""
    coordinator = make_coordinator(
        api_responses={
            "/user": [{"name": "admin", "group": "full"}],
            "/user/group": [{"name": "full", "policy": "write,policy,reboot,test,api"}],
        }
    )
    coordinator.host = "10.0.0.1"
    coordinator.accessrights_reported = False
    cfg = coordinator.config_entry
    cfg.data = {"username": "admin"}
    coordinator.get_access()
    assert "write" in coordinator.ds["access"]
    assert "policy" in coordinator.ds["access"]
    assert "reboot" in coordinator.ds["access"]


# ---------------------------------------------------------------------------
# Group S: get_bridge() — bridge host parsing
# ---------------------------------------------------------------------------


def test_bridge_host_parsed():
    """Bridge hosts are parsed and bridge dict populated."""
    coordinator = make_coordinator(
        api_responses={
            "/interface/bridge/host": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "interface": "ether1",
                    "bridge": "bridge1",
                    "disabled": False,
                    "local": False,
                },
            ],
        }
    )
    coordinator.get_bridge()
    assert "AA:BB:CC:DD:EE:01" in coordinator.ds["bridge_host"]
    host = coordinator.ds["bridge_host"]["AA:BB:CC:DD:EE:01"]
    assert host["interface"] == "ether1"
    assert host["bridge"] == "bridge1"
    assert host["enabled"] is True
    assert coordinator.ds["bridge"]["bridge1"] is True


def test_bridge_skips_local_entries():
    """Bridge host entries with local=True are excluded (only filter)."""
    coordinator = make_coordinator(
        api_responses={
            "/interface/bridge/host": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "interface": "ether1",
                    "bridge": "bridge1",
                    "disabled": False,
                    "local": True,
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:02",
                    "interface": "ether2",
                    "bridge": "bridge1",
                    "disabled": False,
                    "local": False,
                },
            ],
        }
    )
    coordinator.get_bridge()
    assert "AA:BB:CC:DD:EE:01" not in coordinator.ds["bridge_host"]
    assert "AA:BB:CC:DD:EE:02" in coordinator.ds["bridge_host"]


# ---------------------------------------------------------------------------
# Group T: get_arp() — ARP table parsing
# ---------------------------------------------------------------------------


def test_arp_basic_parsing():
    """ARP entries are parsed with mac-address as key."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/arp": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.10",
                    "interface": "ether1",
                },
            ],
        }
    )
    coordinator.get_arp()
    assert "AA:BB:CC:DD:EE:01" in coordinator.ds["arp"]
    entry = coordinator.ds["arp"]["AA:BB:CC:DD:EE:01"]
    assert entry["address"] == "192.168.1.10"
    assert entry["interface"] == "ether1"
    assert entry["bridge"] == ""


def test_arp_bridge_interface_resolution():
    """ARP entries on bridge interfaces get resolved to actual port."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/arp": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.10",
                    "interface": "bridge1",
                },
            ],
        }
    )
    coordinator.ds["bridge"] = {"bridge1": True}
    coordinator.ds["bridge_host"] = {"AA:BB:CC:DD:EE:01": {"interface": "ether2", "bridge": "bridge1"}}
    coordinator.get_arp()
    entry = coordinator.ds["arp"]["AA:BB:CC:DD:EE:01"]
    assert entry["bridge"] == "bridge1"
    assert entry["interface"] == "ether2"


def test_arp_dhcp_client_entries_removed():
    """ARP entries on DHCP client interfaces are removed."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/arp": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.10",
                    "interface": "ether1",
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:02",
                    "address": "10.0.0.2",
                    "interface": "ether1-wan",
                },
            ],
        }
    )
    coordinator.ds["dhcp-client"] = {
        "ether1-wan": {
            "interface": "ether1-wan",
            "status": "bound",
            "address": "10.0.0.2",
        }
    }
    coordinator.get_arp()
    assert "AA:BB:CC:DD:EE:01" in coordinator.ds["arp"]
    assert "AA:BB:CC:DD:EE:02" not in coordinator.ds["arp"]


# ---------------------------------------------------------------------------
# Group U: get_dns() — static DNS parsing
# ---------------------------------------------------------------------------


def test_dns_basic_parsing():
    """DNS static entries are parsed with name as key."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dns/static": [
                {
                    "name": "router.local",
                    "address": "192.168.1.1",
                    "comment": "Main router",
                },
            ],
        }
    )
    coordinator.get_dns()
    assert "router.local" in coordinator.ds["dns"]
    entry = coordinator.ds["dns"]["router.local"]
    assert entry["address"] == "192.168.1.1"
    assert entry["comment"] == "Main router"


def test_dns_none_comment_becomes_string():
    """DNS entries with None comment are converted to string 'None'."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dns/static": [
                {"name": "test.local", "address": "192.168.1.2", "comment": None},
            ],
        }
    )
    coordinator.get_dns()
    assert coordinator.ds["dns"]["test.local"]["comment"] == "None"


# ---------------------------------------------------------------------------
# Group V: get_queue() — simple queue parsing
# ---------------------------------------------------------------------------


def test_queue_basic_parsing():
    """Queue entries are parsed with rate splitting."""
    coordinator = make_coordinator(
        api_responses={
            "/queue/simple": [
                {
                    ".id": "*1",
                    "name": "queue1",
                    "target": "192.168.1.0/24",
                    "rate": "1000000/2000000",
                    "max-limit": "10000000/20000000",
                    "limit-at": "5000000/10000000",
                    "burst-limit": "15000000/25000000",
                    "burst-threshold": "8000000/16000000",
                    "burst-time": "10s/10s",
                    "packet-marks": "none",
                    "parent": "none",
                    "comment": "Test queue",
                    "disabled": False,
                },
            ],
        }
    )
    coordinator.get_queue()
    assert "queue1" in coordinator.ds["queue"]
    q = coordinator.ds["queue"]["queue1"]
    assert q["upload-max-limit"] == "10000000 bps"
    assert q["download-max-limit"] == "20000000 bps"
    assert q["upload-rate"] == "1000000 bps"
    assert q["download-rate"] == "2000000 bps"
    assert q["upload-limit-at"] == "5000000 bps"
    assert q["download-limit-at"] == "10000000 bps"
    assert q["upload-burst-limit"] == "15000000 bps"
    assert q["download-burst-limit"] == "25000000 bps"
    assert q["upload-burst-threshold"] == "8000000 bps"
    assert q["download-burst-threshold"] == "16000000 bps"
    assert q["upload-burst-time"] == "10s"
    assert q["download-burst-time"] == "10s"
    assert q["enabled"] is True


def test_queue_defaults_when_no_rates():
    """Queue entries use defaults for missing rate fields."""
    coordinator = make_coordinator(
        api_responses={
            "/queue/simple": [
                {
                    ".id": "*1",
                    "name": "default-queue",
                    "disabled": False,
                },
            ],
        }
    )
    coordinator.get_queue()
    q = coordinator.ds["queue"]["default-queue"]
    assert q["upload-max-limit"] == "0 bps"
    assert q["download-max-limit"] == "0 bps"
    assert q["upload-rate"] == "0 bps"
    assert q["download-rate"] == "0 bps"


# ---------------------------------------------------------------------------
# Group W: get_script() / get_environment() — script and env parsing
# ---------------------------------------------------------------------------


def test_script_basic_parsing():
    """Scripts are parsed with name as key."""
    coordinator = make_coordinator(
        api_responses={
            "/system/script": [
                {
                    "name": "backup",
                    "last-started": "mar/20/2026 10:00:00",
                    "run-count": "5",
                },
            ],
        }
    )
    coordinator.get_script()
    assert "backup" in coordinator.ds["script"]
    assert coordinator.ds["script"]["backup"]["run-count"] == "5"


def test_environment_basic_parsing():
    """Environment variables are parsed with name as key."""
    coordinator = make_coordinator(
        api_responses={
            "/system/script/environment": [
                {"name": "myVar", "value": "hello"},
                {"name": "count", "value": "42"},
            ],
        }
    )
    coordinator.get_environment()
    assert "myVar" in coordinator.ds["environment"]
    assert coordinator.ds["environment"]["myVar"]["value"] == "hello"
    assert coordinator.ds["environment"]["count"]["value"] == "42"


def test_environment_empty_value_coerced_to_none():
    """Empty / whitespace env values are coerced to None, real values kept.

    Empty-string is not a valid HA sensor state; coercing to None makes the
    entity read 'unknown' and lets _skip_environment_sensor drop value-less
    variables. See ISS-260608-env-sensor-empty-state.
    """
    coordinator = make_coordinator(
        api_responses={
            "/system/script/environment": [
                {"name": "defconfMode", "value": ""},
                {"name": "spaced", "value": "   "},
                {"name": "real", "value": "yes"},
            ],
        }
    )
    coordinator.get_environment()
    assert coordinator.ds["environment"]["defconfMode"]["value"] is None
    assert coordinator.ds["environment"]["spaced"]["value"] is None
    assert coordinator.ds["environment"]["real"]["value"] == "yes"


# ---------------------------------------------------------------------------
# Group X: get_kidcontrol() — kid control parsing
# ---------------------------------------------------------------------------


def test_kidcontrol_basic_parsing():
    """Kid control entries are parsed."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/kid-control": [
                {
                    "name": "child1",
                    "rate-limit": "1M/2M",
                    "mon": "08:00-20:00",
                    "comment": "Kid 1",
                    "blocked": False,
                    "disabled": False,
                },
            ],
        }
    )
    coordinator.get_kidcontrol()
    assert "child1" in coordinator.ds["kid-control"]
    kc = coordinator.ds["kid-control"]["child1"]
    assert kc["rate-limit"] == "1M/2M"
    assert kc["mon"] == "08:00-20:00"
    assert kc["enabled"] is True
    assert kc["comment"] == "Kid 1"


def test_kidcontrol_none_comment_becomes_string():
    """Kid control entries with None comment are converted to string."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/kid-control": [
                {
                    "name": "child1",
                    "rate-limit": "",
                    "comment": None,
                    "disabled": False,
                },
            ],
        }
    )
    coordinator.get_kidcontrol()
    assert coordinator.ds["kid-control"]["child1"]["comment"] == "None"


# ---------------------------------------------------------------------------
# Group Y: get_ppp() — PPP secret/active parsing
# ---------------------------------------------------------------------------


def test_ppp_connected_secret():
    """PPP secret with matching active entry shows as connected."""
    coordinator = make_coordinator(
        api_responses={
            "/ppp/secret": [
                {
                    "name": "vpn-user1",
                    "service": "l2tp",
                    "profile": "default",
                    "comment": "VPN user",
                    "disabled": False,
                },
            ],
            "/ppp/active": [
                {
                    "name": "vpn-user1",
                    "service": "l2tp",
                    "caller-id": "10.0.0.5",
                    "address": "192.168.1.100",
                    "encoding": "MPPE128",
                },
            ],
        }
    )
    coordinator.get_ppp()
    ppp = coordinator.ds["ppp_secret"]["vpn-user1"]
    assert ppp["connected"] is True
    assert ppp["caller-id"] == "10.0.0.5"
    assert ppp["address"] == "192.168.1.100"
    assert ppp["encoding"] == "MPPE128"


def test_ppp_disconnected_secret():
    """PPP secret without matching active entry shows as disconnected."""
    coordinator = make_coordinator(
        api_responses={
            "/ppp/secret": [
                {
                    "name": "vpn-user1",
                    "service": "l2tp",
                    "profile": "default",
                    "comment": "VPN user",
                    "disabled": False,
                },
            ],
            "/ppp/active": [],
        }
    )
    coordinator.get_ppp()
    ppp = coordinator.ds["ppp_secret"]["vpn-user1"]
    assert ppp["connected"] is False
    assert ppp["caller-id"] == "not connected"
    assert ppp["address"] == "not connected"


# ---------------------------------------------------------------------------
# Group Z: get_netwatch() — netwatch parsing
# ---------------------------------------------------------------------------


def test_netwatch_basic_parsing():
    """Netwatch entries are parsed with host as key."""
    coordinator = make_coordinator(
        api_responses={
            "/tool/netwatch": [
                {
                    "host": "8.8.8.8",
                    "type": "icmp",
                    "interval": "30s",
                    "port": "",
                    "http-codes": "",
                    "status": "up",
                    "comment": "Google DNS",
                    "disabled": False,
                },
            ],
        }
    )
    coordinator.get_netwatch()
    assert "8.8.8.8" in coordinator.ds["netwatch"]
    nw = coordinator.ds["netwatch"]["8.8.8.8"]
    assert nw["type"] == "icmp"
    assert nw["enabled"] is True


def test_netwatch_parses_name():
    """get_netwatch surfaces the netwatch name field, alongside its siblings (#70)."""
    coordinator = make_coordinator(
        api_responses={
            "/tool/netwatch": [
                {
                    "host": "1.1.1.1",
                    "name": "WAN uplink",
                    "type": "icmp",
                    "comment": "edge",
                    "disabled": False,
                },
            ],
        }
    )
    coordinator.get_netwatch()
    nw = coordinator.ds["netwatch"]["1.1.1.1"]
    assert nw["name"] == "WAN uplink"
    # the new vals entry must not disturb sibling parsing
    assert nw["comment"] == "edge"
    assert nw["enabled"] is True


def test_netwatch_name_defaults_empty_when_absent_or_empty():
    """Absent or present-empty name both resolve to '' (from_entry default), so
    custom_name falls back to comment/static rather than raising."""
    coordinator = make_coordinator(
        api_responses={
            "/tool/netwatch": [
                {"host": "1.1.1.1", "type": "icmp"},  # name absent (older ROS)
                {"host": "2.2.2.2", "name": "", "type": "icmp"},  # name present-empty
            ],
        }
    )
    coordinator.get_netwatch()
    assert coordinator.ds["netwatch"]["1.1.1.1"]["name"] == ""
    assert coordinator.ds["netwatch"]["2.2.2.2"]["name"] == ""


# ---------------------------------------------------------------------------
# Group AA: get_system_routerboard() — routerboard parsing
# ---------------------------------------------------------------------------


def test_routerboard_x86_board():
    """x86 boards skip routerboard query and set defaults."""
    coordinator = make_coordinator()
    coordinator.ds["resource"]["board-name"] = "x86"
    coordinator.get_system_routerboard()
    assert coordinator.ds["routerboard"]["routerboard"] is False
    assert coordinator.ds["routerboard"]["model"] == "x86"
    assert coordinator.ds["routerboard"]["serial-number"] == "N/A"


def test_routerboard_chr_board():
    """CHR boards skip routerboard query and set defaults."""
    coordinator = make_coordinator()
    coordinator.ds["resource"]["board-name"] = "CHR"
    coordinator.get_system_routerboard()
    assert coordinator.ds["routerboard"]["routerboard"] is False
    assert coordinator.ds["routerboard"]["model"] == "CHR"


def test_routerboard_real_hardware():
    """Real hardware queries /system/routerboard."""
    coordinator = make_coordinator(
        api_responses={
            "/system/routerboard": [
                {
                    "routerboard": True,
                    "model": "RB4011iGS+",
                    "serial-number": "ABC123",
                    "current-firmware": "7.10",
                    "upgrade-firmware": "7.11",
                },
            ],
        }
    )
    coordinator.ds["resource"]["board-name"] = "RB4011iGS+"
    coordinator.get_system_routerboard()
    rb = coordinator.ds["routerboard"]
    assert rb["routerboard"] is True
    assert rb["model"] == "RB4011iGS+"
    assert rb["serial-number"] == "ABC123"
    assert rb["current-firmware"] == "7.10"
    assert rb["upgrade-firmware"] == "7.11"


def test_routerboard_no_access_strips_firmware():
    """Without write+policy+reboot access, firmware fields are removed."""
    coordinator = make_coordinator(
        api_responses={
            "/system/routerboard": [
                {
                    "routerboard": True,
                    "model": "RB4011iGS+",
                    "serial-number": "ABC123",
                    "current-firmware": "7.10",
                    "upgrade-firmware": "7.11",
                },
            ],
        }
    )
    coordinator.ds["resource"]["board-name"] = "RB4011iGS+"
    coordinator.ds["access"] = ["read", "api"]  # no write/policy/reboot
    coordinator.get_system_routerboard()
    rb = coordinator.ds["routerboard"]
    assert "current-firmware" not in rb
    assert "upgrade-firmware" not in rb


# ---------------------------------------------------------------------------
# Group AB: get_system_health() — health data parsing
# ---------------------------------------------------------------------------


def test_health_v6_parsing():
    """RouterOS v6 health data is parsed as flat values."""
    coordinator = make_coordinator(
        major_fw_version=6,
        api_responses={
            "/system/health": [
                {"temperature": 45, "voltage": 24, "cpu-temperature": 55},
            ],
        },
    )
    coordinator.get_system_health()
    assert coordinator.ds["health"]["temperature"] == 45
    assert coordinator.ds["health"]["voltage"] == 24
    assert coordinator.ds["health"]["cpu-temperature"] == 55


def test_health_v7_parsing():
    """RouterOS v7 health data uses name/value pairs."""
    coordinator = make_coordinator(
        major_fw_version=7,
        api_responses={
            "/system/health": [
                {"name": "temperature", "value": "48"},
                {"name": "voltage", "value": "24.1"},
            ],
        },
    )
    coordinator.get_system_health()
    assert coordinator.ds["health"]["temperature"] == "48"
    assert coordinator.ds["health"]["voltage"] == "24.1"


def test_health_no_access_returns_early():
    """Without required access rights, health is not queried."""
    coordinator = make_coordinator(
        api_responses={
            "/system/health": [{"temperature": 45}],
        },
    )
    coordinator.ds["access"] = ["read", "api"]
    coordinator.get_system_health()
    assert coordinator.ds["health"] == {}


# ---------------------------------------------------------------------------
# Group AC: get_captive() — hotspot/captive portal parsing
# ---------------------------------------------------------------------------


def test_captive_basic_parsing():
    """Captive portal hosts are parsed and authorized count updated."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/hotspot/host": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "authorized": True,
                    "bypassed": False,
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:02",
                    "authorized": False,
                    "bypassed": True,
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:03",
                    "authorized": True,
                    "bypassed": False,
                },
            ],
        }
    )
    coordinator.ds["resource"]["captive_authorized"] = 0
    coordinator.get_captive()
    assert len(coordinator.ds["hostspot_host"]) == 3
    assert coordinator.ds["resource"]["captive_authorized"] == 2


# ---------------------------------------------------------------------------
# Group AD: get_dhcp_server() / get_dhcp_client() — DHCP server/client
# ---------------------------------------------------------------------------


def test_dhcp_server_parsing():
    """DHCP server entries are parsed with name as key."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server": [
                {"name": "defconf", "interface": "bridge1"},
            ],
        }
    )
    coordinator.get_dhcp_server()
    assert "defconf" in coordinator.ds["dhcp-server"]
    assert coordinator.ds["dhcp-server"]["defconf"]["interface"] == "bridge1"


def test_dhcp_server_enriched_fields():
    """DHCP server entries include address-pool, enabled, comment."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server": [
                {
                    "name": "defconf",
                    "interface": "bridge1",
                    "address-pool": "dhcp_pool0",
                    "disabled": False,
                    "comment": "LAN DHCP",
                },
            ],
        }
    )
    coordinator.get_dhcp_server()
    entry = coordinator.ds["dhcp-server"]["defconf"]
    assert entry["address-pool"] == "dhcp_pool0"
    assert entry["enabled"] is True
    assert entry["comment"] == "LAN DHCP"


def test_dhcp_server_enriched_defaults():
    """DHCP server enriched fields default when absent from API response."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server": [
                {"name": "defconf", "interface": "bridge1"},
            ],
        }
    )
    coordinator.get_dhcp_server()
    entry = coordinator.ds["dhcp-server"]["defconf"]
    assert entry["address-pool"] == "unknown"
    assert entry["comment"] == ""
    assert entry["lease-count"] == 0
    # When "disabled" is absent, from_entry_bool now correctly applies reverse
    # to the default (bug fix), so enabled=True → status="enabled"
    assert entry["enabled"] is True
    assert entry["status"] == "enabled"


def test_dhcp_server_status_enabled():
    """Enabled DHCP server has status 'enabled'."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server": [
                {"name": "defconf", "interface": "bridge1", "disabled": False},
            ],
        }
    )
    coordinator.get_dhcp_server()
    assert coordinator.ds["dhcp-server"]["defconf"]["status"] == "enabled"


def test_dhcp_server_status_disabled():
    """Disabled DHCP server has status 'disabled'."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server": [
                {"name": "defconf", "interface": "bridge1", "disabled": True},
            ],
        }
    )
    coordinator.get_dhcp_server()
    assert coordinator.ds["dhcp-server"]["defconf"]["status"] == "disabled"


def test_dhcp_server_lease_count():
    """Lease count is calculated from DHCP entries."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.10",
                    "host-name": "pc1",
                    "server": "defconf",
                    "status": "bound",
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:02",
                    "address": "192.168.1.11",
                    "host-name": "pc2",
                    "server": "defconf",
                    "status": "bound",
                },
                {
                    "mac-address": "AA:BB:CC:DD:EE:03",
                    "address": "192.168.2.10",
                    "host-name": "pc3",
                    "server": "guest",
                    "status": "bound",
                },
            ],
            "/ip/dhcp-server": [
                {"name": "defconf", "interface": "bridge1", "disabled": False},
                {"name": "guest", "interface": "bridge-guest", "disabled": False},
            ],
        }
    )
    coordinator.get_dhcp_server()
    coordinator.get_dhcp()
    assert coordinator.ds["dhcp-server"]["defconf"]["lease-count"] == 2
    assert coordinator.ds["dhcp-server"]["guest"]["lease-count"] == 1


def test_dhcp_server_lease_count_unknown_server_ignored():
    """Leases with unknown server don't crash the count."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-server/lease": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "address": "192.168.1.10",
                    "host-name": "pc1",
                    "server": "nonexistent",
                    "status": "bound",
                },
            ],
            "/ip/dhcp-server": [
                {"name": "defconf", "interface": "bridge1", "disabled": False},
            ],
        }
    )
    coordinator.get_dhcp_server()
    coordinator.get_dhcp()
    assert coordinator.ds["dhcp-server"]["defconf"]["lease-count"] == 0


def test_dhcp_client_parsing():
    """DHCP client entries are parsed with interface as key."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-client": [
                {"interface": "ether1", "status": "bound", "address": "10.0.0.5/24"},
            ],
        }
    )
    coordinator.get_dhcp_client()
    assert "ether1" in coordinator.ds["dhcp-client"]
    assert coordinator.ds["dhcp-client"]["ether1"]["status"] == "bound"


def test_dhcp_client_enriched_fields():
    """DHCP client entries include gateway, dns-server, dhcp-server, expires-after, comment."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-client": [
                {
                    "interface": "ether1",
                    "status": "bound",
                    "address": "10.0.0.5/24",
                    "gateway": "10.0.0.1",
                    "dns-server": "8.8.8.8",
                    "dhcp-server": "10.0.0.1",
                    "expires-after": "23:45:00",
                    "comment": "WAN",
                },
            ],
        }
    )
    coordinator.get_dhcp_client()
    entry = coordinator.ds["dhcp-client"]["ether1"]
    assert entry["gateway"] == "10.0.0.1"
    assert entry["dns-server"] == "8.8.8.8"
    assert entry["dhcp-server"] == "10.0.0.1"
    assert entry["expires-after"] == "23:45:00"
    assert entry["comment"] == "WAN"


def test_dhcp_client_enriched_defaults():
    """DHCP client enriched fields default when absent from API response."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/dhcp-client": [
                {"interface": "ether1", "status": "bound", "address": "10.0.0.5/24"},
            ],
        }
    )
    coordinator.get_dhcp_client()
    entry = coordinator.ds["dhcp-client"]["ether1"]
    assert entry["gateway"] == "unknown"
    assert entry["dns-server"] == "unknown"
    assert entry["dhcp-server"] == "unknown"
    assert entry["expires-after"] == "unknown"
    assert entry["comment"] == ""


# ---------------------------------------------------------------------------
# Group AE: get_capsman_hosts() — CAPS-MAN registration table
# ---------------------------------------------------------------------------


def test_capsman_hosts_v6():
    """CAPS-MAN hosts use /caps-man/ path for RouterOS < 7.13, with full metrics."""
    coordinator = make_coordinator(
        major_fw_version=6,
        api_responses={
            "/caps-man/registration-table": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "interface": "Slaapkamer",
                    "ssid": "MyWifi",
                    "rx-signal": "-76",
                    "tx-rate": "57.7Mbps-20MHz/1S/SGI",
                    "rx-rate": "57.7Mbps-20MHz/1S/SGI",
                    "uptime": "1h2m3s",
                    "bytes": "1234,5678",
                    "packets": "10,20",
                    "last-ip": "192.168.1.50",
                    "eap-identity": "",
                },
            ],
        },
    )
    coordinator.get_capsman_hosts()
    host_vals = coordinator.ds["capsman_hosts"]["AA:BB:CC:DD:EE:01"]
    assert host_vals["interface"] == "Slaapkamer"
    assert host_vals["ssid"] == "MyWifi"
    # rx-signal is renamed to signal-strength post-parse_api for cross-endpoint
    # consistency with /interface/wireless/registration-table.
    assert host_vals["signal-strength"] == "-76"
    assert "rx-signal" not in host_vals
    assert host_vals["tx-rate"] == "57.7Mbps-20MHz/1S/SGI"
    assert host_vals["rx-rate"] == "57.7Mbps-20MHz/1S/SGI"
    assert host_vals["uptime"] == "1h2m3s"
    assert host_vals["last-ip"] == "192.168.1.50"


def test_capsman_hosts_v7_13():
    """v7.13+ — primary /interface/wifi/ used when it returns data; legacy ignored."""
    coordinator = make_coordinator(major_fw_version=7)
    coordinator.minor_fw_version = 13
    coordinator.api = MockMikrotikAPI(
        responses={
            "/interface/wifi/registration-table": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "interface": "wifi1",
                    "ssid": "NewWifi",
                },
            ],
            # Legacy path also has data — must be ignored when primary returns rows.
            "/caps-man/registration-table": [
                {
                    "mac-address": "FF:FF:FF:FF:FF:FF",
                    "interface": "should-not-appear",
                    "ssid": "ignore-me",
                },
            ],
        }
    )
    coordinator.get_capsman_hosts()
    assert list(coordinator.ds["capsman_hosts"].keys()) == ["AA:BB:CC:DD:EE:01"]
    assert coordinator.ds["capsman_hosts"]["AA:BB:CC:DD:EE:01"]["interface"] == "wifi1"


def test_capsman_hosts_v7_13_fallback_to_caps_man():
    """v7.13+ — when /interface/wifi/ is empty (e.g. @fuecy on RouterOS 7.21.4
    still running legacy CAPsMAN), fall back to /caps-man/ and use that data.

    Validates ENH-260523-capsman-endpoint-fallback.
    """
    coordinator = make_coordinator(major_fw_version=7)
    coordinator.minor_fw_version = 21  # @fuecy is on 7.21.4
    coordinator.api = MockMikrotikAPI(
        responses={
            "/interface/wifi/registration-table": [],  # empty, as on @fuecy's router
            "/caps-man/registration-table": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "interface": "Slaapkamer",
                    "ssid": "MyWifi",
                    "rx-signal": "-76",
                    "tx-rate": "57.7Mbps",
                    "rx-rate": "57.7Mbps",
                },
            ],
        }
    )
    coordinator.get_capsman_hosts()
    host_vals = coordinator.ds["capsman_hosts"]["AA:BB:CC:DD:EE:01"]
    assert host_vals["interface"] == "Slaapkamer"
    # rx-signal → signal-strength rename must still fire on the fallback path.
    assert host_vals["signal-strength"] == "-76"
    assert "rx-signal" not in host_vals


def test_capsman_hosts_v7_13_both_endpoints_empty():
    """v7.13+ — both endpoints empty → empty capsman_hosts (no crash, no log spam)."""
    coordinator = make_coordinator(major_fw_version=7)
    coordinator.minor_fw_version = 13
    coordinator.api = MockMikrotikAPI(
        responses={
            "/interface/wifi/registration-table": [],
            "/caps-man/registration-table": [],
        }
    )
    coordinator.get_capsman_hosts()
    assert coordinator.ds["capsman_hosts"] == {}


def test_capsman_hosts_v6_does_not_probe_wifi_endpoint():
    """v6 / v7 ≤ 12 — wifi endpoint isn't in the probe list; only /caps-man/ is queried."""
    coordinator = make_coordinator(
        major_fw_version=6,
        api_responses={
            "/caps-man/registration-table": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "interface": "cap1",
                    "ssid": "MyWifi",
                },
            ],
            # /interface/wifi/registration-table intentionally absent — the
            # probe list for v6 doesn't include it, so it must not be queried.
        },
    )
    coordinator.get_capsman_hosts()
    assert "AA:BB:CC:DD:EE:01" in coordinator.ds["capsman_hosts"]


# ---------------------------------------------------------------------------
# Group AF: get_wireless() / get_wireless_hosts()
# ---------------------------------------------------------------------------


def test_wireless_basic_parsing():
    """Wireless interfaces are parsed."""
    coordinator = make_coordinator(major_fw_version=6)
    coordinator._wifimodule = "wireless"
    coordinator.api = MockMikrotikAPI(
        responses={
            "/interface/wireless": [
                {
                    "name": "wlan1",
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "ssid": "TestSSID",
                    "mode": "ap-bridge",
                    "running": True,
                    "disabled": False,
                    "master-interface": "",
                },
            ],
        }
    )
    coordinator.get_wireless()
    assert "wlan1" in coordinator.ds["wireless"]
    assert coordinator.ds["wireless"]["wlan1"]["ssid"] == "TestSSID"


def test_wireless_hosts_parsing():
    """Wireless registration table is parsed."""
    coordinator = make_coordinator(major_fw_version=6)
    coordinator._wifimodule = "wireless"
    coordinator.api = MockMikrotikAPI(
        responses={
            "/interface/wireless/registration-table": [
                {
                    "mac-address": "AA:BB:CC:DD:EE:01",
                    "interface": "wlan1",
                    "ap": False,
                    "uptime": "1h30m",
                    "signal-strength": "-65",
                    "tx-ccq": "90",
                    "tx-rate": "72.2Mbps",
                    "rx-rate": "72.2Mbps",
                },
            ],
        }
    )
    coordinator.get_wireless_hosts()
    assert "AA:BB:CC:DD:EE:01" in coordinator.ds["wireless_hosts"]
    wh = coordinator.ds["wireless_hosts"]["AA:BB:CC:DD:EE:01"]
    assert wh["interface"] == "wlan1"
    assert wh["ap"] is False


# ---------------------------------------------------------------------------
# Group AG: get_capabilities() — package detection
# ---------------------------------------------------------------------------


def test_capabilities_v6_wireless():
    """RouterOS v6 detects wireless package for capsman+wireless support."""
    coordinator = make_coordinator(
        major_fw_version=6,
        api_responses={
            "/system/package": [
                {"name": "wireless", "disabled": False},
                {"name": "ppp", "disabled": False},
            ],
        },
    )
    coordinator.support_ppp = False
    coordinator.support_capsman = False
    coordinator.support_wireless = False
    coordinator.support_ups = False
    coordinator.support_gps = False
    coordinator.host = "10.0.0.1"
    coordinator._wifimodule = "wireless"
    coordinator.get_capabilities()
    assert coordinator.support_ppp is True
    assert coordinator.support_capsman is True
    assert coordinator.support_wireless is True


def test_capabilities_v6_no_wireless():
    """RouterOS v6 without wireless package disables capsman+wireless."""
    coordinator = make_coordinator(
        major_fw_version=6,
        api_responses={
            "/system/package": [
                {"name": "ppp", "disabled": False},
            ],
        },
    )
    coordinator.support_ppp = False
    coordinator.support_capsman = False
    coordinator.support_wireless = False
    coordinator.support_ups = False
    coordinator.support_gps = False
    coordinator.host = "10.0.0.1"
    coordinator._wifimodule = "wireless"
    coordinator.get_capabilities()
    assert coordinator.support_capsman is False
    assert coordinator.support_wireless is False


def test_capabilities_v7_wifiwave2():
    """RouterOS v7 with wifiwave2 package uses wifiwave2 module."""
    coordinator = make_coordinator(
        major_fw_version=7,
        api_responses={
            "/system/package": [
                {"name": "wifiwave2", "disabled": False},
            ],
        },
    )
    coordinator.support_ppp = False
    coordinator.support_capsman = False
    coordinator.support_wireless = False
    coordinator.support_ups = False
    coordinator.support_gps = False
    coordinator.host = "10.0.0.1"
    coordinator._wifimodule = "wireless"
    coordinator.get_capabilities()
    assert coordinator.support_ppp is True
    assert coordinator.support_wireless is True
    assert coordinator.support_capsman is False
    assert coordinator._wifimodule == "wifiwave2"


def test_capabilities_ups_and_gps():
    """UPS and GPS packages are detected."""
    coordinator = make_coordinator(
        major_fw_version=6,
        api_responses={
            "/system/package": [
                {"name": "ups", "disabled": False},
                {"name": "gps", "disabled": False},
            ],
        },
    )
    coordinator.support_ppp = False
    coordinator.support_capsman = False
    coordinator.support_wireless = False
    coordinator.support_ups = False
    coordinator.support_gps = False
    coordinator.host = "10.0.0.1"
    coordinator._wifimodule = "wireless"
    coordinator.get_capabilities()
    assert coordinator.support_ups is True
    assert coordinator.support_gps is True


def test_capabilities_v0_unknown_skips_detection_and_logs(caplog):
    """FW version 0 (unknown): capability detection is skipped, not silently no-op'd."""
    coordinator = make_coordinator(major_fw_version=0)
    coordinator.support_ppp = False
    coordinator.support_capsman = False
    coordinator.support_wireless = False
    coordinator.support_ups = False
    coordinator.support_gps = False
    coordinator.host = "10.0.0.1"
    coordinator._wifimodule = "wireless"

    with caplog.at_level(logging.DEBUG):
        coordinator.get_capabilities()

    assert coordinator.support_capsman is False
    assert coordinator.support_wireless is False
    assert coordinator.support_ppp is False
    assert coordinator._wifimodule == "wireless"
    assert "skipping capability detection" in caplog.text


@pytest.mark.asyncio
async def test_client_traffic_v0_unknown_skips_and_logs(caplog):
    """FW version 0 (unknown): client traffic collection is skipped, not silently no-op'd."""
    coordinator = make_coordinator(
        major_fw_version=0,
        options={CONF_SENSOR_CLIENT_TRAFFIC: True},
    )
    coordinator.host = "10.0.0.1"
    coordinator.api = MagicMock()
    coordinator.api.connected.return_value = True
    coordinator.hass = MagicMock()
    coordinator.hass.async_add_executor_job = AsyncMock()

    with caplog.at_level(logging.DEBUG):
        await coordinator._async_update_client_traffic()

    coordinator.hass.async_add_executor_job.assert_not_called()
    assert "skipping client traffic collection" in caplog.text


# ---------------------------------------------------------------------------
# Group AG2: get_ups() — UPS path handling
# ---------------------------------------------------------------------------


def test_get_ups_no_configured_ups_does_not_query_monitor():
    """When /system/ups returns no entries, skip the monitor query.

    Reproduces issue #61: routers with the UPS package enabled but no UPS
    configured returned an empty list from /system/ups. The reverse-default
    on `enabled` then evaluated truthy, causing get_ups to issue a
    /system/ups monitor query that RouterOS rejects with "no such item",
    triggering a full coordinator disconnect ("Mikrotik Disconnected").
    """
    coordinator = make_coordinator(api_responses={"/system/ups": []})
    monitor_calls = []
    real_query = coordinator.api.query

    def tracking_query(path, command=None, args=None):
        if command == "monitor":
            monitor_calls.append((path, args))
        return real_query(path, command, args)

    coordinator.api.query = tracking_query
    coordinator.get_ups()

    assert monitor_calls == []
    assert coordinator.ds["ups"] == {}


def test_get_ups_configured_ups_runs_monitor_query():
    """When a UPS is present, monitor data is fetched and merged."""
    coordinator = make_coordinator(
        api_responses={
            "/system/ups": [
                {
                    ".id": "*0",
                    "name": "ups1",
                    "model": "Back-UPS",
                    "disabled": False,
                }
            ],
            ("/system/ups", "monitor"): [
                {
                    "on-line": True,
                    "battery-charge": 95,
                    "battery-voltage": 13.4,
                    "line-voltage": 230,
                    "load": 25,
                    "runtime-left": "1h30m",
                    "hid-self-test": "ok",
                }
            ],
        }
    )
    coordinator.get_ups()

    assert coordinator.ds["ups"]["enabled"] is True
    assert coordinator.ds["ups"]["battery-charge"] == 95
    assert coordinator.ds["ups"]["on-line"] is True


# ---------------------------------------------------------------------------
# Group AH: process_interface_client() — interface client mapping
# ---------------------------------------------------------------------------


def test_process_interface_client_single_arp():
    """Single ARP entry maps to interface client fields."""
    coordinator = make_coordinator(
        options={CONF_TRACK_IFACE_CLIENTS: True},
    )
    coordinator.ds["interface"] = {
        "ether1": {"name": "ether1", "client-ip-address": "", "client-mac-address": ""},
    }
    coordinator.ds["arp"] = {
        "AA:BB:CC:DD:EE:01": {
            "address": "192.168.1.10",
            "mac-address": "AA:BB:CC:DD:EE:01",
            "interface": "ether1",
        }
    }
    coordinator.process_interface_client()
    assert coordinator.ds["interface"]["ether1"]["client-ip-address"] == "192.168.1.10"
    assert coordinator.ds["interface"]["ether1"]["client-mac-address"] == "AA:BB:CC:DD:EE:01"


def test_process_interface_client_multiple_arp():
    """Multiple ARP entries on same interface show 'multiple'."""
    coordinator = make_coordinator(
        options={CONF_TRACK_IFACE_CLIENTS: True},
    )
    coordinator.ds["interface"] = {
        "ether1": {"name": "ether1", "client-ip-address": "", "client-mac-address": ""},
    }
    coordinator.ds["arp"] = {
        "AA:BB:CC:DD:EE:01": {
            "address": "192.168.1.10",
            "mac-address": "AA:BB:CC:DD:EE:01",
            "interface": "ether1",
        },
        "AA:BB:CC:DD:EE:02": {
            "address": "192.168.1.11",
            "mac-address": "AA:BB:CC:DD:EE:02",
            "interface": "ether1",
        },
    }
    coordinator.process_interface_client()
    assert coordinator.ds["interface"]["ether1"]["client-ip-address"] == "multiple"
    assert coordinator.ds["interface"]["ether1"]["client-mac-address"] == "multiple"


def test_process_interface_client_disabled():
    """When tracking disabled, client fields show 'disabled'."""
    coordinator = make_coordinator(
        options={CONF_TRACK_IFACE_CLIENTS: False},
    )
    coordinator.ds["interface"] = {
        "ether1": {"name": "ether1", "client-ip-address": "", "client-mac-address": ""},
    }
    coordinator.process_interface_client()
    assert coordinator.ds["interface"]["ether1"]["client-ip-address"] == "disabled"
    assert coordinator.ds["interface"]["ether1"]["client-mac-address"] == "disabled"


def test_process_interface_client_no_arp_uses_dhcp_client():
    """Interface with no ARP entries falls back to DHCP client address."""
    coordinator = make_coordinator(
        options={CONF_TRACK_IFACE_CLIENTS: True},
    )
    coordinator.ds["interface"] = {
        "ether1": {"name": "ether1", "client-ip-address": "", "client-mac-address": ""},
    }
    coordinator.ds["dhcp-client"] = {
        "ether1": {"address": "10.0.0.5/24"},
    }
    coordinator.process_interface_client()
    assert coordinator.ds["interface"]["ether1"]["client-ip-address"] == "10.0.0.5/24"


def test_process_interface_client_no_arp_no_dhcp():
    """Interface with no ARP and no DHCP client shows 'none'."""
    coordinator = make_coordinator(
        options={CONF_TRACK_IFACE_CLIENTS: True},
    )
    coordinator.ds["interface"] = {
        "ether1": {"name": "ether1", "client-ip-address": "", "client-mac-address": ""},
    }
    coordinator.process_interface_client()
    assert coordinator.ds["interface"]["ether1"]["client-ip-address"] == "none"
    assert coordinator.ds["interface"]["ether1"]["client-mac-address"] == "none"


# ---------------------------------------------------------------------------
# Group AI: process_accounting() — client traffic accounting
# ---------------------------------------------------------------------------


def test_accounting_disabled():
    """When accounting is disabled, client_traffic gets available=False."""
    coordinator = make_coordinator()
    coordinator.api._accounting_enabled = False
    coordinator.api._local_traffic_enabled = False
    coordinator.api._snapshot_time_diff = 0
    coordinator.ds["host"] = {
        "AA:BB:CC:DD:EE:01": {
            "address": "192.168.1.10",
            "mac-address": "AA:BB:CC:DD:EE:01",
            "host-name": "pc1",
        }
    }
    coordinator.process_accounting()
    ct = coordinator.ds["client_traffic"]["AA:BB:CC:DD:EE:01"]
    assert ct["available"] is False
    assert ct["local_accounting"] is False


def test_accounting_wan_traffic():
    """WAN traffic is calculated from accounting snapshot."""
    from ipaddress import IPv4Network

    coordinator = make_coordinator()
    coordinator.api._accounting_enabled = True
    coordinator.api._local_traffic_enabled = True
    coordinator.api._snapshot_time_diff = 30
    coordinator.api.responses["/ip/accounting/snapshot"] = [
        {
            ".id": "*1",
            "src-address": "192.168.1.10",
            "dst-address": "8.8.8.8",
            "bytes": "30000",
        },
    ]
    coordinator.api.responses["/ip/accounting"] = [{"threshold": 8192}]
    coordinator.ds["dhcp-network"] = {
        "192.168.1.0/24": {"IPv4Network": IPv4Network("192.168.1.0/24")},
    }
    coordinator.ds["client_traffic"] = {
        "AA:BB:CC:DD:EE:01": {
            "address": "192.168.1.10",
            "mac-address": "AA:BB:CC:DD:EE:01",
            "host-name": "pc1",
            "available": False,
            "local_accounting": False,
        }
    }
    coordinator.process_accounting()
    ct = coordinator.ds["client_traffic"]["AA:BB:CC:DD:EE:01"]
    assert ct["available"] is True
    assert ct["wan-tx"] == 1000  # 30000 / 30
    assert ct["wan-rx"] == 0.0


def test_accounting_lan_traffic():
    """LAN traffic between two local hosts is counted as lan-tx/lan-rx."""
    from ipaddress import IPv4Network

    coordinator = make_coordinator()
    coordinator.api._accounting_enabled = True
    coordinator.api._local_traffic_enabled = True
    coordinator.api._snapshot_time_diff = 10
    coordinator.api.responses["/ip/accounting/snapshot"] = [
        {
            ".id": "*1",
            "src-address": "192.168.1.10",
            "dst-address": "192.168.1.20",
            "bytes": "5000",
        },
    ]
    coordinator.api.responses["/ip/accounting"] = [{"threshold": 8192}]
    coordinator.ds["dhcp-network"] = {
        "192.168.1.0/24": {"IPv4Network": IPv4Network("192.168.1.0/24")},
    }
    coordinator.ds["client_traffic"] = {
        "AA:BB:CC:DD:EE:01": {
            "address": "192.168.1.10",
            "mac-address": "AA:BB:CC:DD:EE:01",
            "host-name": "pc1",
            "available": False,
            "local_accounting": False,
        },
        "AA:BB:CC:DD:EE:02": {
            "address": "192.168.1.20",
            "mac-address": "AA:BB:CC:DD:EE:02",
            "host-name": "pc2",
            "available": False,
            "local_accounting": False,
        },
    }
    coordinator.process_accounting()
    ct1 = coordinator.ds["client_traffic"]["AA:BB:CC:DD:EE:01"]
    ct2 = coordinator.ds["client_traffic"]["AA:BB:CC:DD:EE:02"]
    assert ct1["lan-tx"] == 500  # 5000 / 10
    assert ct2["lan-rx"] == 500


def test_accounting_no_snapshot():
    """When take_client_traffic_snapshot returns 0, throughput stays at 0."""
    coordinator = make_coordinator()
    coordinator.api._accounting_enabled = True
    coordinator.api._local_traffic_enabled = False
    coordinator.api._snapshot_time_diff = 0
    coordinator.ds["host"] = {
        "AA:BB:CC:DD:EE:01": {
            "address": "192.168.1.10",
            "mac-address": "AA:BB:CC:DD:EE:01",
            "host-name": "pc1",
        }
    }
    coordinator.process_accounting()
    ct = coordinator.ds["client_traffic"]["AA:BB:CC:DD:EE:01"]
    assert ct["available"] is True
    # With time_diff=0, the snapshot block is skipped so wan-tx/rx default to 0.0
    assert ct["wan-tx"] == 0.0
    assert ct["wan-rx"] == 0.0


def test_accounting_local_disabled_skips_lan():
    """When local_traffic is disabled, LAN fields are not set."""
    from ipaddress import IPv4Network

    coordinator = make_coordinator()
    coordinator.api._accounting_enabled = True
    coordinator.api._local_traffic_enabled = False
    coordinator.api._snapshot_time_diff = 10
    coordinator.api.responses["/ip/accounting/snapshot"] = [
        {
            ".id": "*1",
            "src-address": "192.168.1.10",
            "dst-address": "192.168.1.20",
            "bytes": "5000",
        },
    ]
    coordinator.api.responses["/ip/accounting"] = [{"threshold": 8192}]
    coordinator.ds["dhcp-network"] = {
        "192.168.1.0/24": {"IPv4Network": IPv4Network("192.168.1.0/24")},
    }
    coordinator.ds["client_traffic"] = {
        "AA:BB:CC:DD:EE:01": {
            "address": "192.168.1.10",
            "mac-address": "AA:BB:CC:DD:EE:01",
            "host-name": "pc1",
            "available": False,
            "local_accounting": False,
        },
        "AA:BB:CC:DD:EE:02": {
            "address": "192.168.1.20",
            "mac-address": "AA:BB:CC:DD:EE:02",
            "host-name": "pc2",
            "available": False,
            "local_accounting": False,
        },
    }
    coordinator.process_accounting()
    ct1 = coordinator.ds["client_traffic"]["AA:BB:CC:DD:EE:01"]
    assert ct1["local_accounting"] is False
    # LAN fields should not be set because local traffic is disabled
    assert "lan-tx" not in ct1


# ---------------------------------------------------------------------------
# Group AJ: _address_part_of_local_network / _get_accounting_uid_by_ip
# ---------------------------------------------------------------------------


def test_address_part_of_local_network():
    """Local network membership check works."""
    from ipaddress import IPv4Network

    coordinator = make_coordinator()
    coordinator.ds["dhcp-network"] = {
        "192.168.1.0/24": {"IPv4Network": IPv4Network("192.168.1.0/24")},
    }
    assert coordinator._address_part_of_local_network("192.168.1.10") is True
    assert coordinator._address_part_of_local_network("10.0.0.1") is False


def test_get_accounting_uid_by_ip():
    """Lookup MAC by IP in client_traffic."""
    coordinator = make_coordinator()
    coordinator.ds["client_traffic"] = {
        "AA:BB:CC:DD:EE:01": {"address": "192.168.1.10"},
    }
    assert coordinator._get_accounting_uid_by_ip("192.168.1.10") == "AA:BB:CC:DD:EE:01"
    assert coordinator._get_accounting_uid_by_ip("10.0.0.1") is None


# ---------------------------------------------------------------------------
# Group AK: _get_iface_from_entry()
# ---------------------------------------------------------------------------


def test_get_iface_from_entry():
    """Interface lookup by name returns the UID key."""
    coordinator = make_coordinator()
    coordinator.ds["interface"] = {
        "ether1": {"name": "LAN"},
        "ether2": {"name": "WAN"},
    }
    assert coordinator._get_iface_from_entry({"interface": "LAN"}) == "ether1"
    assert coordinator._get_iface_from_entry({"interface": "WAN"}) == "ether2"
    assert coordinator._get_iface_from_entry({"interface": "unknown"}) is None


# ---------------------------------------------------------------------------
# Extracted helper method tests
# ---------------------------------------------------------------------------


def test_merge_capsman_hosts_returns_detected():
    """_merge_capsman_hosts claims a new host with source=capsman, writes both
    interface and capsman-interface, and copies optional wireless metrics."""
    coordinator = make_coordinator_for_host()
    coordinator.support_capsman = True
    coordinator.ds["capsman_hosts"] = {
        "AA:BB:CC:DD:EE:01": {
            "mac-address": "AA:BB:CC:DD:EE:01",
            "interface": "Slaapkamer",
            "signal-strength": "-76",
            "tx-rate": "57.7Mbps",
            "rx-rate": "57.7Mbps",
        }
    }

    detected = coordinator._merge_capsman_hosts()

    assert "AA:BB:CC:DD:EE:01" in detected
    host = coordinator.ds["host"]["AA:BB:CC:DD:EE:01"]
    assert host["source"] == "capsman"
    assert host["available"] is True
    assert host["interface"] == "Slaapkamer"
    # ADR-011: capsman-interface is always written for capsman-claimed hosts,
    # so DHCP/ARP merges that later overlay the host do not lose the AP identity.
    assert host["capsman-interface"] == "Slaapkamer"
    assert host["signal-strength"] == "-76"
    assert host["tx-rate"] == "57.7Mbps"
    assert host["rx-rate"] == "57.7Mbps"


def test_merge_capsman_hosts_skips_when_not_supported():
    """_merge_capsman_hosts returns empty when CAPS-MAN not supported."""
    coordinator = make_coordinator_for_host()
    coordinator.support_capsman = False
    coordinator.ds["capsman_hosts"] = {"AA:BB:CC:DD:EE:01": {}}

    detected = coordinator._merge_capsman_hosts()
    assert detected == {}
    assert "AA:BB:CC:DD:EE:01" not in coordinator.ds["host"]


def test_merge_capsman_hosts_overlay_on_dhcp_host():
    """ADR-011 regression test: existing host with source=dhcp gets a
    capsman-interface overlay but its source/interface/availability are
    NOT changed. This is the bug #68 fix — when DHCP claims first
    (persistent leases), capsman previously skipped entirely, hiding the
    AP-virtual interface from device_tracker entities."""
    coordinator = make_coordinator_for_host()
    coordinator.support_capsman = True
    coordinator.ds["host"]["AA:BB:CC:DD:EE:01"] = {
        "source": "dhcp",
        "interface": "bridge",
        "available": True,
        "last-seen": "preserve-me",
    }
    coordinator.ds["capsman_hosts"] = {
        "AA:BB:CC:DD:EE:01": {
            "mac-address": "AA:BB:CC:DD:EE:01",
            "interface": "Slaapkamer",
            "signal-strength": "-76",
            "tx-rate": "57.7Mbps",
            "rx-rate": "57.7Mbps",
        }
    }

    detected = coordinator._merge_capsman_hosts()

    # Not capsman-detected because source is still dhcp — preserves the
    # existing "detected by capsman" set semantics used by _remove_undetected_hosts.
    assert "AA:BB:CC:DD:EE:01" not in detected

    host = coordinator.ds["host"]["AA:BB:CC:DD:EE:01"]
    # Source and primary interface are NOT changed.
    assert host["source"] == "dhcp"
    assert host["interface"] == "bridge"
    # last-seen is NOT touched (the dhcp source manages availability).
    assert host["last-seen"] == "preserve-me"
    # But the capsman-interface IS now recorded for automations.
    assert host["capsman-interface"] == "Slaapkamer"
    # Wireless metrics ARE overlaid (they don't conflict with dhcp-source data).
    assert host["signal-strength"] == "-76"
    assert host["tx-rate"] == "57.7Mbps"
    assert host["rx-rate"] == "57.7Mbps"


def test_merge_capsman_hosts_overlay_updates_availability_for_capsman_source():
    """When the existing host is itself capsman-sourced (not new this poll),
    the overlay path still updates available/last-seen, since capsman owns
    that host's availability."""
    coordinator = make_coordinator_for_host()
    coordinator.support_capsman = True
    coordinator.ds["host"]["AA:BB:CC:DD:EE:02"] = {
        "source": "capsman",
        "interface": "Slaapkamer",
        "available": False,
        "last-seen": "stale",
    }
    coordinator.ds["capsman_hosts"] = {
        "AA:BB:CC:DD:EE:02": {
            "mac-address": "AA:BB:CC:DD:EE:02",
            "interface": "Slaapkamer",
        }
    }

    detected = coordinator._merge_capsman_hosts()

    assert "AA:BB:CC:DD:EE:02" in detected
    host = coordinator.ds["host"]["AA:BB:CC:DD:EE:02"]
    assert host["available"] is True
    assert host["last-seen"] != "stale"
    assert host["capsman-interface"] == "Slaapkamer"


def test_merge_wireless_hosts_returns_detected():
    """_merge_wireless_hosts merges wireless entries and returns detected dict."""
    coordinator = make_coordinator_for_host()
    coordinator.support_wireless = True
    coordinator.ds["wireless_hosts"] = {
        "AA:BB:CC:DD:EE:02": {
            "mac-address": "AA:BB:CC:DD:EE:02",
            "interface": "wlan1",
            "ap": False,
            "signal-strength": "-50",
            "tx-ccq": "90",
            "tx-rate": "100M",
            "rx-rate": "100M",
        }
    }

    detected = coordinator._merge_wireless_hosts()

    assert "AA:BB:CC:DD:EE:02" in detected
    host = coordinator.ds["host"]["AA:BB:CC:DD:EE:02"]
    assert host["source"] == "wireless"
    assert host["signal-strength"] == "-50"


def test_merge_wireless_hosts_skips_ap():
    """_merge_wireless_hosts skips entries marked as AP."""
    coordinator = make_coordinator_for_host()
    coordinator.support_wireless = True
    coordinator.ds["wireless_hosts"] = {
        "AA:BB:CC:DD:EE:03": {
            "mac-address": "AA:BB:CC:DD:EE:03",
            "interface": "wlan1",
            "ap": True,
            "signal-strength": "-50",
            "tx-ccq": "90",
            "tx-rate": "100M",
            "rx-rate": "100M",
        }
    }

    detected = coordinator._merge_wireless_hosts()
    assert detected == {}
    assert "AA:BB:CC:DD:EE:03" not in coordinator.ds["host"]


def test_merge_dhcp_hosts():
    """_merge_dhcp_hosts adds DHCP-enabled hosts."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {
        "AA:BB:CC:DD:EE:04": {
            "enabled": True,
            "address": "192.168.1.20",
            "mac-address": "AA:BB:CC:DD:EE:04",
            "interface": "ether1",
        }
    }

    coordinator._merge_dhcp_hosts()

    host = coordinator.ds["host"]["AA:BB:CC:DD:EE:04"]
    assert host["source"] == "dhcp"
    assert host["address"] == "192.168.1.20"


def test_merge_dhcp_hosts_skips_disabled():
    """_merge_dhcp_hosts skips disabled DHCP entries."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {
        "AA:BB:CC:DD:EE:05": {
            "enabled": False,
            "address": "192.168.1.21",
            "mac-address": "AA:BB:CC:DD:EE:05",
            "interface": "ether1",
        }
    }

    coordinator._merge_dhcp_hosts()
    assert "AA:BB:CC:DD:EE:05" not in coordinator.ds["host"]


def test_merge_arp_hosts_returns_detected_excluding_unreachable():
    """_merge_arp_hosts returns detected set excluding failed/incomplete entries."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["arp"] = {
        "AA:BB:CC:DD:EE:06": {
            "address": "192.168.1.22",
            "mac-address": "AA:BB:CC:DD:EE:06",
            "interface": "ether1",
            "status": "",
        },
        "AA:BB:CC:DD:EE:07": {
            "address": "192.168.1.23",
            "mac-address": "AA:BB:CC:DD:EE:07",
            "interface": "ether1",
            "status": "failed",
        },
        "AA:BB:CC:DD:EE:08": {
            "address": "192.168.1.24",
            "mac-address": "AA:BB:CC:DD:EE:08",
            "interface": "ether1",
            "status": "incomplete",
        },
    }

    detected = coordinator._merge_arp_hosts()

    assert "AA:BB:CC:DD:EE:06" in detected
    assert "AA:BB:CC:DD:EE:07" not in detected
    assert "AA:BB:CC:DD:EE:08" not in detected
    # All still get added as hosts
    assert "AA:BB:CC:DD:EE:06" in coordinator.ds["host"]
    assert "AA:BB:CC:DD:EE:07" in coordinator.ds["host"]
    assert "AA:BB:CC:DD:EE:08" in coordinator.ds["host"]


def test_recover_hass_hosts_runs_once():
    """_recover_hass_hosts only runs on first call."""
    coordinator = make_coordinator_for_host()
    coordinator.host_hass_recovered = False
    coordinator.ds["host_hass"] = {"AA:BB:CC:DD:EE:08": "restored-pc"}

    coordinator._recover_hass_hosts()
    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:08"]["source"] == "restored"
    assert coordinator.host_hass_recovered is True

    # Second call should not re-add
    coordinator.ds["host"] = {}
    coordinator._recover_hass_hosts()
    assert "AA:BB:CC:DD:EE:08" not in coordinator.ds["host"]


def test_ensure_host_defaults():
    """_ensure_host_defaults fills missing keys with defaults."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {"AA:BB:CC:DD:EE:09": {"source": "arp"}}

    coordinator._ensure_host_defaults()

    host = coordinator.ds["host"]["AA:BB:CC:DD:EE:09"]
    assert host["address"] == "unknown"
    assert host["host-name"] == "unknown"
    assert host["manufacturer"] == "detect"
    assert host["available"] is False
    assert host["last-seen"] is False


def test_update_host_availability_capsman_not_detected():
    """Capsman host not in detected set becomes unavailable."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {"AA:BB:CC:DD:EE:10": {"source": "capsman", "available": True}}

    coordinator._update_host_availability(
        "AA:BB:CC:DD:EE:10",
        coordinator.ds["host"]["AA:BB:CC:DD:EE:10"],
        capsman_detected={},
        wireless_detected={},
        arp_detected={},
        bridge_detected={},
    )

    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:10"]["available"] is False


def test_update_host_availability_wired_arp_detected():
    """Wired host in arp_detected set becomes available."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {"AA:BB:CC:DD:EE:11": {"source": "arp", "available": False, "last-seen": False}}

    coordinator._update_host_availability(
        "AA:BB:CC:DD:EE:11",
        coordinator.ds["host"]["AA:BB:CC:DD:EE:11"],
        capsman_detected={},
        wireless_detected={},
        arp_detected={"AA:BB:CC:DD:EE:11": True},
        bridge_detected={},
    )

    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:11"]["available"] is True
    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:11"]["last-seen"] is not False


def test_update_host_address_from_dhcp():
    """DHCP address update changes host address and source."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {
        "mac1": {
            "source": "arp",
            "address": "192.168.1.1",
            "interface": "ether1",
        }
    }
    coordinator.ds["dhcp"] = {
        "mac1": {
            "enabled": True,
            "address": "192.168.1.100",
            "interface": "ether2",
        }
    }

    coordinator._update_host_address("mac1", coordinator.ds["host"]["mac1"])

    assert coordinator.ds["host"]["mac1"]["address"] == "192.168.1.100"
    assert coordinator.ds["host"]["mac1"]["source"] == "dhcp"
    assert coordinator.ds["host"]["mac1"]["interface"] == "ether2"


def test_update_host_address_preserves_wireless_source():
    """Wireless hosts keep their source even when DHCP has a different address."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {
        "mac1": {
            "source": "wireless",
            "address": "192.168.1.1",
            "interface": "wlan1",
        }
    }
    coordinator.ds["dhcp"] = {
        "mac1": {
            "enabled": True,
            "address": "192.168.1.100",
            "interface": "ether2",
        }
    }

    coordinator._update_host_address("mac1", coordinator.ds["host"]["mac1"])

    assert coordinator.ds["host"]["mac1"]["address"] == "192.168.1.100"
    assert coordinator.ds["host"]["mac1"]["source"] == "wireless"


def test_resolve_hostname_from_dns():
    """Hostname resolved from DNS comment."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {
        "mac1": {
            "host-name": "unknown",
            "address": "192.168.1.10",
        }
    }
    coordinator.ds["dns"] = {
        "entry1": {
            "address": "192.168.1.10",
            "comment": "MyPC#ignored",
            "name": "mypc.local",
        }
    }

    coordinator._resolve_hostname("mac1", coordinator.ds["host"]["mac1"])
    assert coordinator.ds["host"]["mac1"]["host-name"] == "MyPC"


def test_resolve_hostname_from_dns_name():
    """Hostname resolved from DNS name when comment is empty."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {"mac1": {"host-name": "unknown", "address": "192.168.1.10"}}
    coordinator.ds["dns"] = {
        "entry1": {
            "address": "192.168.1.10",
            "comment": "",
            "name": "workstation.local",
        }
    }
    coordinator.ds["dhcp"] = {}

    coordinator._resolve_hostname("mac1", coordinator.ds["host"]["mac1"])
    assert coordinator.ds["host"]["mac1"]["host-name"] == "workstation"


def test_resolve_hostname_from_dhcp_comment():
    """Hostname resolved from DHCP comment when DNS has no match."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {"mac1": {"host-name": "unknown", "address": "unknown"}}
    coordinator.ds["dns"] = {}
    coordinator.ds["dhcp"] = {
        "mac1": {
            "enabled": True,
            "comment": "LaptopName#extra",
            "host-name": "other",
        }
    }

    coordinator._resolve_hostname("mac1", coordinator.ds["host"]["mac1"])
    assert coordinator.ds["host"]["mac1"]["host-name"] == "LaptopName"


def test_resolve_hostname_from_dhcp_hostname():
    """Hostname resolved from DHCP host-name when comment is empty."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {"mac1": {"host-name": "unknown", "address": "unknown"}}
    coordinator.ds["dns"] = {}
    coordinator.ds["dhcp"] = {
        "mac1": {
            "enabled": True,
            "comment": "",
            "host-name": "dhcp-hostname",
        }
    }

    coordinator._resolve_hostname("mac1", coordinator.ds["host"]["mac1"])
    assert coordinator.ds["host"]["mac1"]["host-name"] == "dhcp-hostname"


def test_resolve_hostname_fallback_to_mac():
    """Hostname falls back to MAC address when no other source available."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {"AA:BB:CC:DD:EE:FF": {"host-name": "unknown", "address": "unknown"}}
    coordinator.ds["dns"] = {}
    coordinator.ds["dhcp"] = {}

    coordinator._resolve_hostname("AA:BB:CC:DD:EE:FF", coordinator.ds["host"]["AA:BB:CC:DD:EE:FF"])
    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:FF"]["host-name"] == "AA:BB:CC:DD:EE:FF"


def test_resolve_hostname_skips_when_already_known():
    """_resolve_hostname does nothing when hostname is already set."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["host"] = {"mac1": {"host-name": "already-known", "address": "192.168.1.10"}}
    coordinator.ds["dns"] = {}

    coordinator._resolve_hostname("mac1", coordinator.ds["host"]["mac1"])
    assert coordinator.ds["host"]["mac1"]["host-name"] == "already-known"


def test_dhcp_comment_for_host_returns_comment():
    """_dhcp_comment_for_host returns comment before '#'."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {"mac1": {"enabled": True, "comment": "MyDevice#tag"}}
    assert coordinator._dhcp_comment_for_host("mac1") == "MyDevice"


def test_dhcp_comment_for_host_returns_none_for_empty():
    """_dhcp_comment_for_host returns None when comment is empty."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {"mac1": {"enabled": True, "comment": ""}}
    assert coordinator._dhcp_comment_for_host("mac1") is None


def test_dhcp_comment_for_host_returns_none_when_disabled():
    """_dhcp_comment_for_host returns None when DHCP lease is disabled."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {"mac1": {"enabled": False, "comment": "MyDevice"}}
    assert coordinator._dhcp_comment_for_host("mac1") is None


def test_dhcp_comment_for_host_returns_none_when_missing():
    """_dhcp_comment_for_host returns None when host not in DHCP."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {}
    assert coordinator._dhcp_comment_for_host("mac1") is None


def test_update_captive_portal_adds_data():
    """_update_captive_portal copies hotspot data to host."""
    coordinator = make_coordinator_for_host()
    coordinator.config_entry.options["sensor_client_captive"] = True
    coordinator.ds["host"] = {"mac1": {}}
    coordinator.ds["hostspot_host"] = {"mac1": {"authorized": True, "bypassed": False}}

    coordinator._update_captive_portal("mac1")

    assert coordinator.ds["host"]["mac1"]["authorized"] is True
    assert coordinator.ds["host"]["mac1"]["bypassed"] is False


def test_update_captive_portal_removes_stale_data():
    """_update_captive_portal removes authorized/bypassed when host leaves hotspot."""
    coordinator = make_coordinator_for_host()
    coordinator.config_entry.options["sensor_client_captive"] = True
    coordinator.ds["host"] = {"mac1": {"authorized": True, "bypassed": False}}
    coordinator.ds["hostspot_host"] = {}

    coordinator._update_captive_portal("mac1")

    assert "authorized" not in coordinator.ds["host"]["mac1"]
    assert "bypassed" not in coordinator.ds["host"]["mac1"]


def test_update_captive_portal_noop_when_disabled():
    """_update_captive_portal does nothing when option is disabled."""
    coordinator = make_coordinator_for_host()
    # option defaults to False
    coordinator.ds["host"] = {"mac1": {}}
    coordinator.ds["hostspot_host"] = {"mac1": {"authorized": True, "bypassed": False}}

    coordinator._update_captive_portal("mac1")

    assert "authorized" not in coordinator.ds["host"]["mac1"]


def test_init_accounting_hosts():
    """_init_accounting_hosts creates client_traffic entries for new hosts."""
    coordinator = make_coordinator()
    coordinator.ds["host"] = {
        "mac1": {
            "address": "192.168.1.1",
            "mac-address": "mac1",
            "host-name": "pc1",
        }
    }
    coordinator.ds["client_traffic"] = {}

    coordinator._init_accounting_hosts()

    assert "mac1" in coordinator.ds["client_traffic"]
    ct = coordinator.ds["client_traffic"]["mac1"]
    assert ct["address"] == "192.168.1.1"
    assert ct["available"] is False


def test_init_accounting_hosts_skips_existing():
    """_init_accounting_hosts does not overwrite existing entries."""
    coordinator = make_coordinator()
    coordinator.ds["host"] = {
        "mac1": {
            "address": "192.168.1.1",
            "mac-address": "mac1",
            "host-name": "pc1",
        }
    }
    coordinator.ds["client_traffic"] = {"mac1": {"address": "192.168.1.1", "available": True}}

    coordinator._init_accounting_hosts()
    assert coordinator.ds["client_traffic"]["mac1"]["available"] is True


def test_classify_accounting_traffic_wan():
    """_classify_accounting_traffic classifies WAN TX/RX correctly."""
    coordinator = make_coordinator()
    coordinator.ds["dhcp-network"] = {"net1": {"IPv4Network": __import__("ipaddress").IPv4Network("192.168.1.0/24")}}

    tmp = {"192.168.1.10": {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0}}
    accounting_data = {
        "1": {
            "src-address": "192.168.1.10",
            "dst-address": "8.8.8.8",
            "bytes": "1000",
        },
        "2": {
            "src-address": "1.1.1.1",
            "dst-address": "192.168.1.10",
            "bytes": "2000",
        },
    }

    coordinator._classify_accounting_traffic(accounting_data, tmp)

    assert tmp["192.168.1.10"]["wan-tx"] == 1000
    assert tmp["192.168.1.10"]["wan-rx"] == 2000
    assert tmp["192.168.1.10"]["lan-tx"] == 0
    assert tmp["192.168.1.10"]["lan-rx"] == 0


def test_classify_accounting_traffic_lan():
    """_classify_accounting_traffic classifies LAN TX/RX correctly."""
    coordinator = make_coordinator()
    coordinator.ds["dhcp-network"] = {"net1": {"IPv4Network": __import__("ipaddress").IPv4Network("192.168.1.0/24")}}

    tmp = {
        "192.168.1.10": {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0},
        "192.168.1.20": {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0},
    }
    accounting_data = {
        "1": {
            "src-address": "192.168.1.10",
            "dst-address": "192.168.1.20",
            "bytes": "500",
        }
    }

    coordinator._classify_accounting_traffic(accounting_data, tmp)

    assert tmp["192.168.1.10"]["lan-tx"] == 500
    assert tmp["192.168.1.20"]["lan-rx"] == 500


# ---------------------------------------------------------------------------
# _hostname_from_dns / _hostname_from_dhcp tests
# ---------------------------------------------------------------------------


def test_hostname_from_dns_returns_comment():
    """DNS comment takes priority for hostname."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dns"] = {"e1": {"address": "10.0.0.1", "comment": "MyPC#tag", "name": "mypc.local"}}
    assert coordinator._hostname_from_dns("mac1", "10.0.0.1") == "MyPC"


def test_hostname_from_dns_falls_back_to_name():
    """DNS name (before first dot) used when comment is empty and no DHCP comment."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dns"] = {"e1": {"address": "10.0.0.1", "comment": "", "name": "server.lan"}}
    coordinator.ds["dhcp"] = {}
    assert coordinator._hostname_from_dns("mac1", "10.0.0.1") == "server"


def test_hostname_from_dns_no_match():
    """Returns None when no DNS entry matches the address."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dns"] = {"e1": {"address": "10.0.0.99", "comment": "Other", "name": "other.lan"}}
    assert coordinator._hostname_from_dns("mac1", "10.0.0.1") is None


def test_hostname_from_dhcp_returns_comment():
    """DHCP comment used when available."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {"mac1": {"enabled": True, "comment": "Laptop#x", "host-name": "other"}}
    assert coordinator._hostname_from_dhcp("mac1") == "Laptop"


def test_hostname_from_dhcp_returns_hostname():
    """DHCP host-name used when comment is empty."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {"mac1": {"enabled": True, "comment": "", "host-name": "dhcp-name"}}
    assert coordinator._hostname_from_dhcp("mac1") == "dhcp-name"


def test_hostname_from_dhcp_falls_back_to_uid():
    """MAC address returned when no DHCP data available."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["dhcp"] = {}
    assert coordinator._hostname_from_dhcp("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"


# ---------------------------------------------------------------------------
# _add_traffic_bytes tests
# ---------------------------------------------------------------------------


def test_add_traffic_bytes_lan():
    """LAN traffic increments both lan-tx and lan-rx."""
    tmp = {
        "10.0.0.1": {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0},
        "10.0.0.2": {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0},
    }
    MikrotikCoordinator._add_traffic_bytes(tmp, "10.0.0.1", "10.0.0.2", 100, src_local=True, dst_local=True)
    assert tmp["10.0.0.1"]["lan-tx"] == 100
    assert tmp["10.0.0.2"]["lan-rx"] == 100


def test_add_traffic_bytes_wan_tx():
    """WAN TX when source is local and destination is external."""
    tmp = {"10.0.0.1": {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0}}
    MikrotikCoordinator._add_traffic_bytes(tmp, "10.0.0.1", "8.8.8.8", 200, src_local=True, dst_local=False)
    assert tmp["10.0.0.1"]["wan-tx"] == 200


def test_add_traffic_bytes_wan_rx():
    """WAN RX when source is external and destination is local."""
    tmp = {"10.0.0.1": {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0}}
    MikrotikCoordinator._add_traffic_bytes(tmp, "8.8.8.8", "10.0.0.1", 300, src_local=False, dst_local=True)
    assert tmp["10.0.0.1"]["wan-rx"] == 300


def test_add_traffic_bytes_external_to_external():
    """External-to-external traffic is ignored."""
    tmp = {"10.0.0.1": {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0}}
    MikrotikCoordinator._add_traffic_bytes(tmp, "8.8.8.8", "1.1.1.1", 400, src_local=False, dst_local=False)
    assert tmp["10.0.0.1"]["wan-tx"] == 0
    assert tmp["10.0.0.1"]["wan-rx"] == 0


# ---------------------------------------------------------------------------
# Group: get_raw() — firewall RAW rule parsing
# ---------------------------------------------------------------------------


def test_raw_basic_rule():
    """Basic RAW rule is parsed correctly."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/raw": [
                {
                    ".id": "*1",
                    "chain": "prerouting",
                    "action": "drop",
                    "protocol": "tcp",
                    "dst-port": "445",
                    "comment": "Block SMB",
                    "disabled": False,
                }
            ]
        }
    )
    coordinator.raw_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_raw()
    assert "*1" in coordinator.ds["raw"]
    rule = coordinator.ds["raw"]["*1"]
    assert rule["action"] == "drop"
    assert rule["protocol"] == "tcp"
    assert rule["enabled"] is True
    assert rule["name"] == "drop,tcp:445"


def test_raw_skips_dynamic_and_jump():
    """Dynamic rules and jump actions are filtered out."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/raw": [
                {
                    ".id": "*1",
                    "chain": "prerouting",
                    "action": "drop",
                    "protocol": "tcp",
                    "dst-port": "445",
                    "comment": "Keep",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "prerouting",
                    "action": "jump",
                    "protocol": "any",
                    "comment": "Jump rule",
                    "disabled": False,
                },
                {
                    ".id": "*3",
                    "chain": "prerouting",
                    "action": "accept",
                    "dynamic": True,
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.raw_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_raw()
    assert "*1" in coordinator.ds["raw"]
    assert "*2" not in coordinator.ds["raw"]
    assert "*3" not in coordinator.ds["raw"]


def test_raw_duplicate_removal():
    """Duplicate RAW rules (same uniq-id) are both removed."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/raw": [
                {
                    ".id": "*1",
                    "chain": "prerouting",
                    "action": "drop",
                    "protocol": "tcp",
                    "dst-port": "445",
                    "comment": "Rule A",
                    "disabled": False,
                },
                {
                    ".id": "*2",
                    "chain": "prerouting",
                    "action": "drop",
                    "protocol": "tcp",
                    "dst-port": "445",
                    "comment": "Rule B",
                    "disabled": False,
                },
            ]
        }
    )
    coordinator.raw_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_raw()
    assert len(coordinator.ds["raw"]) == 0


def test_raw_comment_converted_to_string():
    """RAW comment field is always converted to string."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/firewall/raw": [
                {
                    ".id": "*1",
                    "chain": "prerouting",
                    "action": "drop",
                    "protocol": "udp",
                    "dst-port": "53",
                    "comment": 99999,
                    "disabled": False,
                }
            ]
        }
    )
    coordinator.raw_removed = {}
    coordinator.host = "10.0.0.1"
    coordinator.get_raw()
    assert coordinator.ds["raw"]["*1"]["comment"] == "99999"


# ---------------------------------------------------------------------------
# Group: get_container() — container monitoring
# ---------------------------------------------------------------------------


def test_container_basic():
    """Container entry is parsed correctly."""
    coordinator = make_coordinator(
        api_responses={
            "/container": [
                {
                    ".id": "*1",
                    "name": "pihole",
                    "tag": "pihole/pihole:latest",
                    "os": "linux",
                    "arch": "arm64",
                    "interface": "veth-pihole",
                    "status": "running",
                }
            ]
        }
    )
    coordinator.get_container()
    assert "*1" in coordinator.ds["container"]
    c = coordinator.ds["container"]["*1"]
    assert c["name"] == "pihole"
    assert c["tag"] == "pihole/pihole:latest"
    assert c["status"] == "running"


def test_container_running_derived():
    """running field is True when status is 'running', False otherwise."""
    coordinator = make_coordinator(
        api_responses={
            "/container": [
                {".id": "*1", "name": "running-ct", "status": "running"},
                {".id": "*2", "name": "stopped-ct", "status": "stopped"},
                {".id": "*3", "name": "error-ct", "status": "error"},
            ]
        }
    )
    coordinator.get_container()
    assert coordinator.ds["container"]["*1"]["running"] is True
    assert coordinator.ds["container"]["*2"]["running"] is False
    assert coordinator.ds["container"]["*3"]["running"] is False


def test_container_defaults():
    """Container fields default when absent from API response."""
    coordinator = make_coordinator(
        api_responses={
            "/container": [
                {".id": "*1"},
            ]
        }
    )
    coordinator.get_container()
    c = coordinator.ds["container"]["*1"]
    assert c["name"] == "unknown"
    assert c["status"] == "stopped"
    assert c["running"] is False
    assert c["comment"] == ""


# =====================================================================
# _is_wireless_host — bridge/interface-based wireless detection
# =====================================================================


def test_is_wireless_host_source_wireless():
    """Host with source 'wireless' is always wireless."""
    coordinator = make_coordinator_for_host()
    vals = {"source": "wireless", "interface": "ether1"}
    assert coordinator._is_wireless_host("AA:BB:CC:DD:EE:01", vals) is True


def test_is_wireless_host_source_capsman():
    """Host with source 'capsman' is always wireless."""
    coordinator = make_coordinator_for_host()
    vals = {"source": "capsman", "interface": "ether1"}
    assert coordinator._is_wireless_host("AA:BB:CC:DD:EE:01", vals) is True


def test_is_wireless_host_direct_interface():
    """ARP host on a wireless interface is detected as wireless."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["wireless"] = {"wlan1": {"name": "wlan1"}}
    vals = {"source": "arp", "interface": "wlan1"}
    assert coordinator._is_wireless_host("AA:BB:CC:DD:EE:01", vals) is True


def test_is_wireless_host_bridge_lookup():
    """ARP host on a bridge is detected as wireless via bridge host table."""
    mac = "AA:BB:CC:DD:EE:01"
    coordinator = make_coordinator_for_host()
    coordinator.ds["wireless"] = {"wlan1": {"name": "wlan1"}}
    coordinator.ds["bridge_host"] = {mac: {"interface": "wlan1", "bridge": "bridge1", "enabled": True}}
    vals = {"source": "arp", "interface": "bridge1"}
    assert coordinator._is_wireless_host(mac, vals) is True


def test_is_wireless_host_wired():
    """ARP host on a wired interface is not wireless."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["wireless"] = {"wlan1": {"name": "wlan1"}}
    coordinator.ds["bridge_host"] = {}
    vals = {"source": "arp", "interface": "ether1"}
    assert coordinator._is_wireless_host("AA:BB:CC:DD:EE:01", vals) is False


def test_is_wireless_host_no_wireless_interfaces():
    """Host is not wireless when no wireless interfaces exist."""
    coordinator = make_coordinator_for_host()
    coordinator.ds["wireless"] = {}
    vals = {"source": "arp", "interface": "ether1"}
    assert coordinator._is_wireless_host("AA:BB:CC:DD:EE:01", vals) is False


@pytest.mark.asyncio
async def test_hapac2_wireless_count_via_bridge():
    """hAP ac2 scenario: empty registration table, clients detected via bridge.

    When the WiFi package registration table returns no entries (hAP ac2),
    clients discovered via ARP/DHCP should still be counted as wireless
    if the bridge host table shows them on a wireless interface.
    """
    mac_wifi = "AA:BB:CC:DD:EE:W1"
    mac_wired = "AA:BB:CC:DD:EE:E1"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac_wifi: {
                "mac-address": mac_wifi,
                "address": "192.168.1.10",
                "interface": "bridge1",
            },
            mac_wired: {
                "mac-address": mac_wired,
                "address": "192.168.1.11",
                "interface": "bridge1",
            },
        }
    )
    # WiFi interfaces exist but registration table is empty (hAP ac2 issue)
    coordinator.support_wireless = True
    coordinator.ds["wireless_hosts"] = {}
    coordinator.ds["wireless"] = {
        "wlan1": {"name": "wlan1"},
        "wlan2": {"name": "wlan2"},
    }
    coordinator.ds["bridge_host"] = {
        mac_wifi: {"interface": "wlan1", "bridge": "bridge1", "enabled": True},
        mac_wired: {"interface": "ether2", "bridge": "bridge1", "enabled": True},
    }

    await coordinator.async_process_host()

    assert coordinator.ds["resource"]["clients_wireless"] == 1
    assert coordinator.ds["resource"]["clients_wired"] == 1


# =====================================================================
# _merge_bridge_hosts — bridged AP host detection
# =====================================================================


@pytest.mark.asyncio
async def test_bridge_host_creates_host_entry():
    """Bridge host table entry creates a host when no other source exists."""
    mac = "AA:BB:CC:DD:EE:B1"
    coordinator = make_coordinator_for_host()
    coordinator.ds["bridge_host"] = {
        mac: {"interface": "wlan1", "bridge": "bridge1", "enabled": True},
    }

    await coordinator.async_process_host()

    assert mac in coordinator.ds["host"]
    host = coordinator.ds["host"][mac]
    assert host["source"] == "bridge"
    assert host["available"] is True
    assert host["interface"] == "wlan1"


@pytest.mark.asyncio
async def test_bridge_host_does_not_overwrite_arp_source():
    """Bridge merge does not overwrite hosts already discovered via ARP."""
    mac = "AA:BB:CC:DD:EE:B2"
    coordinator = make_coordinator_for_host(
        arp_entries={
            mac: {
                "mac-address": mac,
                "address": "192.168.1.50",
                "interface": "bridge1",
            }
        }
    )
    coordinator.ds["bridge_host"] = {
        mac: {"interface": "wlan1", "bridge": "bridge1", "enabled": True},
    }

    await coordinator.async_process_host()

    host = coordinator.ds["host"][mac]
    assert host["source"] == "arp"
    assert host["address"] == "192.168.1.50"


@pytest.mark.asyncio
async def test_bridge_host_unavailable_when_removed():
    """Bridge host becomes unavailable when it disappears from the bridge table."""
    mac = "AA:BB:CC:DD:EE:B3"
    coordinator = make_coordinator_for_host(
        host_entries={
            mac: {
                "source": "bridge",
                "mac-address": mac,
                "address": "unknown",
                "interface": "wlan1",
                "available": True,
                "last-seen": False,
                "host-name": "unknown",
                "manufacturer": "",
            }
        }
    )
    # Bridge host table is now empty — device disconnected
    coordinator.ds["bridge_host"] = {}

    await coordinator.async_process_host()

    assert coordinator.ds["host"][mac]["available"] is False


@pytest.mark.asyncio
async def test_bridged_ap_wireless_count():
    """Bridged AP scenario: all clients from bridge table, counted correctly.

    Simulates a hAP ac2 with no ARP, no DHCP, no registration table.
    All clients discovered solely via bridge host table.
    """
    mac_wifi1 = "AA:BB:CC:DD:EE:W1"
    mac_wifi2 = "AA:BB:CC:DD:EE:W2"
    mac_wired = "AA:BB:CC:DD:EE:E1"
    coordinator = make_coordinator_for_host()
    coordinator.support_wireless = True
    coordinator.ds["wireless"] = {
        "wlan1": {"name": "wlan1"},
        "wlan2": {"name": "wlan2"},
    }
    coordinator.ds["bridge_host"] = {
        mac_wifi1: {"interface": "wlan1", "bridge": "bridge1", "enabled": True},
        mac_wifi2: {"interface": "wlan2", "bridge": "bridge1", "enabled": True},
        mac_wired: {"interface": "ether2", "bridge": "bridge1", "enabled": True},
    }

    await coordinator.async_process_host()

    assert coordinator.ds["resource"]["clients_wireless"] == 2
    assert coordinator.ds["resource"]["clients_wired"] == 1


# ---------------------------------------------------------------------------
# _check_new_uids — new device discovery dispatcher guard
# ---------------------------------------------------------------------------


def test_check_new_uids_first_run_seeds_but_skips():
    """First run seeds tracking but returns empty (no dispatcher on initial load)."""
    coordinator = make_coordinator()
    coordinator.ds["interface"] = {"ether1": {"name": "ether1"}}
    assert coordinator._check_new_uids() == []
    # Tracking is now seeded
    assert "interface" in coordinator._known_uids


def test_check_new_uids_no_change_returns_empty():
    """No new UIDs returns empty list."""
    coordinator = make_coordinator()
    coordinator.ds["interface"] = {"ether1": {"name": "ether1"}}
    coordinator._check_new_uids()  # seed
    assert coordinator._check_new_uids() == []


def test_check_new_uids_new_uid_returns_path():
    """Adding a new UID returns the changed data path."""
    coordinator = make_coordinator()
    coordinator.ds["interface"] = {"ether1": {"name": "ether1"}}
    coordinator._check_new_uids()  # seed

    coordinator.ds["interface"]["ether2"] = {"name": "ether2"}
    result = coordinator._check_new_uids()
    assert "interface" in result


def test_check_new_uids_removed_uid_returns_empty():
    """Removing a UID does not trigger (only new UIDs matter)."""
    coordinator = make_coordinator()
    coordinator.ds["interface"] = {"ether1": {}, "ether2": {}}
    coordinator._check_new_uids()  # seed

    del coordinator.ds["interface"]["ether2"]
    assert coordinator._check_new_uids() == []


def test_check_new_uids_skips_non_dict_paths():
    """Non-dict ds paths (like access list) are skipped."""
    coordinator = make_coordinator()
    coordinator.ds["access"] = ["write", "policy"]  # list, not dict
    coordinator.ds["interface"] = {"ether1": {}}
    coordinator._check_new_uids()  # seed
    assert coordinator._check_new_uids() == []


def test_check_new_uids_new_host_triggers():
    """New host appearing in ds triggers dispatcher."""
    coordinator = make_coordinator()
    coordinator.ds["host"] = {"mac1": {"host-name": "phone"}}
    coordinator._check_new_uids()  # seed

    coordinator.ds["host"]["mac2"] = {"host-name": "laptop"}
    result = coordinator._check_new_uids()
    assert "host" in result


@pytest.mark.asyncio
async def test_async_process_host_sets_is_wireless():
    """async_process_host sets is_wireless field on each host."""
    coordinator = make_coordinator_for_host(
        host_entries={
            "AA:BB:CC:DD:EE:01": {
                "source": "wireless",
                "address": "192.168.1.10",
                "mac-address": "AA:BB:CC:DD:EE:01",
                "interface": "wlan1",
                "host-name": "phone",
                "last-seen": False,
                "available": True,
                "manufacturer": "",
                "is_wireless": False,
            },
            "AA:BB:CC:DD:EE:02": {
                "source": "arp",
                "address": "192.168.1.11",
                "mac-address": "AA:BB:CC:DD:EE:02",
                "interface": "ether1",
                "host-name": "desktop",
                "last-seen": False,
                "available": True,
                "manufacturer": "",
                "is_wireless": False,
            },
        }
    )

    await coordinator.async_process_host()

    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:01"]["is_wireless"] is True
    assert coordinator.ds["host"]["AA:BB:CC:DD:EE:02"]["is_wireless"] is False


# ---------------------------------------------------------------------------
# Group: RouterOS v7 capability detection (_detect_capabilities_v7)
#   Regression coverage for #68 — a 7.13+ router still running the legacy
#   `wireless` package must keep CAPsMAN and the /interface/wireless stack.
# ---------------------------------------------------------------------------


def _make_v7_coordinator(minor):
    coordinator = make_coordinator(major_fw_version=7)
    coordinator.minor_fw_version = minor
    coordinator.host = "10.0.0.1"
    coordinator.support_capsman = False
    coordinator.support_wireless = False
    coordinator.support_ppp = False
    coordinator._wifimodule = "wireless"
    return coordinator


def _pkg(*enabled):
    return {name: {"enabled": True} for name in enabled}


def test_v7_legacy_wireless_package_on_modern_fw_keeps_capsman():
    """7.21 with the legacy `wireless` package: CAPsMAN on, legacy endpoints."""
    coordinator = _make_v7_coordinator(21)

    coordinator._detect_capabilities_v7(_pkg("wireless"))

    assert coordinator.support_capsman is True
    assert coordinator._wifimodule == "wireless"
    # Pins the #68 regression: the old else-branch line
    # `support_wireless = bool(minor_fw_version < 13)` lowered this to False
    # for 7.13+ legacy boxes. _make_v7_coordinator seeds it False, so True
    # here proves the override is gone — do not re-introduce one.
    assert coordinator.support_wireless is True


def test_v7_wifi_qcom_package_disables_capsman():
    coordinator = _make_v7_coordinator(13)

    coordinator._detect_capabilities_v7(_pkg("wifi-qcom"))

    assert coordinator.support_capsman is False
    assert coordinator._wifimodule == "wifi"


def test_v7_wifi_qcom_ac_package_disables_capsman():
    coordinator = _make_v7_coordinator(13)

    coordinator._detect_capabilities_v7(_pkg("wifi-qcom-ac"))

    assert coordinator.support_capsman is False
    assert coordinator._wifimodule == "wifi"


def test_v7_wifiwave2_package_uses_wifiwave2_module():
    coordinator = _make_v7_coordinator(13)

    coordinator._detect_capabilities_v7(_pkg("wifiwave2"))

    assert coordinator.support_capsman is False
    assert coordinator._wifimodule == "wifiwave2"


def test_v7_modern_fw_without_packages_assumes_builtin_wifi():
    """7.13+ with no wireless package signals the built-in wifi driver."""
    coordinator = _make_v7_coordinator(13)

    coordinator._detect_capabilities_v7({})

    assert coordinator.support_capsman is False
    assert coordinator._wifimodule == "wifi"


def test_v7_older_fw_without_packages_uses_legacy_wireless():
    coordinator = _make_v7_coordinator(5)

    coordinator._detect_capabilities_v7({})

    assert coordinator.support_capsman is True
    assert coordinator._wifimodule == "wireless"


def test_v7_wifi_package_wins_over_legacy_wireless():
    """A migrating box with both packages prefers the modern wifi stack."""
    coordinator = _make_v7_coordinator(15)

    coordinator._detect_capabilities_v7(_pkg("wireless", "wifi-qcom"))

    assert coordinator.support_capsman is False
    assert coordinator._wifimodule == "wifi"


def test_has_wifi_package_legacy_wireless_overrides_version_heuristic():
    coordinator = _make_v7_coordinator(21)

    assert coordinator._has_wifi_package(_pkg("wireless")) is False


def test_has_wifi_package_modern_fw_without_packages_is_true():
    coordinator = _make_v7_coordinator(21)

    assert coordinator._has_wifi_package({}) is True


def test_has_wifi_package_explicit_wifi_package_is_true():
    coordinator = _make_v7_coordinator(5)

    assert coordinator._has_wifi_package(_pkg("wifi")) is True


def test_has_wifi_package_disabled_wireless_falls_back_to_version():
    coordinator = _make_v7_coordinator(21)

    assert coordinator._has_wifi_package({"wireless": {"enabled": False}}) is True


# ---------------------------------------------------------------------------
# Group: _parse_fw_version_from_resource() — read-side FW version (#82)
#   Read-only users never reach get_firmware_update() (write+policy+reboot
#   gated), so major_fw_version must also be parseable from the read-only
#   /system/resource.version. Without it, get_capabilities() never dispatches
#   and wireless/CAPsMAN/PPP data stays empty.
# ---------------------------------------------------------------------------


def _resource_coordinator(version, major_fw_version=0):
    coordinator = make_coordinator(major_fw_version=major_fw_version)
    coordinator.host = "10.0.0.1"
    if version is not None:
        coordinator.ds["resource"]["version"] = version
    return coordinator


def test_parse_fw_version_from_resource_reads_major_minor():
    """A real /system/resource.version string yields major+minor."""
    coordinator = _resource_coordinator("7.22.3 (stable)")

    coordinator._parse_fw_version_from_resource()

    assert coordinator.major_fw_version == 7
    assert coordinator.minor_fw_version == 22


def test_parse_fw_version_from_resource_no_minor_defaults_zero():
    """A bare major version parses with minor defaulting to 0."""
    coordinator = _resource_coordinator("7")

    coordinator._parse_fw_version_from_resource()

    assert coordinator.major_fw_version == 7
    assert coordinator.minor_fw_version == 0


def test_parse_fw_version_from_resource_self_skips_when_already_set():
    """get_firmware_update() runs first for privileged users; do not re-parse."""
    coordinator = _resource_coordinator("6.49.10", major_fw_version=7)
    coordinator.minor_fw_version = 13

    coordinator._parse_fw_version_from_resource()

    # Authoritative privileged parse is preserved, not overwritten.
    assert coordinator.major_fw_version == 7
    assert coordinator.minor_fw_version == 13


def test_parse_fw_version_from_resource_unknown_version_is_noop():
    """The parse_api 'unknown' sentinel must not be parsed as a version."""
    coordinator = _resource_coordinator("unknown")

    coordinator._parse_fw_version_from_resource()

    assert coordinator.major_fw_version == 0


def test_parse_fw_version_from_resource_missing_version_is_noop():
    """No version key (resource not yet populated) leaves the sentinel intact."""
    coordinator = _resource_coordinator(None)

    coordinator._parse_fw_version_from_resource()

    assert coordinator.major_fw_version == 0


def test_parse_fw_version_from_resource_malformed_is_noop():
    """A non-numeric version is swallowed without raising or setting a value."""
    coordinator = _resource_coordinator("garbage")

    coordinator._parse_fw_version_from_resource()

    assert coordinator.major_fw_version == 0


def test_readonly_capability_cascade_unblocked_end_to_end():
    """#82: read-side version parse lets get_capabilities() dispatch on a
    wifi-qcom router under a user without write/policy/reboot — the helper
    runs at the tail of get_system_resource(), before get_capabilities()."""
    coordinator = make_coordinator(
        major_fw_version=0,
        api_responses={
            "/system/package": [
                {"name": "wifi-qcom", "disabled": False},
            ],
        },
    )
    coordinator.ds["access"] = ["read", "api", "sensitive"]
    coordinator.ds["resource"]["version"] = "7.22.3 (stable)"
    coordinator.host = "10.0.0.1"
    coordinator.support_ppp = False
    coordinator.support_capsman = False
    coordinator.support_wireless = False
    coordinator.support_ups = False
    coordinator.support_gps = False
    coordinator._wifimodule = "wireless"

    # Order mirrors _async_update_hwinfo: resource parse, then capabilities.
    coordinator._parse_fw_version_from_resource()
    coordinator.get_capabilities()

    assert coordinator.major_fw_version == 7
    assert coordinator.support_wireless is True
    assert coordinator._wifimodule == "wifi"
    assert coordinator.support_capsman is False


# ---------------------------------------------------------------------------
# Group: PoE-out energy accumulation (ADR-017 / ENH-260509)
# ---------------------------------------------------------------------------


def _poe_coordinator(interface=None, neighbor=None, scan_interval=30):
    """Coordinator wired for the PoE energy helpers (real methods, no __init__)."""
    coordinator = make_coordinator(options={CONF_SCAN_INTERVAL: scan_interval})
    coordinator._poe_energy_last_power = {}
    coordinator.ds["interface"] = interface or {}
    coordinator.ds["neighbor"] = neighbor or {}
    return coordinator


def test_poe_energy_step_first_sample_returns_zero():
    """The first sample of a port has no previous power, so it integrates 0."""
    coordinator = _poe_coordinator()
    assert coordinator._poe_energy_step("ether1", 10.0) == 0.0
    assert coordinator._poe_energy_last_power["ether1"] == 10.0


def test_poe_energy_step_trapezoid():
    """Second sample integrates the trapezoid over one scan interval."""
    coordinator = _poe_coordinator(scan_interval=30)
    coordinator._poe_energy_last_power["ether1"] = 10.0
    # (10 + 20) / 2 * 30 / 3600 = 15 * 30 / 3600 = 0.125 Wh
    assert coordinator._poe_energy_step("ether1", 20.0) == pytest.approx(0.125)
    assert coordinator._poe_energy_last_power["ether1"] == 20.0


def test_poe_energy_step_none_clears_state():
    """A None power (port unplugged/disabled) integrates 0 and forgets the prev sample."""
    coordinator = _poe_coordinator()
    coordinator._poe_energy_last_power["ether1"] = 10.0
    assert coordinator._poe_energy_step("ether1", None) == 0.0
    assert "ether1" not in coordinator._poe_energy_last_power


def test_resolve_poe_power_prefers_measured():
    """A real poe-out-power reading is used directly (source=measured)."""
    coordinator = _poe_coordinator()
    iface = {"poe-out-power": 12.1, "poe-out-status": "powered-on", "default-name": "ether1"}
    assert coordinator._resolve_poe_power(iface) == (12.1, "measured", None)


def test_resolve_poe_power_estimates_from_single_neighbor():
    """No metering but a powered port with one known neighbour -> nameplate estimate."""
    coordinator = _poe_coordinator(neighbor={"ether1": ["RBD52G-5HacD2HnD"]})
    iface = {"poe-out-power": None, "poe-out-status": "powered-on", "default-name": "ether1"}
    assert coordinator._resolve_poe_power(iface) == (16.0, "estimated", "RBD52G-5HacD2HnD")


def test_resolve_poe_power_no_estimate_for_ambiguous_multi_neighbor():
    """A port with more than one neighbour cannot be attributed (null-not-guess)."""
    coordinator = _poe_coordinator(neighbor={"ether2": ["RB4011iGS+5HacQ2HnD", "CRS310-8G+2S+"]})
    iface = {"poe-out-power": None, "poe-out-status": "powered-on", "default-name": "ether2"}
    assert coordinator._resolve_poe_power(iface) == (None, None, None)


def test_resolve_poe_power_no_estimate_for_unknown_board():
    """A single neighbour whose board is not in the nameplate table yields no estimate."""
    coordinator = _poe_coordinator(neighbor={"ether1": ["RB-SOME-UNKNOWN-BOARD"]})
    iface = {"poe-out-power": None, "poe-out-status": "powered-on", "default-name": "ether1"}
    assert coordinator._resolve_poe_power(iface) == (None, None, None)


def test_resolve_poe_power_no_estimate_when_not_powered():
    """Estimate only while the port is actually delivering power."""
    coordinator = _poe_coordinator(neighbor={"ether1": ["RBD52G-5HacD2HnD"]})
    iface = {"poe-out-power": None, "poe-out-status": "waiting-for-load", "default-name": "ether1"}
    assert coordinator._resolve_poe_power(iface) == (None, None, None)


def test_accumulate_poe_energy_device_total_sums_ports():
    """Device-total delta equals the sum of the per-port increments (no double-count)."""
    interface = {
        "ether1": {"type": "ether", "poe-out-power": 10.0, "poe-out-status": "powered-on", "default-name": "ether1"},
        "ether2": {"type": "ether", "poe-out-power": 20.0, "poe-out-status": "powered-on", "default-name": "ether2"},
    }
    coordinator = _poe_coordinator(interface=interface, scan_interval=30)
    # Seed previous samples so this poll integrates a non-zero trapezoid.
    coordinator._poe_energy_last_power = {"ether1": 10.0, "ether2": 20.0}
    coordinator._accumulate_poe_energy()
    d1 = interface["ether1"]["poe-out-energy-delta-wh"]
    d2 = interface["ether2"]["poe-out-energy-delta-wh"]
    assert d1 == pytest.approx(10.0 * 30 / 3600)
    assert d2 == pytest.approx(20.0 * 30 / 3600)
    assert coordinator.ds["resource"]["poe-out-energy-delta-wh"] == pytest.approx(d1 + d2)
    assert interface["ether1"]["poe-out-energy-source"] == "measured"


def test_accumulate_poe_energy_total_none_when_no_source():
    """A PoE-enabled router with no attributable PoE-out load leaves the total uncreated."""
    interface = {"ether1": {"type": "ether", "default-name": "ether1"}}
    coordinator = _poe_coordinator(interface=interface)
    coordinator._accumulate_poe_energy()
    assert coordinator.ds["resource"]["poe-out-energy-delta-wh"] is None
    assert interface["ether1"]["poe-out-energy-source"] is None


def test_accumulate_poe_energy_skips_non_ether_ports():
    """Only ether ports are integrated; wlan/bridge are left untouched."""
    interface = {"wlan1": {"type": "wlan"}}
    coordinator = _poe_coordinator(interface=interface)
    coordinator._accumulate_poe_energy()
    assert "poe-out-energy-delta-wh" not in interface["wlan1"]


def test_get_neighbor_builds_interface_board_map():
    """get_neighbor maps each interface (incl. comma-listed) to advertised board(s)."""
    coordinator = make_coordinator(
        api_responses={
            "/ip/neighbor": [
                {"interface": "ether1", "board": "RBD52G-5HacD2HnD", "identity": "hap_ac2"},
                {"interface": "ether2,bridge", "board": "CRS310-8G+2S+", "identity": "csr310"},
                {"interface": "ether3"},  # missing board -> skipped
            ]
        }
    )
    coordinator.get_neighbor()
    assert coordinator.ds["neighbor"] == {
        "ether1": ["RBD52G-5HacD2HnD"],
        "ether2": ["CRS310-8G+2S+"],
        "bridge": ["CRS310-8G+2S+"],
    }


def test_get_neighbor_retains_prior_map_on_query_failure():
    """A failed/None /ip/neighbor query keeps the previous map (no estimate reset)."""
    coordinator = make_coordinator(api_responses={"/ip/neighbor": None})
    coordinator.ds["neighbor"] = {"ether1": ["RBD52G-5HacD2HnD"]}
    coordinator.get_neighbor()
    assert coordinator.ds["neighbor"] == {"ether1": ["RBD52G-5HacD2HnD"]}


def test_resolve_poe_power_non_numeric_measured_yields_no_value():
    """A non-numeric poe-out-power reading null-not-guesses instead of crashing."""
    coordinator = _poe_coordinator()
    iface = {"poe-out-power": "n/a", "poe-out-status": "powered-on", "default-name": "ether1"}
    assert coordinator._resolve_poe_power(iface) == (None, None, None)
