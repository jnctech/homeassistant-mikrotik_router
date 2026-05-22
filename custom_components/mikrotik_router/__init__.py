"""Mikrotik Router integration."""

from __future__ import annotations

import voluptuous as vol
import logging

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify

from homeassistant.const import CONF_NAME, CONF_VERIFY_SSL
from homeassistant.exceptions import HomeAssistantError

from .const import PLATFORMS, DOMAIN, DEFAULT_VERIFY_SSL
from .coordinator import MikrotikData, MikrotikCoordinator, MikrotikTrackerCoordinator

SCRIPT_SCHEMA = vol.Schema({vol.Required("router"): cv.string, vol.Required("script"): cv.string})

_LOGGER = logging.getLogger(__name__)

SERVICE_CLEANUP_ENTITIES = "cleanup_entities"
CLEANUP_SCHEMA = vol.Schema({vol.Required("entry_id"): cv.string})


def _collect_all_descriptions() -> list:
    """Import and collect all entity descriptions from all platforms."""
    from .sensor_types import SENSOR_TYPES
    from .binary_sensor_types import SENSOR_TYPES as BINARY_SENSOR_TYPES
    from .device_tracker_types import SENSOR_TYPES as DEVICE_TRACKER_TYPES
    from .switch_types import SENSOR_TYPES as SWITCH_TYPES
    from .button_types import SENSOR_TYPES as BUTTON_TYPES
    from .update_types import SENSOR_TYPES as UPDATE_TYPES

    return [
        *SENSOR_TYPES,
        *BINARY_SENSOR_TYPES,
        *DEVICE_TRACKER_TYPES,
        *SWITCH_TYPES,
        *BUTTON_TYPES,
        *UPDATE_TYPES,
    ]


def _build_valid_unique_ids(inst: str, coordinator_data: dict) -> set[str]:
    """Build the set of unique_ids that should currently exist."""
    descriptions = _collect_all_descriptions()
    valid_ids: set[str] = set()
    inst_lower = inst.lower()

    for desc in descriptions:
        if desc.data_path not in coordinator_data:
            continue
        _collect_ids_for_desc(desc, coordinator_data[desc.data_path], inst_lower, valid_ids)

    return valid_ids


def _collect_ids_for_desc(desc, data: dict, inst_lower: str, valid_ids: set) -> None:
    """Add unique IDs for a single entity description."""
    if not desc.data_reference:
        if data.get(desc.data_attribute) is not None:
            valid_ids.add(f"{inst_lower}-{desc.key}")
        return

    for uid in data:
        ref_value = data[uid].get(desc.data_reference)
        if ref_value is not None:
            valid_ids.add(f"{inst_lower}-{desc.key}-{slugify(str(ref_value).lower())}")


def _get_mikrotik_data(hass: HomeAssistant, entry_id: str) -> MikrotikData | None:
    """Look up MikrotikData for a config entry, logging an error if missing."""
    domain_data = hass.data.get(DOMAIN, {})
    if entry_id in domain_data:
        return domain_data[entry_id]

    _LOGGER.error(
        "Config entry '%s' not found. Available: %s",
        entry_id,
        list(domain_data.keys()),
    )
    return None


async def async_cleanup_entities(call: ServiceCall) -> ServiceResponse:
    """Remove orphaned entities that no longer have backing data."""
    hass = call.hass
    entry_id = call.data["entry_id"]

    mikrotik_data = _get_mikrotik_data(hass, entry_id)
    if mikrotik_data is None:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found")

    coordinator = mikrotik_data.data_coordinator
    config_entry = coordinator.config_entry
    inst = config_entry.data[CONF_NAME]

    valid_ids = _build_valid_unique_ids(inst, coordinator.ds)
    if not valid_ids:
        raise HomeAssistantError("No valid entity IDs generated — aborting to prevent removing all entities. This may indicate empty coordinator data or a bug.")
    _LOGGER.debug("Built %d valid unique IDs for %s", len(valid_ids), inst)

    entity_registry = er.async_get(hass)
    removed: list[dict[str, str]] = []

    for entity in list(entity_registry.entities.values()):  # NOSONAR S7504 - list() needed: registry mutated in loop
        if entity.config_entry_id != entry_id:
            continue
        if entity.unique_id in valid_ids:
            continue

        _LOGGER.info(
            "Removing orphaned entity %s (unique_id=%s)",
            entity.entity_id,
            entity.unique_id,
        )
        removed.append({"entity_id": entity.entity_id, "unique_id": entity.unique_id})
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


def _find_host_by_mac_slug(host_data: dict, mac_slug: str) -> dict | None:
    """Find a host entry by slugified MAC address."""
    for uid, hdata in host_data.items():
        mac = hdata.get("mac-address", "")
        if slugify(str(mac).lower()) == mac_slug:
            return hdata
    return None


def _classify_host_entity(entity, host_data: dict, prefix: str) -> dict | None:
    """Return a stale-host info dict if the entity is stale, else None."""
    unique_id = entity.unique_id
    if not unique_id.startswith(prefix):
        return None

    mac_slug = unique_id[len(prefix) :]
    host_entry = _find_host_by_mac_slug(host_data, mac_slug)

    if host_entry is None:
        return {
            "entity_id": entity.entity_id,
            "unique_id": unique_id,
            "source": "unknown",
            "available": False,
            "last_seen": "never",
            "reason": "not_in_coordinator_data",
        }

    if not host_entry.get("available", False):
        return {
            "entity_id": entity.entity_id,
            "unique_id": unique_id,
            "source": host_entry.get("source", "unknown"),
            "available": False,
            "last_seen": str(host_entry.get("last-seen", "unknown")),
            "host_name": host_entry.get("host-name", "unknown"),
            "mac_address": host_entry.get("mac-address", "unknown"),
            "reason": "host_unavailable",
        }

    return None


async def async_cleanup_stale_hosts(call: ServiceCall) -> ServiceResponse:
    """Report or remove device tracker entities for away/stale hosts."""
    hass = call.hass
    entry_id = call.data["entry_id"]
    dry_run = call.data.get("dry_run", True)

    mikrotik_data = _get_mikrotik_data(hass, entry_id)
    if mikrotik_data is None:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found")

    coordinator = mikrotik_data.data_coordinator
    inst = coordinator.config_entry.data[CONF_NAME].lower()
    host_data = coordinator.ds.get("host", {})
    entity_registry = er.async_get(hass)
    prefix = f"{inst}-host-"

    stale: list[dict[str, str]] = []
    removed: list[dict[str, str]] = []

    for entity in list(entity_registry.entities.values()):  # NOSONAR S7504 - list() needed: registry mutated in loop
        if entity.config_entry_id != entry_id:
            continue
        if not entity.entity_id.startswith("device_tracker."):
            continue

        entry_info = _classify_host_entity(entity, host_data, prefix)
        if entry_info is None:
            continue

        stale.append(entry_info)
        if not dry_run:
            entity_registry.async_remove(entity.entity_id)
            removed.append(entry_info)

    if dry_run:
        _LOGGER.info("Stale hosts dry run: found %d stale host entities", len(stale))
        return {"stale_count": len(stale), "stale_hosts": stale}

    _LOGGER.info("Stale hosts cleanup: removed %d host entities", len(removed))
    return {
        "stale_count": len(stale),
        "removed_count": len(removed),
        "removed_hosts": removed,
    }


# ---------------------------
#   _async_register_services
# ---------------------------
def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent — safe to call per entry)."""
    if hass.services.has_service(DOMAIN, SERVICE_CLEANUP_ENTITIES):
        return

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


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    _async_register_services(hass)
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

    if unload_ok := await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        hass.data[DOMAIN].pop(config_entry.entry_id)

        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_CLEANUP_ENTITIES)
            hass.services.async_remove(DOMAIN, SERVICE_CLEANUP_STALE_HOSTS)

    return unload_ok


# ---------------------------
#   async_remove_config_entry_device
# ---------------------------
async def async_remove_config_entry_device(
    _hass: HomeAssistant,
    _config_entry: ConfigEntry,
    _device_entry: device_registry.DeviceEntry,
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
