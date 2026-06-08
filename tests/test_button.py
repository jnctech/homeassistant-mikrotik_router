"""Tests for Mikrotik Router button entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mikrotik_router.button import (
    MikrotikButton,
    MikrotikScriptButton,
)
from custom_components.mikrotik_router.exceptions import ApiEntryNotFound
from custom_components.mikrotik_router.button_types import (
    MikrotikButtonEntityDescription,
)

from .conftest import (
    make_mock_coordinator,
    make_mock_entity_description,
    patch_coordinator_entity_init,
)


def _make_button(cls=MikrotikButton, coordinator=None, desc_overrides=None, uid=None):
    coord = coordinator or make_mock_coordinator()
    desc = make_mock_entity_description(cls=MikrotikButtonEntityDescription, **(desc_overrides or {}))
    with patch_coordinator_entity_init():
        entity = cls(coord, desc, uid)
    entity.hass = MagicMock()
    entity.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw))
    return entity


# ---------------------------------------------------------------------------
# MikrotikButton
# ---------------------------------------------------------------------------


class TestMikrotikButton:
    @pytest.mark.asyncio
    async def test_async_press_is_noop(self):
        entity = _make_button()
        await entity.async_press()  # should not raise


# ---------------------------------------------------------------------------
# MikrotikScriptButton
# ---------------------------------------------------------------------------


class TestMikrotikScriptButton:
    @pytest.mark.asyncio
    async def test_async_press_calls_run_script(self):
        coord = make_mock_coordinator()
        coord.data["script"] = {"backup": {"name": "backup"}}
        entity = _make_button(
            cls=MikrotikScriptButton,
            coordinator=coord,
            desc_overrides={"data_path": "script", "data_reference": "name"},
            uid="backup",
        )
        await entity.async_press()
        coord.api.run_script.assert_called_once_with("backup")

    @pytest.mark.asyncio
    async def test_async_press_handles_api_entry_not_found(self):
        coord = make_mock_coordinator()
        coord.data["script"] = {"missing": {"name": "missing"}}
        coord.api.run_script.side_effect = ApiEntryNotFound("script not found")
        entity = _make_button(
            cls=MikrotikScriptButton,
            coordinator=coord,
            desc_overrides={"data_path": "script", "data_reference": "name"},
            uid="missing",
        )
        # Should log error, not raise
        await entity.async_press()

    @pytest.mark.asyncio
    async def test_async_press_refreshes_coordinator(self):
        coord = make_mock_coordinator()
        coord.data["script"] = {"backup": {"name": "backup"}}
        entity = _make_button(
            cls=MikrotikScriptButton,
            coordinator=coord,
            desc_overrides={"data_path": "script", "data_reference": "name"},
            uid="backup",
        )
        await entity.async_press()
        coord.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_press_refreshes_even_on_error(self):
        coord = make_mock_coordinator()
        coord.data["script"] = {"missing": {"name": "missing"}}
        coord.api.run_script.side_effect = ApiEntryNotFound("not found")
        entity = _make_button(
            cls=MikrotikScriptButton,
            coordinator=coord,
            desc_overrides={"data_path": "script", "data_reference": "name"},
            uid="missing",
        )
        await entity.async_press()
        coord.async_refresh.assert_awaited_once()
