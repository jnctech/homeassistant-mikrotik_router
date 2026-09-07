"""Unit tests for scripts/check_no_homelab_leaks.py.

Pure-stdlib: the script has no Home Assistant dependency, so these run without
the Docker/HA test image. The module lives in scripts/ (not a package), so it is
loaded by path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).parent.parent / "scripts" / "check_no_homelab_leaks.py"
_spec = importlib.util.spec_from_file_location("check_no_homelab_leaks", _SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


# --- IP detection ----------------------------------------------------------


def test_private_ip_is_offending():
    assert guard.offending_ip("192.168.88.43") is True
    assert guard.offending_ip("10.5.4.3") is True
    assert guard.offending_ip("172.16.0.1") is True


def test_documentation_ranges_allowed():
    assert guard.offending_ip("192.0.2.5") is False
    assert guard.offending_ip("198.51.100.10") is False
    assert guard.offending_ip("203.0.113.9") is False


def test_placeholder_and_public_ips_allowed():
    assert guard.offending_ip("10.0.0.1") is False  # documented placeholder default
    assert guard.offending_ip("0.0.0.0") is False
    assert guard.offending_ip("255.255.255.255") is False
    assert guard.offending_ip("8.8.8.8") is False  # public, not private
    assert guard.offending_ip("not.an.ip.x") is False


# --- MAC detection ---------------------------------------------------------


def test_real_mac_is_offending():
    assert guard.offending_mac("B0:F8:93:DE:60:AD") is True


def test_example_mac_ouis_allowed():
    assert guard.offending_mac("AA:BB:CC:DD:EE:01") is False
    assert guard.offending_mac("00:00:5E:00:53:01") is False
    assert guard.offending_mac("DE:AD:BE:EF:00:01") is False


# --- Governance / coordination tokens (ISS-260712) -------------------------


def test_governance_tokens_are_flagged():
    for line in (
        "committed to ~/oob following the contract",
        "pushed to jnctech/oob PRIVATE",
        "declaration in oob/registry/standards-intake/",
        "git mv'd the message to mailbox/read/",
        "relayed via mailbox/to-config/",
        "see RELAY-from-mikrotik-to-config-topic-2026-07-12.md",
        "reported by OOB-CHECK-estate-alignment-2026-07-12",
        "gate WATCHDOG-AUDIT-onboard-renderer passed",
        "step-5b STANDARDS-mikrotik declaration",
        "the operator will ratify this next session",
    ):
        assert guard.offending_governance(line), f"should flag: {line!r}"


def test_legitimate_content_is_not_flagged():
    """High-precision patterns must not trip on real integration content."""
    for line in (
        "Supports out-of-band (OOB) management on the router.",
        "See the repo's own CONTRIBUTING.md for the contributor guide.",
        "RouterOS watchdog timer reboots the device on a hang.",
        "The netwatch probe monitors host reachability.",
        "192.0.2.1 is a documentation address.",
        "gratification and ratios are ordinary words",  # substring guard: not 'ratify'
    ):
        assert not guard.offending_governance(line), f"false positive: {line!r}"
