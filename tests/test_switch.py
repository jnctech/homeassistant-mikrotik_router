"""Tests for Mikrotik Router switch entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.mikrotik_router.switch import (
    MikrotikSwitch,
    MikrotikPortSwitch,
    MikrotikNATSwitch,
    MikrotikQueueSwitch,
    MikrotikKidcontrolPauseSwitch,
    MikrotikRawSwitch,
    MikrotikContainerSwitch,
)

from .conftest import (
    make_mock_coordinator,
    make_mock_entity_description,
    patch_coordinator_entity_init,
)


def _make_switch(cls=MikrotikSwitch, coordinator=None, desc_overrides=None, uid=None):
    coord = coordinator or make_mock_coordinator()
    desc = make_mock_entity_description(**(desc_overrides or {}))
    with patch_coordinator_entity_init():
        entity = cls(coord, desc, uid)
    entity.hass = MagicMock()
    entity.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw))
    return entity


_SWITCH_DESC = {
    "data_path": "interface",
    "data_attribute": "enabled",
    "data_reference": "name",
    "data_name": "name",
    "data_switch_path": "/interface",
    "data_switch_parameter": "disabled",
    "icon_enabled": "mdi:check",
    "icon_disabled": "mdi:close",
}


# ---------------------------------------------------------------------------
# MikrotikSwitch
# ---------------------------------------------------------------------------


class TestMikrotikSwitch:
    def test_is_on_true(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True}}
        entity = _make_switch(
            coordinator=coord,
            desc_overrides={**_SWITCH_DESC},
            uid="ether1",
        )
        assert entity.is_on is True

    def test_is_on_false(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": False}}
        entity = _make_switch(
            coordinator=coord,
            desc_overrides={**_SWITCH_DESC},
            uid="ether1",
        )
        assert entity.is_on is False

    def test_icon_when_on(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True}}
        entity = _make_switch(
            coordinator=coord,
            desc_overrides={**_SWITCH_DESC},
            uid="ether1",
        )
        assert entity.icon == "mdi:check"

    def test_icon_when_off(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": False}}
        entity = _make_switch(
            coordinator=coord,
            desc_overrides={**_SWITCH_DESC},
            uid="ether1",
        )
        assert entity.icon == "mdi:close"

    @pytest.mark.asyncio
    async def test_async_turn_on_calls_set_value(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True}}
        entity = _make_switch(coordinator=coord, desc_overrides={**_SWITCH_DESC}, uid="ether1")
        await entity.async_turn_on()
        coord.set_value.assert_called_once_with("/interface", "name", "ether1", "disabled", False)
        coord.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_turn_off_calls_set_value(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True}}
        entity = _make_switch(coordinator=coord, desc_overrides={**_SWITCH_DESC}, uid="ether1")
        await entity.async_turn_off()
        coord.set_value.assert_called_once_with("/interface", "name", "ether1", "disabled", True)

    @pytest.mark.asyncio
    async def test_async_turn_on_raises_without_write_access(self):
        coord = make_mock_coordinator()
        coord.data["access"] = ["policy", "reboot"]  # no "write"
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True}}
        entity = _make_switch(coordinator=coord, desc_overrides={**_SWITCH_DESC}, uid="ether1")
        with pytest.raises(HomeAssistantError, match="Write access required"):
            await entity.async_turn_on()
        coord.set_value.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_turn_off_raises_without_write_access(self):
        coord = make_mock_coordinator()
        coord.data["access"] = ["policy"]
        coord.data["interface"] = {"ether1": {"name": "ether1", "enabled": True}}
        entity = _make_switch(coordinator=coord, desc_overrides={**_SWITCH_DESC}, uid="ether1")
        with pytest.raises(HomeAssistantError, match="Write access required"):
            await entity.async_turn_off()
        coord.set_value.assert_not_called()


# ---------------------------------------------------------------------------
# MikrotikPortSwitch
# ---------------------------------------------------------------------------


_PORT_DESC = {
    **_SWITCH_DESC,
    "func": "MikrotikPortSwitch",
}


class TestMikrotikPortSwitch:
    def _make_port_data(self, **overrides):
        data = {
            "name": "ether1",
            "enabled": True,
            "running": True,
            "type": "ether",
            "about": "",
            "port-mac-address": "AA:BB:CC:DD:EE:FF",
        }
        data.update(overrides)
        return data

    @pytest.mark.asyncio
    async def test_turn_on_capsman_managed_returns_error(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"wlan1": self._make_port_data(name="wlan1", about="managed by CAPsMAN")}
        entity = _make_switch(
            cls=MikrotikPortSwitch,
            coordinator=coord,
            desc_overrides={**_PORT_DESC},
            uid="wlan1",
        )
        result = await entity.async_turn_on()
        assert result == "managed by CAPsMAN"
        coord.set_value.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_on_uses_name_param_when_mac_has_dashes(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": self._make_port_data(port_mac="AA-BB-CC-DD-EE-FF")}
        # The port-mac-address has dashes → param should switch to "name"
        coord.data["interface"]["ether1"]["port-mac-address"] = "AA-BB-CC-DD-EE-FF"
        entity = _make_switch(
            cls=MikrotikPortSwitch,
            coordinator=coord,
            desc_overrides={**_PORT_DESC},
            uid="ether1",
        )
        await entity.async_turn_on()
        # set_value should have been called with param="name"
        call_args = coord.set_value.call_args[0]
        assert call_args[1] == "name"

    @pytest.mark.asyncio
    async def test_turn_on_enables_poe_when_off(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": self._make_port_data(**{"poe-out": "off"})}
        entity = _make_switch(
            cls=MikrotikPortSwitch,
            coordinator=coord,
            desc_overrides={**_PORT_DESC},
            uid="ether1",
        )
        await entity.async_turn_on()
        # Should have two set_value calls: interface enable + poe-out auto-on
        assert coord.set_value.call_count == 2
        poe_call = coord.set_value.call_args_list[1][0]
        assert poe_call[0] == "/interface/ethernet"
        assert poe_call[3] == "poe-out"
        assert poe_call[4] == "auto-on"

    @pytest.mark.asyncio
    async def test_turn_off_disables_poe_when_auto_on(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": self._make_port_data(**{"poe-out": "auto-on"})}
        entity = _make_switch(
            cls=MikrotikPortSwitch,
            coordinator=coord,
            desc_overrides={**_PORT_DESC},
            uid="ether1",
        )
        await entity.async_turn_off()
        assert coord.set_value.call_count == 2
        poe_call = coord.set_value.call_args_list[1][0]
        assert poe_call[3] == "poe-out"
        assert poe_call[4] == "off"

    def test_icon_disabled_interface(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": self._make_port_data(enabled=False, running=False)}
        entity = _make_switch(
            cls=MikrotikPortSwitch,
            coordinator=coord,
            desc_overrides={**_PORT_DESC},
            uid="ether1",
        )
        assert entity.icon == "mdi:lan-disconnect"

    def test_icon_running(self):
        coord = make_mock_coordinator()
        coord.data["interface"] = {"ether1": self._make_port_data(enabled=True, running=True)}
        entity = _make_switch(
            cls=MikrotikPortSwitch,
            coordinator=coord,
            desc_overrides={**_PORT_DESC},
            uid="ether1",
        )
        assert entity.icon == "mdi:check"


# ---------------------------------------------------------------------------
# MikrotikNATSwitch
# ---------------------------------------------------------------------------


class TestMikrotikNATSwitch:
    def _make_nat_data(self):
        return {
            "chain": "dstnat",
            "action": "dst-nat",
            "protocol": "tcp",
            "in-interface": "ether1",
            "dst-port": "80",
            "out-interface": "",
            "to-addresses": "192.168.1.10",
            "to-ports": "8080",
            "enabled": True,
            "name": "NAT Rule",
            "uniq-id": "dstnat,dst-nat,tcp,ether1:80-:192.168.1.10:8080",
            ".id": "*1",
        }

    @pytest.mark.asyncio
    async def test_turn_on_finds_id_by_uniq_id(self):
        coord = make_mock_coordinator()
        nat_data = self._make_nat_data()
        coord.data["nat"] = {"rule1": nat_data}
        coord.data["interface"] = {}  # not needed but data_path defaults
        # Entity data references the nat rule
        entity = _make_switch(
            cls=MikrotikNATSwitch,
            coordinator=coord,
            desc_overrides={
                **_SWITCH_DESC,
                "data_path": "nat",
                "data_switch_path": "/ip/firewall/nat",
            },
            uid="rule1",
        )
        await entity.async_turn_on()
        call_args = coord.set_value.call_args[0]
        assert call_args[1] == ".id"
        assert call_args[2] == "*1"


# ---------------------------------------------------------------------------
# MikrotikQueueSwitch
# ---------------------------------------------------------------------------


class TestMikrotikQueueSwitch:
    @pytest.mark.asyncio
    async def test_turn_on_finds_id_by_name(self):
        coord = make_mock_coordinator()
        coord.data["queue"] = {"q1": {"name": "download-limit", ".id": "*A", "enabled": True}}
        entity = _make_switch(
            cls=MikrotikQueueSwitch,
            coordinator=coord,
            desc_overrides={
                **_SWITCH_DESC,
                "data_path": "queue",
                "data_switch_path": "/queue/simple",
            },
            uid="q1",
        )
        await entity.async_turn_on()
        call_args = coord.set_value.call_args[0]
        assert call_args[1] == ".id"
        assert call_args[2] == "*A"

    @pytest.mark.asyncio
    async def test_turn_off_finds_id_by_name(self):
        coord = make_mock_coordinator()
        coord.data["queue"] = {"q1": {"name": "download-limit", ".id": "*A", "enabled": True}}
        entity = _make_switch(
            cls=MikrotikQueueSwitch,
            coordinator=coord,
            desc_overrides={
                **_SWITCH_DESC,
                "data_path": "queue",
                "data_switch_path": "/queue/simple",
            },
            uid="q1",
        )
        await entity.async_turn_off()
        call_args = coord.set_value.call_args[0]
        assert call_args[2] == "*A"


# ---------------------------------------------------------------------------
# MikrotikKidcontrolPauseSwitch
# ---------------------------------------------------------------------------


class TestMikrotikKidcontrolPauseSwitch:
    @pytest.mark.asyncio
    async def test_turn_on_calls_resume(self):
        coord = make_mock_coordinator()
        coord.data["kid-control"] = {"kid1": {"name": "kid1", "paused": True}}
        entity = _make_switch(
            cls=MikrotikKidcontrolPauseSwitch,
            coordinator=coord,
            desc_overrides={
                **_SWITCH_DESC,
                "data_path": "kid-control",
                "data_switch_path": "/ip/kid-control",
            },
            uid="kid1",
        )
        await entity.async_turn_on()
        coord.execute.assert_called_once()
        call_args = coord.execute.call_args[0]
        assert call_args[1] == "resume"

    @pytest.mark.asyncio
    async def test_turn_off_calls_pause(self):
        coord = make_mock_coordinator()
        coord.data["kid-control"] = {"kid1": {"name": "kid1", "paused": False}}
        entity = _make_switch(
            cls=MikrotikKidcontrolPauseSwitch,
            coordinator=coord,
            desc_overrides={
                **_SWITCH_DESC,
                "data_path": "kid-control",
                "data_switch_path": "/ip/kid-control",
            },
            uid="kid1",
        )
        await entity.async_turn_off()
        coord.execute.assert_called_once()
        call_args = coord.execute.call_args[0]
        assert call_args[1] == "pause"


# ---------------------------------------------------------------------------
# MikrotikRawSwitch
# ---------------------------------------------------------------------------


_RAW_DESC = {
    **_SWITCH_DESC,
    "data_path": "raw",
    "data_switch_path": "/ip/firewall/raw",
}


class TestMikrotikRawSwitch:
    def _make_raw_data(self):
        return {
            "chain": "prerouting",
            "action": "drop",
            "protocol": "tcp",
            "in-interface": "ether1",
            "in-interface-list": "any",
            "src-address": "any",
            "src-address-list": "any",
            "src-port": "any",
            "out-interface": "any",
            "out-interface-list": "any",
            "dst-address": "any",
            "dst-address-list": "any",
            "dst-port": "445",
            "enabled": True,
            "name": "drop,tcp:445",
            "uniq-id": "prerouting,drop,tcp,ether1,any:any,any:any-any,any:any,any:445",
            ".id": "*1",
            "comment": "Block SMB",
        }

    @pytest.mark.asyncio
    async def test_turn_on_finds_id_by_uniq_id(self):
        coord = make_mock_coordinator()
        raw_data = self._make_raw_data()
        coord.data["raw"] = {"rule1": raw_data}
        entity = _make_switch(
            cls=MikrotikRawSwitch,
            coordinator=coord,
            desc_overrides={**_RAW_DESC},
            uid="rule1",
        )
        await entity.async_turn_on()
        call_args = coord.set_value.call_args[0]
        assert call_args[1] == ".id"
        assert call_args[2] == "*1"
        assert call_args[4] is False  # mod_value = enable (disable=False)

    @pytest.mark.asyncio
    async def test_turn_off_finds_id_by_uniq_id(self):
        coord = make_mock_coordinator()
        raw_data = self._make_raw_data()
        coord.data["raw"] = {"rule1": raw_data}
        entity = _make_switch(
            cls=MikrotikRawSwitch,
            coordinator=coord,
            desc_overrides={**_RAW_DESC},
            uid="rule1",
        )
        await entity.async_turn_off()
        call_args = coord.set_value.call_args[0]
        assert call_args[1] == ".id"
        assert call_args[2] == "*1"
        assert call_args[4] is True  # mod_value = disable (disable=True)

    @pytest.mark.asyncio
    async def test_turn_on_no_write_access(self):
        coord = make_mock_coordinator()
        coord.data["access"] = ["read"]
        coord.data["raw"] = {"rule1": self._make_raw_data()}
        entity = _make_switch(
            cls=MikrotikRawSwitch,
            coordinator=coord,
            desc_overrides={**_RAW_DESC},
            uid="rule1",
        )
        with pytest.raises(HomeAssistantError, match="Write access required"):
            await entity.async_turn_on()
        coord.set_value.assert_not_called()


# ---------------------------------------------------------------------------
# MikrotikContainerSwitch
# ---------------------------------------------------------------------------


_CONTAINER_DESC = {
    **_SWITCH_DESC,
    "data_path": "container",
    "data_attribute": "running",
    "data_switch_path": "/container",
    "data_uid": ".id",
    "data_reference": ".id",
}


class TestMikrotikContainerSwitch:
    def _make_container_data(self):
        return {
            ".id": "*1",
            "name": "pihole",
            "tag": "pihole/pihole:latest",
            "os": "linux",
            "arch": "arm64",
            "interface": "veth-pihole",
            "status": "running",
            "running": True,
            "comment": "",
        }

    @pytest.mark.asyncio
    async def test_turn_on_starts_container(self):
        coord = make_mock_coordinator()
        ct_data = self._make_container_data()
        coord.data["container"] = {"*1": ct_data}
        entity = _make_switch(
            cls=MikrotikContainerSwitch,
            coordinator=coord,
            desc_overrides={**_CONTAINER_DESC},
            uid="*1",
        )
        await entity.async_turn_on()
        coord.execute.assert_called_once()
        call_args = coord.execute.call_args[0]
        assert call_args[0] == "/container"
        assert call_args[1] == "start"
        assert call_args[2] == ".id"
        assert call_args[3] == "*1"

    @pytest.mark.asyncio
    async def test_turn_off_stops_container(self):
        coord = make_mock_coordinator()
        ct_data = self._make_container_data()
        coord.data["container"] = {"*1": ct_data}
        entity = _make_switch(
            cls=MikrotikContainerSwitch,
            coordinator=coord,
            desc_overrides={**_CONTAINER_DESC},
            uid="*1",
        )
        await entity.async_turn_off()
        coord.execute.assert_called_once()
        call_args = coord.execute.call_args[0]
        assert call_args[0] == "/container"
        assert call_args[1] == "stop"

    @pytest.mark.asyncio
    async def test_turn_on_no_write_access(self):
        coord = make_mock_coordinator()
        coord.data["access"] = ["read"]
        coord.data["container"] = {"*1": self._make_container_data()}
        entity = _make_switch(
            cls=MikrotikContainerSwitch,
            coordinator=coord,
            desc_overrides={**_CONTAINER_DESC},
            uid="*1",
        )
        with pytest.raises(HomeAssistantError, match="Write access required"):
            await entity.async_turn_on()
        coord.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_turn_on_refreshes_coordinator(self):
        coord = make_mock_coordinator()
        ct_data = self._make_container_data()
        coord.data["container"] = {"*1": ct_data}
        entity = _make_switch(
            cls=MikrotikContainerSwitch,
            coordinator=coord,
            desc_overrides={**_CONTAINER_DESC},
            uid="*1",
        )
        await entity.async_turn_on()
        coord.async_refresh.assert_awaited_once()
