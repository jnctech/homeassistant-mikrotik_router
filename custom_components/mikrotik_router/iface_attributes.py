"""Shared interface attribute lists used by sensor and binary sensor types."""

from __future__ import annotations

DEVICE_ATTRIBUTES_IFACE = [
    "running",
    "enabled",
    "comment",
    "port-mac-address",
    "last-link-down-time",
    "last-link-up-time",
    "link-downs",
    "actual-mtu",
    "type",
    "name",
]

# Shown only when client tracking is enabled and values are meaningful.
DEVICE_ATTRIBUTES_IFACE_CLIENT = [
    "client-ip-address",
    "client-mac-address",
]

DEVICE_ATTRIBUTES_IFACE_ETHER = [
    "status",
    "auto-negotiation",
    "rate",
    "full-duplex",
    "default-name",
]

DEVICE_ATTRIBUTES_IFACE_SFP = [
    "status",
    "rate",
    "full-duplex",
    "auto-negotiation",
    "default-name",
    "advertising",
    "link-partner-advertising",
    "sfp-temperature",
    "sfp-supply-voltage",
    "sfp-module-present",
    "sfp-tx-bias-current",
    "sfp-tx-power",
    "sfp-rx-power",
    "sfp-rx-loss",
    "sfp-tx-fault",
    "sfp-type",
    "sfp-connector-type",
    "sfp-vendor-name",
    "sfp-vendor-part-number",
    "sfp-vendor-revision",
    "sfp-vendor-serial",
    "sfp-manufacturing-date",
    "eeprom-checksum",
]

# /interface/wifi (wifi-qcom*, wifi-mediatek) rows nest their settings as
# dotted keys (`configuration.ssid`, `channel.band`, ...). The legacy
# `wireless` keys (mode, radio-name, country, antenna-gain, wds-*, ...) do not
# exist there, so a dedicated list avoids exposing a dozen `unknown` attributes.
# Names are flattened onto the legacy `wireless` attribute names so templates
# work across old and new hardware; the flattening happens in get_wireless() right after the parse.
DEVICE_ATTRIBUTES_IFACE_WIFI = [
    "ssid",
    "mode",
    "country",
    "band",
    "channel-width",
]

DEVICE_ATTRIBUTES_IFACE_WIRELESS = [
    "ssid",
    "mode",
    "radio-name",
    "interface-type",
    "country",
    "installation",
    "antenna-gain",
    "frequency",
    "band",
    "channel-width",
    "secondary-frequency",
    "wireless-protocol",
    "rate-set",
    "distance",
    "tx-power-mode",
    "vlan-id",
    "wds-mode",
    "wds-default-bridge",
    "bridge-mode",
    "hide-ssid",
]
