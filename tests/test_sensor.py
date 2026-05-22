"""Tests for Mikrotik Router sensor entities."""

from homeassistant.const import UnitOfElectricCurrent

from custom_components.mikrotik_router.sensor import (
    MikrotikSensor,
    MikrotikClientTrafficSensor,
)
from custom_components.mikrotik_router.sensor_types import SENSOR_TYPES

from .conftest import (
    make_mock_coordinator,
    make_mock_entity_description,
    patch_coordinator_entity_init,
)


def test_poe_out_current_uses_milliampere_native_unit():
    """Issue #60: PoE current was declared as AMPERE but the API returns mA,
    causing displayed values to be off by 1000x. The native unit must match
    the raw API units (mA)."""
    desc = next(s for s in SENSOR_TYPES if s.key == "poe_out_current")
    assert desc.native_unit_of_measurement == UnitOfElectricCurrent.MILLIAMPERE


def _make_sensor(cls=MikrotikSensor, coordinator=None, desc_overrides=None, uid=None):
    """Build a sensor entity with patched CoordinatorEntity.__init__."""
    coord = coordinator or make_mock_coordinator()
    desc = make_mock_entity_description(**(desc_overrides or {}))
    with patch_coordinator_entity_init():
        entity = cls(coord, desc, uid)
    return entity


# ---------------------------------------------------------------------------
# MikrotikSensor.native_value
# ---------------------------------------------------------------------------


class TestMikrotikSensorNativeValue:
    def test_returns_data_attribute(self):
        coord = make_mock_coordinator()
        coord.data["health"] = {"temperature": 42}
        entity = _make_sensor(
            coordinator=coord,
            desc_overrides={"data_path": "health", "data_attribute": "temperature"},
        )
        assert entity.native_value == 42

    def test_returns_string_value(self):
        coord = make_mock_coordinator()
        coord.data["resource"] = {"version": "7.16.2"}
        entity = _make_sensor(
            coordinator=coord,
            desc_overrides={"data_path": "resource", "data_attribute": "version"},
        )
        assert entity.native_value == "7.16.2"


# ---------------------------------------------------------------------------
# MikrotikSensor.native_unit_of_measurement
# ---------------------------------------------------------------------------


class TestMikrotikSensorUoM:
    def test_static_uom(self):
        entity = _make_sensor(
            desc_overrides={
                "native_unit_of_measurement": "°C",
                "data_path": "health",
            },
            coordinator=make_mock_coordinator(
                data={
                    "health": {"temperature": 42},
                    "resource": {"board-name": "x", "platform": "x", "version": "x"},
                    "routerboard": {"serial-number": "x"},
                }
            ),
        )
        assert entity.native_unit_of_measurement == "°C"

    def test_dynamic_uom_from_data(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "speed-unit": "Mbps"}}
        entity = _make_sensor(
            coordinator=coord,
            desc_overrides={
                "native_unit_of_measurement": "data__speed-unit",
                "data_path": "interface",
                "data_reference": "name",
            },
            uid="ether1",
        )
        assert entity.native_unit_of_measurement == "Mbps"

    def test_dynamic_uom_key_missing_falls_back(self):
        """When the data__ key isn't in _data, returns the raw string."""
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1"}}
        entity = _make_sensor(
            coordinator=coord,
            desc_overrides={
                "native_unit_of_measurement": "data__speed-unit",
                "data_path": "interface",
                "data_reference": "name",
            },
            uid="ether1",
        )
        assert entity.native_unit_of_measurement == "data__speed-unit"

    def test_none_uom(self):
        entity = _make_sensor(
            desc_overrides={
                "native_unit_of_measurement": None,
                "data_path": "health",
            },
            coordinator=make_mock_coordinator(
                data={
                    "health": {"temperature": 42},
                    "resource": {"board-name": "x", "platform": "x", "version": "x"},
                    "routerboard": {"serial-number": "x"},
                }
            ),
        )
        assert entity.native_unit_of_measurement is None


# ---------------------------------------------------------------------------
# MikrotikClientTrafficSensor.custom_name
# ---------------------------------------------------------------------------


class TestClientTrafficSensorCustomName:
    def test_always_returns_description_name(self):
        coord = make_mock_coordinator()
        coord.data["client_traffic"] = {"AA:BB:CC:DD:EE:FF": {"host-name": "MyPC", "wan-tx": 1000}}
        entity = _make_sensor(
            cls=MikrotikClientTrafficSensor,
            coordinator=coord,
            desc_overrides={
                "name": "WAN TX",
                "data_path": "client_traffic",
                "data_reference": "mac-address",
                "data_name": "host-name",
            },
            uid="AA:BB:CC:DD:EE:FF",
        )
        assert entity.custom_name == "WAN TX"


# ---------------------------------------------------------------------------
# DHCP Client Sensors
# ---------------------------------------------------------------------------


class TestDHCPClientSensors:
    def test_dhcp_status_sensor_value(self):
        coord = make_mock_coordinator()
        coord.data["dhcp-client"] = {
            "ether1": {
                "interface": "ether1",
                "status": "bound",
                "address": "10.0.0.5/24",
                "gateway": "10.0.0.1",
                "dns-server": "8.8.8.8",
                "dhcp-server": "10.0.0.1",
                "expires-after": "23:45:00",
                "comment": "",
            }
        }
        entity = _make_sensor(
            coordinator=coord,
            desc_overrides={
                "data_path": "dhcp-client",
                "data_attribute": "status",
                "data_name": "interface",
                "data_uid": "interface",
                "data_reference": "interface",
            },
            uid="ether1",
        )
        assert entity.native_value == "bound"

    def test_dhcp_address_sensor_value(self):
        coord = make_mock_coordinator()
        coord.data["dhcp-client"] = {
            "ether1": {
                "interface": "ether1",
                "status": "bound",
                "address": "10.0.0.5/24",
                "gateway": "10.0.0.1",
                "dns-server": "8.8.8.8",
                "dhcp-server": "10.0.0.1",
                "expires-after": "23:45:00",
                "comment": "",
            }
        }
        entity = _make_sensor(
            coordinator=coord,
            desc_overrides={
                "data_path": "dhcp-client",
                "data_attribute": "address",
                "data_name": "interface",
                "data_uid": "interface",
                "data_reference": "interface",
            },
            uid="ether1",
        )
        assert entity.native_value == "10.0.0.5/24"
