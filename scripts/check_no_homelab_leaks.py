#!/usr/bin/env python3
"""Fail if private IPs or MAC addresses leak into public, integration-facing files.

This is a public fork. `docs/` (except `docs/internal/`), `custom_components/`,
`README.md`, and `info.md` are visible to every user and must not carry real
homelab specifics. This guard scans those tracked files for RFC1918 private IPv4
addresses and MAC addresses — on this repo, a real one usually means a homelab
value got pasted into an ADR / ISSUES / CHANGE-REGISTER entry from live evidence.

Allowed (won't fail):
  - Documentation IP ranges: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24
  - The placeholder default 10.0.0.1, plus 0.0.0.0 / 255.255.255.255
  - Example MAC OUIs: AA:BB:CC, 00:00:5E (RFC 7042 doc range), DE:AD:BE
  - Any line containing the marker `leak-ok`

`tests/` is intentionally out of scope (fixtures use example data). Use a
documentation range or a `leak-ok` marker for an intentional public reference.

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

    if findings:
        print("Homelab-leak check FAILED - private IPs / MACs in public files:\n")
        for path, lineno, tok in findings:
            print(f"  {path}:{lineno}: {tok}")
        print(
            "\nReplace with a documentation range (198.51.100.x), an example MAC "
            "(AA:BB:CC:DD:EE:NN), or a placeholder. Add a 'leak-ok' marker on the "
            "line only if the value is genuinely public."
        )
        return 1

    print("Homelab-leak check passed: no private IPs / MACs in public files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
