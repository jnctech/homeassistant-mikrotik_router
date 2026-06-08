"""Tests for Mikrotik Router sensor entities.

REFERENCE IMPLEMENTATION (2026-06-08) — worked example for the patterns in
docs/internal/test-suite-review-2026-06-08.md. Read this file as the target
shape when reworking the other test modules:

  * spec= mocks at the boundary — a typo'd/renamed coordinator attribute now
    raises AttributeError instead of silently returning a Mock (no yes-man).
  * REAL entity descriptions — a renamed field in sensor_types.py breaks the
    test, instead of a kitchen-sink MagicMock accepting stale names forever.
  * @pytest.mark.parametrize for data-driven cases — the axis that varies is
    the table; adding a case is one line, not a copy-pasted block.
  * fixtures for shared "arrange".
  * set INPUTS (coordinator.data) and assert OUTPUTS (native_value) — never
    poke or assert internal representation.
"""

from unittest.mock import MagicMock

import pytest

from homeassistant.const import CONF_HOST, CONF_NAME, UnitOfElectricCurrent

from custom_components.mikrotik_router.coordinator import MikrotikCoordinator
from custom_components.mikrotik_router.sensor import (
    MikrotikClientTrafficSensor,
    MikrotikSensor,
)
from custom_components.mikrotik_router.sensor_types import (
    SENSOR_TYPES,
    MikrotikSensorEntityDescription,
)

from .conftest import patch_coordinator_entity_init


# ---------------------------------------------------------------------------
# Local, spec'd scaffolding.
#
# These builders are intentionally local to this file. conftest's make_mock_*
# helpers are unspecced MagicMocks (a "yes-man" that accepts any attribute);
# migrating them to spec= is a separate pass that touches every entity test
# module. This file shows where that pass should land.
# ---------------------------------------------------------------------------


def _coordinator(data: dict) -> MagicMock:
    """A coordinator mock pinned to the real MikrotikCoordinator interface.

    `spec=` means reading an attribute the real class does not define raises
    AttributeError rather than returning a fresh Mock — so a typo or a renamed
    coordinator attribute fails the test loudly instead of passing silently.
    """
    coordinator = MagicMock(spec=MikrotikCoordinator)
    coordinator.data = data
    config_entry = MagicMock()  # ConfigEntry is an HA boundary type; mock is fine
    config_entry.data = {CONF_NAME: "TestRouter", CONF_HOST: "10.0.0.1"}
    config_entry.options = {}
    coordinator.config_entry = config_entry
    return coordinator


def _description(**overrides) -> MikrotikSensorEntityDescription:
    """Build a REAL sensor entity description.

    Using the actual dataclass (not a MagicMock) means a field renamed or
    removed in sensor_types.py breaks these tests — which is the point. It also
    rejects fields that don't belong to a sensor description, so the test can't
    quietly depend on a switch-only attribute.
    """
    overrides.setdefault("key", "test_sensor")
    overrides.setdefault("name", "Test Sensor")
    # data_name / data_reference are read by custom_name() for uid entities;
    # default them so a uid sensor can be built without boilerplate per test.
    overrides.setdefault("data_name", "name")
    overrides.setdefault("data_reference", "name")
    return MikrotikSensorEntityDescription(**overrides)


def _build_sensor(data, description, *, cls=MikrotikSensor, uid=None):
    """Construct a sensor with HA's CoordinatorEntity.__init__ patched out."""
    coordinator = _coordinator(data)
    with patch_coordinator_entity_init():
        return cls(coordinator, description, uid)


# ---------------------------------------------------------------------------
# Regression pin for issue #60 (keep — this is a legitimate "pin a fixed bug").
# ---------------------------------------------------------------------------


def test_poe_out_current_uses_milliampere_native_unit():
    """Issue #60: PoE current was declared AMPERE but the API returns mA, so
    displayed values were 1000x too large. Pin the native unit to mA so a future
    edit can't silently revert it."""
    desc = next(s for s in SENSOR_TYPES if s.key == "poe_out_current")
    assert desc.native_unit_of_measurement == UnitOfElectricCurrent.MILLIAMPERE


# ---------------------------------------------------------------------------
# MikrotikSensor.native_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data_path, data, attribute, expected",
    [
        ("health", {"temperature": 42}, "temperature", 42),
        ("resource", {"version": "7.16.2"}, "version", "7.16.2"),
    ],
)
def test_native_value_returns_data_attribute(data_path, data, attribute, expected):
    """native_value reads description.data_attribute out of the data path."""
    desc = _description(data_path=data_path, data_attribute=attribute)
    sensor = _build_sensor({data_path: data}, desc)
    assert sensor.native_value == expected


# ---------------------------------------------------------------------------
# MikrotikSensor.native_unit_of_measurement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "configured_unit, expected",
    [
        ("°C", "°C"),  # a static unit is returned verbatim
        (None, None),  # no unit configured -> None
    ],
)
def test_static_native_unit(configured_unit, expected):
    desc = _description(
        data_path="health",
        data_attribute="temperature",
        native_unit_of_measurement=configured_unit,
    )
    sensor = _build_sensor({"health": {"temperature": 42}}, desc)
    assert sensor.native_unit_of_measurement == expected


@pytest.mark.parametrize(
    "interface_data, expected",
    [
        ({"name": "ether1", "speed-unit": "Mbps"}, "Mbps"),  # data__ key present -> resolved
        ({"name": "ether1"}, "data__speed-unit"),  # key absent -> raw string returned
    ],
)
def test_dynamic_native_unit_from_data(interface_data, expected):
    """A `data__<key>` unit resolves against the entity's own data, falling back
    to the literal string when the key is absent."""
    desc = _description(
        data_path="interface",
        data_attribute="name",
        native_unit_of_measurement="data__speed-unit",
    )
    sensor = _build_sensor({"interface": {"ether1": interface_data}}, desc, uid="ether1")
    assert sensor.native_unit_of_measurement == expected


# ---------------------------------------------------------------------------
# MikrotikClientTrafficSensor.custom_name
# ---------------------------------------------------------------------------


def test_client_traffic_sensor_name_is_description_name():
    """Client-traffic sensors always name themselves from the description, not
    the per-client host-name."""
    desc = _description(
        name="WAN TX",
        data_path="client_traffic",
        data_reference="mac-address",
        data_name="host-name",
    )
    data = {
        "client_traffic": {
            "AA:BB:CC:DD:EE:FF": {"host-name": "MyPC", "wan-tx": 1000},
        }
    }
    sensor = _build_sensor(data, desc, cls=MikrotikClientTrafficSensor, uid="AA:BB:CC:DD:EE:FF")
    assert sensor.custom_name == "WAN TX"


# ---------------------------------------------------------------------------
# DHCP client sensors
# ---------------------------------------------------------------------------


@pytest.fixture
def dhcp_client_data():
    """A single bound DHCP client lease, shared across the cases below."""
    return {
        "dhcp-client": {
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
    }


@pytest.mark.parametrize(
    "attribute, expected",
    [
        ("status", "bound"),
        ("address", "10.0.0.5/24"),
        ("gateway", "10.0.0.1"),
        ("dns-server", "8.8.8.8"),
    ],
)
def test_dhcp_client_sensor_reads_attribute(dhcp_client_data, attribute, expected):
    desc = _description(
        data_path="dhcp-client",
        data_attribute=attribute,
        data_name="interface",
        data_uid="interface",
        data_reference="interface",
    )
    sensor = _build_sensor(dhcp_client_data, desc, uid="ether1")
    assert sensor.native_value == expected
