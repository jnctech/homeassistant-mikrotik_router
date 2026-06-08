"""Tests for Mikrotik Router binary sensor entities."""

from custom_components.mikrotik_router.binary_sensor import (
    MikrotikBinarySensor,
    MikrotikPPPSecretBinarySensor,
    MikrotikPortBinarySensor,
)
from custom_components.mikrotik_router.const import CONF_SENSOR_PPP
from custom_components.mikrotik_router.binary_sensor_types import (
    MikrotikBinarySensorEntityDescription,
)

from .conftest import (
    make_mock_coordinator,
    make_mock_entity_description,
    patch_coordinator_entity_init,
)


def _make_binary_sensor(cls=MikrotikBinarySensor, coordinator=None, desc_overrides=None, uid=None):
    coord = coordinator or make_mock_coordinator()
    desc = make_mock_entity_description(cls=MikrotikBinarySensorEntityDescription, **(desc_overrides or {}))
    with patch_coordinator_entity_init():
        entity = cls(coord, desc, uid)
    return entity


# ---------------------------------------------------------------------------
# MikrotikBinarySensor.is_on
# ---------------------------------------------------------------------------


class TestBinarySensorIsOn:
    def test_is_on_true(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "running": True}}
        entity = _make_binary_sensor(
            coordinator=coord,
            desc_overrides={"data_path": "interface", "data_attribute": "running"},
            uid="ether1",
        )
        assert entity.is_on is True

    def test_is_on_false(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "running": False}}
        entity = _make_binary_sensor(
            coordinator=coord,
            desc_overrides={"data_path": "interface", "data_attribute": "running"},
            uid="ether1",
        )
        assert entity.is_on is False


# ---------------------------------------------------------------------------
# MikrotikBinarySensor.icon
# ---------------------------------------------------------------------------


class TestBinarySensorIcon:
    def test_icon_when_on(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "running": True}}
        entity = _make_binary_sensor(
            coordinator=coord,
            desc_overrides={
                "data_path": "interface",
                "data_attribute": "running",
                "icon_enabled": "mdi:lan-connect",
                "icon_disabled": "mdi:lan-disconnect",
            },
            uid="ether1",
        )
        assert entity.icon == "mdi:lan-connect"

    def test_icon_when_off(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "running": False}}
        entity = _make_binary_sensor(
            coordinator=coord,
            desc_overrides={
                "data_path": "interface",
                "data_attribute": "running",
                "icon_enabled": "mdi:lan-connect",
                "icon_disabled": "mdi:lan-disconnect",
            },
            uid="ether1",
        )
        assert entity.icon == "mdi:lan-disconnect"

    def test_icon_returns_none_when_no_icon_enabled(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "running": True}}
        entity = _make_binary_sensor(
            coordinator=coord,
            desc_overrides={
                "data_path": "interface",
                "data_attribute": "running",
                "icon_enabled": None,
            },
            uid="ether1",
        )
        assert entity.icon is None


# ---------------------------------------------------------------------------
# MikrotikPPPSecretBinarySensor.is_on
# ---------------------------------------------------------------------------


class TestPPPSecretBinarySensor:
    def test_is_on_when_ppp_enabled(self):
        coord = make_mock_coordinator(options={CONF_SENSOR_PPP: True})
        coord.data["ppp_secret"] = {"user1": {"name": "user1", "connected": True}}
        entity = _make_binary_sensor(
            cls=MikrotikPPPSecretBinarySensor,
            coordinator=coord,
            desc_overrides={"data_path": "ppp_secret", "data_attribute": "connected"},
            uid="user1",
        )
        assert entity.is_on is True

    def test_is_on_false_when_ppp_disabled(self):
        coord = make_mock_coordinator(options={CONF_SENSOR_PPP: False})
        coord.data["ppp_secret"] = {"user1": {"name": "user1", "connected": True}}
        entity = _make_binary_sensor(
            cls=MikrotikPPPSecretBinarySensor,
            coordinator=coord,
            desc_overrides={"data_path": "ppp_secret", "data_attribute": "connected"},
            uid="user1",
        )
        assert entity.is_on is False


# ---------------------------------------------------------------------------
# MikrotikPortBinarySensor.icon
# ---------------------------------------------------------------------------


class TestPortBinarySensorIcon:
    def test_icon_disabled_interface(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {
            "ether1": {
                "name": "ether1",
                "running": True,
                "enabled": False,
                "type": "ether",
            }
        }
        entity = _make_binary_sensor(
            cls=MikrotikPortBinarySensor,
            coordinator=coord,
            desc_overrides={
                "data_path": "interface",
                "data_attribute": "running",
                "icon_enabled": "mdi:lan-connect",
                "icon_disabled": "mdi:lan-pending",
            },
            uid="ether1",
        )
        assert entity.icon == "mdi:lan-disconnect"

    def test_icon_enabled_and_running(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {
            "ether1": {
                "name": "ether1",
                "running": True,
                "enabled": True,
                "type": "ether",
            }
        }
        entity = _make_binary_sensor(
            cls=MikrotikPortBinarySensor,
            coordinator=coord,
            desc_overrides={
                "data_path": "interface",
                "data_attribute": "running",
                "icon_enabled": "mdi:lan-connect",
                "icon_disabled": "mdi:lan-pending",
            },
            uid="ether1",
        )
        assert entity.icon == "mdi:lan-connect"

    def test_icon_enabled_but_not_running(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {
            "ether1": {
                "name": "ether1",
                "running": False,
                "enabled": True,
                "type": "ether",
            }
        }
        entity = _make_binary_sensor(
            cls=MikrotikPortBinarySensor,
            coordinator=coord,
            desc_overrides={
                "data_path": "interface",
                "data_attribute": "running",
                "icon_enabled": "mdi:lan-connect",
                "icon_disabled": "mdi:lan-pending",
            },
            uid="ether1",
        )
        assert entity.icon == "mdi:lan-pending"
