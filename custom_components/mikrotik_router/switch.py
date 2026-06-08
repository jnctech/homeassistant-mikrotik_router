"""Support for the Mikrotik Router switches."""

from __future__ import annotations

from logging import getLogger
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import MikrotikEntity, MikrotikInterfaceEntityMixin, async_add_entities
from .switch_types import (
    SENSOR_TYPES,  # noqa: F401
    SENSOR_SERVICES,  # noqa: F401
)

_LOGGER = getLogger(__name__)

# Switches send commands to the router; serialise them — RouterOS can mishandle
# simultaneous writes (see the API-lock concurrency history, #64).
PARALLEL_UPDATES = 1

_CAPSMAN_MANAGED = "managed by CAPsMAN"
_RULE_NOT_FOUND_ENABLE = "Rule not found for %s, cannot enable"
_RULE_NOT_FOUND_DISABLE = "Rule not found for %s, cannot disable"


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
        "MikrotikSwitch": MikrotikSwitch,
        "MikrotikPortSwitch": MikrotikPortSwitch,
        "MikrotikNATSwitch": MikrotikNATSwitch,
        "MikrotikMangleSwitch": MikrotikMangleSwitch,
        "MikrotikFilterSwitch": MikrotikFilterSwitch,
        "MikrotikQueueSwitch": MikrotikQueueSwitch,
        "MikrotikRawSwitch": MikrotikRawSwitch,
        "MikrotikContainerSwitch": MikrotikContainerSwitch,
        "MikrotikKidcontrolPauseSwitch": MikrotikKidcontrolPauseSwitch,
    }
    await async_add_entities(hass, config_entry, dispatcher)


# ---------------------------
#   MikrotikSwitch
# ---------------------------
class MikrotikSwitch(MikrotikEntity, SwitchEntity, RestoreEntity):
    """Representation of a switch."""

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._data[self.entity_description.data_attribute]

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self._data[self.entity_description.data_attribute]:
            return self.entity_description.icon_enabled
        else:
            return self.entity_description.icon_disabled

    def _require_write_access(self) -> None:
        """Raise HomeAssistantError if write access is not available."""
        if "write" not in self.coordinator.data["access"]:
            raise HomeAssistantError("Write access required")

    def _find_rule_id(self, data_key: str, match_field: str, match_value: str) -> str | None:
        """Find the .id of a rule in coordinator data by matching a field value."""
        for uid in self.coordinator.data[data_key]:
            if self.coordinator.data[data_key][uid][match_field] == match_value:
                return self.coordinator.data[data_key][uid][".id"]
        return None

    async def _toggle_rule(self, data_key: str, match_field: str, match_value: str, disable: bool) -> None:
        """Toggle a firewall/queue rule by looking up its .id and calling set_value."""
        self._require_write_access()

        value = self._find_rule_id(data_key, match_field, match_value)
        if value is None:
            msg = _RULE_NOT_FOUND_DISABLE if disable else _RULE_NOT_FOUND_ENABLE
            _LOGGER.error(msg, self.entity_id)
            return

        path = self.entity_description.data_switch_path
        mod_param = self.entity_description.data_switch_parameter
        await self.hass.async_add_executor_job(self.coordinator.set_value, path, ".id", value, mod_param, disable)
        await self.coordinator.async_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self._require_write_access()

        path = self.entity_description.data_switch_path
        param = self.entity_description.data_reference
        value = self._data[self.entity_description.data_reference]
        if value is None:
            _LOGGER.error(_RULE_NOT_FOUND_ENABLE, self.entity_id)
            return
        mod_param = self.entity_description.data_switch_parameter
        await self.hass.async_add_executor_job(self.coordinator.set_value, path, param, value, mod_param, False)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self._require_write_access()

        path = self.entity_description.data_switch_path
        param = self.entity_description.data_reference
        value = self._data[self.entity_description.data_reference]
        if value is None:
            _LOGGER.error(_RULE_NOT_FOUND_DISABLE, self.entity_id)
            return
        mod_param = self.entity_description.data_switch_parameter
        await self.hass.async_add_executor_job(self.coordinator.set_value, path, param, value, mod_param, True)
        await self.coordinator.async_refresh()


# ---------------------------
#   MikrotikPortSwitch
# ---------------------------
class MikrotikPortSwitch(MikrotikInterfaceEntityMixin, MikrotikSwitch):
    """Representation of a network port switch."""

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self._data["running"]:
            icon = self.entity_description.icon_enabled
        else:
            icon = self.entity_description.icon_disabled

        if not self._data["enabled"]:
            icon = "mdi:lan-disconnect"

        return icon

    async def async_turn_on(self, **kwargs: Any) -> str | None:
        """Turn on the switch."""
        self._require_write_access()

        path = self.entity_description.data_switch_path
        param = self.entity_description.data_reference
        if self._data.get("about") == _CAPSMAN_MANAGED:
            _LOGGER.error("Unable to enable %s, managed by CAPsMAN", self._data[param])
            return _CAPSMAN_MANAGED
        if "-" in self._data.get("port-mac-address", ""):
            param = "name"
        value = self._data[self.entity_description.data_reference]
        mod_param = self.entity_description.data_switch_parameter
        await self.hass.async_add_executor_job(self.coordinator.set_value, path, param, value, mod_param, False)

        if "poe-out" in self._data and self._data["poe-out"] == "off":
            path = "/interface/ethernet"
            await self.hass.async_add_executor_job(self.coordinator.set_value, path, param, value, "poe-out", "auto-on")

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> str | None:
        """Turn off the switch."""
        self._require_write_access()

        path = self.entity_description.data_switch_path
        param = self.entity_description.data_reference
        if self._data.get("about") == _CAPSMAN_MANAGED:
            _LOGGER.error("Unable to disable %s, managed by CAPsMAN", self._data[param])
            return _CAPSMAN_MANAGED
        if "-" in self._data.get("port-mac-address", ""):
            param = "name"
        value = self._data[self.entity_description.data_reference]
        mod_param = self.entity_description.data_switch_parameter
        await self.hass.async_add_executor_job(self.coordinator.set_value, path, param, value, mod_param, True)

        if "poe-out" in self._data and self._data["poe-out"] == "auto-on":
            path = "/interface/ethernet"
            await self.hass.async_add_executor_job(self.coordinator.set_value, path, param, value, "poe-out", "off")

        await self.coordinator.async_refresh()


# ---------------------------
#   MikrotikNATSwitch
# ---------------------------
class MikrotikNATSwitch(MikrotikSwitch):
    """Representation of a NAT switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._toggle_rule("nat", "uniq-id", self._data["uniq-id"], disable=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._toggle_rule("nat", "uniq-id", self._data["uniq-id"], disable=True)


# ---------------------------
#   MikrotikMangleSwitch
# ---------------------------
class MikrotikMangleSwitch(MikrotikSwitch):
    """Representation of a Mangle switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._toggle_rule("mangle", "uniq-id", self._data["uniq-id"], disable=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._toggle_rule("mangle", "uniq-id", self._data["uniq-id"], disable=True)


# ---------------------------
#   MikrotikFilterSwitch
# ---------------------------
class MikrotikFilterSwitch(MikrotikSwitch):
    """Representation of a Filter switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._toggle_rule("filter", "uniq-id", self._data["uniq-id"], disable=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._toggle_rule("filter", "uniq-id", self._data["uniq-id"], disable=True)


# ---------------------------
#   MikrotikQueueSwitch
# ---------------------------
class MikrotikQueueSwitch(MikrotikSwitch):
    """Representation of a queue switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._toggle_rule("queue", "name", self._data["name"], disable=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._toggle_rule("queue", "name", self._data["name"], disable=True)


# ---------------------------
#   MikrotikKidcontrolPauseSwitch
# ---------------------------
class MikrotikKidcontrolPauseSwitch(MikrotikSwitch):
    """Representation of a queue switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self._require_write_access()

        path = self.entity_description.data_switch_path
        param = self.entity_description.data_reference
        value = self._data[self.entity_description.data_reference]
        command = "resume"
        await self.hass.async_add_executor_job(self.coordinator.execute, path, command, param, value)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self._require_write_access()

        path = self.entity_description.data_switch_path
        param = self.entity_description.data_reference
        value = self._data[self.entity_description.data_reference]
        command = "pause"
        await self.hass.async_add_executor_job(self.coordinator.execute, path, command, param, value)
        await self.coordinator.async_refresh()


# ---------------------------
#   MikrotikRawSwitch
# ---------------------------
class MikrotikRawSwitch(MikrotikSwitch):
    """Representation of a Firewall RAW switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._toggle_rule("raw", "uniq-id", self._data["uniq-id"], disable=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._toggle_rule("raw", "uniq-id", self._data["uniq-id"], disable=True)


# ---------------------------
#   MikrotikContainerSwitch
# ---------------------------
class MikrotikContainerSwitch(MikrotikSwitch):
    """Representation of a container start/stop switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the container."""
        self._require_write_access()

        path = self.entity_description.data_switch_path
        await self.hass.async_add_executor_job(self.coordinator.execute, path, "start", ".id", self._data[".id"])
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the container."""
        self._require_write_access()

        path = self.entity_description.data_switch_path
        await self.hass.async_add_executor_job(self.coordinator.execute, path, "stop", ".id", self._data[".id"])
        await self.coordinator.async_refresh()
