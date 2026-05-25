"""Mikrotik coordinator."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from ipaddress import ip_address, IPv4Network
from mac_vendor_lookup import AsyncMacLookup

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import now as dt_now, utcnow


from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
    CONF_ZONE,
    STATE_HOME,
)

from .const import (
    DOMAIN,
    CONF_TRACK_IFACE_CLIENTS,
    DEFAULT_TRACK_IFACE_CLIENTS,
    CONF_TRACK_HOSTS,
    DEFAULT_TRACK_HOSTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_SENSOR_PORT_TRAFFIC,
    DEFAULT_SENSOR_PORT_TRAFFIC,
    CONF_SENSOR_CLIENT_TRAFFIC,
    DEFAULT_SENSOR_CLIENT_TRAFFIC,
    CONF_SENSOR_CLIENT_CAPTIVE,
    DEFAULT_SENSOR_CLIENT_CAPTIVE,
    CONF_SENSOR_SIMPLE_QUEUES,
    DEFAULT_SENSOR_SIMPLE_QUEUES,
    CONF_SENSOR_NAT,
    DEFAULT_SENSOR_NAT,
    CONF_SENSOR_MANGLE,
    DEFAULT_SENSOR_MANGLE,
    CONF_SENSOR_FILTER,
    DEFAULT_SENSOR_FILTER,
    CONF_SENSOR_KIDCONTROL,
    DEFAULT_SENSOR_KIDCONTROL,
    CONF_SENSOR_PPP,
    DEFAULT_SENSOR_PPP,
    CONF_SENSOR_SCRIPTS,
    DEFAULT_SENSOR_SCRIPTS,
    CONF_SENSOR_ENVIRONMENT,
    DEFAULT_SENSOR_ENVIRONMENT,
    CONF_SENSOR_NETWATCH_TRACKER,
    DEFAULT_SENSOR_NETWATCH_TRACKER,
    CONF_SENSOR_POE,
    DEFAULT_SENSOR_POE,
    CONF_SENSOR_RAW,
    DEFAULT_SENSOR_RAW,
    CONF_SENSOR_CONTAINER,
    DEFAULT_SENSOR_CONTAINER,
)
from .apiparser import parse_api
from .mikrotikapi import MikrotikAPI

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIME_ZONE = None


def is_valid_ip(address):
    try:
        ipaddress.ip_address(address)
        return True
    except ValueError:
        return False


def utc_from_timestamp(timestamp: float) -> datetime:
    """Return a UTC time from a timestamp."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


_UPTIME_UNITS = [("w", 604800), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
_PPP_NOT_CONNECTED = "not connected"


def _parse_uptime_to_seconds(uptime_str: str) -> int:
    """Parse MikroTik uptime string (e.g. '1w2d3h4m5s') to total seconds."""
    total = 0
    for unit, multiplier in _UPTIME_UNITS:
        match = re.split(rf"(\d+){unit}", uptime_str)
        if len(match) > 1:
            total += int(match[1]) * multiplier
    return total


def as_local(dattim: datetime) -> datetime:
    """Convert a UTC datetime object to local time zone."""
    if dattim.tzinfo == DEFAULT_TIME_ZONE:
        return dattim
    if dattim.tzinfo is None:
        dattim = dattim.replace(tzinfo=timezone.utc)

    return dattim.astimezone(DEFAULT_TIME_ZONE)


@dataclass
class MikrotikData:
    """Data for the mikrotik integration."""

    data_coordinator: MikrotikCoordinator
    tracker_coordinator: MikrotikTrackerCoordinator


class MikrotikTrackerCoordinator(DataUpdateCoordinator[None]):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        coordinator: MikrotikCoordinator,
    ):
        """Initialize MikrotikTrackerCoordinator."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self.coordinator = coordinator

        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]

        self.api = MikrotikAPI(
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_PORT],
            config_entry.data[CONF_SSL],
            config_entry.data[CONF_VERIFY_SSL],
        )

    # ---------------------------
    #   option_zone
    # ---------------------------
    @property
    def option_zone(self):
        """Config entry option zones."""
        return self.config_entry.options.get(CONF_ZONE, STATE_HOME)

    _HOST_DEFAULTS = {
        "address": "unknown",
        "mac-address": "unknown",
        "interface": "unknown",
        "host-name": "unknown",
        "last-seen": False,
        "available": False,
    }

    async def _async_update_data(self):
        """Trigger update by timer."""
        if not self.coordinator.option_track_network_hosts:
            return

        if "test" not in self.coordinator.ds["access"]:
            return

        first_run = not self.coordinator.host_tracking_initialized

        for uid in list(self.coordinator.ds["host"]):
            host = self.coordinator.ds["host"][uid]
            if first_run:
                self._ensure_host_defaults(host)
                self._first_run_availability(uid, host)
            elif self._should_ping_host(host):
                await self._ping_host(uid, host)

            if host["available"]:
                host["last-seen"] = utcnow()

        self.coordinator.host_tracking_initialized = True

        await self.coordinator.async_process_host()
        return {
            "host": self.coordinator.ds["host"],
            "routerboard": self.coordinator.ds["routerboard"],
        }

    def _ensure_host_defaults(self, host: dict) -> None:
        """Add missing default values to a host entry."""
        for key, default in self._HOST_DEFAULTS.items():
            if key not in host:
                host[key] = default

    def _first_run_availability(self, uid: str, host: dict) -> None:
        """Set availability from ARP on first run (no pinging)."""
        in_arp = uid in self.coordinator.ds["arp"]
        host["available"] = in_arp
        if not in_arp:
            _LOGGER.debug("Host %s not in ARP on first run; will ping next cycle", uid)

    @staticmethod
    def _should_ping_host(host: dict) -> bool:
        """Check if a host should be pinged (non-wireless with valid address/interface)."""
        return host.get("source", "") not in ("capsman", "wireless") and host.get("address", "unknown") not in ("unknown", "") and host.get("interface", "unknown") not in ("unknown", "")

    async def _ping_host(self, uid: str, host: dict) -> None:
        """Ping a host and update availability."""
        interface = host["interface"]
        if uid in self.coordinator.ds["arp"] and self.coordinator.ds["arp"][uid].get("bridge", "") != "":
            interface = self.coordinator.ds["arp"][uid]["bridge"]

        _LOGGER.debug("Ping host: %s", host["address"])
        host["available"] = await self.hass.async_add_executor_job(self.api.arp_ping, host["address"], interface)


class MikrotikCoordinator(DataUpdateCoordinator[None]):
    """MikrotikCoordinator Class"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize MikrotikCoordinator."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self.option_scan_interval,
        )
        self.name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]

        self.ds = {
            "access": {},
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

        self.notified_flags = []

        self.api = MikrotikAPI(
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_PORT],
            config_entry.data[CONF_SSL],
            config_entry.data[CONF_VERIFY_SSL],
        )

        self.debug = False
        if _LOGGER.getEffectiveLevel() == 10:
            self.debug = True

        self.nat_removed = {}
        self.mangle_removed = {}
        self.filter_removed = {}
        self.raw_removed = {}
        self.host_hass_recovered = False
        self.host_tracking_initialized = False
        self._known_uids: dict[str, set[str]] = {}

        self.support_capsman = False
        self.support_wireless = False
        self.support_ppp = False
        self.support_ups = False
        self.support_gps = False
        self.support_container = False
        self._wifimodule = "wireless"

        self.major_fw_version = 0
        self.minor_fw_version = 0

        self.async_mac_lookup = AsyncMacLookup()
        self.accessrights_reported = False

        self.last_hwinfo_update = datetime(1970, 1, 1, tzinfo=timezone.utc)
        self.rebootcheck = 0

    # ---------------------------
    #   option_track_iface_clients
    # ---------------------------
    @property
    def option_track_iface_clients(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_TRACK_IFACE_CLIENTS, DEFAULT_TRACK_IFACE_CLIENTS)

    # ---------------------------
    #   option_track_network_hosts
    # ---------------------------
    @property
    def option_track_network_hosts(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_TRACK_HOSTS, DEFAULT_TRACK_HOSTS)

    # ---------------------------
    #   option_sensor_port_traffic
    # ---------------------------
    @property
    def option_sensor_port_traffic(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_PORT_TRAFFIC, DEFAULT_SENSOR_PORT_TRAFFIC)

    # ---------------------------
    #   option_sensor_client_traffic
    # ---------------------------
    @property
    def option_sensor_client_traffic(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_CLIENT_TRAFFIC, DEFAULT_SENSOR_CLIENT_TRAFFIC)

    # ---------------------------
    #   option_sensor_client_captive
    # ---------------------------
    @property
    def option_sensor_client_captive(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_CLIENT_CAPTIVE, DEFAULT_SENSOR_CLIENT_CAPTIVE)

    # ---------------------------
    #   option_sensor_simple_queues
    # ---------------------------
    @property
    def option_sensor_simple_queues(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_SIMPLE_QUEUES, DEFAULT_SENSOR_SIMPLE_QUEUES)

    # ---------------------------
    #   option_sensor_nat
    # ---------------------------
    @property
    def option_sensor_nat(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_NAT, DEFAULT_SENSOR_NAT)

    # ---------------------------
    #   option_sensor_mangle
    # ---------------------------
    @property
    def option_sensor_mangle(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_MANGLE, DEFAULT_SENSOR_MANGLE)

    # ---------------------------
    #   option_sensor_filter
    # ---------------------------
    @property
    def option_sensor_filter(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_FILTER, DEFAULT_SENSOR_FILTER)

    # ---------------------------
    #   option_sensor_kidcontrol
    # ---------------------------
    @property
    def option_sensor_kidcontrol(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_KIDCONTROL, DEFAULT_SENSOR_KIDCONTROL)

    # ---------------------------
    #   option_sensor_netwatch
    # ---------------------------
    @property
    def option_sensor_netwatch(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_NETWATCH_TRACKER, DEFAULT_SENSOR_NETWATCH_TRACKER)

    # ---------------------------
    #   option_sensor_ppp
    # ---------------------------
    @property
    def option_sensor_ppp(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_PPP, DEFAULT_SENSOR_PPP)

    # ---------------------------
    #   option_sensor_poe
    # ---------------------------
    @property
    def option_sensor_poe(self):
        """Config entry option for PoE monitoring sensors."""
        return self.config_entry.options.get(CONF_SENSOR_POE, DEFAULT_SENSOR_POE)

    # ---------------------------
    #   option_sensor_raw
    # ---------------------------
    @property
    def option_sensor_raw(self):
        """Config entry option for firewall raw rule sensors."""
        return self.config_entry.options.get(CONF_SENSOR_RAW, DEFAULT_SENSOR_RAW)

    # ---------------------------
    #   option_sensor_container
    # ---------------------------
    @property
    def option_sensor_container(self):
        """Config entry option for container sensors."""
        return self.config_entry.options.get(CONF_SENSOR_CONTAINER, DEFAULT_SENSOR_CONTAINER)

    # ---------------------------
    #   option_sensor_scripts
    # ---------------------------
    @property
    def option_sensor_scripts(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_SCRIPTS, DEFAULT_SENSOR_SCRIPTS)

    # ---------------------------
    #   option_sensor_environment
    # ---------------------------
    @property
    def option_sensor_environment(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_SENSOR_ENVIRONMENT, DEFAULT_SENSOR_ENVIRONMENT)

    # ---------------------------
    #   option_scan_interval
    # ---------------------------
    @property
    def option_scan_interval(self):
        """Config entry option scan interval."""
        scan_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return timedelta(seconds=scan_interval)

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self):
        """Return connected state"""
        return self.api.connected()

    # ---------------------------
    #   set_value
    # ---------------------------
    def set_value(self, path, param, value, mod_param, mod_value):
        """Change value using Mikrotik API"""
        return self.api.set_value(path, param, value, mod_param, mod_value)

    # ---------------------------
    #   execute
    # ---------------------------
    def execute(self, path, command, param, value, attributes=None):
        """Change value using Mikrotik API"""
        return self.api.execute(path, command, param, value, attributes)

    # ---------------------------
    #   get_capabilities
    # ---------------------------
    def get_capabilities(self):
        """Update Mikrotik data"""
        packages = parse_api(
            data={},
            source=self.api.query("/system/package"),
            key="name",
            vals=[
                {"name": "name"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
        )

        if 0 < self.major_fw_version < 7:
            self._detect_capabilities_v6(packages)
        elif self.major_fw_version >= 7:
            self._detect_capabilities_v7(packages)

        for pkg, attr in [
            ("ups", "support_ups"),
            ("gps", "support_gps"),
            ("container", "support_container"),
        ]:
            if pkg in packages and packages[pkg]["enabled"]:
                setattr(self, attr, True)

    def _detect_capabilities_v6(self, packages: dict) -> None:
        """Detect wireless/PPP capabilities for RouterOS v6."""
        if "ppp" in packages:
            self.support_ppp = packages["ppp"]["enabled"]
        if "wireless" in packages:
            self.support_capsman = packages["wireless"]["enabled"]
            self.support_wireless = packages["wireless"]["enabled"]
        else:
            self.support_capsman = False
            self.support_wireless = False

    def _detect_capabilities_v7(self, packages: dict) -> None:
        """Detect wireless/PPP/wifi module capabilities for RouterOS v7+."""
        self.support_ppp = True
        self.support_wireless = True

        if "wifiwave2" in packages and packages["wifiwave2"]["enabled"]:
            self.support_capsman = False
            self._wifimodule = "wifiwave2"
        elif self._has_wifi_package(packages):
            self.support_capsman = False
            self._wifimodule = "wifi"
        else:
            # Legacy `wireless` package (CAPsMAN-capable /interface/wireless
            # stack), including RouterOS 7.13+ routers that still run it.
            self.support_capsman = True
            self._wifimodule = "wireless"

        _LOGGER.debug("Mikrotik %s wifi module=%s", self.host, self._wifimodule)

    def _has_wifi_package(self, packages: dict) -> bool:
        """Check if a wifi package is enabled or version implies wifi module."""
        if any(pkg in packages and packages[pkg]["enabled"] for pkg in ("wifi", "wifi-qcom", "wifi-qcom-ac")):
            return True
        # An explicitly enabled legacy `wireless` package wins over the
        # version heuristic: 7.13+ routers that still ship it are not on
        # the built-in wifi driver.
        if "wireless" in packages and packages["wireless"]["enabled"]:
            return False
        return (self.major_fw_version == 7 and self.minor_fw_version >= 13) or self.major_fw_version > 7

    async def async_get_host_hass(self):
        """Get host data from HA entity registry"""
        registry = entity_registry.async_get(self.hass)
        for entity in registry.entities.values():
            if entity.config_entry_id == self.config_entry.entry_id and entity.entity_id.startswith("device_tracker."):
                tmp = entity.unique_id.split("-")
                if tmp[0] != self.name.lower():
                    continue

                if tmp[1] != "host":
                    continue

                if ":" not in tmp[2]:
                    continue

                self.ds["host_hass"][tmp[2].upper()] = entity.original_name

    # ---------------------------
    #   _run_if_enabled
    # ---------------------------
    async def _run_if_enabled(self, func, *, requires: bool = True) -> None:
        """Run a blocking API call in the executor if connected and enabled."""
        if self.api.connected() and requires:
            await self.hass.async_add_executor_job(func)

    # ---------------------------
    #   _async_update_hwinfo
    # ---------------------------
    async def _async_update_hwinfo(self) -> bool:
        """Refresh hardware info (runs every 4 hours or on reconnect).

        Returns True if the refresh ran (so callers can skip duplicate work).
        """
        delta = dt_now().replace(microsecond=0) - self.last_hwinfo_update
        if not self.api.has_reconnected() and delta.total_seconds() <= 60 * 60 * 4:
            return False

        await self.hass.async_add_executor_job(self.get_access)

        for func in [
            self.get_firmware_update,
            self.get_system_resource,
            self.get_capabilities,
            self.get_system_routerboard,
        ]:
            await self._run_if_enabled(func)

        await self._run_if_enabled(self.get_script, requires=self.option_sensor_scripts)

        for func in [self.get_dhcp_network, self.get_dns]:
            await self._run_if_enabled(func)

        if not self.api.connected():
            raise UpdateFailed("Mikrotik Disconnected")

        self.last_hwinfo_update = dt_now().replace(microsecond=0)
        return True

    # ---------------------------
    #   _async_update_data
    # ---------------------------
    async def _async_update_data(self):
        """Update Mikrotik data"""
        hwinfo_ran = await self._async_update_hwinfo()

        # get_system_resource already ran inside _async_update_hwinfo;
        # only call it again on normal polling cycles where hwinfo was skipped.
        if not hwinfo_ran:
            await self._run_if_enabled(self.get_system_resource)

        for func in [self.get_system_health, self.get_dhcp_client, self.get_interface]:
            await self._run_if_enabled(func)

        if self.api.connected() and not self.ds["host_hass"]:
            await self.async_get_host_hass()

        await self._run_if_enabled(self.get_capsman_hosts, requires=self.support_capsman)
        await self._run_if_enabled(self.get_wireless, requires=self.support_wireless)
        await self._run_if_enabled(self.get_wireless_hosts, requires=self.support_wireless)

        # Order matters: get_dhcp_server must run before get_dhcp (lease counting)
        for func in [
            self.get_bridge,
            self.get_arp,
            self.get_dhcp_server,
            self.get_dhcp,
        ]:
            await self._run_if_enabled(func)

        if self.api.connected():
            await self.async_process_host()

        await self._run_if_enabled(self.process_interface_client)

        for func, enabled in [
            (self.get_nat, self.option_sensor_nat),
            (self.get_kidcontrol, self.option_sensor_kidcontrol),
            (self.get_mangle, self.option_sensor_mangle),
            (self.get_filter, self.option_sensor_filter),
            (self.get_raw, self.option_sensor_raw),
            (self.get_netwatch, self.option_sensor_netwatch),
            (self.get_ppp, self.support_ppp and self.option_sensor_ppp),
        ]:
            await self._run_if_enabled(func, requires=enabled)

        await self._async_update_client_traffic()

        for func, enabled in [
            (self.get_captive, self.option_sensor_client_captive),
            (self.get_queue, self.option_sensor_simple_queues),
            (self.get_environment, self.option_sensor_environment),
            (self.get_ups, self.support_ups),
            (self.get_gps, self.support_gps),
            (
                self.get_container,
                self.support_container and self.option_sensor_container,
            ),
        ]:
            await self._run_if_enabled(func, requires=enabled)

        if not self.api.connected():
            raise UpdateFailed("Mikrotik Disconnected")

        # UID tracking: monitor for new entities across update cycles.
        # Dispatcher is NOT fired automatically — _check_entity_exists guard
        # needs hardening before re-enabling (see ISS-260320-new-device-discovery).
        # Track UIDs for future use and debug visibility.
        self._check_new_uids()
        return self.ds

    # Data paths where dict keys are entity UIDs (not data field names).
    _ENTITY_UID_PATHS = frozenset(
        {
            "interface",
            "host",
            "nat",
            "mangle",
            "filter",
            "raw",
            "queue",
            "ppp_secret",
            "script",
            "dhcp",
            "dhcp-server",
            "dhcp-client",
            "kid-control",
            "container",
            "environment",
            "netwatch",
        }
    )

    def _check_new_uids(self) -> list[str]:
        """Return list of entity-relevant data paths with new UIDs since last check.

        On the first call (empty _known_uids), seeds the tracking but returns empty
        list to avoid redundant entity setup during initial load.
        Only checks paths in _ENTITY_UID_PATHS (where dict keys are entity UIDs).
        """
        first_run = not self._known_uids
        changed_paths: list[str] = []
        for path in self._ENTITY_UID_PATHS:
            data = self.ds.get(path)
            if not isinstance(data, dict):
                continue
            current = set(data.keys())
            previous = self._known_uids.get(path, set())
            new_keys = current - previous
            if not first_run and new_keys:
                changed_paths.append(path)
                _LOGGER.debug("New UIDs in %s: %s", path, new_keys)
            self._known_uids[path] = current
        return changed_paths

    async def _async_update_client_traffic(self) -> None:
        """Run accounting or kid-control traffic collection if enabled."""
        if not self.api.connected() or not self.option_sensor_client_traffic:
            return
        if 0 < self.major_fw_version < 7:
            await self.hass.async_add_executor_job(self.process_accounting)
        elif self.major_fw_version >= 7:
            await self.hass.async_add_executor_job(self.process_kid_control_devices)

    def get_access(self) -> None:
        """Get access rights from Mikrotik"""
        tmp_user = parse_api(
            data={},
            source=self.api.query("/user"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "group"},
            ],
        )

        tmp_group = parse_api(
            data={},
            source=self.api.query("/user/group"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "policy"},
            ],
        )

        username = self.config_entry.data[CONF_USERNAME]
        if username not in tmp_user:
            _LOGGER.error(
                "Mikrotik %s user '%s' not found in router user list. Check integration configuration.",
                self.host,
                username,
            )
            return

        if tmp_user[username]["group"] in tmp_group:
            self.ds["access"] = tmp_group[tmp_user[username]["group"]]["policy"].split(",")

        if not self.accessrights_reported:
            self.accessrights_reported = True
            if "write" not in self.ds["access"] or "policy" not in self.ds["access"] or "reboot" not in self.ds["access"] or "test" not in self.ds["access"]:
                _LOGGER.warning(
                    "Mikrotik %s user %s does not have sufficient access rights. Integration functionality will be limited.",
                    self.host,
                    username,
                )

    # ---------------------------
    #   _monitor_ethernet_port
    # ---------------------------
    _SFP_MONITOR_VALS = [
        {"name": "status", "default": "unknown"},
        {"name": "rate", "default": "unknown"},
        {"name": "full-duplex", "default": "unknown"},
        {"name": "auto-negotiation", "default": "unknown"},
        {"name": "advertising", "default": "unknown"},
        {"name": "link-partner-advertising", "default": "unknown"},
        {"name": "sfp-temperature", "default": None},
        {"name": "sfp-supply-voltage", "default": "unknown"},
        {"name": "sfp-module-present", "default": "unknown"},
        {"name": "sfp-tx-bias-current", "default": "unknown"},
        {"name": "sfp-tx-power", "default": "unknown"},
        {"name": "sfp-rx-power", "default": "unknown"},
        {"name": "sfp-rx-loss", "default": "unknown"},
        {"name": "sfp-tx-fault", "default": "unknown"},
        {"name": "sfp-type", "default": "unknown"},
        {"name": "sfp-connector-type", "default": "unknown"},
        {"name": "sfp-vendor-name", "default": "unknown"},
        {"name": "sfp-vendor-part-number", "default": "unknown"},
        {"name": "sfp-vendor-revision", "default": "unknown"},
        {"name": "sfp-vendor-serial", "default": "unknown"},
        {"name": "sfp-manufacturing-date", "default": "unknown"},
        {"name": "eeprom-checksum", "default": "unknown"},
    ]

    _COPPER_MONITOR_VALS = [
        {"name": "status", "default": "unknown"},
        {"name": "rate", "default": "unknown"},
        {"name": "full-duplex", "default": "unknown"},
        {"name": "auto-negotiation", "default": "unknown"},
    ]

    _POE_MONITOR_VALS = [
        {"name": "poe-out-status", "default": "unknown"},
        {"name": "poe-out-voltage", "default": None},
        {"name": "poe-out-current", "default": None},
        {"name": "poe-out-power", "default": None},
    ]

    def _monitor_ethernet_port(self, vals) -> None:
        """Fetch monitor data for a single ethernet port (SFP or copper + PoE)."""
        has_sfp = "sfp-shutdown-temperature" in vals and vals["sfp-shutdown-temperature"] != ""
        monitor_vals = self._SFP_MONITOR_VALS if has_sfp else self._COPPER_MONITOR_VALS

        self.ds["interface"] = parse_api(
            data=self.ds["interface"],
            source=self.api.query(
                "/interface/ethernet",
                command="monitor",
                args={".id": vals[".id"], "once": True},
            ),
            key_search="name",
            vals=monitor_vals,
        )

        if self.option_sensor_poe and vals.get("poe-out") not in (None, "N/A", ""):
            self.ds["interface"] = parse_api(
                data=self.ds["interface"],
                source=self.api.query(
                    "/interface/ethernet/poe",
                    command="monitor",
                    args={".id": vals[".id"], "once": True},
                ),
                key_search="name",
                vals=self._POE_MONITOR_VALS,
            )

    def _calculate_interface_traffic(self) -> None:
        """Calculate per-interface TX/RX throughput from byte counters."""
        interval = self.option_scan_interval.seconds
        for uid, vals in self.ds["interface"].items():
            iface = self.ds["interface"][uid]
            for direction in ("tx", "rx"):
                current = vals[f"{direction}-current"]
                previous = vals[f"{direction}-previous"] or current
                iface[direction] = round(max(0, current - previous) / interval)
                iface[f"{direction}-previous"] = current
                iface[f"{direction}-total"] = current

    def get_interface(self) -> None:
        """Get all interfaces data from Mikrotik"""
        self.ds["interface"] = parse_api(
            data=self.ds["interface"],
            source=self.api.query("/interface"),
            key="default-name",
            key_secondary="name",
            vals=[
                {"name": "default-name"},
                {"name": ".id"},
                {"name": "name", "default_val": "default-name"},
                {"name": "type", "default": "unknown"},
                {"name": "running", "type": "bool"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
                {"name": "port-mac-address", "source": "mac-address"},
                {"name": "comment"},
                {"name": "last-link-down-time"},
                {"name": "last-link-up-time"},
                {"name": "link-downs"},
                {"name": "tx-queue-drop"},
                {"name": "actual-mtu"},
                {"name": "about", "source": ".about", "default": ""},
                {"name": "rx-current", "source": "rx-byte", "default": 0.0},
                {"name": "tx-current", "source": "tx-byte", "default": 0.0},
            ],
            ensure_vals=[
                {"name": "client-ip-address"},
                {"name": "client-mac-address"},
                {"name": "rx-previous", "default": 0.0},
                {"name": "tx-previous", "default": 0.0},
                {"name": "rx", "default": 0.0},
                {"name": "tx", "default": 0.0},
                {"name": "rx-total", "default": 0.0},
                {"name": "tx-total", "default": 0.0},
            ],
            skip=[
                {"name": "type", "value": "bridge"},
                {"name": "type", "value": "ppp-in"},
                {"name": "type", "value": "pptp-in"},
                {"name": "type", "value": "sstp-in"},
                {"name": "type", "value": "l2tp-in"},
                {"name": "type", "value": "pppoe-in"},
                {"name": "type", "value": "ovpn-in"},
            ],
        )

        if self.option_sensor_port_traffic:
            self._calculate_interface_traffic()

        self.ds["interface"] = parse_api(
            data=self.ds["interface"],
            source=self.api.query("/interface/ethernet"),
            key="default-name",
            key_secondary="name",
            vals=[
                {"name": "default-name"},
                {"name": "name", "default_val": "default-name"},
                {"name": "poe-out", "default": "N/A"},
                {"name": "sfp-shutdown-temperature", "default": 0},
            ],
            skip=[
                {"name": "type", "value": "bridge"},
                {"name": "type", "value": "ppp-in"},
                {"name": "type", "value": "pptp-in"},
                {"name": "type", "value": "sstp-in"},
                {"name": "type", "value": "l2tp-in"},
                {"name": "type", "value": "pppoe-in"},
                {"name": "type", "value": "ovpn-in"},
            ],
        )

        # Update virtual interfaces
        self._process_interface_metadata()

    def _process_interface_metadata(self) -> None:
        """Post-process interfaces: comments, virtual names, ethernet monitoring, bonding."""
        has_bonding = False
        for uid, vals in self.ds["interface"].items():
            iface = self.ds["interface"][uid]
            if iface["type"] == "bond":
                has_bonding = True

            iface["comment"] = str(iface["comment"])

            if vals["default-name"] == "":
                iface["default-name"] = vals["name"]
                iface["port-mac-address"] = f"{vals['port-mac-address']}-{vals['name']}"

            if iface["type"] == "ether":
                self._monitor_ethernet_port(vals)

        if has_bonding:
            self._process_bonding()

    def _process_bonding(self) -> None:
        """Fetch bonding config and build slave→master mapping."""
        self.ds["bonding"] = parse_api(
            data={},
            source=self.api.query("/interface/bonding"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "mac-address"},
                {"name": "slaves"},
                {"name": "mode"},
            ],
        )
        self.ds["bonding_slaves"] = {}
        for uid, vals in self.ds["bonding"].items():
            for tmp in vals["slaves"].split(","):
                self.ds["bonding_slaves"][tmp] = vals
                self.ds["bonding_slaves"][tmp]["master"] = uid

    def get_bridge(self) -> None:
        """Get system resources data from Mikrotik"""
        self.ds["bridge_host"] = parse_api(
            data=self.ds["bridge_host"],
            source=self.api.query("/interface/bridge/host"),
            key="mac-address",
            vals=[
                {"name": "mac-address"},
                {"name": "interface", "default": "unknown"},
                {"name": "bridge", "default": "unknown"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
            only=[{"key": "local", "value": False}],
        )

        for uid, vals in self.ds["bridge_host"].items():
            self.ds["bridge"][vals["bridge"]] = True

    def process_interface_client(self) -> None:
        """Resolve client IP/MAC for each interface from ARP and DHCP data."""
        if not self.option_track_iface_clients:
            for uid in self.ds["interface"]:
                self.ds["interface"][uid]["client-ip-address"] = "disabled"
                self.ds["interface"][uid]["client-mac-address"] = "disabled"
            return

        for uid, vals in self.ds["interface"].items():
            self.ds["interface"][uid]["client-ip-address"] = ""
            self.ds["interface"][uid]["client-mac-address"] = ""
            self._match_arp_clients(uid, vals)
            self._fallback_client_ip(uid)
            if self.ds["interface"][uid]["client-mac-address"] == "":
                self.ds["interface"][uid]["client-mac-address"] = "none"

    def _arp_matches_interface(self, arp_vals: dict, iface_name: str) -> bool:
        """Check if an ARP entry belongs to an interface (direct or via bonding)."""
        if arp_vals["interface"] == iface_name:
            return True
        if iface_name in self.ds["bonding_slaves"]:
            return self.ds["bonding_slaves"][iface_name]["master"] == arp_vals["interface"]
        return False

    def _match_arp_clients(self, uid: str, vals: dict) -> None:
        """Match ARP entries to an interface, setting client-ip/mac or 'multiple'."""
        iface = self.ds["interface"][uid]
        for arp_vals in self.ds["arp"].values():
            if not self._arp_matches_interface(arp_vals, vals["name"]):
                continue

            if iface["client-ip-address"] == "":
                iface["client-ip-address"] = arp_vals["address"]
            else:
                iface["client-ip-address"] = "multiple"

            if iface["client-mac-address"] == "":
                iface["client-mac-address"] = arp_vals["mac-address"]
            else:
                iface["client-mac-address"] = "multiple"

    def _fallback_client_ip(self, uid: str) -> None:
        """Fall back to DHCP client address if no ARP match found."""
        iface = self.ds["interface"][uid]
        if iface["client-ip-address"] != "":
            return
        name = iface["name"]
        if name in self.ds["dhcp-client"]:
            iface["client-ip-address"] = self.ds["dhcp-client"][name]["address"]
        else:
            iface["client-ip-address"] = "none"

    def _dedup_firewall_rules(self, ds_key: str, removed_log: dict) -> None:
        """Remove duplicate firewall rules (by uniq-id) and coerce comments to str.

        Shared by get_nat, get_mangle, get_filter, and get_raw.  When two
        entries share the same uniq-id both are removed to prevent entity
        registration crashes.  The first occurrence is logged as an error.
        """
        data = self.ds[ds_key]
        seen: dict[str, str] = {}
        duplicates: dict[str, int] = {}

        for uid in data:
            data[uid]["comment"] = str(data[uid]["comment"])
            uniq = data[uid]["uniq-id"]
            if uniq not in seen:
                seen[uniq] = uid
            else:
                duplicates[uid] = 1
                duplicates[seen[uniq]] = 1

        for uid in duplicates:
            uniq = data[uid]["uniq-id"]
            if uniq not in removed_log:
                removed_log[uniq] = 1
                _LOGGER.error(
                    "Mikrotik %s duplicate %s rule %s, entity will be unavailable.",
                    self.host,
                    ds_key,
                    data[uid]["name"],
                )
            del data[uid]

    def _get_firewall_rules(
        self,
        rule_type: str,
        api_path: str,
        vals: list,
        val_proc: list,
        only: list | None = None,
        skip: list | None = None,
    ) -> None:
        """Fetch, parse, and dedup firewall rules of any type."""
        self.ds[rule_type] = parse_api(
            data=self.ds[rule_type],
            source=self.api.query(api_path),
            key=".id",
            vals=vals,
            val_proc=val_proc,
            only=only or [],
            skip=skip or [],
        )
        removed_log = getattr(self, f"{rule_type}_removed")
        self._dedup_firewall_rules(rule_type, removed_log)

    _ENABLED_VAL = {
        "name": "enabled",
        "source": "disabled",
        "type": "bool",
        "reverse": True,
    }

    _SKIP_DYNAMIC_JUMP = [
        {"name": "dynamic", "value": True},
        {"name": "action", "value": "jump"},
    ]

    # ---------------------------
    #   get_nat
    # ---------------------------
    def get_nat(self) -> None:
        """Get NAT data from Mikrotik"""
        self._get_firewall_rules(
            "nat",
            "/ip/firewall/nat",
            vals=[
                {"name": ".id"},
                {"name": "chain", "default": "unknown"},
                {"name": "action", "default": "unknown"},
                {"name": "protocol", "default": "any"},
                {"name": "dst-port", "default": "any"},
                {"name": "in-interface", "default": "any"},
                {"name": "out-interface", "default": "any"},
                {"name": "to-addresses"},
                {"name": "to-ports", "default": "any"},
                {"name": "comment"},
                self._ENABLED_VAL,
            ],
            val_proc=[
                [
                    {"name": "uniq-id"},
                    {"action": "combine"},
                    {"key": "chain"},
                    {"text": ","},
                    {"key": "action"},
                    {"text": ","},
                    {"key": "protocol"},
                    {"text": ","},
                    {"key": "in-interface"},
                    {"text": ":"},
                    {"key": "dst-port"},
                    {"text": "-"},
                    {"key": "out-interface"},
                    {"text": ":"},
                    {"key": "to-addresses"},
                    {"text": ":"},
                    {"key": "to-ports"},
                ],
                [
                    {"name": "name"},
                    {"action": "combine"},
                    {"key": "protocol"},
                    {"text": ":"},
                    {"key": "dst-port"},
                ],
            ],
            only=[{"key": "action", "value": "dst-nat"}],
        )

    # ---------------------------
    #   get_mangle
    # ---------------------------
    def get_mangle(self) -> None:
        """Get Mangle data from Mikrotik"""
        self._get_firewall_rules(
            "mangle",
            "/ip/firewall/mangle",
            vals=[
                {"name": ".id"},
                {"name": "chain"},
                {"name": "action"},
                {"name": "comment"},
                {"name": "address-list"},
                {"name": "passthrough", "type": "bool", "default": False},
                {"name": "protocol", "default": "any"},
                {"name": "src-address", "default": "any"},
                {"name": "src-port", "default": "any"},
                {"name": "dst-address", "default": "any"},
                {"name": "dst-port", "default": "any"},
                {"name": "src-address-list", "default": "any"},
                {"name": "dst-address-list", "default": "any"},
                {"name": "in-interface", "default": "any"},
                {"name": "out-interface", "default": "any"},
                self._ENABLED_VAL,
            ],
            val_proc=[
                [
                    {"name": "uniq-id"},
                    {"action": "combine"},
                    {"key": "chain"},
                    {"text": ","},
                    {"key": "action"},
                    {"text": ","},
                    {"key": "protocol"},
                    {"text": ","},
                    {"key": "src-address"},
                    {"text": ":"},
                    {"key": "src-port"},
                    {"text": "-"},
                    {"key": "dst-address"},
                    {"text": ":"},
                    {"key": "dst-port"},
                    {"text": ","},
                    {"key": "src-address-list"},
                    {"text": "-"},
                    {"key": "dst-address-list"},
                    {"text": ","},
                    {"key": "in-interface"},
                    {"text": "-"},
                    {"key": "out-interface"},
                ],
                [
                    {"name": "name"},
                    {"action": "combine"},
                    {"key": "action"},
                    {"text": ","},
                    {"key": "protocol"},
                    {"text": ":"},
                    {"key": "dst-port"},
                ],
            ],
            skip=self._SKIP_DYNAMIC_JUMP,
        )

    # ---------------------------
    #   get_filter
    # ---------------------------
    def get_filter(self) -> None:
        """Get Filter data from Mikrotik"""
        self._get_firewall_rules(
            "filter",
            "/ip/firewall/filter",
            vals=[
                {"name": ".id"},
                {"name": "chain"},
                {"name": "action"},
                {"name": "comment"},
                {"name": "address-list"},
                {"name": "protocol", "default": "any"},
                {"name": "in-interface", "default": "any"},
                {"name": "in-interface-list", "default": "any"},
                {"name": "out-interface", "default": "any"},
                {"name": "out-interface-list", "default": "any"},
                {"name": "src-address", "default": "any"},
                {"name": "src-address-list", "default": "any"},
                {"name": "src-port", "default": "any"},
                {"name": "dst-address", "default": "any"},
                {"name": "dst-address-list", "default": "any"},
                {"name": "dst-port", "default": "any"},
                {"name": "layer7-protocol", "default": "any"},
                {"name": "connection-state", "default": "any"},
                {"name": "tcp-flags", "default": "any"},
                self._ENABLED_VAL,
            ],
            val_proc=[
                [
                    {"name": "uniq-id"},
                    {"action": "combine"},
                    {"key": "chain"},
                    {"text": ","},
                    {"key": "action"},
                    {"text": ","},
                    {"key": "protocol"},
                    {"text": ","},
                    {"key": "layer7-protocol"},
                    {"text": ","},
                    {"key": "in-interface"},
                    {"text": ","},
                    {"key": "in-interface-list"},
                    {"text": ":"},
                    {"key": "src-address"},
                    {"text": ","},
                    {"key": "src-address-list"},
                    {"text": ":"},
                    {"key": "src-port"},
                    {"text": "-"},
                    {"key": "out-interface"},
                    {"text": ","},
                    {"key": "out-interface-list"},
                    {"text": ":"},
                    {"key": "dst-address"},
                    {"text": ","},
                    {"key": "dst-address-list"},
                    {"text": ":"},
                    {"key": "dst-port"},
                ],
                [
                    {"name": "name"},
                    {"action": "combine"},
                    {"key": "action"},
                    {"text": ","},
                    {"key": "protocol"},
                    {"text": ":"},
                    {"key": "dst-port"},
                ],
            ],
            skip=self._SKIP_DYNAMIC_JUMP,
        )

    # ---------------------------
    #   get_raw
    # ---------------------------
    def get_raw(self) -> None:
        """Get Firewall RAW data from Mikrotik"""
        self._get_firewall_rules(
            "raw",
            "/ip/firewall/raw",
            vals=[
                {"name": ".id"},
                {"name": "chain"},
                {"name": "action"},
                {"name": "comment"},
                {"name": "protocol", "default": "any"},
                {"name": "in-interface", "default": "any"},
                {"name": "in-interface-list", "default": "any"},
                {"name": "out-interface", "default": "any"},
                {"name": "out-interface-list", "default": "any"},
                {"name": "src-address", "default": "any"},
                {"name": "src-address-list", "default": "any"},
                {"name": "src-port", "default": "any"},
                {"name": "dst-address", "default": "any"},
                {"name": "dst-address-list", "default": "any"},
                {"name": "dst-port", "default": "any"},
                self._ENABLED_VAL,
            ],
            val_proc=[
                [
                    {"name": "uniq-id"},
                    {"action": "combine"},
                    {"key": "chain"},
                    {"text": ","},
                    {"key": "action"},
                    {"text": ","},
                    {"key": "protocol"},
                    {"text": ","},
                    {"key": "in-interface"},
                    {"text": ","},
                    {"key": "in-interface-list"},
                    {"text": ":"},
                    {"key": "src-address"},
                    {"text": ","},
                    {"key": "src-address-list"},
                    {"text": ":"},
                    {"key": "src-port"},
                    {"text": "-"},
                    {"key": "out-interface"},
                    {"text": ","},
                    {"key": "out-interface-list"},
                    {"text": ":"},
                    {"key": "dst-address"},
                    {"text": ","},
                    {"key": "dst-address-list"},
                    {"text": ":"},
                    {"key": "dst-port"},
                ],
                [
                    {"name": "name"},
                    {"action": "combine"},
                    {"key": "action"},
                    {"text": ","},
                    {"key": "protocol"},
                    {"text": ":"},
                    {"key": "dst-port"},
                ],
            ],
            skip=self._SKIP_DYNAMIC_JUMP,
        )

    # ---------------------------
    #   get_container
    # ---------------------------
    def get_container(self) -> None:
        """Get container data from Mikrotik"""
        self.ds["container"] = parse_api(
            data=self.ds["container"],
            source=self.api.query("/container"),
            key=".id",
            vals=[
                {"name": ".id"},
                {"name": "name", "default": "unknown"},
                {"name": "tag", "default": "unknown"},
                {"name": "os", "default": "unknown"},
                {"name": "arch", "default": "unknown"},
                {"name": "interface", "default": "unknown"},
                {"name": "root-dir", "default": "unknown"},
                {"name": "mounts", "default": "unknown"},
                {"name": "dns", "default": "unknown"},
                {"name": "logging", "default": "unknown"},
                {"name": "cmd", "default": ""},
                {"name": "entrypoint", "default": ""},
                {"name": "envlist", "default": ""},
                {"name": "hostname", "default": ""},
                {"name": "workdir", "default": ""},
                {"name": "comment", "default": ""},
                {"name": "status", "default": "stopped"},
            ],
        )

        for uid in self.ds["container"]:
            self.ds["container"][uid]["running"] = self.ds["container"][uid]["status"] == "running"

    # ---------------------------
    #   get_kidcontrol
    # ---------------------------
    def get_kidcontrol(self) -> None:
        """Get Kid-control data from Mikrotik"""
        self.ds["kid-control"] = parse_api(
            data=self.ds["kid-control"],
            source=self.api.query("/ip/kid-control"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "rate-limit"},
                {"name": "mon", "default": "None"},
                {"name": "tue", "default": "None"},
                {"name": "wed", "default": "None"},
                {"name": "thu", "default": "None"},
                {"name": "fri", "default": "None"},
                {"name": "sat", "default": "None"},
                {"name": "sun", "default": "None"},
                {"name": "comment"},
                {"name": "blocked", "type": "bool", "default": False},
                {"name": "paused", "type": "bool", "reverse": True},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
        )

        for uid in self.ds["kid-control"]:
            self.ds["kid-control"][uid]["comment"] = str(self.ds["kid-control"][uid]["comment"])

    # ---------------------------
    #   get_ppp
    # ---------------------------
    def get_ppp(self) -> None:
        """Get PPP data from Mikrotik"""
        self.ds["ppp_secret"] = parse_api(
            data=self.ds["ppp_secret"],
            source=self.api.query("/ppp/secret"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "service"},
                {"name": "profile"},
                {"name": "comment"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
            ensure_vals=[
                {"name": "caller-id", "default": ""},
                {"name": "address", "default": ""},
                {"name": "encoding", "default": ""},
                {"name": "connected", "default": False},
            ],
        )

        self.ds["ppp_active"] = parse_api(
            data={},
            source=self.api.query("/ppp/active"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "service"},
                {"name": "caller-id"},
                {"name": "address"},
                {"name": "encoding"},
            ],
        )

        for uid in self.ds["ppp_secret"]:
            self.ds["ppp_secret"][uid]["comment"] = str(self.ds["ppp_secret"][uid]["comment"])

            if self.ds["ppp_secret"][uid]["name"] in self.ds["ppp_active"]:
                self.ds["ppp_secret"][uid]["connected"] = True
                self.ds["ppp_secret"][uid]["caller-id"] = self.ds["ppp_active"][uid]["caller-id"]
                self.ds["ppp_secret"][uid]["address"] = self.ds["ppp_active"][uid]["address"]
                self.ds["ppp_secret"][uid]["encoding"] = self.ds["ppp_active"][uid]["encoding"]
            else:
                self.ds["ppp_secret"][uid]["connected"] = False
                self.ds["ppp_secret"][uid]["caller-id"] = _PPP_NOT_CONNECTED
                self.ds["ppp_secret"][uid]["address"] = _PPP_NOT_CONNECTED
                self.ds["ppp_secret"][uid]["encoding"] = _PPP_NOT_CONNECTED

    # ---------------------------
    #   get_netwatch
    # ---------------------------
    def get_netwatch(self) -> None:
        """Get netwatch data from Mikrotik"""
        self.ds["netwatch"] = parse_api(
            data=self.ds["netwatch"],
            source=self.api.query("/tool/netwatch"),
            key="host",
            vals=[
                {"name": "host"},
                {"name": "type"},
                {"name": "interval"},
                {"name": "port"},
                {"name": "http-codes"},
                {"name": "status", "type": "bool", "default": "unknown"},
                {"name": "comment"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
        )

    # ---------------------------
    #   get_system_routerboard
    # ---------------------------
    def get_system_routerboard(self) -> None:
        """Get routerboard data from Mikrotik"""
        if self.ds["resource"]["board-name"].startswith("x86") or self.ds["resource"]["board-name"].startswith("CHR"):
            self.ds["routerboard"]["routerboard"] = False
            self.ds["routerboard"]["model"] = self.ds["resource"]["board-name"]
            self.ds["routerboard"]["serial-number"] = "N/A"
        else:
            self.ds["routerboard"] = parse_api(
                data=self.ds["routerboard"],
                source=self.api.query("/system/routerboard"),
                vals=[
                    {"name": "routerboard", "type": "bool"},
                    {"name": "model", "default": "unknown"},
                    {"name": "serial-number", "default": "unknown"},
                    {"name": "current-firmware", "default": "unknown"},
                    {"name": "upgrade-firmware", "default": "unknown"},
                ],
            )

            if "write" not in self.ds["access"] or "policy" not in self.ds["access"] or "reboot" not in self.ds["access"]:
                self.ds["routerboard"].pop("current-firmware")
                self.ds["routerboard"].pop("upgrade-firmware")

    # ---------------------------
    #   get_system_health
    # ---------------------------
    def get_system_health(self) -> None:
        """Get routerboard data from Mikrotik"""
        if "write" not in self.ds["access"] or "policy" not in self.ds["access"] or "reboot" not in self.ds["access"]:
            return

        if 0 < self.major_fw_version < 7:
            self.ds["health"] = parse_api(
                data=self.ds["health"],
                source=self.api.query("/system/health"),
                vals=[
                    {"name": "temperature", "default": 0},
                    {"name": "voltage", "default": 0},
                    {"name": "cpu-temperature", "default": 0},
                    {"name": "power-consumption", "default": 0},
                    {"name": "board-temperature1", "default": 0},
                    {"name": "phy-temperature", "default": 0},
                    {"name": "fan1-speed", "default": 0},
                    {"name": "fan2-speed", "default": 0},
                    {"name": "poe-in-voltage", "default": 0},
                    {"name": "poe-in-current", "default": 0},
                ],
            )
        elif 0 < self.major_fw_version >= 7:
            self.ds["health7"] = parse_api(
                data=self.ds["health7"],
                source=self.api.query("/system/health"),
                key="name",
                vals=[
                    {"name": "value", "default": "unknown"},
                ],
            )
            if self.ds["health7"]:
                for uid, vals in self.ds["health7"].items():
                    self.ds["health"][uid] = vals["value"]

    # ---------------------------
    #   get_system_resource
    # ---------------------------
    def get_system_resource(self) -> None:
        """Get system resources data from Mikrotik"""
        self.ds["resource"] = parse_api(
            data=self.ds["resource"],
            source=self.api.query("/system/resource"),
            vals=[
                {"name": "platform", "default": "unknown"},
                {"name": "board-name", "default": "unknown"},
                {"name": "version", "default": "unknown"},
                {"name": "uptime_str", "source": "uptime", "default": "unknown"},
                {"name": "cpu-load", "default": "unknown"},
                {"name": "free-memory", "default": 0},
                {"name": "total-memory", "default": 0},
                {"name": "free-hdd-space", "default": 0},
                {"name": "total-hdd-space", "default": 0},
            ],
            ensure_vals=[
                {"name": "uptime", "default": 0},
                {"name": "uptime_epoch", "default": 0},
                {"name": "clients_wired", "default": 0},
                {"name": "clients_wireless", "default": 0},
                {"name": "captive_authorized", "default": 0},
            ],
        )

        tmp_uptime = _parse_uptime_to_seconds(self.ds["resource"]["uptime_str"])

        self.ds["resource"]["uptime_epoch"] = tmp_uptime
        now = dt_now().replace(microsecond=0)
        uptime_tm = datetime.timestamp(now - timedelta(seconds=tmp_uptime))
        update_uptime = False
        if not self.ds["resource"]["uptime"]:
            update_uptime = True
        else:
            uptime_old = datetime.timestamp(self.ds["resource"]["uptime"])
            if uptime_tm > uptime_old + 10:
                update_uptime = True

        if update_uptime:
            self.ds["resource"]["uptime"] = utc_from_timestamp(uptime_tm)

        if self.ds["resource"]["total-memory"] > 0:
            self.ds["resource"]["memory-usage"] = round(((self.ds["resource"]["total-memory"] - self.ds["resource"]["free-memory"]) / self.ds["resource"]["total-memory"]) * 100)
        else:
            self.ds["resource"]["memory-usage"] = "unknown"

        if self.ds["resource"]["total-hdd-space"] > 0:
            self.ds["resource"]["hdd-usage"] = round(((self.ds["resource"]["total-hdd-space"] - self.ds["resource"]["free-hdd-space"]) / self.ds["resource"]["total-hdd-space"]) * 100)
        else:
            self.ds["resource"]["hdd-usage"] = "unknown"

        if "uptime_epoch" in self.ds["resource"] and self.rebootcheck > self.ds["resource"]["uptime_epoch"]:
            self.get_firmware_update()

        if "uptime_epoch" in self.ds["resource"]:
            self.rebootcheck = self.ds["resource"]["uptime_epoch"]

    # ---------------------------
    #   get_firmware_update
    # ---------------------------
    def get_firmware_update(self) -> None:
        """Check for firmware update on Mikrotik"""
        if "write" not in self.ds["access"] or "policy" not in self.ds["access"] or "reboot" not in self.ds["access"]:
            return

        self.execute("/system/package/update", "check-for-updates", None, None, {"duration": 10})
        self.ds["fw-update"] = parse_api(
            data=self.ds["fw-update"],
            source=self.api.query("/system/package/update"),
            vals=[
                {"name": "status"},
                {"name": "channel", "default": "unknown"},
                {"name": "installed-version", "default": "unknown"},
                {"name": "latest-version", "default": "unknown"},
            ],
        )

        if "status" in self.ds["fw-update"]:
            self.ds["fw-update"]["available"] = self.ds["fw-update"]["status"] == "New version is available"

        else:
            self.ds["fw-update"]["available"] = False

        if self.ds["fw-update"]["installed-version"] != "unknown":
            try:
                full_version = self.ds["fw-update"].get("installed-version")
                split_end = min(len(full_version), 4)
                version = re.sub("[^0-9\\.]", "", full_version[0:split_end])
                version_parts = version.split(".")
                self.major_fw_version = int(version_parts[0])
                self.minor_fw_version = int(version_parts[1]) if len(version_parts) > 1 else 0
                _LOGGER.debug(
                    "Mikrotik %s FW version major=%s minor=%s (%s)",
                    self.host,
                    self.major_fw_version,
                    self.minor_fw_version,
                    full_version,
                )
            except (ValueError, IndexError) as e:
                _LOGGER.warning(
                    "Mikrotik %s unable to determine FW version from '%s' (%s); some features may be disabled until next successful parse",
                    self.host,
                    full_version,
                    e,
                )

    # ---------------------------
    #   get_ups
    # ---------------------------
    def get_ups(self) -> None:
        """Get UPS info from Mikrotik"""
        ups_source = self.api.query("/system/ups")
        if not ups_source:
            self.ds["ups"] = {}
            return

        self.ds["ups"] = parse_api(
            data=self.ds["ups"],
            source=ups_source,
            vals=[
                {"name": "name", "default": "unknown"},
                {"name": "offline-time", "default": "unknown"},
                {"name": "min-runtime", "default": "unknown"},
                {"name": "alarm-setting", "default": "unknown"},
                {"name": "model", "default": "unknown"},
                {"name": "serial", "default": "unknown"},
                {"name": "manufacture-date", "default": "unknown"},
                {"name": "nominal-battery-voltage", "default": "unknown"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
            ensure_vals=[
                {"name": "on-line", "type": "bool"},
                {"name": "runtime-left", "default": "unknown"},
                {"name": "battery-charge", "default": 0},
                {"name": "battery-voltage", "default": 0.0},
                {"name": "line-voltage", "default": 0},
                {"name": "load", "default": 0},
                {"name": "hid-self-test", "default": "unknown"},
            ],
        )
        if self.ds["ups"].get("enabled"):
            self.ds["ups"] = parse_api(
                data=self.ds["ups"],
                source=self.api.query(
                    "/system/ups",
                    command="monitor",
                    args={".id": 0, "once": True},
                ),
                vals=[
                    {"name": "on-line", "type": "bool"},
                    {"name": "runtime-left", "default": 0},
                    {"name": "battery-charge", "default": 0},
                    {"name": "battery-voltage", "default": 0.0},
                    {"name": "line-voltage", "default": 0},
                    {"name": "load", "default": 0},
                    {"name": "hid-self-test", "default": "unknown"},
                ],
            )

    # ---------------------------
    #   get_gps
    # ---------------------------
    def get_gps(self) -> None:
        """Get GPS data from Mikrotik"""
        self.ds["gps"] = parse_api(
            data=self.ds["gps"],
            source=self.api.query(
                "/system/gps",
                command="monitor",
                args={"once": True},
            ),
            vals=[
                {"name": "valid", "type": "bool"},
                {"name": "latitude", "default": "unknown"},
                {"name": "longitude", "default": "unknown"},
                {"name": "altitude", "default": "unknown"},
                {"name": "speed", "default": "unknown"},
                {"name": "destination-bearing", "default": "unknown"},
                {"name": "true-bearing", "default": "unknown"},
                {"name": "magnetic-bearing", "default": "unknown"},
                {"name": "satellites", "default": 0},
                {"name": "fix-quality", "default": 0},
                {"name": "horizontal-dilution", "default": "unknown"},
            ],
        )

    # ---------------------------
    #   get_script
    # ---------------------------
    def get_script(self) -> None:
        """Get list of all scripts from Mikrotik"""
        self.ds["script"] = parse_api(
            data=self.ds["script"],
            source=self.api.query("/system/script"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "last-started", "default": "unknown"},
                {"name": "run-count", "default": "unknown"},
            ],
        )

    # ---------------------------
    #   get_environment
    # ---------------------------
    def get_environment(self) -> None:
        """Get list of all environment variables from Mikrotik"""
        self.ds["environment"] = parse_api(
            data=self.ds["environment"],
            source=self.api.query("/system/script/environment"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "value"},
            ],
        )

    # ---------------------------
    #   get_captive
    # ---------------------------
    def get_captive(self) -> None:
        """Get list of all environment variables from Mikrotik"""
        self.ds["hostspot_host"] = parse_api(
            data={},
            source=self.api.query("/ip/hotspot/host"),
            key="mac-address",
            vals=[
                {"name": "mac-address"},
                {"name": "authorized", "type": "bool"},
                {"name": "bypassed", "type": "bool"},
            ],
        )

        auth_hosts = sum(1 for uid in self.ds["hostspot_host"] if self.ds["hostspot_host"][uid]["authorized"])
        self.ds["resource"]["captive_authorized"] = auth_hosts

    # ---------------------------
    #   get_queue
    # ---------------------------
    def get_queue(self) -> None:
        """Get Queue data from Mikrotik"""
        self.ds["queue"] = parse_api(
            data=self.ds["queue"],
            source=self.api.query("/queue/simple"),
            key="name",
            vals=[
                {"name": ".id"},
                {"name": "name", "default": "unknown"},
                {"name": "target", "default": "unknown"},
                {"name": "rate", "default": "0/0"},
                {"name": "max-limit", "default": "0/0"},
                {"name": "limit-at", "default": "0/0"},
                {"name": "burst-limit", "default": "0/0"},
                {"name": "burst-threshold", "default": "0/0"},
                {"name": "burst-time", "default": "0s/0s"},
                {"name": "packet-marks", "default": "none"},
                {"name": "parent", "default": "none"},
                {"name": "comment"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
        )

        for uid, vals in self.ds["queue"].items():
            self.ds["queue"][uid]["comment"] = str(self.ds["queue"][uid]["comment"])
            try:
                self._parse_queue_values(uid, vals)
            except (ValueError, IndexError) as e:
                _LOGGER.warning(
                    "Queue %s has unexpected value format (%s), skipping",
                    uid,
                    e,
                )

    @staticmethod
    def _parse_queue_pair(raw: str) -> tuple[str, str]:
        """Split an 'upload/download' value and format as bps strings."""
        up, down = (int(x) for x in raw.split("/"))
        return f"{up} bps", f"{down} bps"

    def _parse_queue_values(self, uid: str, vals: dict) -> None:
        """Parse all queue rate/limit fields for a single entry."""
        q = self.ds["queue"][uid]
        for field, up_key, down_key in [
            ("max-limit", "upload-max-limit", "download-max-limit"),
            ("rate", "upload-rate", "download-rate"),
            ("limit-at", "upload-limit-at", "download-limit-at"),
            ("burst-limit", "upload-burst-limit", "download-burst-limit"),
            ("burst-threshold", "upload-burst-threshold", "download-burst-threshold"),
        ]:
            q[up_key], q[down_key] = self._parse_queue_pair(vals[field])

        upload_burst_time, download_burst_time = vals["burst-time"].split("/")
        q["upload-burst-time"] = upload_burst_time
        q["download-burst-time"] = download_burst_time

    # ---------------------------
    #   get_arp
    # ---------------------------
    def get_arp(self) -> None:
        """Get ARP data from Mikrotik"""
        self.ds["arp"] = parse_api(
            data={},
            source=self.api.query("/ip/arp"),
            key="mac-address",
            vals=[
                {"name": "mac-address"},
                {"name": "address"},
                {"name": "interface"},
                {"name": "status", "default": ""},
            ],
            ensure_vals=[{"name": "bridge", "default": ""}],
        )

        for uid, vals in self.ds["arp"].items():
            if vals["interface"] in self.ds["bridge"] and uid in self.ds["bridge_host"]:
                self.ds["arp"][uid]["bridge"] = vals["interface"]
                self.ds["arp"][uid]["interface"] = self.ds["bridge_host"][uid]["interface"]

        if self.ds["dhcp-client"]:
            to_remove = [uid for uid, vals in self.ds["arp"].items() if vals["interface"] in self.ds["dhcp-client"]]

            for uid in to_remove:
                self.ds["arp"].pop(uid)

    # ---------------------------
    #   get_dns
    # ---------------------------
    def get_dns(self) -> None:
        """Get static DNS data from Mikrotik"""
        self.ds["dns"] = parse_api(
            data=self.ds["dns"],
            source=self.api.query("/ip/dns/static"),
            key="name",
            vals=[{"name": "name"}, {"name": "address"}, {"name": "comment"}],
        )

        for uid, vals in self.ds["dns"].items():
            self.ds["dns"][uid]["comment"] = str(self.ds["dns"][uid]["comment"])

    # ---------------------------
    #   get_dhcp
    # ---------------------------
    def get_dhcp(self) -> None:
        """Get DHCP data from Mikrotik"""
        self.ds["dhcp"] = parse_api(
            data=self.ds["dhcp"],
            source=self.api.query("/ip/dhcp-server/lease"),
            key="mac-address",
            vals=[
                {"name": "mac-address"},
                {"name": "active-mac-address", "default": "unknown"},
                {"name": "address", "default": "unknown"},
                {"name": "active-address", "default": "unknown"},
                {"name": "host-name", "default": "unknown"},
                {"name": "status", "default": "unknown"},
                {"name": "last-seen", "default": "unknown"},
                {"name": "server", "default": "unknown"},
                {"name": "comment", "default": ""},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
            ensure_vals=[{"name": "interface", "default": "unknown"}],
        )

        dhcpserver_query = False
        for uid in self.ds["dhcp"]:
            self.ds["dhcp"][uid]["comment"] = str(self.ds["dhcp"][uid]["comment"])
            self._normalize_dhcp_lease(uid)
            dhcpserver_query = self._resolve_dhcp_interface(uid, dhcpserver_query)

        self._count_leases_per_server()

    def _normalize_dhcp_lease(self, uid: str) -> None:
        """Validate and normalize address/MAC for a single DHCP lease."""
        lease = self.ds["dhcp"][uid]
        if lease["address"] == "unknown":
            return

        if not is_valid_ip(lease["address"]):
            lease["address"] = "unknown"
            return

        if lease["active-address"] not in (lease["address"], "unknown"):
            lease["address"] = lease["active-address"]

        if lease["mac-address"] != lease["active-mac-address"] != "unknown":
            lease["mac-address"] = lease["active-mac-address"]

    def _resolve_dhcp_interface(self, uid: str, dhcpserver_queried: bool) -> bool:
        """Resolve interface for a DHCP lease from server or ARP data."""
        lease = self.ds["dhcp"][uid]
        if not dhcpserver_queried and lease["server"] not in self.ds["dhcp-server"]:
            self.get_dhcp_server()
            dhcpserver_queried = True

        if lease["server"] in self.ds["dhcp-server"]:
            lease["interface"] = self.ds["dhcp-server"][lease["server"]]["interface"]
        elif uid in self.ds["arp"]:
            arp = self.ds["arp"][uid]
            lease["interface"] = arp["bridge"] if arp["bridge"] != "unknown" else arp["interface"]

        return dhcpserver_queried

    def _count_leases_per_server(self) -> None:
        """Count active leases per DHCP server."""
        for server_name in self.ds["dhcp-server"]:
            self.ds["dhcp-server"][server_name]["lease-count"] = 0
        for uid in self.ds["dhcp"]:
            server = self.ds["dhcp"][uid].get("server", "unknown")
            if server in self.ds["dhcp-server"]:
                self.ds["dhcp-server"][server]["lease-count"] += 1

    # ---------------------------
    #   get_dhcp_server
    # ---------------------------
    def get_dhcp_server(self) -> None:
        """Get DHCP server data from Mikrotik"""
        self.ds["dhcp-server"] = parse_api(
            data=self.ds["dhcp-server"],
            source=self.api.query("/ip/dhcp-server"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "interface", "default": "unknown"},
                {"name": "address-pool", "default": "unknown"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
                {"name": "comment", "default": ""},
            ],
            ensure_vals=[
                {"name": "lease-count", "default": 0},
                {"name": "status", "default": "unknown"},
            ],
        )

        for uid in self.ds["dhcp-server"]:
            self.ds["dhcp-server"][uid]["status"] = "enabled" if self.ds["dhcp-server"][uid]["enabled"] else "disabled"

    # ---------------------------
    #   get_dhcp_client
    # ---------------------------
    def get_dhcp_client(self) -> None:
        """Get DHCP client data from Mikrotik"""
        self.ds["dhcp-client"] = parse_api(
            data=self.ds["dhcp-client"],
            source=self.api.query("/ip/dhcp-client"),
            key="interface",
            vals=[
                {"name": "interface", "default": "unknown"},
                {"name": "status", "default": "unknown"},
                {"name": "address", "default": "unknown"},
                {"name": "gateway", "default": "unknown"},
                {"name": "dns-server", "default": "unknown"},
                {"name": "dhcp-server", "default": "unknown"},
                {"name": "expires-after", "default": "unknown"},
                {"name": "comment", "default": ""},
            ],
        )

    # ---------------------------
    #   get_dhcp_network
    # ---------------------------
    def get_dhcp_network(self) -> None:
        """Get DHCP network data from Mikrotik"""
        self.ds["dhcp-network"] = parse_api(
            data=self.ds["dhcp-network"],
            source=self.api.query("/ip/dhcp-server/network"),
            key="address",
            vals=[
                {"name": "address"},
                {"name": "gateway", "default": ""},
                {"name": "netmask", "default": ""},
                {"name": "dns-server", "default": ""},
                {"name": "domain", "default": ""},
            ],
            ensure_vals=[{"name": "address"}, {"name": "IPv4Network", "default": ""}],
        )

        for uid, vals in self.ds["dhcp-network"].items():
            if vals["IPv4Network"] == "":
                self.ds["dhcp-network"][uid]["IPv4Network"] = IPv4Network(vals["address"])

    # ---------------------------
    #   get_capsman_hosts
    # ---------------------------
    # Field lists shared between primary and fallback endpoint probing.
    # /caps-man/ returns the full payload (RSSI/rates/uptime/bytes/packets/last-ip/eap);
    # /interface/wifi/ field schema isn't yet verified from a live device, so the
    # conservative shape ships first and expands once a v7.13+ payload is observed.
    _CAPSMAN_VALS_LEGACY = (
        {"name": "mac-address"},
        {"name": "interface", "default": "unknown"},
        {"name": "ssid", "default": "unknown"},
        {"name": "rx-signal", "default": "unknown"},
        {"name": "tx-rate", "default": "unknown"},
        {"name": "rx-rate", "default": "unknown"},
        {"name": "tx-rate-set", "default": "unknown"},
        {"name": "uptime", "default": "unknown"},
        {"name": "bytes", "default": "unknown"},
        {"name": "packets", "default": "unknown"},
        {"name": "last-ip", "default": "unknown"},
        {"name": "eap-identity", "default": "unknown"},
    )
    _CAPSMAN_VALS_WIFI = (
        {"name": "mac-address"},
        {"name": "interface", "default": "unknown"},
        {"name": "ssid", "default": "unknown"},
    )
    _CAPSMAN_LEGACY_PATH = "/caps-man/registration-table"
    _CAPSMAN_WIFI_PATH = "/interface/wifi/registration-table"

    def get_capsman_hosts(self) -> None:
        """Get CAPS-MAN hosts data from Mikrotik with dual-endpoint fallback.

        RouterOS exposes two overlapping endpoints:
        - `/caps-man/registration-table` (legacy CAPsMAN — full metrics).
        - `/interface/wifi/registration-table` (new WiFi package on v7.13+).

        The version-based primary picks the modern endpoint on v7.13+, legacy
        on v6 / v7 ≤ 12. But some v7.13+ users (#68 @fuecy on RouterOS 7.21.4)
        still run legacy CAPsMAN — their version-preferred endpoint returns
        empty. We probe primary first; if it returns no rows, fall back to
        the other endpoint and log so the operator can confirm the fallback
        is firing in their environment.
        """
        endpoints = self._capsman_endpoints_to_probe()
        chosen_path = None
        for path, vals in endpoints:
            self.ds["capsman_hosts"] = self._fetch_capsman_table(path, list(vals))
            if self.ds["capsman_hosts"]:
                chosen_path = path
                break

        # If we fell back to a non-preferred endpoint, log the transition so
        # users can correlate the new attribute showing up with the fallback.
        if chosen_path is not None and chosen_path != endpoints[0][0]:
            _LOGGER.info(
                "CAPsMAN endpoint fallback: primary %s returned no rows, using %s instead",
                endpoints[0][0],
                chosen_path,
            )

        # parse_api doesn't support field aliasing; rename rx-signal to
        # signal-strength so the rest of the integration sees one key.
        if chosen_path == self._CAPSMAN_LEGACY_PATH:
            for host_vals in self.ds["capsman_hosts"].values():
                host_vals["signal-strength"] = host_vals.pop("rx-signal", "unknown")

    def _capsman_endpoints_to_probe(self) -> list[tuple[str, tuple]]:
        """Return capsman endpoints to probe in preference order.

        v7.13+ → wifi first, caps-man fallback.
        v6 / v7 ≤ 12 → caps-man only (wifi endpoint doesn't exist there).
        """
        if self.major_fw_version > 7 or (self.major_fw_version == 7 and self.minor_fw_version >= 13):
            return [
                (self._CAPSMAN_WIFI_PATH, self._CAPSMAN_VALS_WIFI),
                (self._CAPSMAN_LEGACY_PATH, self._CAPSMAN_VALS_LEGACY),
            ]
        return [(self._CAPSMAN_LEGACY_PATH, self._CAPSMAN_VALS_LEGACY)]

    def _fetch_capsman_table(self, path: str, vals: list) -> dict:
        """Query one capsman endpoint and return parsed rows (empty on no data)."""
        return parse_api(
            data={},
            source=self.api.query(path),
            key="mac-address",
            vals=vals,
        )

    # ---------------------------
    #   get_wireless
    # ---------------------------
    def get_wireless(self) -> None:
        """Get wireless data from Mikrotik"""

        self.ds["wireless"] = parse_api(
            data=self.ds["wireless"],
            source=self.api.query(f"/interface/{self._wifimodule}"),
            key="name",
            vals=[
                {"name": "master-interface", "default": ""},
                {"name": "mac-address", "default": "unknown"},
                {"name": "ssid", "default": "unknown"},
                {"name": "mode", "default": "unknown"},
                {"name": "radio-name", "default": "unknown"},
                {"name": "interface-type", "default": "unknown"},
                {"name": "country", "default": "unknown"},
                {"name": "installation", "default": "unknown"},
                {"name": "antenna-gain", "default": "unknown"},
                {"name": "frequency", "default": "unknown"},
                {"name": "band", "default": "unknown"},
                {"name": "channel-width", "default": "unknown"},
                {"name": "secondary-frequency", "default": "unknown"},
                {"name": "wireless-protocol", "default": "unknown"},
                {"name": "rate-set", "default": "unknown"},
                {"name": "distance", "default": "unknown"},
                {"name": "tx-power-mode", "default": "unknown"},
                {"name": "vlan-id", "default": "unknown"},
                {"name": "wds-mode", "default": "unknown"},
                {"name": "wds-default-bridge", "default": "unknown"},
                {"name": "bridge-mode", "default": "unknown"},
                {"name": "hide-ssid", "type": "bool"},
                {"name": "running", "type": "bool"},
                {"name": "disabled", "type": "bool"},
            ],
        )

        for uid in self.ds["wireless"]:
            if self.ds["wireless"][uid]["master-interface"]:
                for tmp in self.ds["wireless"][uid]:
                    if self.ds["wireless"][uid][tmp] == "unknown":
                        self.ds["wireless"][uid][tmp] = self.ds["wireless"][self.ds["wireless"][uid]["master-interface"]][tmp]

            if uid in self.ds["interface"]:
                for tmp in self.ds["wireless"][uid]:
                    self.ds["interface"][uid][tmp] = self.ds["wireless"][uid][tmp]

    # ---------------------------
    #   get_wireless_hosts
    # ---------------------------
    def get_wireless_hosts(self) -> None:
        """Get wireless hosts data from Mikrotik"""
        self.ds["wireless_hosts"] = parse_api(
            data={},
            source=self.api.query(f"/interface/{self._wifimodule}/registration-table"),
            key="mac-address",
            vals=[
                {"name": "mac-address"},
                {"name": "interface", "default": "unknown"},
                {"name": "ap", "type": "bool"},
                {"name": "uptime"},
                {"name": "signal-strength"},
                {"name": "tx-ccq"},
                {"name": "tx-rate"},
                {"name": "rx-rate"},
            ],
        )

    # ---------------------------
    #   _merge_capsman_hosts
    # ---------------------------
    def _merge_capsman_hosts(self) -> dict:
        """Merge CAPS-MAN hosts into ds['host'] and return detected set.

        Two-path logic (see ADR-011):
        - New host: claim with source="capsman", write full record including
          the AP-virtual interface name in `interface` AND `capsman-interface`.
        - Existing host (any source): always write `capsman-interface` and any
          available wireless metrics so the AP identity is recoverable even
          when DHCP/ARP claimed the host first; do not overwrite `source` or
          `interface` (preserves automations that filter on those keys).
          `available`/`last-seen` are updated only when this host is itself
          capsman-sourced.
        """
        detected = {}
        if not self.support_capsman:
            return detected

        for uid, vals in self.ds["capsman_hosts"].items():
            if uid not in self.ds["host"]:
                self.ds["host"][uid] = {"source": "capsman"}
                self._write_capsman_claim(uid, vals)
                detected[uid] = True
            else:
                self._write_capsman_overlay(uid, vals)
                if self.ds["host"][uid]["source"] == "capsman":
                    detected[uid] = True

        return detected

    def _write_capsman_claim(self, uid: str, vals: dict) -> None:
        """Write a full host record for a capsman-claimed host."""
        self.ds["host"][uid]["available"] = True
        self.ds["host"][uid]["last-seen"] = utcnow()
        self.ds["host"][uid]["mac-address"] = vals["mac-address"]
        self.ds["host"][uid]["interface"] = vals["interface"]
        self.ds["host"][uid]["capsman-interface"] = vals["interface"]
        self._copy_capsman_metrics(uid, vals)

    def _write_capsman_overlay(self, uid: str, vals: dict) -> None:
        """Overlay capsman-interface + wireless metrics on an existing host.

        Does not touch `source` or `interface` — those are owned by whichever
        merge claimed the host first. Updates availability only if the host
        is itself capsman-sourced (otherwise the owning source manages it).
        """
        self.ds["host"][uid]["capsman-interface"] = vals["interface"]
        self._copy_capsman_metrics(uid, vals)
        if self.ds["host"][uid]["source"] == "capsman":
            self.ds["host"][uid]["available"] = True
            self.ds["host"][uid]["last-seen"] = utcnow()

    def _copy_capsman_metrics(self, uid: str, vals: dict) -> None:
        """Copy optional wireless metric fields from capsman vals (v6 / v7≤12 only)."""
        for key in ("signal-strength", "tx-rate", "rx-rate"):
            if key in vals:
                self.ds["host"][uid][key] = vals[key]

    # ---------------------------
    #   _merge_wireless_hosts
    # ---------------------------
    def _merge_wireless_hosts(self) -> dict:
        """Merge wireless hosts into ds['host'] and return detected set."""
        detected = {}
        if not self.support_wireless:
            return detected

        for uid, vals in self.ds["wireless_hosts"].items():
            if vals["ap"]:
                continue

            if uid not in self.ds["host"]:
                self.ds["host"][uid] = {"source": "wireless"}
            elif self.ds["host"][uid]["source"] != "wireless":
                continue

            detected[uid] = True
            self.ds["host"][uid]["available"] = True
            self.ds["host"][uid]["last-seen"] = utcnow()
            for key in [
                "mac-address",
                "interface",
                "signal-strength",
                "tx-ccq",
                "tx-rate",
                "rx-rate",
            ]:
                self.ds["host"][uid][key] = vals[key]

        return detected

    # ---------------------------
    #   _merge_dhcp_hosts
    # ---------------------------
    def _merge_dhcp_hosts(self) -> None:
        """Merge DHCP hosts into ds['host']."""
        for uid, vals in self.ds["dhcp"].items():
            if not vals["enabled"]:
                continue

            if uid not in self.ds["host"]:
                self.ds["host"][uid] = {"source": "dhcp"}
            elif self.ds["host"][uid]["source"] != "dhcp":
                continue

            for key in ["address", "mac-address", "interface"]:
                self.ds["host"][uid][key] = vals[key]

    # ---------------------------
    #   _merge_arp_hosts
    # ---------------------------
    # RouterOS ARP statuses (Linux neighbor table states):
    #   ""          – static entry or no explicit status  → reachable
    #   reachable   – confirmed via ARP reply             → reachable
    #   stale       – previously reachable, not refreshed → reachable
    #   delay       – waiting for confirmation probe      → reachable (transitional)
    #   probe       – actively sending ARP probes         → reachable (transitional)
    #   noarp       – interface doesn't use ARP           → reachable
    #   incomplete  – ARP request sent, no reply yet      → UNREACHABLE
    #   failed      – ARP resolution failed               → UNREACHABLE
    _ARP_UNREACHABLE_STATUSES = frozenset({"failed", "incomplete"})

    def _merge_arp_hosts(self) -> dict:
        """Merge ARP hosts into ds['host'] and return detected set.

        Only count reachable ARP entries as detected — failed/incomplete
        entries indicate the device is unreachable (#17).  We keep all
        entries in ds["arp"] so that bridge-interface lookups still work
        for the tracker coordinator's ping logic.
        """
        detected = {}
        for uid, vals in self.ds["arp"].items():
            if vals.get("status") not in self._ARP_UNREACHABLE_STATUSES:
                detected[uid] = True
            if uid not in self.ds["host"]:
                self.ds["host"][uid] = {"source": "arp"}
            elif self.ds["host"][uid]["source"] != "arp":
                continue

            for key in ["address", "mac-address", "interface"]:
                self.ds["host"][uid][key] = vals[key]

        return detected

    # ---------------------------
    #   _merge_bridge_hosts
    # ---------------------------
    def _merge_bridge_hosts(self) -> dict:
        """Merge bridge host table entries into ds['host'] and return detected set.

        On bridged APs (e.g. hAP ac2), the ARP table is on the gateway router,
        not the AP. The bridge host table is the only source of connected client
        MACs. This creates host entries for MACs not already discovered by
        wireless registration, DHCP, or ARP merges.
        """
        detected = {}
        for uid, vals in self.ds["bridge_host"].items():
            detected[uid] = True
            if uid not in self.ds["host"]:
                self.ds["host"][uid] = {
                    "source": "bridge",
                    "mac-address": uid,
                    "address": "unknown",
                    "interface": vals.get("interface", "unknown"),
                }
            elif self.ds["host"][uid]["source"] == "bridge":
                self.ds["host"][uid]["interface"] = vals.get("interface", "unknown")

        return detected

    # ---------------------------
    #   _recover_hass_hosts
    # ---------------------------
    def _recover_hass_hosts(self) -> None:
        """Restore hosts from the HA entity registry (one-time)."""
        if self.host_hass_recovered:
            return

        self.host_hass_recovered = True
        for uid in self.ds["host_hass"]:
            if uid not in self.ds["host"]:
                self.ds["host"][uid] = {"source": "restored"}
                self.ds["host"][uid]["mac-address"] = uid
                self.ds["host"][uid]["host-name"] = self.ds["host_hass"][uid]

    # ---------------------------
    #   _ensure_host_defaults
    # ---------------------------
    _HOST_DEFAULTS = {
        "address": "unknown",
        "mac-address": "unknown",
        "interface": "unknown",
        "host-name": "unknown",
        "manufacturer": "detect",
        "last-seen": False,
        "available": False,
        "is_wireless": False,
    }

    def _ensure_host_defaults(self) -> None:
        """Fill missing default values for all hosts."""
        for uid in self.ds["host"]:
            for key, default in self._HOST_DEFAULTS.items():
                if key not in self.ds["host"][uid]:
                    self.ds["host"][uid][key] = default

    # ---------------------------
    #   _update_host_availability
    # ---------------------------
    def _update_host_availability(
        self,
        uid,
        vals,
        capsman_detected,
        wireless_detected,
        arp_detected,
        bridge_detected,
    ) -> None:
        """Set availability based on source and detection state."""
        source = vals["source"]
        if source == "capsman" and uid not in capsman_detected:
            self.ds["host"][uid]["available"] = False
        elif source == "wireless" and uid not in wireless_detected:
            self.ds["host"][uid]["available"] = False
        elif source == "bridge":
            if uid in bridge_detected:
                self.ds["host"][uid]["available"] = True
                self.ds["host"][uid]["last-seen"] = utcnow()
            else:
                self.ds["host"][uid]["available"] = False
        elif source in ["arp", "dhcp"]:
            if uid in arp_detected:
                self.ds["host"][uid]["available"] = True
                self.ds["host"][uid]["last-seen"] = utcnow()
            else:
                self.ds["host"][uid]["available"] = False

    # ---------------------------
    #   _update_host_address
    # ---------------------------
    def _update_host_address(self, uid, vals) -> None:
        """Update IP address and interface from DHCP or ARP."""
        if uid in self.ds["dhcp"] and self.ds["dhcp"][uid]["enabled"] and "." in self.ds["dhcp"][uid]["address"]:
            if self.ds["dhcp"][uid]["address"] != self.ds["host"][uid]["address"]:
                self.ds["host"][uid]["address"] = self.ds["dhcp"][uid]["address"]
                if vals["source"] not in ["capsman", "wireless"]:
                    self.ds["host"][uid]["source"] = "dhcp"
                    self.ds["host"][uid]["interface"] = self.ds["dhcp"][uid]["interface"]
        elif uid in self.ds["arp"] and "." in self.ds["arp"][uid]["address"] and self.ds["arp"][uid]["address"] != self.ds["host"][uid]["address"]:
            self.ds["host"][uid]["address"] = self.ds["arp"][uid]["address"]
            if vals["source"] not in ["capsman", "wireless"]:
                self.ds["host"][uid]["source"] = "arp"
                self.ds["host"][uid]["interface"] = self.ds["arp"][uid]["interface"]

    # ---------------------------
    #   _resolve_hostname
    # ---------------------------
    def _resolve_hostname(self, uid, vals) -> None:
        """Resolve hostname from DNS, DHCP comment, DHCP hostname, or MAC."""
        if vals["host-name"] != "unknown":
            return

        # Try static DNS first
        if vals["address"] != "unknown":
            dns_name = self._hostname_from_dns(uid, vals["address"])
            if dns_name:
                self.ds["host"][uid]["host-name"] = dns_name
                return

        self.ds["host"][uid]["host-name"] = self._hostname_from_dhcp(uid)

    # ---------------------------
    #   _hostname_from_dns
    # ---------------------------
    def _hostname_from_dns(self, uid, address) -> str | None:
        """Match address against static DNS and return the best hostname."""
        for dns_vals in self.ds["dns"].values():
            if dns_vals["address"] != address:
                continue

            dns_comment = dns_vals["comment"].split("#", 1)[0]
            if dns_comment:
                return dns_comment

            dhcp_comment = self._dhcp_comment_for_host(uid)
            if dhcp_comment:
                return dhcp_comment

            return dns_vals["name"].split(".")[0]

        return None

    # ---------------------------
    #   _hostname_from_dhcp
    # ---------------------------
    def _hostname_from_dhcp(self, uid) -> str:
        """Return hostname from DHCP comment, DHCP hostname, or fall back to MAC."""
        dhcp_comment = self._dhcp_comment_for_host(uid)
        if dhcp_comment:
            return dhcp_comment

        if uid in self.ds["dhcp"] and self.ds["dhcp"][uid]["enabled"] and self.ds["dhcp"][uid]["host-name"] != "unknown":
            return self.ds["dhcp"][uid]["host-name"]

        return uid

    # ---------------------------
    #   _dhcp_comment_for_host
    # ---------------------------
    def _dhcp_comment_for_host(self, uid) -> str | None:
        """Return the DHCP comment (before '#') if available, else None."""
        if uid not in self.ds["dhcp"] or not self.ds["dhcp"][uid]["enabled"]:
            return None
        comment = self.ds["dhcp"][uid]["comment"].split("#", 1)[0]
        return comment or None

    # ---------------------------
    #   _update_captive_portal
    # ---------------------------
    def _update_captive_portal(self, uid) -> None:
        """Sync captive portal data for a host."""
        if not self.option_sensor_client_captive:
            return

        if uid in self.ds["hostspot_host"]:
            self.ds["host"][uid]["authorized"] = self.ds["hostspot_host"][uid]["authorized"]
            self.ds["host"][uid]["bypassed"] = self.ds["hostspot_host"][uid]["bypassed"]
        elif "authorized" in self.ds["host"][uid]:
            del self.ds["host"][uid]["authorized"]
            del self.ds["host"][uid]["bypassed"]

    # ---------------------------
    #   _resolve_manufacturer
    # ---------------------------
    async def _resolve_manufacturer(self, uid: str, mac: str) -> None:
        """Resolve a single MAC address to a manufacturer name."""
        try:
            self.ds["host"][uid]["manufacturer"] = await self.async_mac_lookup.lookup(mac)
        except Exception as err:
            _LOGGER.debug("MAC vendor lookup failed for %s: %s", mac, err)
            self.ds["host"][uid]["manufacturer"] = ""

    # ---------------------------
    #   _is_wireless_host
    # ---------------------------
    def _is_wireless_host(self, uid: str, vals: dict, wireless_interfaces: set | None = None) -> bool:
        """Check if a host is connected via a wireless interface.

        Uses source, bridge host table, and wireless interface list to
        determine if a client is wireless — even when the registration
        table is empty (e.g. hAP ac2 with the new WiFi package).
        """
        if vals["source"] in ["capsman", "wireless"]:
            return True

        if wireless_interfaces is None:
            wireless_interfaces = self._build_wireless_interface_set()
        if not wireless_interfaces:
            return False

        if vals.get("interface") in wireless_interfaces:
            return True

        bridge_entry = self.ds.get("bridge_host", {}).get(uid)
        if bridge_entry and bridge_entry.get("interface") in wireless_interfaces:
            return True

        return False

    # ---------------------------
    #   _build_wireless_interface_set
    # ---------------------------
    def _build_wireless_interface_set(self) -> set:
        """Build set of wireless interface names from all available sources.

        Combines the wireless data store (populated by get_wireless) with
        interfaces whose type is 'wlan' from the interface data store.
        This handles routers where get_wireless queries the wrong wifi module
        (e.g. hAP ac2 using the old wireless module while the integration
        queries /interface/wifi).
        """
        ifaces = set(self.ds.get("wireless", {}))
        for name, vals in self.ds.get("interface", {}).items():
            if vals.get("type") == "wlan":
                ifaces.add(name)
        return ifaces

    # ---------------------------
    #   async_process_host
    # ---------------------------
    async def async_process_host(self) -> None:
        """Get host tracking data"""
        capsman_detected = self._merge_capsman_hosts()
        wireless_detected = self._merge_wireless_hosts()
        self._merge_dhcp_hosts()
        arp_detected = self._merge_arp_hosts()
        bridge_detected = self._merge_bridge_hosts()
        self._recover_hass_hosts()
        self._ensure_host_defaults()

        # Build wireless interface set once for the entire loop
        wireless_ifaces = self._build_wireless_interface_set()

        # Process hosts
        self.ds["resource"]["clients_wired"] = 0
        self.ds["resource"]["clients_wireless"] = 0
        mac_tasks: list[asyncio.Task] = []
        for uid, vals in self.ds["host"].items():
            self._update_captive_portal(uid)
            self._update_host_availability(
                uid,
                vals,
                capsman_detected,
                wireless_detected,
                arp_detected,
                bridge_detected,
            )
            self._update_host_address(uid, vals)
            self._resolve_hostname(uid, vals)

            if vals["manufacturer"] == "detect" and vals["mac-address"] != "unknown":
                mac_tasks.append(asyncio.create_task(self._resolve_manufacturer(uid, vals["mac-address"])))
            elif vals["manufacturer"] == "detect":
                self.ds["host"][uid]["manufacturer"] = ""

            is_wireless = self._is_wireless_host(uid, vals, wireless_ifaces)
            self.ds["host"][uid]["is_wireless"] = is_wireless

            if self.ds["host"][uid]["available"]:
                if is_wireless:
                    self.ds["resource"]["clients_wireless"] += 1
                else:
                    self.ds["resource"]["clients_wired"] += 1

        if mac_tasks:
            await asyncio.gather(*mac_tasks)

    # ---------------------------
    #   process_accounting
    # ---------------------------
    def _init_accounting_hosts(self) -> None:
        """Ensure all hosts have a client_traffic entry."""
        for uid, vals in self.ds["host"].items():
            if uid not in self.ds["client_traffic"]:
                self.ds["client_traffic"][uid] = {
                    "address": vals["address"],
                    "mac-address": vals["mac-address"],
                    "host-name": vals["host-name"],
                    "available": False,
                    "local_accounting": False,
                }

    # ---------------------------
    #   _classify_accounting_traffic
    # ---------------------------
    def _classify_accounting_traffic(self, accounting_data, tmp_values) -> None:
        """Classify each accounting entry into WAN/LAN TX/RX buckets."""
        for item in accounting_data.values():
            source_ip = str(item.get("src-address")).strip()
            destination_ip = str(item.get("dst-address")).strip()
            byte_count = int(str(item.get("bytes")).strip())

            src_local = self._address_part_of_local_network(source_ip)
            dst_local = self._address_part_of_local_network(destination_ip)

            self._add_traffic_bytes(tmp_values, source_ip, destination_ip, byte_count, src_local, dst_local)

    # ---------------------------
    #   _add_traffic_bytes
    # ---------------------------
    @staticmethod
    def _add_traffic_bytes(tmp_values, source_ip, destination_ip, byte_count, src_local, dst_local) -> None:
        """Add byte count to the appropriate WAN/LAN TX/RX bucket."""
        if src_local and dst_local:
            if source_ip in tmp_values:
                tmp_values[source_ip]["lan-tx"] += byte_count
            if destination_ip in tmp_values:
                tmp_values[destination_ip]["lan-rx"] += byte_count
        elif src_local:
            if source_ip in tmp_values:
                tmp_values[source_ip]["wan-tx"] += byte_count
        elif dst_local and destination_ip in tmp_values:
            tmp_values[destination_ip]["wan-rx"] += byte_count

    # ---------------------------
    #   _check_accounting_threshold
    # ---------------------------
    def _check_accounting_threshold(self, entry_count) -> None:
        """Log warning if accounting entries are near or at the threshold."""
        accounting_config = self.api.query("/ip/accounting")
        threshold = accounting_config[0].get("threshold") if accounting_config else None
        if threshold is None:
            return

        if entry_count == threshold:
            _LOGGER.warning(
                "Accounting entries count reached the threshold of %s!"
                " Some entries were not saved by Mikrotik so accounting calculation won't be correct."
                " Consider shortening update interval or"
                " increasing the accounting threshold value in Mikrotik.",
                threshold,
            )
        elif entry_count > threshold * 0.9:
            _LOGGER.info(
                "Accounting entries count (%s) reached 90%% of the threshold, currently set to %s! Consider shortening update interval or increasing the accounting threshold value in Mikrotik.",
                entry_count,
                threshold,
            )

    # ---------------------------
    #   _apply_accounting_throughput
    # ---------------------------
    @staticmethod
    def _calc_throughput(byte_count, time_diff) -> float:
        """Calculate throughput rate, returning 0.0 if inputs are zero."""
        return round(byte_count / time_diff) if byte_count and time_diff else 0.0

    def _apply_accounting_throughput(self, tmp_values, time_diff, accounting_enabled, local_traffic_enabled) -> None:
        """Calculate throughput from raw byte counters and update ds."""
        for addr, vals in tmp_values.items():
            uid = self._get_accounting_uid_by_ip(addr)
            if not uid:
                _LOGGER.warning(f"Address {addr} not found in accounting data, skipping update")
                continue

            ct = self.ds["client_traffic"][uid]
            ct["available"] = accounting_enabled
            ct["local_accounting"] = local_traffic_enabled

            if not accounting_enabled:
                continue

            ct["wan-tx"] = self._calc_throughput(vals["wan-tx"], time_diff)
            ct["wan-rx"] = self._calc_throughput(vals["wan-rx"], time_diff)

            if not local_traffic_enabled:
                continue

            ct["lan-tx"] = self._calc_throughput(vals["lan-tx"], time_diff)
            ct["lan-rx"] = self._calc_throughput(vals["lan-rx"], time_diff)

    # ---------------------------
    #   process_accounting
    # ---------------------------
    def process_accounting(self) -> None:
        """Get Accounting data from Mikrotik"""
        (
            accounting_enabled,
            local_traffic_enabled,
        ) = self.api.is_accounting_and_local_traffic_enabled()

        self._init_accounting_hosts()

        _LOGGER.debug(f"Working with {len(self.ds['client_traffic'])} accounting devices")

        tmp_accounting_values = {vals["address"]: {"wan-tx": 0, "wan-rx": 0, "lan-tx": 0, "lan-rx": 0} for vals in self.ds["client_traffic"].values()}

        time_diff = self.api.take_client_traffic_snapshot(True)
        if time_diff:
            accounting_data = parse_api(
                data={},
                source=self.api.query("/ip/accounting/snapshot"),
                key=".id",
                vals=[
                    {"name": ".id"},
                    {"name": "src-address"},
                    {"name": "dst-address"},
                    {"name": "bytes", "default": 0},
                ],
            )

            self._check_accounting_threshold(len(accounting_data))
            self._classify_accounting_traffic(accounting_data, tmp_accounting_values)

        self._apply_accounting_throughput(tmp_accounting_values, time_diff, accounting_enabled, local_traffic_enabled)

    # ---------------------------
    #   _address_part_of_local_network
    # ---------------------------
    def _address_part_of_local_network(self, address) -> bool:
        try:
            addr = ip_address(address)
        except ValueError:
            return False
        for vals in self.ds["dhcp-network"].values():
            if addr in vals["IPv4Network"]:
                return True
        return False

    # ---------------------------
    #   _get_accounting_uid_by_ip
    # ---------------------------
    def _get_accounting_uid_by_ip(self, requested_ip):
        for mac, vals in self.ds["client_traffic"].items():
            if vals.get("address") == requested_ip:
                return mac
        return None

    # ---------------------------
    #   _get_iface_from_entry
    # ---------------------------
    def _get_iface_from_entry(self, entry):
        """Get interface default-name using name from interface dict"""
        uid = None
        for ifacename in self.ds["interface"]:
            if self.ds["interface"][ifacename]["name"] == entry["interface"]:
                uid = ifacename
                break

        return uid

    # ---------------------------
    #   process_kid_control
    # ---------------------------
    def process_kid_control_devices(self) -> None:
        """Get Kid Control Device data from Mikrotik"""

        # Build missing hosts from main hosts dict
        for uid, vals in self.ds["host"].items():
            if uid not in self.ds["client_traffic"]:
                self.ds["client_traffic"][uid] = {
                    "address": vals["address"],
                    "mac-address": vals["mac-address"],
                    "host-name": vals["host-name"],
                    "previous-bytes-up": 0.0,
                    "previous-bytes-down": 0.0,
                    "tx": 0.0,
                    "rx": 0.0,
                    "available": False,
                    "local_accounting": False,
                }

        _LOGGER.debug(f"Working with {len(self.ds['client_traffic'])} kid control devices")

        kid_control_devices_data = parse_api(
            data={},
            source=self.api.query("/ip/kid-control/device"),
            key="mac-address",
            vals=[
                {"name": "mac-address"},
                {"name": "bytes-down"},
                {"name": "bytes-up"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
        )

        time_diff = self.api.take_client_traffic_snapshot(False)

        if not kid_control_devices_data:
            if "kid-control-devices" not in self.notified_flags:
                _LOGGER.error("No kid control devices found on your Mikrotik device, make sure kid-control feature is configured")
                self.notified_flags.append("kid-control-devices")
            return
        elif "kid-control-devices" in self.notified_flags:
            self.notified_flags.remove("kid-control-devices")

        for uid, vals in kid_control_devices_data.items():
            if uid not in self.ds["client_traffic"]:
                _LOGGER.debug(f"Skipping unknown device {uid}")
                continue

            self.ds["client_traffic"][uid]["available"] = vals["enabled"]

            current_tx = vals["bytes-up"]
            previous_tx = self.ds["client_traffic"][uid]["previous-bytes-up"]
            if time_diff:
                delta_tx = max(0, current_tx - previous_tx)
                self.ds["client_traffic"][uid]["tx"] = round(delta_tx / time_diff)
            self.ds["client_traffic"][uid]["previous-bytes-up"] = current_tx

            current_rx = vals["bytes-down"]
            previous_rx = self.ds["client_traffic"][uid]["previous-bytes-down"]
            if time_diff:
                delta_rx = max(0, current_rx - previous_rx)
                self.ds["client_traffic"][uid]["rx"] = round(delta_rx / time_diff)
            self.ds["client_traffic"][uid]["previous-bytes-down"] = current_rx
