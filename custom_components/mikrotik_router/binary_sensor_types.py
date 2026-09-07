"""Definitions for Mikrotik Router binary sensor entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .iface_attributes import (
    DEVICE_ATTRIBUTES_IFACE,
)

DEVICE_ATTRIBUTES_PPP_SECRET = [
    "connected",
    "service",
    "profile",
    "comment",
    "caller-id",
    "encoding",
]

DEVICE_ATTRIBUTES_UPS = [
    "name",
    "offline-time",
    "min-runtime",
    "alarm-setting",
    "model",
    "serial",
    "manufacture-date",
    "nominal-battery-voltage",
    "runtime-left",
    "battery-charge",
    "battery-voltage",
    "line-voltage",
    "load",
    "hid-self-test",
]

DEVICE_ATTRIBUTES_NETWATCH = [
    "host",
    "name",
    "type",
    "interval",
    "port",
    "http-codes",
    "status",
    "comment",
]

DEVICE_ATTRIBUTES_WIREGUARD_PEER = [
    "interface",
    "name",
    "comment",
    "responder",
    "current-endpoint-address",
    "current-endpoint-port",
    "allowed-address",
    "disabled",
]


@dataclass
class MikrotikBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing mikrotik entities."""

    icon_enabled: str | None = None
    icon_disabled: str | None = None
    ha_group: str | None = None
    ha_connection: str | None = None
    ha_connection_value: str | None = None
    data_path: str | None = None
    data_attribute: str = "available"
    data_name: str | None = None
    data_name_comment: bool = False
    # When True, custom_name prefers a non-empty data_name over the comment,
    # then falls back to comment, then the static name. Used by netwatch so
    # entries sharing a comment are disambiguated by their distinct name.
    # Other platforms' descriptions lack the field, so custom_name reads it
    # defensively. See ADR-018.
    data_name_prefer: bool = False
    data_uid: str | None = None
    data_reference: str | None = None
    data_attributes_list: List = field(default_factory=lambda: [])
    func: str = "MikrotikBinarySensor"


SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    MikrotikBinarySensorEntityDescription(
        key="lte_connection",
        name="Connection",
        icon_enabled="mdi:signal",
        icon_disabled="mdi:signal-off",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="LTE",
        data_path="lte",
        data_attribute="connected",
        data_uid="",
        data_reference="",
    ),
    MikrotikBinarySensorEntityDescription(
        key="system_ups",
        name="UPS",
        icon_enabled="",
        icon_disabled="",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        ha_group="System",
        data_path="ups",
        data_attribute="on-line",
        data_uid="",
        data_reference="",
        data_attributes_list=DEVICE_ATTRIBUTES_UPS,
    ),
    MikrotikBinarySensorEntityDescription(
        key="ppp_tracker",
        name="PPP",
        icon_enabled="mdi:account-network-outline",
        icon_disabled="mdi:account-off-outline",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        ha_group="PPP",
        ha_connection=DOMAIN,
        ha_connection_value="PPP",
        data_path="ppp_secret",
        data_attribute="connected",
        data_name="name",
        data_uid="name",
        data_reference="name",
        data_attributes_list=DEVICE_ATTRIBUTES_PPP_SECRET,
        func="MikrotikPPPSecretBinarySensor",
    ),
    MikrotikBinarySensorEntityDescription(
        key="interface",
        name="Connection",
        icon_enabled="mdi:lan-connect",
        icon_disabled="mdi:lan-pending",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        ha_group="data__default-name",
        ha_connection=CONNECTION_NETWORK_MAC,
        ha_connection_value="data__port-mac-address",
        data_path="interface",
        data_attribute="running",
        data_name="default-name",
        data_uid="default-name",
        data_reference="default-name",
        data_attributes_list=DEVICE_ATTRIBUTES_IFACE,
        func="MikrotikPortBinarySensor",
    ),
    MikrotikBinarySensorEntityDescription(
        key="netwatch",
        name="Netwatch",
        icon_enabled="mdi:lan-connect",
        icon_disabled="mdi:lan-pending",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        ha_group="Netwatch",
        ha_connection=DOMAIN,
        ha_connection_value="Netwatch",
        data_path="netwatch",
        data_attribute="status",
        data_name="name",
        data_name_prefer=True,
        data_uid="host",
        data_reference="host",
        data_attributes_list=DEVICE_ATTRIBUTES_NETWATCH,
        func="MikrotikBinarySensor",
    ),
    MikrotikBinarySensorEntityDescription(
        key="wireguard_peer_connected",
        name="Connected",
        icon_enabled="mdi:vpn",
        icon_disabled="mdi:vpn",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        ha_group="WireGuard",
        ha_connection=DOMAIN,
        ha_connection_value="WireGuard",
        data_path="wireguard_peers",
        data_attribute="connected",
        data_name="peer-label",
        data_name_prefer=True,
        data_uid="public-key",
        data_reference="public-key",
        data_attributes_list=DEVICE_ATTRIBUTES_WIREGUARD_PEER,
        func="MikrotikBinarySensor",
    ),
)

SENSOR_SERVICES = {}
