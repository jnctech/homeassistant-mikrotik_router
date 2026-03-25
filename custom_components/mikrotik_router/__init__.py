"""Mikrotik Router integration."""

from __future__ import annotations

import voluptuous as vol
import logging

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify

from homeassistant.const import CONF_NAME, CONF_VERIFY_SSL

from .const import PLATFORMS, DOMAIN, DEFAULT_VERIFY_SSL
from .coordinator import MikrotikData, MikrotikCoordinator, MikrotikTrackerCoordinator

SCRIPT_SCHEMA = vol.Schema(
    {vol.Required("router"): cv.string, vol.Required("script"): cv.string}
)

_LOGGER = logging.getLogger(__name__)

SERVICE_CLEANUP_ENTITIES = "cleanup_entities"
CLEANUP_SCHEMA = vol.Schema(
    {vol.Required("entry_id"): cv.string}
)


def _collect_all_descriptions() -> list:
    """Import and collect all entity descriptions from all platforms."""
    from .sensor_types import SENSOR_TYPES
    from .binary_sensor_types import SENSOR_TYPES as BINARY_SENSOR_TYPES
    from .device_tracker_types import SENSOR_TYPES as DEVICE_TRACKER_TYPES
    from .switch_types import SENSOR_TYPES as SWITCH_TYPES
    from .button_types import SENSOR_TYPES as BUTTON_TYPES
    from .update_types import SENSOR_TYPES as UPDATE_TYPES

    descriptions = []
    descriptions.extend(SENSOR_TYPES)
    descriptions.extend(BINARY_SENSOR_TYPES)
    descriptions.extend(DEVICE_TRACKER_TYPES)
    descriptions.extend(SWITCH_TYPES)
    descriptions.extend(BUTTON_TYPES)
    descriptions.extend(UPDATE_TYPES)
    return descriptions


def _build_valid_unique_ids(inst: str, coordinator_data: dict) -> set[str]:
    """Build the set of unique_ids that should currently exist."""
    descriptions = _collect_all_descriptions()
    valid_ids: set[str] = set()
    inst_lower = inst.lower()

    for desc in descriptions:
        data_path = desc.data_path
        if data_path not in coordinator_data:
            continue

        data = coordinator_data[data_path]

        if not desc.data_reference:
            # System-level entity (no per-device reference)
            if data.get(desc.data_attribute) is not None:
                valid_ids.add(f"{inst_lower}-{desc.key}")
        else:
            # Per-device/per-item entity
            for uid in data:
                ref_value = data[uid].get(desc.data_reference)
                if ref_value is not None:
                    valid_ids.add(
                        f"{inst_lower}-{desc.key}-"
                        f"{slugify(str(ref_value).lower())}"
                    )

    return valid_ids


async def async_cleanup_entities(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Remove orphaned entities that no longer have backing data."""
    entry_id = call.data["entry_id"]

    if entry_id not in hass.data.get(DOMAIN, {}):
        raise vol.Invalid(f"Config entry '{entry_id}' not found for {DOMAIN}")

    mikrotik_data: MikrotikData = hass.data[DOMAIN][entry_id]
    coordinator = mikrotik_data.data_coordinator
    config_entry = coordinator.config_entry
    inst = config_entry.data[CONF_NAME]

    valid_ids = _build_valid_unique_ids(inst, coordinator.ds)

    entity_registry = er.async_get(hass)
    removed: list[dict[str, str]] = []

    for entity in list(entity_registry.entities.values()):
        if entity.config_entry_id != entry_id:
            continue
        if entity.unique_id in valid_ids:
            continue

        _LOGGER.info(
            "Removing orphaned entity %s (unique_id=%s)",
            entity.entity_id,
            entity.unique_id,
        )
        removed.append(
            {"entity_id": entity.entity_id, "unique_id": entity.unique_id}
        )
        entity_registry.async_remove(entity.entity_id)

    _LOGGER.info("Cleanup complete: removed %d orphaned entities", len(removed))
    return {"removed_count": len(removed), "removed_entities": removed}


SERVICE_CLEANUP_STALE_HOSTS = "cleanup_stale_hosts"
CLEANUP_STALE_HOSTS_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Optional("dry_run", default=True): cv.boolean,
    }
)


async def async_cleanup_stale_hosts(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Report or remove device tracker entities for away/stale hosts."""
    entry_id = call.data["entry_id"]
    dry_run = call.data.get("dry_run", True)

    if entry_id not in hass.data.get(DOMAIN, {}):
        raise vol.Invalid(f"Config entry '{entry_id}' not found for {DOMAIN}")

    mikrotik_data: MikrotikData = hass.data[DOMAIN][entry_id]
    coordinator = mikrotik_data.data_coordinator
    config_entry = coordinator.config_entry
    inst = config_entry.data[CONF_NAME].lower()

    host_data = coordinator.ds.get("host", {})
    entity_registry = er.async_get(hass)

    stale: list[dict[str, str]] = []
    removed: list[dict[str, str]] = []

    for entity in list(entity_registry.entities.values()):
        if entity.config_entry_id != entry_id:
            continue
        if not entity.entity_id.startswith("device_tracker."):
            continue

        # Parse unique_id: {inst}-host-{mac_slug}
        unique_id = entity.unique_id
        prefix = f"{inst}-host-"
        if not unique_id.startswith(prefix):
            continue

        mac_slug = unique_id[len(prefix):]
        # Find matching host by slugified mac-address
        host_entry = None
        for uid, hdata in host_data.items():
            mac = hdata.get("mac-address", "")
            if slugify(str(mac).lower()) == mac_slug:
                host_entry = hdata
                break

        if host_entry is None:
            # Host no longer in coordinator data at all
            entry_info = {
                "entity_id": entity.entity_id,
                "unique_id": unique_id,
                "source": "unknown",
                "available": False,
                "last_seen": "never",
                "reason": "not_in_coordinator_data",
            }
            stale.append(entry_info)
            if not dry_run:
                entity_registry.async_remove(entity.entity_id)
                removed.append(entry_info)
            continue

        is_available = host_entry.get("available", False)
        source = host_entry.get("source", "unknown")
        last_seen = host_entry.get("last-seen", "unknown")

        if not is_available:
            entry_info = {
                "entity_id": entity.entity_id,
                "unique_id": unique_id,
                "source": source,
                "available": False,
                "last_seen": str(last_seen),
                "host_name": host_entry.get("host-name", "unknown"),
                "mac_address": host_entry.get("mac-address", "unknown"),
                "reason": "host_unavailable",
            }
            stale.append(entry_info)
            if not dry_run:
                entity_registry.async_remove(entity.entity_id)
                removed.append(entry_info)

    if dry_run:
        _LOGGER.info(
            "Stale hosts dry run: found %d stale host entities", len(stale)
        )
        return {"stale_count": len(stale), "stale_hosts": stale}

    _LOGGER.info(
        "Stale hosts cleanup: removed %d host entities", len(removed)
    )
    return {
        "stale_count": len(stale),
        "removed_count": len(removed),
        "removed_hosts": removed,
    }


# ---------------------------
#   async_setup
# ---------------------------
async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Mikrotik Router integration (register services)."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEANUP_ENTITIES,
        async_cleanup_entities,
        schema=CLEANUP_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEANUP_STALE_HOSTS,
        async_cleanup_stale_hosts,
        schema=CLEANUP_STALE_HOSTS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    coordinator = MikrotikCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    coordinator_tracker = MikrotikTrackerCoordinator(hass, config_entry, coordinator)
    await coordinator_tracker.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = MikrotikData(
        data_coordinator=coordinator,
        tracker_coordinator=coordinator_tracker,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    return True


# ---------------------------
#   async_reload_entry
# ---------------------------
async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)


# ---------------------------
#   async_unload_entry
# ---------------------------
async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


# ---------------------------
#   async_remove_config_entry_device
# ---------------------------
async def async_remove_config_entry_device(
    hass, config_entry: ConfigEntry, device_entry: device_registry.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


# ---------------------------
#   async_migrate_entry
# ---------------------------
async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version < 2:
        new_data = {**config_entry.data}
        new_data[CONF_VERIFY_SSL] = DEFAULT_VERIFY_SSL
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
