"""Tests for update.py — version list generation and update entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from packaging.version import Version

from custom_components.mikrotik_router.update import (
    MikrotikRouterOSUpdate,
    MikrotikRouterBoardFWUpdate,
    generate_version_list,
    decrement_version,
)

from custom_components.mikrotik_router.update_types import (
    MikrotikUpdateEntityDescription,
)

from .conftest import (
    make_mock_coordinator,
    make_mock_entity_description,
    patch_coordinator_entity_init,
)


# ---------------------------------------------------------------------------
# decrement_version
# ---------------------------------------------------------------------------


class TestDecrementVersion:
    def test_decrement_patch(self):
        """7.16.2 → 7.16.1"""
        result = decrement_version(Version("7.16.2"), Version("7.0"))
        assert result == Version("7.16.1")

    def test_decrement_patch_to_zero(self):
        """7.16.1 → 7.16.0"""
        result = decrement_version(Version("7.16.1"), Version("7.0"))
        assert result == Version("7.16.0")

    def test_decrement_rolls_minor(self):
        """7.16.0 → 7.15.999 (rolls minor when patch is 0)."""
        result = decrement_version(Version("7.16.0"), Version("7.0"))
        assert result == Version("7.15.999")

    def test_decrement_rolls_major(self):
        """7.0.0 → 6.999.999 (rolls major when minor is 0)."""
        result = decrement_version(Version("7.0.0"), Version("6.0"))
        assert result == Version("6.999.999")


# ---------------------------------------------------------------------------
# generate_version_list
# ---------------------------------------------------------------------------


class TestGenerateVersionList:
    def test_same_version(self):
        """Same start and end → single entry."""
        result = generate_version_list("7.16.0", "7.16.0")
        assert result == ["7.16.0"]

    def test_patch_range(self):
        """Short patch range generates correct list in reverse order."""
        result = generate_version_list("7.16.0", "7.16.2")
        assert result == ["7.16.2", "7.16.1", "7.16.0"]

    def test_start_included(self):
        """Start version is included in the list."""
        result = generate_version_list("7.16.1", "7.16.2")
        assert "7.16.1" in result
        assert "7.16.2" in result

    def test_reverse_order(self):
        """Versions are returned newest-first."""
        result = generate_version_list("7.16.0", "7.16.3")
        versions = [Version(v) for v in result]
        assert versions == sorted(versions, reverse=True)


# ---------------------------------------------------------------------------
# Helpers for entity tests
# ---------------------------------------------------------------------------


def _make_update_entity(cls=MikrotikRouterOSUpdate, coordinator=None, desc_overrides=None, uid=None):
    coord = coordinator or make_mock_coordinator()
    desc = make_mock_entity_description(cls=MikrotikUpdateEntityDescription, **(desc_overrides or {}))
    with patch_coordinator_entity_init():
        entity = cls(coord, desc, uid)
    entity.hass = MagicMock()
    entity.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw))
    return entity


_FW_UPDATE_DESC = {
    "data_path": "fw-update",
    "data_attribute": "available",
    "data_reference": "",
    "data_name": "",
    "title": "RouterOS",
}


# ---------------------------------------------------------------------------
# MikrotikRouterOSUpdate
# ---------------------------------------------------------------------------


class TestMikrotikRouterOSUpdate:
    def test_installed_version(self):
        coord = make_mock_coordinator()
        coord.data["fw-update"] = {
            "installed-version": "7.16.1",
            "latest-version": "7.16.2",
            "available": True,
        }
        entity = _make_update_entity(coordinator=coord, desc_overrides={**_FW_UPDATE_DESC})
        assert entity.installed_version == "7.16.1"

    def test_latest_version(self):
        coord = make_mock_coordinator()
        coord.data["fw-update"] = {
            "installed-version": "7.16.1",
            "latest-version": "7.16.2",
            "available": True,
        }
        entity = _make_update_entity(coordinator=coord, desc_overrides={**_FW_UPDATE_DESC})
        assert entity.latest_version == "7.16.2"

    @pytest.mark.asyncio
    async def test_async_install_without_backup(self):
        coord = make_mock_coordinator()
        coord.data["fw-update"] = {
            "installed-version": "7.16.1",
            "latest-version": "7.16.2",
            "available": True,
        }
        entity = _make_update_entity(coordinator=coord, desc_overrides={**_FW_UPDATE_DESC})
        await entity.async_install(version="7.16.2", backup=False)
        coord.execute.assert_called_once_with("/system/package/update", "install", None, None)

    @pytest.mark.asyncio
    async def test_async_install_with_backup(self):
        coord = make_mock_coordinator()
        coord.data["fw-update"] = {
            "installed-version": "7.16.1",
            "latest-version": "7.16.2",
            "available": True,
        }
        entity = _make_update_entity(coordinator=coord, desc_overrides={**_FW_UPDATE_DESC})
        await entity.async_install(version="7.16.2", backup=True)
        assert coord.execute.call_count == 2
        backup_call = coord.execute.call_args_list[0][0]
        assert backup_call[0] == "/system/backup"
        assert backup_call[1] == "save"
        install_call = coord.execute.call_args_list[1][0]
        assert install_call[0] == "/system/package/update"

    def test_release_url(self):
        entity = _make_update_entity(
            desc_overrides={**_FW_UPDATE_DESC},
            coordinator=make_mock_coordinator(
                data={
                    "fw-update": {
                        "installed-version": "7.16.1",
                        "latest-version": "7.16.2",
                        "available": True,
                    },
                    "resource": {"board-name": "x", "platform": "x", "version": "x"},
                    "routerboard": {"serial-number": "x"},
                }
            ),
        )
        assert "mikrotik.com" in entity.release_url


# ---------------------------------------------------------------------------
# MikrotikRouterBoardFWUpdate
# ---------------------------------------------------------------------------


_RB_UPDATE_DESC = {
    "data_path": "routerboard",
    "data_attribute": "available",
    "data_reference": "",
    "data_name": "",
    "title": "RouterBOARD Firmware",
}


class TestMikrotikRouterBoardFWUpdate:
    def test_installed_version(self):
        coord = make_mock_coordinator()
        coord.data["routerboard"] = {
            "serial-number": "X",
            "current-firmware": "7.16.1",
            "upgrade-firmware": "7.16.2",
        }
        entity = _make_update_entity(
            cls=MikrotikRouterBoardFWUpdate,
            coordinator=coord,
            desc_overrides={**_RB_UPDATE_DESC},
        )
        assert entity.installed_version == "7.16.1"

    def test_latest_version(self):
        coord = make_mock_coordinator()
        coord.data["routerboard"] = {
            "serial-number": "X",
            "current-firmware": "7.16.1",
            "upgrade-firmware": "7.16.2",
        }
        entity = _make_update_entity(
            cls=MikrotikRouterBoardFWUpdate,
            coordinator=coord,
            desc_overrides={**_RB_UPDATE_DESC},
        )
        assert entity.latest_version == "7.16.2"

    @pytest.mark.asyncio
    async def test_async_install_upgrades_and_reboots(self):
        coord = make_mock_coordinator()
        coord.data["routerboard"] = {
            "serial-number": "X",
            "current-firmware": "7.16.1",
            "upgrade-firmware": "7.16.2",
        }
        entity = _make_update_entity(
            cls=MikrotikRouterBoardFWUpdate,
            coordinator=coord,
            desc_overrides={**_RB_UPDATE_DESC},
        )
        await entity.async_install(version="7.16.2", backup=False)
        assert coord.execute.call_count == 2
        upgrade_call = coord.execute.call_args_list[0][0]
        assert upgrade_call[0] == "/system/routerboard"
        assert upgrade_call[1] == "upgrade"
        reboot_call = coord.execute.call_args_list[1][0]
        assert reboot_call[0] == "/system"
        assert reboot_call[1] == "reboot"
