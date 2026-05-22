"""Tests for Mikrotik Router device tracker entities."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from homeassistant.const import STATE_NOT_HOME

from custom_components.mikrotik_router.device_tracker import (
    MikrotikDeviceTracker,
    MikrotikHostDeviceTracker,
)
from custom_components.mikrotik_router.const import (
    CONF_TRACK_HOSTS,
    CONF_TRACK_HOSTS_TIMEOUT,
)

from .conftest import (
    make_mock_coordinator,
    make_mock_entity_description,
    patch_coordinator_entity_init,
)


def _make_tracker(cls=MikrotikDeviceTracker, coordinator=None, desc_overrides=None, uid=None):
    coord = coordinator or make_mock_coordinator()
    desc = make_mock_entity_description(**(desc_overrides or {}))
    with patch_coordinator_entity_init():
        entity = cls(coord, desc, uid)
    return entity


def _host_data(source="arp", last_seen=None, available=True, is_wireless=None, **extra):
    """Build a host data dict."""
    data = {
        "host-name": "MyPC",
        "mac-address": "AA:BB:CC:DD:EE:FF",
        "address": "192.168.1.100",
        "source": source,
        "available": available,
        "last-seen": last_seen,
        "is_wireless": is_wireless if is_wireless is not None else source in ("capsman", "wireless"),
    }
    data.update(extra)
    return data


_HOST_DESC = {
    "data_path": "host",
    "data_attribute": "available",
    "data_reference": "mac-address",
    "data_name": "host-name",
    "data_attributes_list": ["last-seen"],
    "icon_enabled": "mdi:lan-connect",
    "icon_disabled": "mdi:lan-disconnect",
}


# ---------------------------------------------------------------------------
# MikrotikDeviceTracker
# ---------------------------------------------------------------------------


class TestMikrotikDeviceTracker:
    def test_is_connected(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "running": True}}
        entity = _make_tracker(
            coordinator=coord,
            desc_overrides={"data_path": "interface", "data_attribute": "running"},
            uid="ether1",
        )
        assert entity.is_connected is True

    def test_ip_address_present(self):
        coord = make_mock_coordinator()
        coord.data["host"] = {
            "mac1": {
                "host-name": "PC",
                "address": "192.168.1.10",
                "mac-address": "AA:BB",
            }
        }
        entity = _make_tracker(
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.ip_address == "192.168.1.10"

    def test_ip_address_missing(self):
        coord = make_mock_coordinator()
        coord.data["host"] = {"mac1": {"host-name": "PC", "mac-address": "AA:BB"}}
        entity = _make_tracker(
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.ip_address is None

    def test_mac_address(self):
        coord = make_mock_coordinator()
        coord.data["host"] = {"mac1": {"host-name": "PC", "mac-address": "AA:BB:CC:DD:EE:FF"}}
        entity = _make_tracker(
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.mac_address == "AA:BB:CC:DD:EE:FF"

    def test_hostname(self):
        coord = make_mock_coordinator()
        coord.data["host"] = {"mac1": {"host-name": "MyPC", "mac-address": "AA:BB"}}
        entity = _make_tracker(
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.hostname == "MyPC"


# ---------------------------------------------------------------------------
# MikrotikHostDeviceTracker
# ---------------------------------------------------------------------------


class TestMikrotikHostDeviceTracker:
    def test_is_connected_false_when_tracking_disabled(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: False})
        coord.data["host"] = {"mac1": _host_data(available=True)}
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.is_connected is False

    def test_is_connected_wireless_source_uses_data_attribute(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True})
        coord.data["host"] = {"mac1": _host_data(source="wireless", available=True)}
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.is_connected is True

    def test_is_connected_capsman_source_uses_data_attribute(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True})
        coord.data["host"] = {"mac1": _host_data(source="capsman", available=False)}
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.is_connected is False

    def test_is_connected_arp_source_within_timeout(self):
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True, CONF_TRACK_HOSTS_TIMEOUT: 180})
        coord.data["host"] = {"mac1": _host_data(source="arp", last_seen=now - timedelta(seconds=60))}
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        with patch(
            "custom_components.mikrotik_router.device_tracker.utcnow",
            return_value=now,
        ):
            assert entity.is_connected is True

    def test_is_connected_arp_source_beyond_timeout(self):
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True, CONF_TRACK_HOSTS_TIMEOUT: 180})
        coord.data["host"] = {"mac1": _host_data(source="arp", last_seen=now - timedelta(seconds=300))}
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        with patch(
            "custom_components.mikrotik_router.device_tracker.utcnow",
            return_value=now,
        ):
            assert entity.is_connected is False

    def test_state_home_when_connected(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True})
        coord.data["host"] = {"mac1": _host_data(source="wireless", available=True)}
        coord.option_zone = "home"
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.state == "home"

    def test_state_not_home_when_disconnected(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: False})
        coord.data["host"] = {"mac1": _host_data(available=True)}
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        assert entity.state == STATE_NOT_HOME

    def test_extra_state_attributes_connected_shows_now(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True})
        coord.data["host"] = {"mac1": _host_data(source="wireless", available=True)}
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        attrs = entity.extra_state_attributes
        assert attrs["last_seen"] == "Now"

    def test_extra_state_attributes_disconnected_no_last_seen_shows_unknown(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: False})
        coord.data["host"] = {"mac1": _host_data(last_seen=None)}
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        attrs = entity.extra_state_attributes
        assert attrs["last_seen"] == "Unknown"

    def test_extra_state_attributes_wireless_host_shows_signal_attrs(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True})
        coord.data["host"] = {
            "mac1": _host_data(
                source="wireless",
                available=True,
                **{
                    "signal-strength": -55,
                    "tx-ccq": 90,
                    "tx-rate": "54Mbps",
                    "rx-rate": "72Mbps",
                },
            )
        }
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        attrs = entity.extra_state_attributes
        assert attrs["signal_strength"] == -55
        assert attrs["tx_ccq"] == 90
        assert attrs["tx_rate"] == "54Mbps"
        assert attrs["rx_rate"] == "72Mbps"

    def test_extra_state_attributes_wired_host_no_wireless_attrs(self):
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True})
        coord.data["host"] = {
            "mac1": _host_data(
                source="arp",
                available=True,
                **{
                    "signal-strength": 0,
                    "tx-ccq": 0,
                    "tx-rate": "",
                    "rx-rate": "",
                },
            )
        }
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        attrs = entity.extra_state_attributes
        assert "signal_strength" not in attrs
        assert "tx_ccq" not in attrs
        assert "tx_rate" not in attrs
        assert "rx_rate" not in attrs

    def test_bridge_wireless_host_uses_wireless_behaviour(self):
        """Host discovered via bridge table with is_wireless=True uses wireless logic."""
        coord = make_mock_coordinator(options={CONF_TRACK_HOSTS: True})
        coord.data["host"] = {
            "mac1": _host_data(
                source="arp",
                available=True,
                is_wireless=True,
                **{
                    "signal-strength": -60,
                    "tx-ccq": 85,
                    "tx-rate": "72Mbps",
                    "rx-rate": "54Mbps",
                },
            )
        }
        entity = _make_tracker(
            cls=MikrotikHostDeviceTracker,
            coordinator=coord,
            desc_overrides={**_HOST_DESC},
            uid="mac1",
        )
        # Uses registration-based connection (available=True directly)
        assert entity.is_connected is True
        # Shows wireless icon
        assert entity.icon == entity.entity_description.icon_enabled
        # Shows wireless attributes
        attrs = entity.extra_state_attributes
        assert attrs["signal_strength"] == -60
        assert attrs["tx_ccq"] == 85
