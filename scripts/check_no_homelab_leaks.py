#!/usr/bin/env python3
"""Fail if private IPs, MACs, or internal-coordination tokens leak into public files.

This is a public fork. `docs/` (except `docs/internal/`), `custom_components/`,
`README.md`, and `info.md` are visible to every user and must not carry real
homelab specifics. This guard scans those tracked files for:
  1. RFC1918 private IPv4 addresses and MAC addresses — usually a homelab value
     pasted into an ADR / ISSUES / CHANGE-REGISTER entry from live evidence.
  2. Internal-coordination tokens — paths and artifact names from the maintainer's
     private multi-repo agent-coordination estate (private-repo paths, mailbox
     routing, relay/check/standards artifacts, ratification terms). These have no
     place in an integration-facing doc; on 2026-07-12 a batch leaked into the
     public In-flight block and passed the IP/MAC-only gate silently (ISS-260712).

Allowed (won't fail):
  - Documentation IP ranges: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24
  - The placeholder default 10.0.0.1, plus 0.0.0.0 / 255.255.255.255
  - Example MAC OUIs: AA:BB:CC, 00:00:5E (RFC 7042 doc range), DE:AD:BE
  - Any line containing the marker `leak-ok`

The governance patterns are deliberately high-precision (structured paths /
artifact prefixes, not bare words) so legitimate integration content — e.g.
"out-of-band management", the repo's own `CONTRIBUTING.md`, RouterOS "watchdog"
— does not trip them. Add a term here only if it is unambiguously estate-internal.

`tests/` is intentionally out of scope (fixtures use example data), as is
`scripts/` (this file documents the tokens by example). Use a documentation range
or a `leak-ok` marker for an intentional public reference.

Exit code 1 (with the offending file:line) on any finding; 0 otherwise.
"""

from __future__ import annotations

import ipaddress
import re
import subprocess
import sys

INCLUDE_PREFIXES = ("docs/", "custom_components/", "README.md", "info.md")
EXCLUDE_PREFIXES = ("docs/internal/",)
ALLOW_MARKER = "leak-ok"

ALLOW_IPS = {"0.0.0.0", "10.0.0.1", "255.255.255.255"}
DOC_NETS = [
    ipaddress.ip_network(n)
    for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
]
ALLOW_MAC_OUI = ("aa:bb:cc", "00:00:5e", "de:ad:be")

IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")

# Internal-coordination ("estate") tokens. High-precision by design: structured
# paths and artifact prefixes, never bare words, so legit integration content
# (out-of-band management, this repo's own CONTRIBUTING.md, RouterOS watchdog)
# does not false-positive. See the module docstring and ISS-260712.
GOVERNANCE_RE = re.compile(
    r"""
      ~/oob\b                                       # private estate repo path
    | \bjnctech/oob\b                               # private estate repo slug
    | \boob/(?:registry|standards|verification|mailbox|reports|gates|runs|status|prompts|architecture)\b
    | \bmailbox/(?:to-|from-|read)\b                # estate mailbox routing
    | \bRELAY-from-\S+-to-\S+                        # estate relay artifacts
    | \bOOB-CHECK\b                                 # estate check artifacts
    | \bWATCHDOG-(?:PROMPT|AUDIT|VERIFY)\b          # estate watchdog artifacts
    | \bSTANDARDS-(?:mikrotik|tandem|config)\b      # standards-intake declarations
    | \bratif(?:y|ied|ication|ies)\b                # ratification governance term
    """,
    re.IGNORECASE | re.VERBOSE,
)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout
    files = [f for f in out.split("\0") if f]
    return [
        f
        for f in files
        if f.startswith(INCLUDE_PREFIXES) and not f.startswith(EXCLUDE_PREFIXES)
    ]


def offending_ip(token: str) -> bool:
    try:
        addr = ipaddress.ip_address(token)
    except ValueError:
        return False
    if str(addr) in ALLOW_IPS or any(addr in net for net in DOC_NETS):
        return False
    return addr.is_private


def offending_mac(token: str) -> bool:
    return not token.lower().startswith(ALLOW_MAC_OUI)


def offending_governance(line: str) -> list[str]:
    """Return the estate/coordination tokens found on a line (empty if none)."""
    return [m.group(0) for m in GOVERNANCE_RE.finditer(line)]


def main() -> int:
    findings: list[tuple[str, int, str]] = []
    for path in tracked_files():
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if ALLOW_MARKER in line:
                continue
            for tok in IP_RE.findall(line):
                if offending_ip(tok):
                    findings.append((path, lineno, tok))
            for tok in MAC_RE.findall(line):
                if offending_mac(tok):
                    findings.append((path, lineno, tok))
            for tok in offending_governance(line):
                findings.append((path, lineno, tok))

    if findings:
        print(
            "Homelab-leak check FAILED - private IPs / MACs / coordination tokens "
            "in public files:\n"
        )
        for path, lineno, tok in findings:
            print(f"  {path}:{lineno}: {tok}")
        print(
            "\nReplace an IP/MAC with a documentation range (198.51.100.x) or example "
            "MAC (AA:BB:CC:DD:EE:NN). Move internal-coordination detail to gitignored "
            "docs/internal/ and describe it generically here. Add a 'leak-ok' marker "
            "on the line only if the value is genuinely public."
        )
        return 1

    print(
        "Homelab-leak check passed: no private IPs / MACs / coordination tokens "
        "in public files."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
