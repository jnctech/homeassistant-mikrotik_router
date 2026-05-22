"""Support for the Mikrotik Router binary sensor service."""

from __future__ import annotations

from logging import getLogger

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SENSOR_PPP,
    DEFAULT_SENSOR_PPP,
    CONF_SENSOR_PORT_TRACKER,
    DEFAULT_SENSOR_PORT_TRACKER,
)
from .entity import MikrotikEntity, MikrotikInterfaceEntityMixin, async_add_entities
from .binary_sensor_types import SENSOR_TYPES, SENSOR_SERVICES  # noqa: F401

_LOGGER = getLogger(__name__)


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
        "MikrotikBinarySensor": MikrotikBinarySensor,
        "MikrotikPPPSecretBinarySensor": MikrotikPPPSecretBinarySensor,
        "MikrotikPortBinarySensor": MikrotikPortBinarySensor,
    }
    await async_add_entities(hass, config_entry, dispatcher)


# ---------------------------
#   MikrotikBinarySensor
# ---------------------------
class MikrotikBinarySensor(MikrotikEntity, BinarySensorEntity):
    """Define an Mikrotik Controller Binary Sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._data[self.entity_description.data_attribute]

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.entity_description.icon_enabled:
            if self._data[self.entity_description.data_attribute]:
                return self.entity_description.icon_enabled
            else:
                return self.entity_description.icon_disabled


# ---------------------------
#   MikrotikPPPSecretBinarySensor
# ---------------------------
class MikrotikPPPSecretBinarySensor(MikrotikBinarySensor):
    """Representation of a network device."""

    @property
    def option_sensor_ppp(self) -> bool:
        """Config entry option."""
        return self._config_entry.options.get(CONF_SENSOR_PPP, DEFAULT_SENSOR_PPP)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._data[self.entity_description.data_attribute] if self.option_sensor_ppp else False


# ---------------------------
#   MikrotikPortBinarySensor
# ---------------------------
class MikrotikPortBinarySensor(MikrotikInterfaceEntityMixin, MikrotikBinarySensor):
    """Representation of a network port."""

    @property
    def option_sensor_port_tracker(self) -> bool:
        """Config entry option to not track ARP."""
        return self._config_entry.options.get(CONF_SENSOR_PORT_TRACKER, DEFAULT_SENSOR_PORT_TRACKER)

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self._data[self.entity_description.data_attribute]:
            icon = self.entity_description.icon_enabled
        else:
            icon = self.entity_description.icon_disabled

        if not self._data["enabled"]:
            icon = "mdi:lan-disconnect"

        return icon
