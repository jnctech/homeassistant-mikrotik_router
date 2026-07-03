# Release Validation

How this integration is validated before a release is tagged. Two complementary,
**repeatable** layers — the automated test suite (every push, in CI) and a live
cross-check of every sensor class against a real RouterOS device (each
release/RC). Both are designed to be re-run identically each cycle, not one-off.

See also [Quality Gates](quality-gates.md).

---

## Layer 1 — Automated tests (CI, every push)

The unit/integration suite runs on every push and pull request; it must be green
before a release branch is cut.

- **Framework:** `pytest` + `pytest-homeassistant-custom-component`.
- **Matrix:** Python **3.13** (HA 2026.1–2026.2 runtime) and **3.14** (HA 2026.3+),
  matching the [CI workflow](../.github/workflows/ci.yml).
- **Entity golden tests:** deterministic per-platform snapshots of the entities the
  integration produces from fixed API fixtures — see
  [ADR-014](decisions/ADR-014-entity-golden-tests.md). These pin entity output
  (state, unit, device class, attributes) so a regression in any sensor definition
  fails loudly.
- **Scope:** the suite drives the coordinator and platforms against **mocked**
  RouterOS API responses. It proves the parsing/derivation logic is correct for
  the modelled inputs — it does **not** prove the integration matches a *live*
  router (that's Layer 2).

Run locally:

```bash
pytest tests/ -v
```

The suite needs a Home Assistant test environment (Python 3.13/3.14). If your
workstation can't host one directly, run it in a matching container, e.g.:

```bash
docker run --rm -v "$PWD":/work -w /work python:3.14 \
  bash -c "pip install -q pytest pytest-homeassistant-custom-component \
           pytest-cov mac-vendor-lookup librouteros && pytest -q"
```

---

## Layer 2 — Live validation (each release / RC)

The automated suite uses mocked data, so it can't catch a class of issues that only
appear against real firmware: wrong unit/`device_class`, values that don't match the
router, entities stuck `unknown`/`unavailable`, or hardware-dependent sensors that
should (or shouldn't) exist. Layer 2 closes that gap by cross-checking **each sensor
class** against the device's own values.

### Method (tooling-agnostic)

1. **Home Assistant side** — read each entity's state + attributes (Developer Tools →
   States, the `/api/states` REST endpoint, or a template). Confirm
   `unit_of_measurement`, `device_class`, `state_class`, and that no entity is
   `unknown`/`unavailable` without an explained cause.
2. **Router side** — read the same value at source via RouterOS (Winbox/WebFig
   terminal, SSH, or the REST API). The relevant paths per class are below.
3. **Compare** HA vs router within the tolerances noted.

### Per-class source map

| Sensor class | RouterOS source | Check |
|---|---|---|
| temperature / voltage / cpu·switch·board·phy-temp / fan / PSU / power / PoE-in | `/system/health` | value within drift; correct unit + `device_class` |
| uptime / cpu-load / memory / hdd / client counts | `/system/resource` (+ derived) | `memory`,`hdd` ≈ `(total−free)/total`; uptime matches boot time |
| interface TX/RX (rate) | `/interface` (live) | non-zero on active links; `data_rate`, measurement |
| interface TX/RX total | `/interface` `tx-byte`/`rx-byte` | ≈ counter ÷ 1e9 (GB); `total_increasing` |
| PoE-out status / V / I / P | `/interface/ethernet/poe` (+ `poe monitor`) | status present; V/I/P only when the hardware reports them |
| DHCP client status / address | `/ip/dhcp-client` | `address` is `unknown` when the client is stopped/PPPoE (correct) |
| DHCP server status / leases | `/ip/dhcp-server` (+ `/ip/dhcp-server/lease`) | per-server naming; **leases = all lease-table entries** (incl. static), not bound-only |
| wired / wireless clients | host table (ARP + DHCP + bridge + wireless/CAPsMAN reg) | see derivation note |
| environment | `/system/script/environment` | only populated when the global variable holds a value |
| GPS lat/long | `/system/gps` | only on LTE/GPS hardware |

### Tolerances & known semantics (so they aren't re-flagged each run)

- **Measurement drift:** temperatures ±1–2 °C; CPU-load and client counts vary
  between polls — small differences are expected.
- **Traffic totals** reset when an interface flaps (check `link-downs`); a large gap
  there is expected, not a bug.
- **DHCP "leases"** counts every lease-table entry for the server (bound + waiting +
  static reservations), not just bound — compare against the full lease list.
- **Wired/wireless counts are derived**, per-device, from that device's host table
  (deduped by MAC, only currently-reachable hosts). On an AP `wired ≈ bridge-hosts −
  wireless-registrations`; on the gateway `wired ≈ reachable ARP entries`. They are a
  per-device perspective, **not** a network-wide unique total — the same client is
  counted by every device that sees it.
- **Environment sensors** track RouterOS global *script* variables, which are RAM-only
  and cleared on reboot; a value-less variable yields no sensor (by design).
- **Hardware-dependent classes** (PSU, GPS, switch-temperature, power-consumption,
  PoE-in, extra fans, PoE-out voltage/current/power) are **correctly absent** when the
  board doesn't report them. A device that exposes no `/system/health` at all should
  have no health sensors. Verify absence at the source rather than treating it as a
  failure.

### Coverage to aim for

Validate against representative hardware/firmware so each path is exercised at least
once: a routing device (health + DHCP servers), a switch (multiple temps + fan), and
APs on **both** the legacy `wireless` and the new `wifi` packages. Run at least once
with a **read-only** Home Assistant user — wireless/CAPsMAN/PPP capability detection
behaves differently without write access.

### Hardware the maintainer can't validate — beta-first gate

Some features depend on hardware **absent from the maintainer's fleet** (e.g. LTE
modems, SFP-temperature boards, PoE-metering PSUs). Layer 2 can't exercise them here,
so they **ship as a pre-release (`-beta.N`) first** and reach stable only after the
beta is validated on real hardware — by the contributor who owns the device, a user,
or the maintainer once hardware is available. An unvalidated hardware-gated feature is
**not releasable as stable**.

- Cut the beta off `dev` (pre-release; no `dev → master` — see [Quality Gates](quality-gates.md#branch-model)).
- Record the hardware, RouterOS version, and observed result in the Validation log below.
- Promote to stable only once that gate is cleared.

Precedents: PoE-out energy (beta-gated on @Dillton's metering hardware, [#59](https://github.com/jnctech/homeassistant-mikrotik_router/issues/59)); LTE modem sensors (beta-gated on @zvldz's Chateau S53UG, [#116](https://github.com/jnctech/homeassistant-mikrotik_router/pull/116)).

---

## Release checklist

- [ ] Automated suite green in CI on **both** Python 3.13 and 3.14.
- [ ] Non-trivial changes passed the [Review Gates](quality-gates.md#review-gates) —
      multi-agent audit panels (design/diagnosis) and the specialized pre-PR review passes.
- [ ] Any hardware-gated feature the maintainer can't validate on-fleet has cleared its
      **beta-first gate** (validated on real hardware — see above) before stable.
- [ ] Live cross-check of every sensor class against router truth on representative
      hardware (router + switch + AP; legacy + new Wi-Fi; read-only + full-access user).
- [ ] No entity stuck `unknown`/`unavailable` without an explained cause.
- [ ] Any discrepancy filed as an issue and fixed before tagging the stable release.
- [ ] `CHANGE-REGISTER.md` updated.

## Validation log

| Version | Live validation | Outcome |
|---|---|---|
| `v2.3.19-beta.2` | Full per-class cross-check against a live multi-device RouterOS deployment (router + switch + APs on legacy & new Wi-Fi; read-only HA user) | All sensor classes report router truth within tolerance. One state-quality issue found and fixed: empty/transient environment variables (`ISS-260608` → [#105](https://github.com/jnctech/homeassistant-mikrotik_router/pull/105)). |
