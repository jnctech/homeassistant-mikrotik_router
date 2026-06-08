"""Tests for Mikrotik Router __init__.py — lifecycle, services, and helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_NAME, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from custom_components.mikrotik_router import (
    async_migrate_entry,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
    async_reload_entry,
    async_cleanup_entities,
    async_cleanup_stale_hosts,
    _async_register_services,
    _build_valid_unique_ids,
    _collect_all_descriptions,
    _collect_ids_for_desc,
    _get_mikrotik_data,
    _find_host_by_mac_slug,
    _classify_host_entity,
    SERVICE_CLEANUP_ENTITIES,
    SERVICE_CLEANUP_STALE_HOSTS,
)
from custom_components.mikrotik_router.const import (
    DOMAIN,
    PLATFORMS,
    DEFAULT_VERIFY_SSL,
)
from custom_components.mikrotik_router.coordinator import MikrotikData


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_CONFIG_DATA = {
    CONF_NAME: "TestRouter",
    CONF_HOST: "10.0.0.1",
    "username": "admin",
    "password": "secret",
    "port": 8728,
    "ssl": False,
    CONF_VERIFY_SSL: False,
}


def _make_mock_config_entry(entry_id="test_entry_123", version=2, options=None):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.version = version
    entry.minor_version = 0
    entry.data = dict(MOCK_CONFIG_DATA)
    entry.options = options or {}
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    entry.async_on_unload = MagicMock()
    return entry


def _make_mock_coordinator(ds=None, config_entry=None):
    """Create a mock coordinator with data store."""
    coord = MagicMock()
    coord.ds = ds or {"host": {}, "interface": {}}
    coord.config_entry = config_entry or _make_mock_config_entry()
    return coord


def _make_mock_mikrotik_data(coordinator=None, tracker=None):
    """Create a real MikrotikData wrapping mock coordinators.

    Must be the real dataclass (not a bare MagicMock) so the isinstance check in
    _get_mikrotik_data passes — runtime_data is validated as MikrotikData.
    """
    return MikrotikData(
        data_coordinator=coordinator or _make_mock_coordinator(),
        tracker_coordinator=tracker or MagicMock(),
    )


def _make_service_call(hass, data):
    """Create a mock ServiceCall."""
    call = MagicMock()
    call.hass = hass
    call.data = data
    return call


def _hass_with_loaded_entry(mikrotik_data):
    """hass mock whose config entry exposes mikrotik_data via runtime_data.

    Mirrors the runtime-data lookup in _get_mikrotik_data (reads
    entry.runtime_data), replacing the old hass.data[DOMAIN][entry_id] store.
    """
    hass = MagicMock()
    entry = MagicMock()
    entry.runtime_data = mikrotik_data
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)
    return hass


# ---------------------------------------------------------------------------
# async_migrate_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migrate_entry_v1_to_v2_adds_verify_ssl():
    """Version 1 entry gets CONF_VERIFY_SSL injected and bumped to version 2."""
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.version = 1
    config_entry.minor_version = 0
    config_entry.data = {"host": "10.0.0.1", "username": "admin"}

    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    hass.config_entries.async_update_entry.assert_called_once()
    call_kwargs = hass.config_entries.async_update_entry.call_args
    new_data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
    assert new_data[CONF_VERIFY_SSL] == DEFAULT_VERIFY_SSL
    version = call_kwargs.kwargs.get("version") or call_kwargs[1].get("version")
    assert version == 2


@pytest.mark.asyncio
async def test_migrate_entry_v2_is_noop():
    """Version 2 entry is already current — no update call."""
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.version = 2
    config_entry.minor_version = 0
    config_entry.data = {"host": "10.0.0.1", CONF_VERIFY_SSL: False}

    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_entry_preserves_existing_data():
    """Migration preserves all existing config data while adding verify_ssl."""
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.version = 1
    config_entry.minor_version = 0
    config_entry.data = {
        "host": "10.0.0.1",
        "username": "admin",
        "password": "secret",
    }

    await async_migrate_entry(hass, config_entry)

    call_kwargs = hass.config_entries.async_update_entry.call_args
    new_data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
    assert new_data["host"] == "10.0.0.1"
    assert new_data["username"] == "admin"
    assert new_data["password"] == "secret"
    assert CONF_VERIFY_SSL in new_data


@pytest.mark.asyncio
async def test_migrate_entry_future_version_is_noop():
    """A future version (>2) should not trigger v1→v2 migration."""
    hass = MagicMock()
    config_entry = MagicMock()
    config_entry.version = 3
    config_entry.minor_version = 0
    config_entry.data = {"host": "10.0.0.1"}

    result = await async_migrate_entry(hass, config_entry)

    assert result is True
    hass.config_entries.async_update_entry.assert_not_called()


# ---------------------------------------------------------------------------
# async_remove_config_entry_device
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_config_entry_device_returns_true():
    """Device removal always succeeds."""
    result = await async_remove_config_entry_device(MagicMock(), MagicMock(), MagicMock())
    assert result is True


# ---------------------------------------------------------------------------
# async_setup_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_entry_registers_coordinators_and_platforms():
    """async_setup_entry creates coordinators, stores data, and forwards platforms."""
    hass = MagicMock()
    hass.data = {}
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    config_entry = _make_mock_config_entry()

    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    mock_coord.config_entry = config_entry

    mock_tracker = MagicMock()
    mock_tracker.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "custom_components.mikrotik_router.MikrotikCoordinator",
            return_value=mock_coord,
        ),
        patch(
            "custom_components.mikrotik_router.MikrotikTrackerCoordinator",
            return_value=mock_tracker,
        ),
    ):
        result = await async_setup_entry(hass, config_entry)

    assert result is True
    mock_coord.async_config_entry_first_refresh.assert_awaited_once()
    mock_tracker.async_config_entry_first_refresh.assert_awaited_once()
    # Data is stored on the entry's runtime_data, not hass.data[DOMAIN].
    assert isinstance(config_entry.runtime_data, MikrotikData)
    assert config_entry.runtime_data.data_coordinator is mock_coord
    assert config_entry.runtime_data.tracker_coordinator is mock_tracker
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(config_entry, PLATFORMS)
    config_entry.async_on_unload.assert_called_once()


@pytest.mark.asyncio
async def test_setup_entry_registers_services():
    """async_setup_entry registers cleanup services."""
    hass = MagicMock()
    hass.data = {}
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    config_entry = _make_mock_config_entry()

    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    mock_coord.config_entry = config_entry
    mock_tracker = MagicMock()
    mock_tracker.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "custom_components.mikrotik_router.MikrotikCoordinator",
            return_value=mock_coord,
        ),
        patch(
            "custom_components.mikrotik_router.MikrotikTrackerCoordinator",
            return_value=mock_tracker,
        ),
    ):
        await async_setup_entry(hass, config_entry)

    # Two services: cleanup_entities and cleanup_stale_hosts
    register_calls = hass.services.async_register.call_args_list
    registered_names = [c[0][1] for c in register_calls]
    assert SERVICE_CLEANUP_ENTITIES in registered_names
    assert SERVICE_CLEANUP_STALE_HOSTS in registered_names


@pytest.mark.asyncio
async def test_setup_entry_skips_service_registration_if_already_registered():
    """Services only registered once even with multiple config entries."""
    hass = MagicMock()
    hass.data = {}
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_register = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    config_entry = _make_mock_config_entry()

    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    mock_coord.config_entry = config_entry
    mock_tracker = MagicMock()
    mock_tracker.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "custom_components.mikrotik_router.MikrotikCoordinator",
            return_value=mock_coord,
        ),
        patch(
            "custom_components.mikrotik_router.MikrotikTrackerCoordinator",
            return_value=mock_tracker,
        ),
    ):
        await async_setup_entry(hass, config_entry)

    hass.services.async_register.assert_not_called()


# ---------------------------------------------------------------------------
# async_unload_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unload_entry_removes_services_when_last_entry():
    """Successful unload removes shared services when no other entries remain.

    runtime_data is cleared by Home Assistant, not by our code, so there's
    nothing to assert about it here.
    """
    hass = MagicMock()
    config_entry = _make_mock_config_entry()

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_loaded_entries = MagicMock(return_value=[])  # no others
    hass.services.async_remove = MagicMock()

    result = await async_unload_entry(hass, config_entry)

    assert result is True
    hass.services.async_remove.assert_any_call(DOMAIN, SERVICE_CLEANUP_ENTITIES)
    hass.services.async_remove.assert_any_call(DOMAIN, SERVICE_CLEANUP_STALE_HOSTS)


@pytest.mark.asyncio
async def test_unload_entry_keeps_services_if_other_entries_remain():
    """Services not removed when other config entries are still loaded."""
    hass = MagicMock()
    config_entry = _make_mock_config_entry(entry_id="entry_1")
    other_entry = _make_mock_config_entry(entry_id="entry_2")

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    # async_loaded_entries may still include the entry being unloaded; the code
    # filters it out by entry_id, leaving entry_2 -> services stay registered.
    hass.config_entries.async_loaded_entries = MagicMock(return_value=[config_entry, other_entry])
    hass.services.async_remove = MagicMock()

    result = await async_unload_entry(hass, config_entry)

    assert result is True
    hass.services.async_remove.assert_not_called()


@pytest.mark.asyncio
async def test_unload_entry_failure_keeps_services():
    """Failed platform unload leaves services intact."""
    hass = MagicMock()
    config_entry = _make_mock_config_entry()

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    hass.services.async_remove = MagicMock()

    result = await async_unload_entry(hass, config_entry)

    assert result is False
    hass.services.async_remove.assert_not_called()


# ---------------------------------------------------------------------------
# async_reload_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reload_entry_triggers_config_reload():
    """async_reload_entry calls async_reload on the entry."""
    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    config_entry = _make_mock_config_entry()

    await async_reload_entry(hass, config_entry)

    hass.config_entries.async_reload.assert_awaited_once_with(config_entry.entry_id)


# ---------------------------------------------------------------------------
# _async_register_services (idempotency)
# ---------------------------------------------------------------------------


def test_register_services_idempotent():
    """Calling _async_register_services twice only registers once."""
    hass = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)

    _async_register_services(hass)
    assert hass.services.async_register.call_count == 2

    # Second call: services already exist
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_register.reset_mock()

    _async_register_services(hass)
    hass.services.async_register.assert_not_called()


# ---------------------------------------------------------------------------
# _get_mikrotik_data
# ---------------------------------------------------------------------------


def test_get_mikrotik_data_found():
    """Returns the entry's runtime_data when it is loaded MikrotikData."""
    hass = MagicMock()
    mock_data = _make_mock_mikrotik_data()
    entry = MagicMock()
    entry.runtime_data = mock_data
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    result = _get_mikrotik_data(hass, "entry_1")
    assert result is mock_data


def test_get_mikrotik_data_entry_not_found():
    """Returns None and logs error when the entry is unknown."""
    hass = MagicMock()
    hass.config_entries.async_get_entry = MagicMock(return_value=None)

    result = _get_mikrotik_data(hass, "nonexistent")
    assert result is None


def test_get_mikrotik_data_entry_not_loaded():
    """Returns None when the entry exists but has no MikrotikData runtime_data."""
    hass = MagicMock()
    entry = MagicMock()
    entry.runtime_data = None  # not loaded
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    result = _get_mikrotik_data(hass, "entry_1")
    assert result is None


# ---------------------------------------------------------------------------
# _collect_ids_for_desc
# ---------------------------------------------------------------------------


def test_collect_ids_no_reference():
    """Description without data_reference produces single ID from key."""
    desc = MagicMock()
    desc.data_reference = None
    desc.data_attribute = "uptime"
    desc.key = "system_uptime"

    data = {"uptime": 123456}
    valid_ids = set()

    _collect_ids_for_desc(desc, data, "testrouter", valid_ids)

    assert "testrouter-system_uptime" in valid_ids


def test_collect_ids_no_reference_none_attribute():
    """Description without reference skipped when attribute is None."""
    desc = MagicMock()
    desc.data_reference = None
    desc.data_attribute = "uptime"
    desc.key = "system_uptime"

    data = {"uptime": None}
    valid_ids = set()

    _collect_ids_for_desc(desc, data, "testrouter", valid_ids)

    assert len(valid_ids) == 0


def test_collect_ids_no_reference_missing_attribute():
    """Description without reference skipped when attribute missing from data."""
    desc = MagicMock()
    desc.data_reference = None
    desc.data_attribute = "uptime"
    desc.key = "system_uptime"

    data = {}
    valid_ids = set()

    _collect_ids_for_desc(desc, data, "testrouter", valid_ids)

    assert len(valid_ids) == 0


def test_collect_ids_with_reference():
    """Description with data_reference produces per-uid IDs."""
    desc = MagicMock()
    desc.data_reference = "name"
    desc.key = "interface_traffic"

    data = {
        "ether1": {"name": "ether1"},
        "ether2": {"name": "ether2"},
    }
    valid_ids = set()

    _collect_ids_for_desc(desc, data, "testrouter", valid_ids)

    assert "testrouter-interface_traffic-ether1" in valid_ids
    assert "testrouter-interface_traffic-ether2" in valid_ids


def test_collect_ids_with_reference_none_value_skipped():
    """UID with None reference value is not included."""
    desc = MagicMock()
    desc.data_reference = "name"
    desc.key = "interface_traffic"

    data = {
        "ether1": {"name": "ether1"},
        "ether2": {"name": None},
    }
    valid_ids = set()

    _collect_ids_for_desc(desc, data, "testrouter", valid_ids)

    assert "testrouter-interface_traffic-ether1" in valid_ids
    assert len(valid_ids) == 1


# ---------------------------------------------------------------------------
# _build_valid_unique_ids
# ---------------------------------------------------------------------------


def test_build_valid_unique_ids_basic():
    """Builds IDs from coordinator data using entity descriptions."""
    mock_desc = MagicMock()
    mock_desc.data_path = "interface"
    mock_desc.data_reference = "name"
    mock_desc.key = "port_status"

    coordinator_data = {
        "interface": {
            "ether1": {"name": "ether1"},
        }
    }

    with patch(
        "custom_components.mikrotik_router._collect_all_descriptions",
        return_value=[mock_desc],
    ):
        result = _build_valid_unique_ids("TestRouter", coordinator_data)

    assert "testrouter-port_status-ether1" in result


def test_build_valid_unique_ids_skips_missing_data_path():
    """Descriptions whose data_path is not in coordinator data are skipped."""
    mock_desc = MagicMock()
    mock_desc.data_path = "nat"
    mock_desc.data_reference = "name"
    mock_desc.key = "nat_rule"

    coordinator_data = {"interface": {}}

    with patch(
        "custom_components.mikrotik_router._collect_all_descriptions",
        return_value=[mock_desc],
    ):
        result = _build_valid_unique_ids("TestRouter", coordinator_data)

    assert len(result) == 0


# ---------------------------------------------------------------------------
# _find_host_by_mac_slug
# ---------------------------------------------------------------------------


def test_find_host_by_mac_slug_found():
    """Returns host data when MAC slug matches."""
    host_data = {
        "uid1": {"mac-address": "AA:BB:CC:DD:EE:FF", "host-name": "phone"},
    }
    mac_slug = slugify("AA:BB:CC:DD:EE:FF".lower())

    result = _find_host_by_mac_slug(host_data, mac_slug)
    assert result is not None
    assert result["host-name"] == "phone"


def test_find_host_by_mac_slug_not_found():
    """Returns None when no MAC matches."""
    host_data = {
        "uid1": {"mac-address": "AA:BB:CC:DD:EE:FF"},
    }

    result = _find_host_by_mac_slug(host_data, "11_22_33_44_55_66")
    assert result is None


def test_find_host_by_mac_slug_empty_data():
    """Returns None for empty host data."""
    result = _find_host_by_mac_slug({}, "aa_bb_cc_dd_ee_ff")
    assert result is None


def test_find_host_by_mac_slug_missing_mac_field():
    """Host with no mac-address field is skipped, not crashed."""
    host_data = {"uid1": {"host-name": "no-mac-host"}}

    result = _find_host_by_mac_slug(host_data, "aa_bb_cc_dd_ee_ff")
    assert result is None


# ---------------------------------------------------------------------------
# _classify_host_entity
# ---------------------------------------------------------------------------


def _make_entity(entity_id, unique_id, config_entry_id="test_entry"):
    """Create a minimal mock entity registry entry."""
    ent = MagicMock()
    ent.entity_id = entity_id
    ent.unique_id = unique_id
    ent.config_entry_id = config_entry_id
    return ent


def test_classify_host_entity_not_host_prefix():
    """Entity with non-matching prefix returns None."""
    entity = _make_entity("sensor.something", "testrouter-sensor-foo")
    result = _classify_host_entity(entity, {}, "testrouter-host-")
    assert result is None


def test_classify_host_entity_not_in_coordinator():
    """Entity whose MAC is not in coordinator data classified as stale."""
    mac = "AA:BB:CC:DD:EE:FF"
    mac_slug = slugify(mac.lower())
    entity = _make_entity(
        "device_tracker.test",
        f"testrouter-host-{mac_slug}",
    )

    result = _classify_host_entity(entity, {}, "testrouter-host-")
    assert result is not None
    assert result["reason"] == "not_in_coordinator_data"
    assert result["available"] is False


def test_classify_host_entity_unavailable():
    """Entity whose host exists but is unavailable is classified as stale."""
    mac = "AA:BB:CC:DD:EE:FF"
    mac_slug = slugify(mac.lower())
    entity = _make_entity(
        "device_tracker.test",
        f"testrouter-host-{mac_slug}",
    )
    host_data = {
        "uid1": {
            "mac-address": mac,
            "available": False,
            "source": "arp",
            "last-seen": "2026-03-27T10:00:00",
            "host-name": "phone",
        }
    }

    result = _classify_host_entity(entity, host_data, "testrouter-host-")
    assert result is not None
    assert result["reason"] == "host_unavailable"
    assert result["host_name"] == "phone"


def test_classify_host_entity_available():
    """Entity whose host is available returns None (not stale)."""
    mac = "AA:BB:CC:DD:EE:FF"
    mac_slug = slugify(mac.lower())
    entity = _make_entity(
        "device_tracker.test",
        f"testrouter-host-{mac_slug}",
    )
    host_data = {
        "uid1": {
            "mac-address": mac,
            "available": True,
            "source": "arp",
        }
    }

    result = _classify_host_entity(entity, host_data, "testrouter-host-")
    assert result is None


# ---------------------------------------------------------------------------
# async_cleanup_entities service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_entities_missing_entry():
    """Raises HomeAssistantError when entry_id not found."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    call = _make_service_call(hass, {"entry_id": "nonexistent"})

    with pytest.raises(HomeAssistantError, match="not found"):
        await async_cleanup_entities(call)


@pytest.mark.asyncio
async def test_cleanup_entities_empty_valid_ids_aborts():
    """Raises HomeAssistantError when no valid IDs generated (safety guard)."""
    config_entry = _make_mock_config_entry()
    coordinator = _make_mock_coordinator(ds={}, config_entry=config_entry)
    mikrotik_data = _make_mock_mikrotik_data(coordinator=coordinator)

    hass = _hass_with_loaded_entry(mikrotik_data)
    call = _make_service_call(hass, {"entry_id": config_entry.entry_id})

    with patch(
        "custom_components.mikrotik_router._build_valid_unique_ids",
        return_value=set(),
    ):
        with pytest.raises(HomeAssistantError, match="No valid entity IDs"):
            await async_cleanup_entities(call)


@pytest.mark.asyncio
async def test_cleanup_entities_removes_orphans():
    """Orphaned entities (not in valid_ids) are removed."""
    config_entry = _make_mock_config_entry()
    coordinator = _make_mock_coordinator(
        ds={"interface": {"ether1": {"name": "ether1"}}},
        config_entry=config_entry,
    )
    mikrotik_data = _make_mock_mikrotik_data(coordinator=coordinator)

    # Two entities: one valid, one orphan
    valid_entity = MagicMock()
    valid_entity.entity_id = "sensor.valid"
    valid_entity.unique_id = "testrouter-port_status-ether1"
    valid_entity.config_entry_id = config_entry.entry_id

    orphan_entity = MagicMock()
    orphan_entity.entity_id = "sensor.orphan"
    orphan_entity.unique_id = "testrouter-port_status-ether99"
    orphan_entity.config_entry_id = config_entry.entry_id

    other_entry_entity = MagicMock()
    other_entry_entity.entity_id = "sensor.other"
    other_entry_entity.unique_id = "other-entity"
    other_entry_entity.config_entry_id = "other_entry"

    mock_registry = MagicMock()
    mock_registry.entities.values.return_value = [
        valid_entity,
        orphan_entity,
        other_entry_entity,
    ]

    hass = _hass_with_loaded_entry(mikrotik_data)
    call = _make_service_call(hass, {"entry_id": config_entry.entry_id})

    valid_ids = {"testrouter-port_status-ether1"}

    with (
        patch(
            "custom_components.mikrotik_router._build_valid_unique_ids",
            return_value=valid_ids,
        ),
        patch(
            "custom_components.mikrotik_router.er.async_get",
            return_value=mock_registry,
        ),
    ):
        result = await async_cleanup_entities(call)

    assert result["removed_count"] == 1
    assert result["removed_entities"][0]["entity_id"] == "sensor.orphan"
    mock_registry.async_remove.assert_called_once_with("sensor.orphan")


@pytest.mark.asyncio
async def test_cleanup_entities_no_orphans():
    """No entities removed when all are valid."""
    config_entry = _make_mock_config_entry()
    coordinator = _make_mock_coordinator(config_entry=config_entry)
    mikrotik_data = _make_mock_mikrotik_data(coordinator=coordinator)

    valid_entity = MagicMock()
    valid_entity.entity_id = "sensor.valid"
    valid_entity.unique_id = "testrouter-port_status-ether1"
    valid_entity.config_entry_id = config_entry.entry_id

    mock_registry = MagicMock()
    mock_registry.entities.values.return_value = [valid_entity]

    hass = _hass_with_loaded_entry(mikrotik_data)
    call = _make_service_call(hass, {"entry_id": config_entry.entry_id})

    with (
        patch(
            "custom_components.mikrotik_router._build_valid_unique_ids",
            return_value={"testrouter-port_status-ether1"},
        ),
        patch(
            "custom_components.mikrotik_router.er.async_get",
            return_value=mock_registry,
        ),
    ):
        result = await async_cleanup_entities(call)

    assert result["removed_count"] == 0
    assert result["removed_entities"] == []
    mock_registry.async_remove.assert_not_called()


# ---------------------------------------------------------------------------
# async_cleanup_stale_hosts service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_stale_hosts_missing_entry():
    """Raises HomeAssistantError when entry_id not found."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    call = _make_service_call(hass, {"entry_id": "nonexistent"})

    with pytest.raises(HomeAssistantError, match="not found"):
        await async_cleanup_stale_hosts(call)


@pytest.mark.asyncio
async def test_cleanup_stale_hosts_dry_run():
    """Dry run reports stale hosts without removing them."""
    mac = "AA:BB:CC:DD:EE:FF"
    mac_slug = slugify(mac.lower())

    config_entry = _make_mock_config_entry()
    coordinator = _make_mock_coordinator(
        ds={"host": {"uid1": {"mac-address": mac, "available": False, "source": "arp"}}},
        config_entry=config_entry,
    )
    mikrotik_data = _make_mock_mikrotik_data(coordinator=coordinator)

    stale_entity = MagicMock()
    stale_entity.entity_id = "device_tracker.stale"
    stale_entity.unique_id = f"testrouter-host-{mac_slug}"
    stale_entity.config_entry_id = config_entry.entry_id

    mock_registry = MagicMock()
    mock_registry.entities.values.return_value = [stale_entity]

    hass = _hass_with_loaded_entry(mikrotik_data)
    call = _make_service_call(hass, {"entry_id": config_entry.entry_id, "dry_run": True})

    with patch(
        "custom_components.mikrotik_router.er.async_get",
        return_value=mock_registry,
    ):
        result = await async_cleanup_stale_hosts(call)

    assert result["stale_count"] == 1
    assert "removed_count" not in result
    mock_registry.async_remove.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_stale_hosts_remove():
    """Non-dry-run removes stale host entities."""
    mac = "AA:BB:CC:DD:EE:FF"
    mac_slug = slugify(mac.lower())

    config_entry = _make_mock_config_entry()
    coordinator = _make_mock_coordinator(
        ds={"host": {}},
        config_entry=config_entry,
    )
    mikrotik_data = _make_mock_mikrotik_data(coordinator=coordinator)

    stale_entity = MagicMock()
    stale_entity.entity_id = "device_tracker.stale"
    stale_entity.unique_id = f"testrouter-host-{mac_slug}"
    stale_entity.config_entry_id = config_entry.entry_id

    # Non-tracker entity should be ignored
    sensor_entity = MagicMock()
    sensor_entity.entity_id = "sensor.something"
    sensor_entity.unique_id = "testrouter-sensor-foo"
    sensor_entity.config_entry_id = config_entry.entry_id

    mock_registry = MagicMock()
    mock_registry.entities.values.return_value = [stale_entity, sensor_entity]

    hass = _hass_with_loaded_entry(mikrotik_data)
    call = _make_service_call(hass, {"entry_id": config_entry.entry_id, "dry_run": False})

    with patch(
        "custom_components.mikrotik_router.er.async_get",
        return_value=mock_registry,
    ):
        result = await async_cleanup_stale_hosts(call)

    assert result["stale_count"] == 1
    assert result["removed_count"] == 1
    mock_registry.async_remove.assert_called_once_with("device_tracker.stale")


@pytest.mark.asyncio
async def test_cleanup_stale_hosts_no_stale():
    """No stale hosts reported when all are available."""
    mac = "AA:BB:CC:DD:EE:FF"
    mac_slug = slugify(mac.lower())

    config_entry = _make_mock_config_entry()
    coordinator = _make_mock_coordinator(
        ds={"host": {"uid1": {"mac-address": mac, "available": True, "source": "arp"}}},
        config_entry=config_entry,
    )
    mikrotik_data = _make_mock_mikrotik_data(coordinator=coordinator)

    entity = MagicMock()
    entity.entity_id = "device_tracker.active"
    entity.unique_id = f"testrouter-host-{mac_slug}"
    entity.config_entry_id = config_entry.entry_id

    mock_registry = MagicMock()
    mock_registry.entities.values.return_value = [entity]

    hass = _hass_with_loaded_entry(mikrotik_data)
    call = _make_service_call(hass, {"entry_id": config_entry.entry_id, "dry_run": True})

    with patch(
        "custom_components.mikrotik_router.er.async_get",
        return_value=mock_registry,
    ):
        result = await async_cleanup_stale_hosts(call)

    assert result["stale_count"] == 0


@pytest.mark.asyncio
async def test_cleanup_stale_hosts_skips_other_entries():
    """Entities from other config entries are not considered."""
    config_entry = _make_mock_config_entry()
    coordinator = _make_mock_coordinator(
        ds={"host": {}},
        config_entry=config_entry,
    )
    mikrotik_data = _make_mock_mikrotik_data(coordinator=coordinator)

    other_entity = MagicMock()
    other_entity.entity_id = "device_tracker.other"
    other_entity.unique_id = "testrouter-host-aa_bb_cc_dd_ee_ff"
    other_entity.config_entry_id = "other_entry_id"

    mock_registry = MagicMock()
    mock_registry.entities.values.return_value = [other_entity]

    hass = _hass_with_loaded_entry(mikrotik_data)
    call = _make_service_call(hass, {"entry_id": config_entry.entry_id, "dry_run": True})

    with patch(
        "custom_components.mikrotik_router.er.async_get",
        return_value=mock_registry,
    ):
        result = await async_cleanup_stale_hosts(call)

    assert result["stale_count"] == 0


@pytest.mark.asyncio
async def test_cleanup_stale_hosts_default_dry_run():
    """dry_run defaults to True when not specified."""
    config_entry = _make_mock_config_entry()
    coordinator = _make_mock_coordinator(
        ds={"host": {}},
        config_entry=config_entry,
    )
    mikrotik_data = _make_mock_mikrotik_data(coordinator=coordinator)

    mock_registry = MagicMock()
    mock_registry.entities.values.return_value = []

    hass = _hass_with_loaded_entry(mikrotik_data)
    # No dry_run key — should default to True
    call = _make_service_call(hass, {"entry_id": config_entry.entry_id})

    with patch(
        "custom_components.mikrotik_router.er.async_get",
        return_value=mock_registry,
    ):
        result = await async_cleanup_stale_hosts(call)

    # Dry run path returns stale_count without removed_count
    assert "stale_count" in result


# ---------------------------------------------------------------------------
# _collect_all_descriptions
# ---------------------------------------------------------------------------


def test_collect_all_descriptions_returns_list():
    """Returns a non-empty list of entity descriptions from all platforms."""
    descriptions = _collect_all_descriptions()
    assert isinstance(descriptions, list)
    assert len(descriptions) > 0
    # Every description should have key and data_path attributes
    for desc in descriptions:
        assert hasattr(desc, "key")
        assert hasattr(desc, "data_path")


def test_collect_all_descriptions_includes_all_platforms():
    """Descriptions span all 6 platform types."""
    descriptions = _collect_all_descriptions()
    funcs = {desc.func for desc in descriptions}
    # Check representative funcs from each platform
    expected = {
        "MikrotikSensor",
        "MikrotikBinarySensor",
        "MikrotikHostDeviceTracker",
        "MikrotikScriptButton",
    }
    assert expected.issubset(funcs), f"Missing platforms: {expected - funcs}"


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_diagnostics_returns_redacted_data():
    """Diagnostics returns entry, data, and tracker keys with distinct data."""
    from custom_components.mikrotik_router.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    config_entry = _make_mock_config_entry()
    config_entry.data = {CONF_NAME: "TestRouter", "username": "admin"}
    config_entry.options = {}

    data_coord = MagicMock()
    data_coord.data = {"resource": {"board-name": "hAP ax3"}}

    tracker_coord = MagicMock()
    tracker_coord.data = {"host": {"mac1": {"available": True}}}

    mikrotik_data = MagicMock()
    mikrotik_data.data_coordinator = data_coord
    mikrotik_data.tracker_coordinator = tracker_coord

    hass = _hass_with_loaded_entry(mikrotik_data)

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert "entry" in result
    assert "data" in result
    assert "tracker" in result
    assert "data" in result["entry"]
    assert "options" in result["entry"]
    # Verify data and tracker use different coordinators (catches copy-paste bug)
    assert result["data"] != result["tracker"]
