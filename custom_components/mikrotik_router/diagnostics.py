"""Diagnostics support for Mikrotik Router."""

from __future__ import annotations
from typing import Any
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from .const import TO_REDACT
from .coordinator import MikrotikConfigEntry


def _redact_wireguard_peer_keys(data: dict) -> dict:
    """Redact the public keys used as the wireguard_peers map keys.

    async_redact_data redacts dict *values* whose name is in TO_REDACT, but not
    the dict *keys*. The peer map is keyed by the full public key (a sensitive
    cryptographic identity), so the key itself would otherwise appear verbatim in
    a diagnostics dump even though "public-key" is in TO_REDACT. Re-key the map to
    an anonymous index; every identifying field in the value is already redacted,
    so no correlation is lost. See ADR-021.
    """
    peers = data.get("wireguard_peers")
    if isinstance(peers, dict) and peers:
        data["wireguard_peers"] = {f"peer_{index}": value for index, value in enumerate(peers.values())}
    return data


async def async_get_config_entry_diagnostics(hass: HomeAssistant, config_entry: MikrotikConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data_coordinator = config_entry.runtime_data.data_coordinator
    tracker_coordinator = config_entry.runtime_data.tracker_coordinator

    return {
        "entry": {
            "data": async_redact_data(config_entry.data, TO_REDACT),
            "options": async_redact_data(config_entry.options, TO_REDACT),
        },
        "data": _redact_wireguard_peer_keys(async_redact_data(data_coordinator.data, TO_REDACT)),
        "tracker": async_redact_data(tracker_coordinator.data, TO_REDACT),
    }
