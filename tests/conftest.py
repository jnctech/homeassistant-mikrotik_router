"""Fixtures for Mikrotik Router tests."""

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.const import CONF_NAME, CONF_HOST

from custom_components.mikrotik_router.sensor_types import (
    MikrotikSensorEntityDescription,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    yield


# ---------------------------------------------------------------------------
# Shared helpers for entity-level tests
# ---------------------------------------------------------------------------


# Shared defaults spanning every platform's description. The factory filters
# these to the fields the chosen class actually declares, so e.g. a switch test
# can't lean on a sensor-only field.
_ENTITY_DESC_DEFAULTS = {
    "key": "test_key",
    "name": "Test Sensor",
    "func": "MikrotikSensor",
    "ha_group": "System",
    "ha_connection": None,
    "ha_connection_value": None,
    "data_path": "interface",
    "data_attribute": "enabled",
    "data_name": "name",
    "data_name_comment": False,
    "data_name_compose": False,
    "data_uid": "",
    "data_reference": "name",
    "data_attributes_list": [],
    "data_switch_path": "/interface",
    "data_switch_parameter": "disabled",
    "icon_enabled": "mdi:check",
    "icon_disabled": "mdi:close",
    "native_unit_of_measurement": None,
    "suggested_unit_of_measurement": None,
}


def make_mock_entity_description(cls=MikrotikSensorEntityDescription, **overrides):
    """Build a REAL Mikrotik*EntityDescription of the given platform type.

    Unlike the old yes-man MagicMock (which returned a truthy Mock for *any*
    attribute, hiding renamed/removed fields), this constructs the real frozen-ish
    dataclass. Shared defaults are filtered to the fields the class declares;
    overrides are passed straight through, so a field that does not exist on `cls`
    raises TypeError — surfacing a test coupled to the wrong platform's description.

    Pass `cls=` the platform description under test (e.g.
    MikrotikSwitchEntityDescription for switch tests).
    """
    valid = {f.name for f in dataclasses.fields(cls)}
    fields = {k: v for k, v in _ENTITY_DESC_DEFAULTS.items() if k in valid}
    fields.update(overrides)
    fields.setdefault("key", "test_key")
    return cls(**fields)


def make_mock_coordinator(data=None, options=None, name="TestRouter", host="10.0.0.1"):
    """Build a lightweight coordinator mock for entity-level tests.

    Unlike make_coordinator() in test_coordinator.py which uses object.__new__,
    this returns a MagicMock so entities can be constructed without any real HA
    coordinator machinery.
    """
    coord = MagicMock()
    coord.data = data or {
        "resource": {
            "board-name": "hAP ax3",
            "platform": "MikroTik",
            "version": "7.16.2",
        },
        "routerboard": {
            "serial-number": "HGR1234567",
            "current-firmware": "7.16.2",
            "upgrade-firmware": "7.16.2",
        },
        "interface": {},
        "access": ["write", "policy", "reboot", "test"],
        "host": {},
        "fw-update": {
            "installed-version": "7.16.2",
            "latest-version": "7.16.2",
            "available": False,
        },
        "raw": {},
        "container": {},
    }
    cfg = MagicMock()
    cfg.data = {CONF_NAME: name, CONF_HOST: host}
    cfg.options = options or {}
    coord.config_entry = cfg
    coord.set_value = MagicMock(return_value=True)
    coord.execute = MagicMock()
    coord.async_refresh = AsyncMock()
    coord.api = MagicMock()
    coord.api.run_script = MagicMock()
    coord.option_zone = "home"
    return coord


def patch_coordinator_entity_init():
    """Patch CoordinatorEntity.__init__ to only set self.coordinator.

    The real __init__ registers with HA internals (event loops, listeners).
    We only need the coordinator attribute for entity-level tests.
    """
    from unittest.mock import patch as _patch

    def _init(self, coordinator, context=None):
        self.coordinator = coordinator

    return _patch(
        "custom_components.mikrotik_router.entity.CoordinatorEntity.__init__",
        _init,
    )


class MockMikrotikAPI:
    """Minimal MikrotikAPI mock that dispatches query() calls by path/command."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.error = ""
        self.disable_health = False
        self.client_traffic_last_run = None
        self._accounting_enabled = False
        self._local_traffic_enabled = False
        self._snapshot_time_diff = 0

    def connect(self):
        return True

    def disconnect(self):
        pass

    def query(self, path, command=None, args=None):
        key = (path, command) if command else path
        return self.responses.get(key, [])

    def execute(self, path, command, param=None, value=None, options=None):
        pass

    def set_value(self, path, param, value, mod_param, mod_value):
        return True

    def is_accounting_and_local_traffic_enabled(self):
        return self._accounting_enabled, self._local_traffic_enabled

    def take_client_traffic_snapshot(self, accounting):
        return self._snapshot_time_diff
