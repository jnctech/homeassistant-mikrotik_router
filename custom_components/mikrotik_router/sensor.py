"""Mikrotik sensor platform."""

from __future__ import annotations

from logging import getLogger
from datetime import date, datetime
from decimal import Decimal

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import MikrotikCoordinator
from .entity import MikrotikEntity, MikrotikInterfaceEntityMixin, async_add_entities
from .sensor_types import SENSOR_TYPES, SENSOR_SERVICES  # noqa: F401

_LOGGER = getLogger(__name__)

# The coordinator centralises all polling; sensor updates perform no per-entity
# device I/O, so no parallelism limit is needed.
PARALLEL_UPDATES = 0


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
        "MikrotikSensor": MikrotikSensor,
        "MikrotikInterfaceTrafficSensor": MikrotikInterfaceTrafficSensor,
        "MikrotikClientTrafficSensor": MikrotikClientTrafficSensor,
        "MikrotikPoEEnergySensor": MikrotikPoEEnergySensor,
        "MikrotikPoEEnergyTotalSensor": MikrotikPoEEnergyTotalSensor,
    }
    await async_add_entities(hass, config_entry, dispatcher)


# ---------------------------
#   MikrotikSensor
# ---------------------------
class MikrotikSensor(MikrotikEntity, SensorEntity):
    """Define an Mikrotik sensor."""

    def __init__(
        self,
        coordinator: MikrotikCoordinator,
        entity_description,
        uid: str | None = None,
    ):
        super().__init__(coordinator, entity_description, uid)
        self._attr_suggested_unit_of_measurement = self.entity_description.suggested_unit_of_measurement

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self._data[self.entity_description.data_attribute]

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        if self.entity_description.native_unit_of_measurement:
            if self.entity_description.native_unit_of_measurement.startswith("data__"):
                uom = self.entity_description.native_unit_of_measurement[6:]
                if uom in self._data:
                    return self._data[uom]

            return self.entity_description.native_unit_of_measurement

        return None


# ---------------------------
#   MikrotikInterfaceTrafficSensor
# ---------------------------
class MikrotikInterfaceTrafficSensor(MikrotikInterfaceEntityMixin, MikrotikSensor):
    """Define an Mikrotik MikrotikInterfaceTrafficSensor sensor."""


# ---------------------------
#   MikrotikClientTrafficSensor
# ---------------------------
class MikrotikClientTrafficSensor(MikrotikSensor):
    """Define an Mikrotik MikrotikClientTrafficSensor sensor."""

    @property
    def custom_name(self) -> str:
        """Return the name for this entity"""
        return f"{self.entity_description.name}"


# ---------------------------
#   MikrotikPoEEnergySensor
# ---------------------------
class MikrotikPoEEnergySensor(MikrotikSensor, RestoreSensor):
    """PoE-out energy sensor (kWh, total_increasing).

    Integrates the coordinator's per-poll energy increment into a running kWh
    total. The total is restored across HA restarts via RestoreSensor, so it
    does NOT reset to zero on reload (the Energy Dashboard would otherwise treat
    a reset as a new billing cycle). The increment may be measured (real
    poe-out-power) or estimated (nameplate) — surfaced via the power_source
    attribute. See ADR-017.
    """

    def __init__(
        self,
        coordinator: MikrotikCoordinator,
        entity_description,
        uid: str | None = None,
    ):
        super().__init__(coordinator, entity_description, uid)
        self._accumulated_kwh: float = 0.0

    async def async_added_to_hass(self) -> None:
        """Restore the accumulated kWh total from the previous run."""
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._accumulated_kwh = float(last.native_value)
            except (TypeError, ValueError):
                _LOGGER.warning(
                    "Could not restore PoE energy total for %s (got %r); starting from 0",
                    self.entity_description.key,
                    last.native_value,
                )
                self._accumulated_kwh = 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        # Resolve and accumulate the increment BEFORE super() writes HA state:
        # the base couples data-refresh and async_write_ha_state(), so deferring
        # the accumulation past super() would record last poll's total (a one-poll
        # lag). The duplicated lookup is the deliberate cost of correct ordering.
        try:
            fresh = self.coordinator.data[self.entity_description.data_path]
            if self._uid:
                fresh = fresh[self._uid]
        except KeyError:
            _LOGGER.debug(
                "Data path %s uid=%s not found, skipping PoE energy update",
                self.entity_description.data_path,
                self._uid,
            )
            return
        delta_wh = fresh.get(self.entity_description.data_attribute) or 0.0
        # Clamp >= 0 so the exposed total is monotonic (total_increasing).
        self._accumulated_kwh += max(0.0, delta_wh) / 1000
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        """Return the accumulated energy in kWh."""
        return round(self._accumulated_kwh, 6)

    @property
    def extra_state_attributes(self) -> dict:
        """Expose whether the energy is measured or estimated."""
        attrs = dict(self._attr_extra_state_attributes or {})
        source = self._data.get("poe-out-energy-source")
        if source:
            attrs["power_source"] = source
        model = self._data.get("poe-out-energy-model")
        if model:
            attrs["estimated_from_model"] = model
        return attrs


# ---------------------------
#   MikrotikPoEEnergyTotalSensor
# ---------------------------
class MikrotikPoEEnergyTotalSensor(MikrotikPoEEnergySensor):
    """Device-total PoE-out energy — sum of the per-port increments (kWh)."""
