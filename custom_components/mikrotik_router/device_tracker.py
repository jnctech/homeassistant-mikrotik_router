"""Support for the Mikrotik Router device tracker."""

from __future__ import annotations

from logging import getLogger
from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Callable

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import STATE_NOT_HOME
from homeassistant.helpers import entity_platform as ep
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from homeassistant.components.device_tracker.const import SourceType

from .coordinator import MikrotikCoordinator
from .device_tracker_types import (
    SENSOR_TYPES,  # noqa: F401
    SENSOR_SERVICES,  # noqa: F401
    DEVICE_ATTRIBUTES_HOST_WIRELESS,
)
from .entity import _run_entity_setup_loop, MikrotikEntity, copy_attrs
from .helper import format_attribute
from .const import (
    DOMAIN,
    CONF_TRACK_HOSTS,
    DEFAULT_TRACK_HOSTS,
    CONF_TRACK_HOSTS_TIMEOUT,
    DEFAULT_TRACK_HOST_TIMEOUT,
)

_LOGGER = getLogger(__name__)

# The coordinator centralises all polling; tracker updates perform no per-entity
# device I/O, so no parallelism limit is needed.
PARALLEL_UPDATES = 0


async def async_add_entities(hass: HomeAssistant, config_entry: ConfigEntry, dispatcher: dict[str, Callable]):
    """Add entities."""
    platform = ep.async_get_current_platform()
    services = platform.platform.SENSOR_SERVICES
    descriptions = platform.platform.SENSOR_TYPES

    for service in services:
        platform.async_register_entity_service(service[0], service[1], service[2])

    tracker_coord = hass.data[DOMAIN][config_entry.entry_id].tracker_coordinator

    @callback
    async def async_update_controller(coordinator):
        """Update the values of the controller."""
        if coordinator is not tracker_coord:
            return
        if coordinator.data is None:
            return
        await _run_entity_setup_loop(hass, platform, config_entry, dispatcher, descriptions, coordinator)

    await async_update_controller(tracker_coord)

    unsub = async_dispatcher_connect(hass, "update_sensors", async_update_controller)
    config_entry.async_on_unload(unsub)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    _async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for component"""
    dispatcher = {
        "MikrotikDeviceTracker": MikrotikDeviceTracker,
        "MikrotikHostDeviceTracker": MikrotikHostDeviceTracker,
    }
    await async_add_entities(hass, config_entry, dispatcher)


# ---------------------------
#   MikrotikDeviceTracker
# ---------------------------
class MikrotikDeviceTracker(MikrotikEntity, ScannerEntity):
    """Representation of a device tracker."""

    def __init__(
        self,
        coordinator: MikrotikCoordinator,
        entity_description,
        uid: str | None = None,
    ):
        """Initialize entity"""
        super().__init__(coordinator, entity_description, uid)
        self._attr_name = None

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._data["address"] if "address" in self._data else None

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        if self.entity_description.data_reference in self._data:
            return self._data[self.entity_description.data_reference]

        return ""

    @property
    def hostname(self) -> str:
        """Return hostname of the device."""
        if self.entity_description.data_name in self._data:
            return self._data[self.entity_description.data_name]

        return ""

    @property
    def is_connected(self) -> bool:
        """Return true if device is connected."""
        return self._data[self.entity_description.data_attribute]

    @property
    def source_type(self) -> str:
        """Return the source type of the port."""
        return SourceType.ROUTER


# ---------------------------
#   MikrotikHostDeviceTracker
# ---------------------------
class MikrotikHostDeviceTracker(MikrotikDeviceTracker):
    """Representation of a network device."""

    @property
    def option_track_network_hosts(self):
        """Config entry option to not track ARP."""
        return self._config_entry.options.get(CONF_TRACK_HOSTS, DEFAULT_TRACK_HOSTS)

    @property
    def option_track_network_hosts_timeout(self):
        """Config entry option scan interval."""
        track_network_hosts_timeout = self._config_entry.options.get(CONF_TRACK_HOSTS_TIMEOUT, DEFAULT_TRACK_HOST_TIMEOUT)
        return timedelta(seconds=track_network_hosts_timeout)

    @property
    def is_connected(self) -> bool:
        """Return true if the host is connected to the network."""
        if not self.option_track_network_hosts:
            return False

        if self._data.get("is_wireless", False):
            return self._data[self.entity_description.data_attribute]

        return bool(self._data["last-seen"] and utcnow() - self._data["last-seen"] < self.option_track_network_hosts_timeout)

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self._data.get("is_wireless", False):
            if self._data[self.entity_description.data_attribute]:
                return self.entity_description.icon_enabled
            else:
                return self.entity_description.icon_disabled

        if self._data["last-seen"] and (utcnow() - self._data["last-seen"]) < self.option_track_network_hosts_timeout:
            return self.entity_description.icon_enabled
        return self.entity_description.icon_disabled

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return self.coordinator.option_zone if self.is_connected else STATE_NOT_HOME

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        if self.is_connected:
            attributes[format_attribute("last-seen")] = "Now"

        if not attributes[format_attribute("last-seen")]:
            attributes[format_attribute("last-seen")] = "Unknown"

        # Wireless metrics only for wireless hosts
        if self._data.get("is_wireless", False):
            copy_attrs(attributes, self._data, DEVICE_ATTRIBUTES_HOST_WIRELESS)

        return attributes
