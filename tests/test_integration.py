"""Integration tests against a live MikroTik device (CHR or real hardware).

These tests are skipped automatically in CI (no env vars set).
To run locally against a CHR or real router:

    MIKROTIK_HOST=192.168.x.x \
    MIKROTIK_USER=admin \
    MIKROTIK_PASSWORD=yourpassword \
    pytest tests/test_integration.py -v -m integration
"""

import os

import pytest

from custom_components.mikrotik_router.mikrotikapi import MikrotikAPI

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def live_api():
    """Connect to a live MikroTik device; skip if env vars not set."""
    host = os.environ.get("MIKROTIK_HOST")
    if not host:
        pytest.skip("MIKROTIK_HOST not set — skipping integration tests")

    api = MikrotikAPI(
        host=host,
        username=os.environ.get("MIKROTIK_USER", "admin"),
        password=os.environ.get("MIKROTIK_PASSWORD", ""),
        port=int(os.environ.get("MIKROTIK_PORT", 8728)),
        use_ssl=os.environ.get("MIKROTIK_SSL", "false").lower() == "true",
        ssl_verify=False,
    )
    assert api.connect(), f"Could not connect to MikroTik at {host}: {api.error}"
    yield api
    api.disconnect()


def test_live_system_resource(live_api):
    """Live: /system/resource returns board-name and version."""
    result = live_api.query("/system/resource")
    assert result, "/system/resource returned empty"
    entry = result[0] if isinstance(result, list) else result
    assert "board-name" in entry, f"board-name missing from: {entry}"
    assert "version" in entry, f"version missing from: {entry}"


def test_live_interfaces(live_api):
    """Live: /interface returns at least one entry with name and type."""
    result = live_api.query("/interface")
    assert result, "/interface returned empty"
    for entry in result:
        assert "name" in entry, f"name missing from interface entry: {entry}"
        assert "type" in entry, f"type missing from interface entry: {entry}"


def test_live_health(live_api):
    """Live: /system/health returns at least one health entry."""
    result = live_api.query("/system/health")
    assert result is not None, "/system/health returned None"


def test_live_routerboard(live_api):
    """Live: /system/routerboard returns routerboard field."""
    result = live_api.query("/system/routerboard")
    assert result, "/system/routerboard returned empty"
    entry = result[0] if isinstance(result, list) else result
    assert "routerboard" in entry, f"routerboard field missing from: {entry}"


def test_live_poe_monitor_on_poe_interfaces(live_api):
    """Live: PoE monitor returns data for any interface with poe-out enabled."""
    interfaces = live_api.query("/interface/ethernet")
    if not interfaces:
        pytest.skip("No ethernet interfaces found")

    poe_interfaces = [i for i in interfaces if i.get("poe-out") not in (None, "N/A", "")]
    if not poe_interfaces:
        pytest.skip("No PoE-capable ethernet interfaces found on this device")

    iface = poe_interfaces[0]
    result = live_api.query(
        "/interface/ethernet/poe",
        command="monitor",
        args={".id": iface[".id"], "once": True},
    )
    assert result is not None, "PoE monitor returned None"
    if result:
        entry = result[0] if isinstance(result, list) else result
        assert "name" in entry, f"name missing from PoE monitor entry: {entry}"
