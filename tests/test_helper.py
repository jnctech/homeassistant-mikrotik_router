"""Tests for helper utility functions."""

from custom_components.mikrotik_router.helper import format_attribute, format_value


# --- format_attribute ---


def test_format_attribute_replaces_hyphens():
    assert format_attribute("mac-address") == "mac_address"


def test_format_attribute_replaces_spaces():
    assert format_attribute("host name") == "host_name"


def test_format_attribute_lowercases():
    assert format_attribute("MAC-Address") == "mac_address"


def test_format_attribute_combined():
    assert format_attribute("SFP Shutdown-Temperature") == "sfp_shutdown_temperature"


def test_format_attribute_no_change():
    assert format_attribute("already_clean") == "already_clean"


# --- format_value ---


def test_format_value_dhcp():
    assert format_value("dhcp") == "DHCP"


def test_format_value_dns():
    assert format_value("dns") == "DNS"


def test_format_value_capsman():
    assert format_value("capsman") == "CAPsMAN"


def test_format_value_wireless():
    assert format_value("wireless") == "Wireless"


def test_format_value_restored():
    assert format_value("restored") == "Restored"


def test_format_value_no_match():
    assert format_value("ethernet") == "ethernet"


def test_format_value_multiple_replacements():
    assert format_value("dhcp dns") == "DHCP DNS"
