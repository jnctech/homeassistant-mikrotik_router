"""Unit tests for Mikrotik Router entity _skip_sensor(), MikrotikInterfaceEntityMixin, and MikrotikEntity."""

from unittest.mock import MagicMock, patch

from custom_components.mikrotik_router.entity import (
    copy_attrs,
    _skip_sensor,
    MikrotikEntity,
    MikrotikInterfaceEntityMixin,
)
from custom_components.mikrotik_router.const import (
    CONF_SENSOR_PORT_TRAFFIC,
    CONF_SENSOR_PORT_TRACKER,
    CONF_SENSOR_NETWATCH_TRACKER,
    CONF_TRACK_HOSTS,
    CONF_SENSOR_POE,
)
from .conftest import (
    make_mock_coordinator,
    make_mock_entity_description,
    patch_coordinator_entity_init,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_entity_desc(**kwargs):
    """Build a minimal entity_description MagicMock with given attributes."""
    desc = MagicMock()
    desc.func = kwargs.get("func", "MikrotikSensor")
    desc.data_path = kwargs.get("data_path", "interface")
    desc.data_attribute = kwargs.get("data_attribute", "tx")
    return desc


def make_config_entry(options=None):
    """Build a mock config_entry with the given options dict."""
    cfg = MagicMock()
    cfg.options = options or {}
    return cfg


def _make_entity(coordinator=None, desc_overrides=None, uid=None):
    """Build a MikrotikEntity with patched CoordinatorEntity.__init__."""
    coord = coordinator or make_mock_coordinator()
    desc = make_mock_entity_description(**(desc_overrides or {}))
    with patch_coordinator_entity_init():
        entity = MikrotikEntity(coord, desc, uid)
    return entity


# ---------------------------------------------------------------------------
# MikrotikEntity.__init__ tests
# ---------------------------------------------------------------------------


class TestMikrotikEntityInit:
    """Tests for MikrotikEntity construction."""

    def test_init_without_uid(self):
        """Entity without uid uses data_path data directly."""
        coord = make_mock_coordinator()
        coord.data["health"] = {"temperature": 45}
        desc = make_mock_entity_description(data_path="health", data_attribute="temperature", data_reference="")
        with patch_coordinator_entity_init():
            entity = MikrotikEntity(coord, desc)
        assert entity._inst == "TestRouter"
        assert entity._uid is None
        assert entity._data == {"temperature": 45}

    def test_init_with_uid(self):
        """Entity with uid indexes into nested data."""
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True, "type": "ether"}}
        desc = make_mock_entity_description(data_path="interface", data_reference="name")
        with patch_coordinator_entity_init():
            entity = MikrotikEntity(coord, desc, uid="ether1")
        assert entity._uid == "ether1"
        assert entity._data["name"] == "ether1"


# ---------------------------------------------------------------------------
# MikrotikEntity.custom_name tests
# ---------------------------------------------------------------------------


class TestMikrotikEntityCustomName:
    """Tests for entity custom_name property."""

    def test_custom_name_no_uid_returns_description_name(self):
        entity = _make_entity(
            desc_overrides={"name": "Uptime", "data_path": "resource"},
            coordinator=make_mock_coordinator(
                data={
                    "resource": {"uptime": 12345},
                    "routerboard": {"serial-number": "X"},
                }
            ),
        )
        assert entity.custom_name == "Uptime"

    def test_custom_name_no_uid_comment_override(self):
        coord = make_mock_coordinator(
            data={
                "resource": {"uptime": 12345, "comment": "My Router Uptime"},
                "routerboard": {"serial-number": "X"},
            }
        )
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "name": "Uptime",
                "data_path": "resource",
                "data_name_comment": True,
            },
        )
        assert entity.custom_name == "My Router Uptime"

    def test_custom_name_with_uid_reference_equals_name_shortens(self):
        """When data_reference == data_name, name is just entity_description.name."""
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True}}
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "name": "Port",
                "data_path": "interface",
                "data_reference": "name",
                "data_name": "name",
            },
            uid="ether1",
        )
        assert entity.custom_name == "Port"

    def test_custom_name_with_uid_different_reference_and_name(self):
        """When data_reference != data_name, includes data_name in output."""
        coord = make_mock_coordinator()
        coord.data["interface"] = {
            "ether1": {
                "name": "ether1",
                "default-name": "ether1",
                "mac": "AA:BB:CC:DD:EE:FF",
            }
        }
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "name": "TX",
                "data_path": "interface",
                "data_reference": "mac",
                "data_name": "name",
            },
            uid="ether1",
        )
        assert entity.custom_name == "ether1 TX"

    def test_custom_name_with_uid_no_description_name(self):
        """When entity_description.name is empty, returns just data_name."""
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1"}}
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "name": "",
                "data_path": "interface",
                "data_name": "name",
            },
            uid="ether1",
        )
        assert entity.custom_name == "ether1"


# ---------------------------------------------------------------------------
# MikrotikEntity.unique_id tests
# ---------------------------------------------------------------------------


class TestMikrotikEntityUniqueId:
    def test_unique_id_without_uid(self):
        entity = _make_entity(
            desc_overrides={"key": "system_uptime", "data_path": "resource"},
            coordinator=make_mock_coordinator(data={"resource": {"uptime": 1}, "routerboard": {"serial-number": "X"}}),
        )
        assert entity.unique_id == "testrouter-system_uptime"

    def test_unique_id_with_uid(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "mac": "AA:BB"}}
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "key": "port_status",
                "data_path": "interface",
                "data_reference": "name",
            },
            uid="ether1",
        )
        assert entity.unique_id == "testrouter-port_status-ether1"


# ---------------------------------------------------------------------------
# MikrotikEntity.device_info tests
# ---------------------------------------------------------------------------


class TestMikrotikEntityDeviceInfo:
    def test_device_info_system_group(self):
        coord = make_mock_coordinator()
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "ha_group": "System",
                "data_path": "resource",
                "data_reference": "",
            },
        )
        info = entity.device_info
        assert info["model"] == "hAP ax3"
        assert info["manufacturer"] == "MikroTik"

    def test_device_info_mac_address_group(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "mac-address": "AA:BB:CC:DD:EE:FF"}}
        coord.data["host"] = {"AA:BB:CC:DD:EE:FF": {"host-name": "MyPC", "manufacturer": "Intel"}}
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "ha_group": "Interface",
                "data_path": "interface",
                "data_reference": "mac-address",
                "data_name": "name",
                "ha_connection": None,
                "ha_connection_value": "data__mac-address",
            },
            uid="ether1",
        )
        info = entity.device_info
        assert info["name"] == "MyPC"
        assert info["manufacturer"] == "Intel"

    def test_device_info_generic_group(self):
        coord = make_mock_coordinator()
        coord.data["nat"] = {"rule1": {"name": "NAT Rule 1", "chain": "srcnat"}}
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "ha_group": "NAT",
                "data_path": "nat",
                "data_reference": "name",
                "data_name": "name",
                "ha_connection": None,
                "ha_connection_value": None,
            },
            uid="rule1",
        )
        info = entity.device_info
        assert "via_device" in info


# ---------------------------------------------------------------------------
# MikrotikEntity.extra_state_attributes tests
# ---------------------------------------------------------------------------


class TestMikrotikEntityExtraStateAttributes:
    def test_copies_data_attributes_list(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "rate": "1Gbps", "status": "up"}}
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={
                "data_path": "interface",
                "data_attributes_list": ["rate", "status"],
            },
            uid="ether1",
        )
        attrs = entity.extra_state_attributes
        assert attrs["rate"] == "1Gbps"
        assert attrs["status"] == "up"


# ---------------------------------------------------------------------------
# MikrotikEntity._handle_coordinator_update tests
# ---------------------------------------------------------------------------


class TestMikrotikEntityCoordinatorUpdate:
    def test_handle_update_refreshes_data_with_uid(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True}}
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={"data_path": "interface", "data_reference": "name"},
            uid="ether1",
        )
        # Simulate coordinator data change
        coord.data["interface"]["ether1"]["enabled"] = False
        with patch.object(type(entity).__mro__[2], "_handle_coordinator_update", return_value=None):
            entity._handle_coordinator_update()
        assert entity._data["enabled"] is False

    def test_handle_update_refreshes_data_without_uid(self):
        coord = make_mock_coordinator()
        coord.data["resource"] = {"uptime": 100}
        entity = _make_entity(
            coordinator=coord,
            desc_overrides={"data_path": "resource"},
        )
        coord.data["resource"]["uptime"] = 200
        with patch.object(type(entity).__mro__[2], "_handle_coordinator_update", return_value=None):
            entity._handle_coordinator_update()
        assert entity._data["uptime"] == 200


# ---------------------------------------------------------------------------
# Traffic sensor tests
# ---------------------------------------------------------------------------


def test_skip_traffic_sensor_when_option_disabled():
    """Traffic sensor is skipped when CONF_SENSOR_PORT_TRAFFIC is False."""
    desc = make_entity_desc(func="MikrotikInterfaceTrafficSensor")
    data = {"ether1": {"type": "ether"}}
    cfg = make_config_entry({CONF_SENSOR_PORT_TRAFFIC: False})

    assert _skip_sensor(cfg, desc, data, "ether1") is True


def test_skip_traffic_sensor_on_bridge_interface():
    """Traffic sensor is skipped for bridge-type interfaces."""
    desc = make_entity_desc(func="MikrotikInterfaceTrafficSensor")
    data = {"bridge1": {"type": "bridge"}}
    cfg = make_config_entry({CONF_SENSOR_PORT_TRAFFIC: True})

    assert _skip_sensor(cfg, desc, data, "bridge1") is True


def test_no_skip_traffic_sensor_on_ether_interface():
    """Traffic sensor is not skipped for ether interfaces when option enabled."""
    desc = make_entity_desc(func="MikrotikInterfaceTrafficSensor")
    data = {"ether1": {"type": "ether"}}
    cfg = make_config_entry({CONF_SENSOR_PORT_TRAFFIC: True})

    assert _skip_sensor(cfg, desc, data, "ether1") is False


# ---------------------------------------------------------------------------
# Port binary sensor tests
# ---------------------------------------------------------------------------


def test_skip_port_binary_sensor_on_wlan_interface():
    """Port binary sensor is skipped for wlan-type interfaces."""
    desc = make_entity_desc(func="MikrotikPortBinarySensor")
    data = {"wlan1": {"type": "wlan"}}
    cfg = make_config_entry({CONF_SENSOR_PORT_TRACKER: True})

    assert _skip_sensor(cfg, desc, data, "wlan1") is True


def test_skip_port_binary_sensor_when_option_disabled():
    """Port binary sensor is skipped when CONF_SENSOR_PORT_TRACKER is False."""
    desc = make_entity_desc(func="MikrotikPortBinarySensor")
    data = {"ether1": {"type": "ether"}}
    cfg = make_config_entry({CONF_SENSOR_PORT_TRACKER: False})

    assert _skip_sensor(cfg, desc, data, "ether1") is True


def test_no_skip_port_binary_sensor_on_ether_when_enabled():
    """Port binary sensor is not skipped for ether interface when option enabled."""
    desc = make_entity_desc(func="MikrotikPortBinarySensor")
    data = {"ether1": {"type": "ether"}}
    cfg = make_config_entry({CONF_SENSOR_PORT_TRACKER: True})

    assert _skip_sensor(cfg, desc, data, "ether1") is False


# ---------------------------------------------------------------------------
# Netwatch + host tracker tests
# ---------------------------------------------------------------------------


def test_skip_netwatch_sensor_when_option_disabled():
    """Netwatch sensor is skipped when CONF_SENSOR_NETWATCH_TRACKER is False."""
    desc = make_entity_desc(data_path="netwatch")
    data = {"8.8.8.8": {"host": "8.8.8.8"}}
    cfg = make_config_entry({CONF_SENSOR_NETWATCH_TRACKER: False})

    assert _skip_sensor(cfg, desc, data, "8.8.8.8") is True


def test_skip_host_tracker_when_option_disabled():
    """Host device tracker is skipped when CONF_TRACK_HOSTS is False."""
    desc = make_entity_desc(func="MikrotikHostDeviceTracker")
    data = {"aa:bb:cc:dd:ee:ff": {"mac-address": "aa:bb:cc:dd:ee:ff"}}
    cfg = make_config_entry({CONF_TRACK_HOSTS: False})

    assert _skip_sensor(cfg, desc, data, "aa:bb:cc:dd:ee:ff") is True


# ---------------------------------------------------------------------------
# PoE sensor tests
# ---------------------------------------------------------------------------


def test_skip_poe_sensor_when_option_disabled():
    """PoE-out sensor is skipped when CONF_SENSOR_POE is False."""
    desc = make_entity_desc(data_attribute="poe-out-status")
    data = {
        "ether1": {
            "type": "ether",
            "poe-out": "auto-on",
            "poe-out-status": "powered-on",
        }
    }
    cfg = make_config_entry({CONF_SENSOR_POE: False})

    assert _skip_sensor(cfg, desc, data, "ether1") is True


def test_skip_poe_sensor_when_interface_not_poe_capable():
    """PoE-out sensor is skipped when poe-out-status is None (non-PoE interface)."""
    desc = make_entity_desc(data_attribute="poe-out-status")
    data = {"ether1": {"type": "ether", "poe-out": "N/A"}}
    cfg = make_config_entry({CONF_SENSOR_POE: True})

    assert _skip_sensor(cfg, desc, data, "ether1") is True


def test_no_skip_poe_sensor_on_poe_capable_interface():
    """PoE-out sensor is not skipped when poe-out-status is set and option enabled."""
    desc = make_entity_desc(data_attribute="poe-out-status")
    data = {
        "ether1": {
            "type": "ether",
            "poe-out": "auto-on",
            "poe-out-status": "powered-on",
        }
    }
    cfg = make_config_entry({CONF_SENSOR_POE: True})

    assert _skip_sensor(cfg, desc, data, "ether1") is False


def test_skip_poe_voltage_sensor_on_non_poe_interface():
    """PoE-out voltage sensor is also skipped on non-PoE interfaces."""
    desc = make_entity_desc(data_attribute="poe-out-voltage")
    data = {"ether1": {"type": "ether"}}
    cfg = make_config_entry({CONF_SENSOR_POE: True})

    assert _skip_sensor(cfg, desc, data, "ether1") is True


def test_skip_poe_measurement_sensor_when_value_is_none():
    """PoE measurement sensors are skipped when API returns None (passive PoE hardware).

    Passive PoE ports (e.g. hAP ax3 ether1) report poe-out-status but the
    measurement fields are absent from the API response and default to None.
    """
    desc = make_entity_desc(data_attribute="poe-out-voltage")
    data = {
        "ether1": {
            "type": "ether",
            "poe-out": "auto-on",
            "poe-out-status": "powered-on",
            "poe-out-voltage": None,
            "poe-out-current": None,
            "poe-out-power": None,
        }
    }
    cfg = make_config_entry({CONF_SENSOR_POE: True})

    assert _skip_sensor(cfg, desc, data, "ether1") is True


def test_no_skip_poe_measurement_sensor_when_hardware_reports_values():
    """PoE measurement sensors are shown when hardware returns real values (CRS, etc.)."""
    desc = make_entity_desc(data_attribute="poe-out-voltage")
    data = {
        "ether1": {
            "type": "ether",
            "poe-out": "auto-on",
            "poe-out-status": "powered-on",
            "poe-out-voltage": 23.8,
            "poe-out-current": 180,
            "poe-out-power": 4.3,
        }
    }
    cfg = make_config_entry({CONF_SENSOR_POE: True})

    assert _skip_sensor(cfg, desc, data, "ether1") is False


# ---------------------------------------------------------------------------
# Client traffic test
# ---------------------------------------------------------------------------


def test_skip_client_traffic_when_attribute_missing():
    """Client traffic sensor is skipped when attribute is not in the data entry."""
    desc = make_entity_desc(data_path="client_traffic", data_attribute="tx-rx-bytes")
    data = {"aa:bb:cc:dd:ee:ff": {"mac-address": "aa:bb:cc:dd:ee:ff"}}
    cfg = make_config_entry()

    assert _skip_sensor(cfg, desc, data, "aa:bb:cc:dd:ee:ff") is True


def test_skip_poe_sensor_when_uid_absent_from_data():
    """PoE sensor is skipped when uid is not present in the data dict at all.

    Guards against KeyError introduced in the PoE uid-not-in-data fix.
    """
    desc = make_entity_desc(data_attribute="poe-out-status")
    data = {}  # uid not present
    cfg = make_config_entry({CONF_SENSOR_POE: True})

    assert _skip_sensor(cfg, desc, data, "ether1") is True


# ---------------------------------------------------------------------------
# MikrotikInterfaceEntityMixin tests
# ---------------------------------------------------------------------------


class _BaseSpy:
    """Minimal base that simulates the HA base-class extra_state_attributes."""

    @property
    def extra_state_attributes(self):
        return {"attribution": "Mikrotik"}


class _ConcreteEntity(MikrotikInterfaceEntityMixin, _BaseSpy):
    """Concrete entity used to exercise the mixin without a real coordinator."""

    def __init__(self, data):
        self._data = data


def test_mixin_ether_adds_ether_attributes():
    """Ether-type interface populates ether-specific attributes."""
    entity = _ConcreteEntity({"type": "ether", "status": "link-ok", "rate": "1Gbps"})
    attrs = entity.extra_state_attributes
    assert "status" in attrs
    assert attrs["status"] == "link-ok"
    assert "rate" in attrs
    assert attrs["rate"] == "1Gbps"
    # SFP attrs should NOT be present on copper ports
    assert "sfp_temperature" not in attrs
    assert "sfp_vendor_name" not in attrs


def test_mixin_ether_skips_missing_ether_keys():
    """Only attributes actually present in _data are included."""
    entity = _ConcreteEntity({"type": "ether"})
    attrs = entity.extra_state_attributes
    # DEVICE_ATTRIBUTES_IFACE_ETHER keys should be absent when not in _data
    assert "status" not in attrs
    assert "auto_negotiation" not in attrs


def test_mixin_ether_with_sfp_adds_sfp_attributes():
    """SFP attributes are added for ether interfaces that expose sfp-shutdown-temperature."""
    entity = _ConcreteEntity(
        {
            "type": "ether",
            "sfp-shutdown-temperature": "95C",
            "sfp-temperature": "45C",
            "sfp-vendor-name": "ACME",
        }
    )
    attrs = entity.extra_state_attributes
    assert "sfp_temperature" in attrs
    assert attrs["sfp_temperature"] == "45C"
    assert "sfp_vendor_name" in attrs
    # Copper-only attrs should NOT appear on SFP ports
    assert "rate" not in attrs
    assert "full_duplex" not in attrs


def test_mixin_ether_sfp_skips_junk_defaults():
    """SFP attributes with 'unknown' or None values are omitted."""
    entity = _ConcreteEntity(
        {
            "type": "ether",
            "sfp-shutdown-temperature": "95C",
            "sfp-temperature": "45C",
            "sfp-vendor-name": "unknown",
            "sfp-rx-power": None,
            "sfp-module-present": "yes",
        }
    )
    attrs = entity.extra_state_attributes
    assert attrs["sfp_temperature"] == "45C"
    assert "sfp_vendor_name" not in attrs
    assert "sfp_rx_power" not in attrs
    assert attrs["sfp_module_present"] == "yes"


def test_mixin_ether_without_sfp_does_not_add_sfp_attributes():
    """SFP attributes are omitted when sfp-shutdown-temperature is absent."""
    entity = _ConcreteEntity({"type": "ether", "status": "link-ok", "sfp-temperature": "45C"})
    attrs = entity.extra_state_attributes
    # sfp-temperature present in data but sfp-shutdown-temperature is not → SFP block skipped
    assert "sfp_temperature" not in attrs


def test_mixin_ether_sfp_shutdown_temp_zero_means_no_sfp():
    """sfp-shutdown-temperature defaulting to 0 (coordinator default) is treated as no SFP."""
    entity = _ConcreteEntity(
        {
            "type": "ether",
            "sfp-shutdown-temperature": 0,
            "sfp-temperature": 0,
            "sfp-vendor-name": "unknown",
            "status": "link-ok",
            "rate": "1Gbps",
        }
    )
    attrs = entity.extra_state_attributes
    # Should show copper attrs, NOT SFP attrs
    assert attrs["status"] == "link-ok"
    assert attrs["rate"] == "1Gbps"
    assert "sfp_temperature" not in attrs
    assert "sfp_vendor_name" not in attrs


def test_mixin_ether_poe_out_shown_when_supported():
    """poe-out is shown only when the port has PoE support."""
    entity = _ConcreteEntity({"type": "ether", "poe-out": "auto-on"})
    attrs = entity.extra_state_attributes
    assert attrs["poe_out"] == "auto-on"


def test_mixin_ether_poe_out_hidden_when_na():
    """poe-out 'N/A' (non-PoE ports) is not shown."""
    entity = _ConcreteEntity({"type": "ether", "poe-out": "N/A"})
    attrs = entity.extra_state_attributes
    assert "poe_out" not in attrs


def test_mixin_client_attrs_shown_when_meaningful():
    """client-ip-address and client-mac-address shown when they have real values."""
    entity = _ConcreteEntity(
        {
            "type": "ether",
            "client-ip-address": "192.168.1.10",
            "client-mac-address": "AA:BB:CC:DD:EE:FF",
        }
    )
    attrs = entity.extra_state_attributes
    assert attrs["client_ip_address"] == "192.168.1.10"
    assert attrs["client_mac_address"] == "AA:BB:CC:DD:EE:FF"


def test_mixin_client_attrs_hidden_when_junk():
    """client-ip-address and client-mac-address hidden when 'unknown'/'none'."""
    entity = _ConcreteEntity({"type": "ether", "client-ip-address": "unknown", "client-mac-address": "none"})
    attrs = entity.extra_state_attributes
    assert "client_ip_address" not in attrs
    assert "client_mac_address" not in attrs


def test_mixin_wlan_adds_wireless_attributes():
    """Wlan-type interface populates wireless-specific attributes."""
    entity = _ConcreteEntity({"type": "wlan", "ssid": "MyWifi", "band": "2ghz-b/g/n"})
    attrs = entity.extra_state_attributes
    assert "ssid" in attrs
    assert attrs["ssid"] == "MyWifi"
    assert "band" in attrs


def test_mixin_other_type_adds_no_type_specific_attributes():
    """Non-ether/wlan interfaces (e.g. bridge) produce no type-specific attributes."""
    entity = _ConcreteEntity({"type": "bridge", "status": "active"})
    attrs = entity.extra_state_attributes
    assert "status" not in attrs
    assert "attribution" in attrs


def test_mixin_missing_type_adds_no_extra_attributes():
    """Missing 'type' key is treated the same as an unrecognised type."""
    entity = _ConcreteEntity({"status": "active"})
    attrs = entity.extra_state_attributes
    assert "status" not in attrs
    assert "attribution" in attrs


def test_mixin_preserves_base_attributes():
    """Mixin does not overwrite attributes returned by the base class."""
    entity = _ConcreteEntity({"type": "ether", "status": "link-ok"})
    attrs = entity.extra_state_attributes
    assert attrs["attribution"] == "Mikrotik"


# ---------------------------------------------------------------------------
# copy_attrs tests
# ---------------------------------------------------------------------------


def testcopy_attrs_copies_existing_keys():
    """Copies matching variables from data to attributes."""
    attributes = {}
    data = {"status": "up", "rate": "1Gbps", "unused": "value"}
    copy_attrs(attributes, data, ["status", "rate"])
    assert "status" in attributes
    assert "rate" in attributes
    assert "unused" not in attributes


def testcopy_attrs_skips_missing_keys():
    """Missing keys in data are skipped without error."""
    attributes = {}
    data = {"status": "up"}
    copy_attrs(attributes, data, ["status", "missing-key"])
    assert "status" in attributes
    assert len(attributes) == 1


def testcopy_attrs_empty_variables_list():
    """Empty variables list copies nothing."""
    attributes = {}
    data = {"status": "up"}
    copy_attrs(attributes, data, [])
    assert len(attributes) == 0


def testcopy_attrs_skip_junk_filters_defaults():
    """skip_junk=True omits 'unknown', 'none', 'N/A', and None values."""
    attributes = {}
    data = {
        "real": "link-ok",
        "junk1": "unknown",
        "junk2": "none",
        "junk3": "N/A",
        "junk4": None,
        "zero": 0,
        "empty": "",
    }
    copy_attrs(
        attributes,
        data,
        ["real", "junk1", "junk2", "junk3", "junk4", "zero", "empty"],
        skip_junk=True,
    )
    assert attributes["real"] == "link-ok"
    assert "junk1" not in attributes
    assert "junk2" not in attributes
    assert "junk3" not in attributes
    assert "junk4" not in attributes
    # 0 and "" are NOT filtered — they can be valid values
    assert attributes["zero"] == 0
    assert attributes["empty"] == ""


def testcopy_attrs_without_skip_junk_includes_all():
    """Default skip_junk=False preserves all values including junk defaults."""
    attributes = {}
    data = {"status": "unknown", "rate": None}
    copy_attrs(attributes, data, ["status", "rate"])
    assert attributes["status"] == "unknown"
    assert attributes["rate"] is None


# ---------------------------------------------------------------------------
# Client traffic skip tests
# ---------------------------------------------------------------------------


def test_no_skip_client_traffic_when_attribute_present():
    """Client traffic sensor allowed when attribute exists in data entry."""
    desc = make_entity_desc(data_path="client_traffic", data_attribute="wan-tx")
    data = {"aa:bb:cc:dd:ee:ff": {"wan-tx": 100}}
    cfg = make_config_entry()
    assert _skip_sensor(cfg, desc, data, "aa:bb:cc:dd:ee:ff") is False


# ---------------------------------------------------------------------------
# Host tracker allowed test
# ---------------------------------------------------------------------------


def test_no_skip_host_tracker_when_enabled():
    """Host device tracker allowed when CONF_TRACK_HOSTS is True."""
    desc = make_entity_desc(
        func="MikrotikHostDeviceTracker",
        data_attribute="available",
    )
    data = {"aa:bb:cc:dd:ee:ff": {"available": True}}
    cfg = make_config_entry({CONF_TRACK_HOSTS: True})
    assert _skip_sensor(cfg, desc, data, "aa:bb:cc:dd:ee:ff") is False


# ---------------------------------------------------------------------------
# Netwatch allowed test
# ---------------------------------------------------------------------------


def test_no_skip_netwatch_when_enabled():
    """Netwatch sensor allowed when CONF_SENSOR_NETWATCH_TRACKER is True."""
    desc = make_entity_desc(
        data_path="netwatch",
        data_attribute="status",
    )
    data = {"8.8.8.8": {"status": "up"}}
    cfg = make_config_entry({CONF_SENSOR_NETWATCH_TRACKER: True})
    assert _skip_sensor(cfg, desc, data, "8.8.8.8") is False
