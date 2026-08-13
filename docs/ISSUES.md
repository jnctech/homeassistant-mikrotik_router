# Issues — Mikrotik Router HACS Integration

## In-flight

> **Updated 2026-07-12 (leak-redaction session).** **Public-leak fix (ISS-260712):** a private homelab IP + internal-coordination notes had shipped to public `dev` via the In-flight refresh precedent; redacted at HEAD (`f8e3a72`→`c90b053`, leak gate passes), detail moved to gitignored `docs/internal/`, root-caused (direct-to-`dev` push bypasses the PR gate; pre-commit skipped; post-push CI red can't block; gate was IP/MAC-only). **Leak gate extended** to also flag internal-coordination tokens — **[PR #122](https://github.com/jnctech/homeassistant-mikrotik_router/pull/122)** (`fix/leak-gate-governance-tokens` → `dev`, tests added), closes ISS-260712(b). **Operator-open:** ISS-260712(c) history-scrub decision (my lean: *don't* scrub — RFC1918/LAN-only, already cached; 2 tip commits after the beta tag, `master` clean), (d) `dev` branch protection requiring the leak gate.
>
> **Prior session (LTE beta):** **Cut pre-release [v2.3.21-beta.1](https://github.com/jnctech/homeassistant-mikrotik_router/releases/tag/v2.3.21-beta.1)** off `dev` (`release.yml` built the HACS zip; no `dev→master` — beta). Merged the full LTE chain: **#116** LTE modem sensors (@zvldz, merge-commit, authorship preserved, credited on PR + release notes) · **#120** maintainer hardening (base-class `native_value`/`is_on`→`.get()` **unknown-not-stale** fix + LTE entity tests) · **#119** standards docs (CONTRIBUTING, ADR-index reconciliation, beta-first + test-ownership) · **#121** beta release. **ADR-019 Accepted.** CRs: `CR-260703-lte-hardening`, `CR-260703-contributing-adr-numbering`, `CR-260703-release-v2.3.21-beta.1`.
>
> **Live-validated PASS.** Baseline (2.3.20) vs post-deploy vs final **HACS-installed beta** compare: **identical** unavailable/unknown sets (7 sensor unavail = documented orphans, 3 `dhcp_address` unknown by-design, 2 binary unavail), **clean HA log**, **0 phantom LTE entities** (conditional-creation correct on non-LTE fleet). Operator HACS-updated to the beta (manifest now reads `2.3.21-beta.1`). Validation report retained in gitignored `docs/internal/`. The `.get()` change is read-only (can't create entities); any count churn is additive.
>
> **Live-validation note (don't re-flag):** RB4011 WireGuard server interface renamed `wireguard1`→`wg-home` (config CR-260616) — `wireguard1_*` entities orphaned→`unavailable`, fresh `wg_home_*` live. Working as designed. Bare `sensor.mikrotik_tx/rx` + `[TEST] #70 netwatch` are pre-existing orphans.
>
> **NEXT SESSION (lead):**
> 0. **Merge PR #122** (leak-gate governance-token extension) once CI green; then close ISS-260712(b). Surface ISS-260712(c) history-scrub + (d) `dev` branch-protection decisions to the operator.
> 1. **PR #123 reconnect-on-poll (`ISS-260813-no-reconnect-until-hwinfo`)** — @sappsys's fix for the coordinator never retrying the API after a transient disconnect. Root cause confirmed and reproduced; code change sound. **Waiting on the contributor** for two test defects (read-only `option_sensor_*` assignment → suite red; `ruff format`); offered to push the fixes to their branch if they'd rather. **Approve the fork CI run** so their next push gets checks. Then merge-commit (not squash), and land the maintainer follow-up: happy-path + `wrong_login` → `ConfigEntryAuthFailed` coverage, ADR-007 `_async_ensure_connected()` extraction. Rolls into the open v2.3.21 beta. CR-260813-reconnect-on-poll.
> 2. **LTE field-validation gate (`ENH-260614-lte-modem-info`)** — v2.3.21-beta.1 **stays beta** until **@zvldz or an LTE user** confirms the LTE sensors on real hardware (maintainer fleet has none). On confirmation: **promote to stable** (`dev→master` PR + immediate back-merge, `master ⊆ dev` guard green; GitHub release, not pre-release) and **close ENH-260614**. Ping @zvldz on #116 when he can run the beta.
> 3. **WireGuard peer sensors (`ENH-260703-wireguard-sensors`)** — **operator-requested: plan next session.** Surface per-peer state from `/interface/wireguard/peers` (last-handshake→connected/stale, endpoint, per-peer rx/tx); today only interface-level tx/rx exists. Scope keying (`public-key`), capability gate, ADR-020, redaction — see the ENH entry.
> 4. **librouteros cap-lift** — `ENH-260512-librouteros-test-matrix`: 3.4.1 / latest-3.x / expected-fail-4.x CI matrix, then lift `manifest` to `>=4.0,<5` (the floor-bump is the **v2.4.0** trigger).
> 5. **Stale-debt sweep** — write the deferred `ISS-260512-librouteros-concurrency-adr` (Open, doc-only); reconcile stale statuses.
>
> **Cross-repo coordination (no integration-code impact):** downstream Home Assistant dashboard/config consumers were advised out-of-band of the `wireguard1`→`wg_home` sensor rename (repoint cards, delete orphaned `wireguard1_*` entities). Coordination and session detail live in gitignored `docs/internal/`.
>
> **Tooling:** pytest runs via **CI** (push to a PR triggers the matrix; feature-branch pushes don't). `manifest.json` is CRLF — Edit the version line, don't python-rewrite. Session/tooling specifics (shell, deploy target, test runner) live in gitignored `docs/internal/`, never in this tracked file.
>
> **Open threads (durable):**
> - **`ENH-260615-netwatch-host-key-collision`** — Filed/deferred (same-host probe collapse; needs `.id` re-key + unique_id migration). **`ISS-260616-test-fixture-subnet`** — Filed/Low (test_coordinator fixtures use the maintainer's real management subnet; guard excludes tests).
> - **Upstream-ported enhancements:** `ENH-260614-sfp-temperature` ([tomaae#499], Low — hardware-gated) · `ENH-260614-lte-modem-info` ([tomaae#249], Medium — needs LTE hardware/contributor).
> - **Test-catch hardening:** deprecation-as-failure `setup_integration` test (folded into `ENH-260608` goldens) + `ENH-260614-ha-canary-ci` (non-blocking HA-latest lane).
> - **Goldens BUILD (ADR-014 / `ENH-260608-test-suite-hardening`)** — `setup_integration` fixture → per-path `MockMikrotikAPI` fixtures → per-platform exemplars → drop `sonar-project.properties` exclusions → portable `config/docs/templates/hacs-testing/`.
> - **#76** capsman AP-vs-bridge name (@fuecy), **`ISS-260608-cleanup-over-logging`** (#92).
> - **Gold/Platinum conformance** — `reconfiguration-flow` + `strict-typing`. **Coordinator decomposition — DEFERRED** (would be ADR-016).
>
> **Standards:** all PRs target `dev`; `master` release-only via PR + immediate back-merge (guard enforces `master ⊆ dev`). Betas are pre-releases off `dev` (no `dev→master`). Refresh this `## In-flight` at session-end; don't delete merged PR branches immediately. Live validation each release per `docs/release-validation.md`. **HA side-load gotcha:** put any backup **outside** `/config/custom_components/` — a `*.bak` dir there with a `manifest.json` collides on domain and breaks the integration. New CI gate: `homelab-leak` (no private IPs/MACs in public docs). Test-runner host specifics live in gitignored `docs/internal/`. **Session/tooling and any homelab-specific detail stays in `docs/internal/` — never in this tracked file.**

## Current Priorities

1. ISS-260525-issue-68-capsman-detection — **🟢 Shipped in v2.3.18** (#77, "CAPsMAN on legacy-wireless 7.13+ routers"). Orphaned branches `claude/modest-einstein-0Ulby` / `feature/issue-68-capsman-interface` — prune.
2. ISS-260523-issue-68-capsman-interface — **🟢 Shipped** — `capsman-interface` attribute (ADR-011) is in the released integration. Low-priority refinement (prefer bridge name when a bridge-host row exists) open as [#76](https://github.com/jnctech/homeassistant-mikrotik_router/issues/76).
3. ISS-260509-mikrotikapi-concurrency — `set_value`/`execute` iterate the librouteros response outside the API lock; fixed in v2.3.16 (#64)
4. ISS-260509-ha-2026.5-untested — **🔴 Closed** — indirectly resolved via the v2.3.16 concurrency fix (#64/#65); integration runs on HA 2026.x / py3.14 (live box + CI matrix) with no 2026.5-specific regression.
5. ISS-260417-librouteros-4x-break — librouteros 4.0.1 breaks `connect()` kwarg; hotfix v2.3.14 pinned `<4.0` (proper 4.x migration tracked separately)
6. ISS-260320-new-device-discovery — New devices require HA restart (UID tracking in place, dispatcher needs entity guard hardening)
7. ENH-260523-ha-release-watch — scheduled HA release-notes watcher (proposed, low priority)
8. ENH-260523-scope-drift-hook — UserPromptSubmit detector for off-plan pivots (proposed, low priority)

(ISS-260512-ci-manifest-drift closed in PR #69; ISS-260522-ruff-format-drift closed in PR #71.)

---

## Active

### ISS-260813-no-reconnect-until-hwinfo — coordinator never retries the API after a transient disconnect
**Type:** Bug (availability / recovery)
**Priority:** High
**Created:** 2026-08-13
**Status:** 🟡 Fix in review — [#123](https://github.com/jnctech/homeassistant-mikrotik_router/pull/123) (@sappsys), CR-260813-reconnect-on-poll

**Symptom:**
After a transient RouterOS API outage (e.g. an upstream gateway reboot), entities stay `unavailable` even once the network is healthy again. Recovery needs a manual config-entry reload — the integration does not self-heal.

**Root cause:**
`MikrotikCoordinator._async_update_data()` is the only path that reaches the API without a `connection_check()` guard. Every entry point in `mikrotikapi.py` opens with one — `query` (:176), `set_value` (:231), `arp_ping` (:324), and four others — but the poll never gets that far. `_run_if_enabled()` gates on `api.connected()` and skips every fetch while disconnected, and `_async_update_hwinfo()` early-returns inside its 4h window, so the `get_access` → `query` → `connection_check` path that would reconnect is never taken. The poll then raises `UpdateFailed` having made no reconnect attempt. Worst case the integration stays down for ~4h from the last successful hwinfo refresh (after which `last_hwinfo_update` stops advancing, so every subsequent poll retries).

`_connection_retry_sec` (58s) is not the blocker: `api.disconnect()` zeroes `_connection_epoch`, so an attempt would be permitted immediately if one were made.

**Reproduced (2026-08-13):** driving the real `_async_update_data()` on `dev` with a disconnected API and `last_hwinfo_update` set to now raises `UpdateFailed("Mikrotik Disconnected")` with zero `connection_check` calls and zero executor jobs dispatched.

**Contrast:** `MikrotikTrackerCoordinator` holds a separate `MikrotikAPI` instance whose `arp_ping` carries the guard, so it reconnects normally during the same outage. The two coordinators differ in recoverability, which is what makes this a missing guard rather than a missing feature.

**Relationship to other issues:** this is the *recovery* half of `ISS-260507-ups-empty-path` and the [#64](https://github.com/jnctech/homeassistant-mikrotik_router/issues/64) PoE-toggle disconnect. It fixes neither cause, but it stops both from being permanent until a reload.

**Fix (in review):** [#123](https://github.com/jnctech/homeassistant-mikrotik_router/pull/123) calls `connection_check()` in the executor at the top of each poll when disconnected, raising via `_raise_disconnected()` if it fails. Contributor patch verified locally: no regressions (694 passed, 5 skipped), complexity 9 → 11 (gate ≤15), blocking call correctly in the executor (ADR-004). Two test defects returned to the contributor (read-only `option_sensor_*` property assignment; `ruff format`). Maintainer follow-up to add connected-happy-path and `wrong_login` → `ConfigEntryAuthFailed` coverage, plus an ADR-007 helper extraction. No ADR — behavioural fix, not a data-format/entity-identity/API-contract change.

---

### ENH-260703-wireguard-sensors — WireGuard peer/handshake status sensors
**Type:** Enhancement (new sensors)
**Priority:** Medium
**Created:** 2026-07-03
**Status:** 🔵 Filed — **plan next session** (operator-requested 2026-07-03)

Today the integration surfaces WireGuard only at the **interface** level (per-iface tx/rx + a connection binary_sensor — e.g. `wg-home`, `wg-us` on the RB4011). It does **not** surface **per-peer** state. RouterOS exposes that at `/interface/wireguard/peers` — per peer: `public-key`, `endpoint-address`/`endpoint-port`, `current-endpoint-address`/`-port`, **`last-handshake`**, `rx`/`tx`, `allowed-address`, `disabled`.

**Scope to plan (next session):**
- Which peer fields to expose (likely: last-handshake → a **connected/stale binary_sensor** or TIMESTAMP; current-endpoint; rx/tx per peer) and their `device_class`/`state_class`.
- **Entity identity / keying** — peers keyed by `public-key` (stable) vs name/comment; `unique_id` design + whether it needs a migration. Public keys are identifier-ish → consider hidden-by-default + `TO_REDACT` (same pattern as LTE IMEI/IMSI/ICCID, ADR-019).
- **Capability gate** — `support_wireguard` via `bool(query("/interface/wireguard"))`; conditional creation so non-WG routers get nothing (same pattern as `support_lte`).
- **"Connected" heuristic** — WG is connectionless; derive from `last-handshake` age (e.g. < ~3 min = up). Decide the threshold + whether it's a binary_sensor or an attribute.
- **ADR?** — likely yes (entity identity / new data source) → next unused **ADR-020** (per `docs/decisions/README.md § Numbering`).
- Check upstream/forks for prior art; verify field names on a live RB4011 (`/interface/wireguard/peers print detail`) before descriptors.

Note: this is separate from the `wireguard1`→`wg-home` rename orphans (config-side, not a bug).

---

### ISS-260608-fw-version-silent-fallthrough — fw-version-gated paths silently no-op at version 0
**Type:** Bug
**Priority:** Medium
**Created:** 2026-06-08
**Status:** 🟢 Merged to `dev` (PR #97); shipped in **v2.3.19-beta.2** (CR-260608-fw-version-silent-fallthrough). Folds into stable v2.3.19.

**Symptom:**
When `major_fw_version` is `0`, three version-gated coordinator methods silently did nothing with no diagnostic log: `get_capabilities` (capability detection skipped → `support_*` flags left at defaults), `_async_update_client_traffic` (client-traffic collection skipped), and `get_system_health` (health skipped). For read-only accounts this is a persistent state, so capsman/wireless/ppp sensors and client-traffic could be silently absent.

**Root cause:**
`major_fw_version` initialises to `0` (`coordinator.py:324`) and is only set in `get_firmware_update` (`:1719`), which early-returns for accounts lacking write/policy/reboot rights and leaves `0` on a firmware-string parse failure. The three `if 0 < v < 7 / elif v >= 7` chains had no `else`, so version 0 fell through silently. `get_system_health` additionally had a malformed `elif 0 < self.major_fw_version >= 7` (dead `0 <` clause; worked for v7 by accident).

**Fix (§2.1):**
Add an explicit `else:` to each chain that logs at **DEBUG** ("firmware version unknown (0); skipping … this cycle"); fix the malformed elif to `elif self.major_fw_version >= 7`. DEBUG (not WARNING) because a read-only account never self-heals the version → a per-poll warning would spam; the contributor read-only fw-version fix (#82) addresses the *reachability* at source. Tests: `major_fw_version=0` cases for all three (caplog). Verified 609 passed/5 skipped (py3.14); coordinator-reviewer PASS.

**Related:** #82/#81 (read-only fw-version at source); part of the §2.1 batch (remaining §2.1 items still open — see In-flight).

---

### ISS-260608-readonly-capability-detection — capability detection fails for read-only users on RouterOS 7.x
**Type:** Bug
**Priority:** High
**Created:** 2026-06-08
**Status:** 🟢 MERGED to `dev` — core fix [#81](https://github.com/jnctech/homeassistant-mikrotik_router/pull/81) (@ahharvey, `3b14465`) + maintainer hardening #98. Shipped in **v2.3.19-beta.2**; awaiting @ahharvey validation (wifi-qcom read-only) before closing [#82](https://github.com/jnctech/homeassistant-mikrotik_router/issues/82).

**Symptom:**
On RouterOS 7.x, an integration user without `write`/`policy`/`reboot` permissions silently gets no wireless / CAPsMAN / PPP / per-client-traffic data — e.g. `sensor._wireless_clients` reads `0` with clients connected, and `wifi-qcom` routers are queried on the non-existent `/interface/wireless` endpoint (`400 "no such command or directory (wireless)"`). Reported in [#82](https://github.com/jnctech/homeassistant-mikrotik_router/issues/82) by @ahharvey (hAP ax³ / wifi-qcom, RouterOS 7.22.3).

**Root cause:**
`major_fw_version` is only parsed inside `get_firmware_update()`, which early-returns under read-only access. It stays `0`, so `get_capabilities()` dispatch (gated on `major_fw_version`) never runs and support flags / `_wifimodule` keep their defaults.

**Fix:**
New `_parse_fw_version_from_resource()` parses the version from the read-only `/system/resource.version` at the tail of `get_system_resource()` (runs before `get_capabilities()` in the hwinfo loop). Self-skips when `major_fw_version > 0`, leaving the privileged `get_firmware_update()` path authoritative. Maintainer hardening adds 7 tests + a DEBUG log on the version-unavailable branch. No ADR (internal sourcing change). Complements `ISS-260608-fw-version-silent-fallthrough` (§2.1, downstream consumers).

---

### ENH-260608-entity-naming — distinct entities collide on friendly names (`_N` entity_id suffixes)
**Type:** Enhancement (entity naming / quality)
**Priority:** Medium
**Created:** 2026-06-08
**Status:** 🟢 Resolved on `feature/entity-naming` (ADR-013, CR-260608-entity-naming) — pending PR merge to `dev`

**Symptom:**
On networks with many clients or multiple DHCP servers, distinct entities receive the **same friendly name**, so Home Assistant disambiguates the entity_ids with `_2`/`_3`/… suffixes — e.g. `device_tracker.lwip0`, `lwip0_2`…`lwip0_6` (six different MACs), or one `dhcp_server` sensor per VLAN all named `…DHCP server`. The entities are valid and distinct (different `unique_id`s); only the *naming* collides.

**Root cause (corrected by live recorder-DB evidence 2026-06-08 — the original "named by interface" premise was wrong):**
- **Clients:** not interface-naming. The colliding hosts report a **non-unique DHCP hostname** (e.g. `lwip0`, the lwIP embedded-stack default on ESP-class IoT devices); their `interface` attribute is `bridge`, not `lwip0`. The coordinator only falls back to MAC when host-name is `unknown` (`coordinator.py:2548`), so a present-but-duplicate hostname slips through.
- **DHCP servers:** `dhcp_server_status`/`_lease_count` have `data_name == data_reference == "name"`, so the `entity.py` equality shortcut always fires and drops the distinct VLAN name; all servers share the one `System` device, so there is no device-level disambiguation either.

**Resolution (ADR-013):**
- Coordinator `_disambiguate_duplicate_hostnames()` appends the MAC to any host-name shared by >1 host → `"{host-name} ({mac})"`. Runs at the end of `async_process_host` so **both** client_traffic copy sites inherit it (`_init_accounting_hosts` fw<7, `process_kid_control_devices` fw≥7).
- Scoped `data_name_compose` descriptor flag (set only on the two `dhcp_server_*` descriptors) → `"{name} DHCP server"`.
- `unique_id` unchanged in both families → existing entity_ids/automations preserved; only friendly names + new entities change. No migration. Behaviour tests added (incl. v7 path + unique_id invariance + scope guard).
- **Out of scope (mechanism-compatible follow-up):** netwatch naming (jnctech #70) — see ENH-260608-netwatch-naming.

---

### ENH-260608-netwatch-naming — name netwatch entities by `name`, not shared `comment` (jnctech #70)
**Type:** Enhancement (entity naming / quality)
**Priority:** Low
**Created:** 2026-06-08
**Status:** 🔴 Closed — shipped in stable **v2.3.20** ([#114](https://github.com/jnctech/homeassistant-mikrotik_router/pull/114), CR-260615, ADR-018, CR-260629). Reporter **@L2jLiga** validated on beta.3 ("works like a charm") and **closed [#70](https://github.com/jnctech/homeassistant-mikrotik_router/issues/70)** himself (2026-06-18) — entity-level naming is sufficient; no per-host devices wanted.

**Request ([jnctech #70](https://github.com/jnctech/homeassistant-mikrotik_router/issues/70)):** with 50+ netwatch entries, many **share a `comment`**, so they collapse to one display name; the user wants the distinct **`name`** field shown instead.

**Resolution (ADR-018):** new `data_name_prefer` flag on the binary_sensor description; netwatch now resolves its display name **`name` (non-empty) → `comment` → static "Netwatch"**, bare (no suffix, since `has_entity_name` prepends the `<inst> Netwatch` device). `get_netwatch` parses `name` (`vals`, defaults `""`); `data_reference="host"` kept, so `unique_id`/entity_ids are unchanged. A new flag (not the `data_name_compose` reorder) was needed because the 5 `data_name_comment` switches require comment-first ordering. Scope: **entity display names only** (per-host devices out of scope). Same-host key collision is a separate root → **ENH-260615**.

---

### ENH-260615-netwatch-host-key-collision — same-host netwatch probes collapse to one entity
**Type:** Enhancement (entity identity)
**Priority:** Low
**Created:** 2026-06-15
**Status:** 🔵 Filed (split out from ENH-260608-netwatch-naming / #70)

`get_netwatch` keys netwatch on `host` (`coordinator.py:1690`), which is **not unique**: RouterOS allows multiple probes on the same host (different type/port). Two same-host entries resolve to the same uid and overwrite each other in `data[uid]` (`apiparser.py:143`, `_get_uid_from_keys` returns `entry["host"]`) → only **one** HA entity. Live-observed: two netwatch entries (`.id` `*1`/`*2`) on the same `host` surface as a single entity.

This is distinct from #70 (display-name collapse, fixed in ADR-018) — naming cannot fix a genuine key collision. `key_secondary` is an absent-key fallback, not a composite (`apiparser.py:163-171`), so it can't separate same-host rows. RouterOS exposes a unique `.id` (already used as a key elsewhere — `coordinator.py:1277/1567/3095`), but it is **unstable across reorders**, so re-keying changes `unique_id` and needs an **entity-registry migration**. Defer until a concrete need; design the migration first.

---

### ISS-260712-inflight-leak-bypass — homelab IP + internal-coordination notes leaked to public `dev` via In-flight refresh
**Type:** Bug (privacy hygiene / process)
**Priority:** High
**Created:** 2026-07-12
**Status:** 🟡 HEAD redacted; gate-extension + history-scrub decision open

Commit `a8a21ee` pushed a private homelab IP (RFC1918; value recorded only in gitignored `docs/internal/`) and internal-coordination notes (private-repo paths and workflow routing) into the tracked, **public** `docs/ISSUES.md` `## In-flight` block. The repo's own `scripts/check_no_homelab_leaks.py` **failed (exit 1)** on the IP, yet the content shipped.

**Root cause (four-part):**
1. **Direct-to-`dev` push, no PR gate** — the "In-flight refresh as a direct `dev` docs commit" precedent (`df2df36`) skips PR review, so no pre-merge gate runs.
2. **Pre-commit bypassed locally** — the `homelab-leak-check` hook wasn't run (`--no-verify` or not installed in that environment).
3. **Post-push CI can't block** — `ci.yml` runs `homelab-leak` on `push` to `dev`, so it went RED on `a8a21ee`, but a red CI on an already-pushed direct commit blocks nothing.
4. **Gate scope is IP/MAC only** — the coordination-note leak passed silently; `check_no_homelab_leaks.py` has no check for internal-coordination tokens.

**Actions:** (a) HEAD redacted, session/homelab detail moved to gitignored `docs/internal/`; ✅ (b) extend the leak gate to flag internal-coordination tokens (private-repo paths, workflow-routing paths, cross-repo contribution refs) — open; (c) **operator decision:** scrub the IP from public git history (rewrite = steward/force-push op) or accept the RFC1918 residue — open; (d) consider branch protection on `dev` requiring the leak gate to pass. Reported via an internal estate-alignment check.

---

### ISS-260616-test-fixture-subnet — test fixtures use the maintainer's real management subnet
**Type:** Chore (privacy hygiene)
**Priority:** Low
**Created:** 2026-06-16
**Status:** 🔵 Filed

`tests/test_coordinator.py` fixtures use the maintainer's real management subnet (the `_host` helper default and several DHCP/host fixtures). Pre-existing; low sensitivity (a /24 number). The CR-260616 leak guard deliberately **excludes `tests/`** (example data), so this is not auto-caught. Genericize to a documentation/`192.168.1.x` form when convenient; verify no assertion pins the exact value first. (The public-doc leaks — ADR-018 IP/infra and ADR-013 MACs — were already scrubbed; see CR-260616.)

---

### ISS-260608-env-sensor-empty-state — environment sensor reports `''` when the RouterOS env var is empty
**Type:** Bug (state quality)
**Priority:** Low
**Created:** 2026-06-08
**Status:** 🟢 Fixed — merged to `dev` ([#105](https://github.com/jnctech/homeassistant-mikrotik_router/pull/105), CR-260614-fix-env-sensor-empty-state). Ships in v2.3.19.

**Symptom:**
A `*_environment_<name>` sensor reports an empty string (`''`) as its state when the corresponding RouterOS environment variable exists but is empty (observed: `environment_defconfMode`). Empty-string is not a valid HA state convention — HA expects `None` → `unknown`/`unavailable`. On other routers where the same variable has no value the sensor correctly reads `unavailable`, so the behaviour is inconsistent.

**Root cause (confirmed live 2026-06-14):** `defconfMode` is a RouterOS global *script* variable (`/system/script/environment`) — RAM-only, set by the default-config script and wiped on reboot. SSH to hap_ax3 confirmed the env table is now empty (`env_count=0`; device rebooted ~06-13), so the once-`''` entity is now an orphaned `unavailable`/`restored` registry entry.

**Fix (two parts):**
- `coordinator.get_environment` coerces empty/whitespace values to `None`, so the entity reads `unknown` rather than `''` (incl. when a live entity's variable later goes empty).
- `entity._skip_environment_sensor` skips entity creation for value-less variables, so transient/empty globals don't create orphan-prone entities in the first place.
- Tests: `test_environment_empty_value_coerced_to_none` (coordinator), `test_skip_environment_sensor_*` (entity).
- Residual: the pre-existing orphan entity (`sensor.mikrotik_hapax3_environment_defconfmode`) was **deleted manually by the maintainer 2026-06-14**. The broader "transient non-empty global orphans on reboot" class is out of scope (would need entity cleanup, tracked separately if it recurs).

---

### ENH-260509-poe-energy — native PoE-out energy sensors (#59)
**Type:** Enhancement (new sensors)
**Priority:** Medium
**Created:** 2026-05-09
**Status:** 🔴 Closed — shipped in stable **v2.3.20** (ADR-017, CR-260614-poe-energy-sensors, CR-260629, [#59](https://github.com/jnctech/homeassistant-mikrotik_router/issues/59)/#109). **@Dillton validated measured energy on metering hardware (2026-06-29):** value increments correctly, survives HA restart, and is **selectable in the Energy Dashboard as an individual device** — confirming the one open **G1** (Energy-Dashboard selectability; `entity_category=None`). (G0 panel 2026-06-14 recommended the Option A blueprint; maintainer chose the turnkey native path, beta-gated; validation now complete.)

**Summary:**
Native per-port PoE-out **energy** sensors (kWh, `total_increasing`) derived from the existing PoE-out **power** reading, so users get Energy-dashboard-compatible consumption without template sensors. Detail/scoping notes live on the retained branch `docs/enh-260509-poe-energy` (commit `339932e`, +22 lines to ISSUES); the reserved beta name `v2.4.0-beta` is earmarked for this feature. `[branch contents verified 2026-06-14; full design UNVERIFIED — to be scoped next session]`

**G0 verdict (2026-06-14):** HA's Energy Dashboard consumes *energy* (kWh, `total_increasing`); the existing PoE *power* sensors are valid power inputs, but HA's idiomatic path for power-only devices is the **Integration (Riemann) + Utility Meter helper** — which already does trapezoidal Riemann + restart-persistence. RouterOS exposes only instantaneous power (no energy accumulator), so "native energy" = doing in-integration what HA core already does. **Recommended Option A:** keep power sensors, ship a **blueprint/package** that creates the helpers (closes #59 without reinventing core). **Option B** (native `RestoreSensor` energy, the branch plan) only if turnkey UX is wanted — **beta-gated on @Dillton's hardware** (maintainer HW reports null PoE power, so accuracy/restore can't be self-validated). **Open G1 decisions:** total = sum-of-ports vs device-total; reuse `CONF_SENSOR_POE` vs a new toggle; whether the DIAGNOSTIC `entity_category` blocks Energy-Dashboard selection (verify on live HA). Full panel report in the 2026-06-14 handoff.

---

### ISS-260614-configflow-reload-deprecation — HA deprecations: config-flow reload double-reload + ScannerEntity alias
**Type:** Bug (HA deprecation)
**Priority:** Medium — hard deadline HA Core **2026.12**
**Created:** 2026-06-14
**Status:** 🟢 Fixed on `chore/ha-deprecations-cleanup` (CR-260614-ha-deprecations-cleanup) — bundled with the ScannerEntity alias deprecation (upstream #495).

**Symptom:** HA deprecated (2026.6) using a config-entry update listener together with config-flow reload methods (double-reload / race); becomes an **error in 2026.12**. `[verified: developers.home-assistant.io/blog]`

**Where:** the integration uses both — `config_entry.add_update_listener(async_reload_entry)` (`__init__.py`) **and** `async_update_reload_and_abort(...)` in reauth (`config_flow.py`). `[verified: grep]`

**Fix (per HA):** drop the listener and rely on the config-flow reload, **or** switch to `async_update_and_abort()` / set `reload_on_update=False`. Small change; land before 2026.12.

**Resolution:** reauth switched to `async_update_and_abort()` (`config_flow.py`) — the update listener performs the single reload, ending the double-reload. **Bundled (upstream #495, HA 2026.6 → alias removed 2027.6):** `device_tracker.py` now imports `ScannerEntity`/`SourceType` from `homeassistant.components.device_tracker` instead of the deprecated `.config_entry`/`.const` aliases. 654 tests pass.

**Note:** other 2026.x deprecations checked — `FlowHandler.show_advanced_options` (removed 2027.6) not used; MQTT publish-param change N/A. Python 3.14 already the HA runtime (CI covers 3.13/3.14).

---

### ENH-260614-sfp-temperature — expose `sfp-temperature` health sensor (upstream #499)
**Type:** Enhancement (new sensor)
**Priority:** Low
**Created:** 2026-06-14
**Status:** 🔵 Filed — ported from upstream [tomaae#499](https://github.com/tomaae/homeassistant-mikrotik_router/issues/499)

Some boards (e.g. CRS317-1G-16S+) report `sfp-temperature` in `/system/health`, which the integration does not surface. Add it as a temperature sensor alongside the existing health temps — a small addition to the v7 `health7` consumption + a `sensor_types.py` descriptor (`device_class=temperature`, °C, DIAGNOSTIC). Hardware-gated like the other health sensors; verify the exact field name on a live SFP-equipped board (`/system/health print`) before shipping (no SFP-temp board in the maintainer fleet — csr310 reports cpu/phy/board only).

---

### ENH-260614-lte-modem-info — LTE modem cell-info sensors (upstream #249)
**Type:** Enhancement (new sensors)
**Priority:** Medium — high upstream demand (26 comments)
**Created:** 2026-06-14
**Status:** 🟢 Merged to `dev` — **contributor PR [#116](https://github.com/jnctech/homeassistant-mikrotik_router/pull/116) (@zvldz)** (merge commit, authorship preserved; CI green on 3.13/3.14 after fork-run approval). @zvldz applied all 4 change-request items (session-uptime null, stale-clear, debug logs, ADR-015→019). **Maintainer hardening** on `chore/lte-hardening`: LTE entity-layer tests + a base-class `unknown`-not-stale read fix (`native_value`/`is_on` use `.get()`; integration-wide — `system_ups` shared the same KeyError→stale path). ADR-019 Accepted. **Ships beta-first as `v2.3.21-beta.1`** (LTE hardware absent from the maintainer fleet — see release-validation beta-gate); validate on real hardware before stable, then close. Live validation on @zvldz's Chateau S53UG / Quectel EG18-EA (RouterOS 7.23.1) already done for the feature.

Expose LTE modem cell metrics (RSSI/RSRP/RSRQ/SINR, registration status, operator, band/EARFCN, cell-id) for RouterOS LTE interfaces from `/interface/lte/monitor [find] once`, gated on LTE-interface detection. Neither upstream nor the Csontikka alternative implements this → a genuine differentiator. **Contributor hardware closes the LTE-hardware gate** (maintainer fleet has none).

**Review outcome (PR #116, change-request — 4 required):**
1. `session-uptime` fabricates a "now" TIMESTAMP when the field is absent / modem not `running` (null-not-guess violation) → set `None`.
2. Early-return guards don't clear `ds["lte"]`/`ds["lte_firmware"]` (unlike `get_ups`) → stale RSSI/operator persist; clear on absent paths.
3. No debug logging on absent-data returns (repo convention) → add.
4. **ADR-number collision:** PR adds `ADR-015` (reserved for librouteros salvage; 016 reserved coordinator-decomp; 017/018 taken) → **renumber to ADR-019** + fix `docs/decisions/README.md`.
- Nits (optional): `int()` nulls decimal metrics (`sinr="13.5"`); add stale-data + absent-session-uptime tests.
- ✅ **Verified safe:** the `support_lte = bool(query("/interface/lte"))` probe returns empty (not error) on 4 non-LTE fleet archs (RB4011/hAP ac²/CRS310/hAP ax3) — no non-LTE disconnect (ISS-260507 shape ruled out). Complexity OK (`get_lte_signal`≈9, `get_lte_firmware`≈5, ≤15). Descriptors consistent; IMEI/IMSI/ICCID hidden-by-default + in `TO_REDACT`.
- Merge plan: preserve @zvldz authorship (merge commit, like #81); maintainer folds in What's New / `CR-…-lte-modem-sensors` + credits @zvldz; approve fork CI run (0 checks so far). **No v2.4.0 coupling** (per maintainer 2026-06-29).

---

### ENH-260614-ha-canary-ci — non-blocking CI lane against HA latest/dev to surface deprecations early
**Type:** Enhancement (CI / test quality)
**Priority:** Medium
**Created:** 2026-06-14
**Status:** 🔵 Filed

The suite pins one HA version (whatever `pytest-homeassistant-custom-component` resolves), so a deprecation introduced upstream — e.g. `ScannerEntity` in HA 2026.6 (#495) — isn't seen until a user reports log noise. Add a **non-blocking** (`continue-on-error`) CI matrix lane that installs the newest HA (or HA `dev`) and runs the suite, surfacing new deprecations/removals the day they ship. Pairs with `ENH-260523-ha-release-watch` (release-notes watcher) but operates at the test level; treat a red canary as an early-warning signal to file a deprecation ISS, not a PR blocker.

---

### ENH-260608-test-suite-hardening — migrate tests to spec'd mocks, parametrize, behaviour assertions
**Type:** Enhancement (test quality)
**Priority:** **High — pre-release deliverable** (maintainer 2026-06-08: must land before the next release)
**Created:** 2026-06-08
**Status:** 🟡 In Progress — reference (`test_sensor.py`) + real-typed description factory done. **Direction update (ADR-014, 2026-06-09):** the entity-surface layer moves to **L1 entity-golden tests** (syrupy over a mocked API boundary); the `make_mock_coordinator → spec=` coordinator-factory pass is now **optional** (goldens supersede it). The build is tracked by ADR-014's implementation plan and is the next-session focus.

The suite leans on unspecced `MagicMock` (yes-man) coordinators/descriptions, near-zero `parametrize`, and assertions on internal representation rather than behaviour. Migrate each module to: `spec=`/real-type mocks (typos/renames fail), `@pytest.mark.parametrize` for data-driven cases, fixtures for shared arrange, and input→output assertions. Full findings: `docs/internal/test-suite-review-2026-06-08.md`.

**Standing rule (maintainer):** new tests must be spec'd/real-typed at write time — do **not** lean on the yes-man factories. (Applied in ADR-013: its `custom_name` tests build the real `MikrotikSensorEntityDescription`.)

- [x] `test_sensor.py` — reference implementation (`feature/test-sensor-exemplar`, CR-260608-test-sensor-exemplar)
- [x] new ADR-013 tests written spec'd (real description dataclass; behaviour assertions) — `feature/entity-naming`
- [x] `conftest.py::make_mock_entity_description` — now builds the **real** `Mikrotik*EntityDescription` per platform (8 sites / 6 modules) so renamed/removed fields fail (`test/spec-entity-description`). Surfaced + fixed the switch/update tests building sensor-typed descriptions.
- [ ] **Goldens build — implement ADR-014** (the durable target): syrupy wiring → `setup_integration` fixture → deterministic per-path `MockMikrotikAPI` fixtures (make-or-break) → sensor exemplar → expand per platform → drop `sonar-project.properties` platform exclusions → portable `config/docs/templates/hacs-testing/` template. **Next-session focus.**
- [ ] (OPTIONAL — superseded by ADR-014 goldens) `conftest.py::make_mock_coordinator` `spec=MikrotikCoordinator` bridge; do only as a quick win before goldens land
- [ ] remaining (orthogonal): T4 parametrize clusters, T6 fixtures, T3 `make_coordinator` `object.__new__`
- [ ] **Deprecation-as-failure** (retrospective on ScannerEntity #495 / config-flow double-reload ISS-260614 / librouteros ISS-260417 — all warnings/silent fallbacks our mocked unit tests can't see): once the `setup_integration` fixture lands, add a test that loads the entry through HA and asserts `caplog` has no `deprecated` / `will be removed` records; investigate whether `pytest-homeassistant-custom-component` can promote HA deprecation reports to errors. Pin external-lib call contracts at every mock seam (done for `librouteros.connect` — `TestConnectKwargs`/`TestLoginMethod`; extend to remaining seams).

---

### ISS-260608-cleanup-over-logging — cleanup services log one INFO line per removed entity
**Type:** Bug (log verbosity / quality-scale appropriate-logging)
**Priority:** Low — benign; no functional impact
**Created:** 2026-06-08
**Status:** 🔵 Filed (fix deferred)

`async_cleanup_entities` logs **one INFO line per removed entity** (`__init__.py:137`), so a single cleanup that removes many orphans emits a burst of INFO lines. On the live v2.3.18 box (2026-06-08 15:02:53) a cleanup removed **71 orphaned `client_traffic_tx/rx` entities** (the `_2/_3/_4` naming-collision debris), tripping HA's per-integration rate limiter: `homeassistant.util.logging — Module custom_components.mikrotik_router is logging too frequently. 200 messages since last count`. The per-call summaries also log at INFO even when 0 were removed (`__init__.py:145/236/239`).

**Investigation (2026-06-08):** the cleanup services are **not** driven by any standing automation — searched `/config` (automations.yaml, scripts.yaml, configuration.yaml, `.storage`, `packages/`, `/config/scripts/`): no caller; the integration does not self-schedule. All 224 cleanup log lines are clustered in the 15:xx window only (none after) → a one-off, session-driven batch (the live entity audit + cleanup of ~335 stale entities). Will not recur unless cleanup is re-run over a large orphan set.

**Proposed fix (off `dev`, gated):**
- `__init__.py:137` per-entity removal → `_LOGGER.debug` (keep one INFO summary per call).
- Summaries (`:145/236/239`) → INFO when count > 0, DEBUG when 0.
- Behaviour test: a multi-removal cleanup emits ≤ 1 INFO line.

Present identically on **master (v2.3.18, running)** and **dev**.

---

### ENH-260608-quality-scale-conformance — close HA Integration Quality Scale gaps
**Type:** Enhancement (conformance)
**Priority:** Medium
**Created:** 2026-06-08
**Status:** 🟡 In Progress

Bring the integration to the HA Integration Quality Scale Bronze/Silver baseline. Verified scorecard reviewed against the official rules 2026-06-08.

- [x] **parallel-updates** (Silver) — `PARALLEL_UPDATES` per platform (`feature/parallel-updates`, CR-260608-parallel-updates)
- [x] **runtime-data** (Bronze) — typed `ConfigEntry.runtime_data` (`feature/runtime-data`, ADR-012, CR-260608-runtime-data)
- [x] **reauthentication-flow** (Silver) — `async_step_reauth` + raise `ConfigEntryAuthFailed` on `wrong_login` (`feature/reauthentication-flow`, CR-260608-reauthentication-flow)
- [x] **declare `quality_scale`** — `"quality_scale": "silver"` in `manifest.json` now that Bronze+Silver are met (`feature/declare-quality-scale`, CR-260608-declare-quality-scale)
- [ ] **reconfiguration-flow** (Gold), **strict-typing** (Platinum) — later, alongside the coordinator decomposition
- Already conformant: config-flow, has-entity-name, test-before-setup/-configure, entity-unique-id, brands, entity-translations (26 locales), diagnostics, config-entry-unloading.

Bronze+Silver met and declared (`quality_scale: silver`). Remaining tiers (Gold reconfiguration-flow, Platinum strict-typing) tracked above.

---

### ISS-260608-dev-master-divergence — `dev` and `master` synced by parallel commits, not merges
**Type:** Process / repo hygiene
**Priority:** Medium
**Created:** 2026-06-08
**Status:** 🟢 Reconciled on `dev` (PR #83, merge commit); going-forward rule added to CLAUDE.md

**Symptom:**
`git merge-base --is-ancestor origin/master origin/dev` returned **false** — `master` appeared "4 commits ahead" of `dev` even though the *code trees were content-identical* (only `README.md` differed by the PoE-energy guide). The 4 commits were patch-duplicates already on `dev` under different SHAs (e.g. `b98b7e2 fix(ci): lock-threads` vs `f71da08 …(dev parity)`; `1877bb5 Release v2.3.18` vs `4adda71`).

**Root cause:**
master↔dev were kept in sync by **re-applying changes as parallel commits** (`…(dev parity)`, duplicate release commits) instead of true merges, so git never recorded shared history and the branches drift permanently. This makes feature branching ambiguous (which base?) and PRs noisy (a master-based branch rebased onto dev drags master-only commits along).

**Resolution:**
One-time `master → dev` reconciliation **merge commit** (PR #83) — clean, brought only the README PoE guide. Going forward: features → `dev` → `master`; releases cut by **merging** `dev → master`; any hotfix landing on `master` first is **back-merged to `dev` with a real merge commit** so `dev ⊇ master` always holds. Rule documented in CLAUDE.md § Branch Strategy.

---

### ISS-260525-issue-68-capsman-detection — CAPsMAN + wireless disabled for 7.13+ routers on the legacy `wireless` package
**Type:** Bug
**Priority:** High
**Created:** 2026-05-25
**Status:** 🟡 In Review — fix in `claude/modest-einstein-0Ulby`; awaiting @fuecy validation on a `dev` pre-release

**Symptom:**
On RouterOS 7.13+ routers still running the legacy `wireless` package (not the new wifi driver), CAPsMAN client data never appears and wireless interface attributes are empty — even after the v2.3.17 dual-endpoint fallback. Reported in [#68](https://github.com/jnctech/homeassistant-mikrotik_router/issues/68) by @fuecy (RouterOS 7.21.4).

**Root cause:**
`coordinator._has_wifi_package()` returned `True` on the firmware version alone (`major==7 and minor>=13`), so a 7.13+ router still on the legacy `wireless` package was misclassified as a built-in-wifi-driver box. That set `support_capsman=False` — which gates the *entire* CAPsMAN fetch via `_run_if_enabled(self.get_capsman_hosts, requires=self.support_capsman)`, so the v2.3.17 (ISS-260523) endpoint fallback never even ran — **and** `_wifimodule="wifi"`, routing `get_wireless`/`get_wireless_hosts` at the empty `/interface/wifi*` endpoints. @fuecy's manual `support_capsman=True` patch confirmed the diagnosis but only restored CAPsMAN; interface enrichment was still mis-routed.

**Fix (`claude/modest-einstein-0Ulby`):**
Package-driven detection. `_has_wifi_package()` returns `False` when an enabled legacy `wireless` package is present (before the version heuristic); an explicitly enabled `wifi`/`wifi-qcom`/`wifi-qcom-ac` package still wins first. `_detect_capabilities_v7()` else-branch sets `_wifimodule="wireless"` explicitly. The version heuristic stays as the fallback for genuine 7.13+ boxes with no separate wifi package (built-in driver). 16 detection tests added; reviewed by the coordinator-reviewer agent across all scenarios.

---

### ISS-260523-issue-68-capsman-interface — CAPsMAN AP-virtual interface hidden when DHCP claimed first
**Type:** Bug
**Priority:** High
**Created:** 2026-05-23
**Status:** 🟡 In Progress — fix in `feature/issue-68-capsman-interface` (v2.3.17)

**Symptom:**
On a router with CAPsMAN APs (`Slaapkamer`, `Zolder`, etc.) the `interface` attribute on `device_tracker.<wireless-mac>` entities shows the bridge name, not the AP-virtual interface. Reported in [#68](https://github.com/jnctech/homeassistant-mikrotik_router/issues/68) by @fuecy.

**Root cause:**
`coordinator._merge_capsman_hosts()` (pre-v2.3.17) early-continued whenever an existing host's `source` was already something other than `"capsman"` — i.e. claimed by DHCP/ARP/bridge merges. Routers with persistent DHCP leases see DHCP claim hosts on every poll, so the capsman merge almost always skipped, and the AP-virtual interface was never recorded at all for those hosts.

**Fix (v2.3.17):**
ADR-011 — add a new additive `capsman-interface` attribute, always written by `_merge_capsman_hosts` regardless of source. Existing `source` / `interface` semantics unchanged.

**Fallback for v7.13+ users on legacy CAPsMAN:** Bundled into the same PR — `get_capsman_hosts` now probes the wifi endpoint first, falls back to `/caps-man/` if the primary returns no rows. Logs the transition at INFO level. See ADR-011 §3.

---

### ENH-260523-capsman-endpoint-fallback — probe both capsman endpoints, not just version-selected one
**Type:** Enhancement
**Priority:** Medium
**Created:** 2026-05-23
**Status:** 🔴 Closed — shipped in v2.3.17 with `feature/issue-68-capsman-interface`

**Need:**
`get_capsman_hosts()` picks the endpoint based on `major.minor` firmware version: `/caps-man/registration-table` for ≤7.12, `/interface/wifi/registration-table` for ≥7.13. Some users on RouterOS 7.13+ continue to run legacy CAPsMAN — for them the version-selected wifi endpoint returns an empty list while the legacy endpoint still has their data. Concretely: @fuecy on RouterOS 7.21.4 (#68) reports `/interface/wifi/registration-table` empty and `/caps-man/registration-table` populated.

**Implemented approach (v2.3.17, ADR-011 §3):**
Endpoints are probed in preference order (v7.13+ → wifi first then caps-man; v6/v7≤12 → caps-man only). First endpoint returning rows wins. The transition is logged at INFO level (`"CAPsMAN endpoint fallback: primary X returned no rows, using Y instead"`) so users can confirm the fallback is firing.

The fallback fires only when the primary returns zero rows; users on the new WiFi package incur no extra API call.

**Tests (v2.3.17):**
- `test_capsman_hosts_v7_13` — primary returns rows; fallback NOT used; legacy endpoint ignored even if populated.
- `test_capsman_hosts_v7_13_fallback_to_caps_man` — primary empty; falls back to caps-man; `rx-signal → signal-strength` rename still fires.
- `test_capsman_hosts_v7_13_both_endpoints_empty` — both empty → empty `capsman_hosts`, no crash.
- `test_capsman_hosts_v6_does_not_probe_wifi_endpoint` — v6 only probes the legacy endpoint.

---

### ENH-260523-ha-release-watch — scheduled HA release-notes watcher
**Type:** Enhancement (tooling / ops awareness)
**Priority:** Low
**Created:** 2026-05-23
**Status:** 🟡 Proposed

**Need:**
HA major/minor releases occasionally introduce changes that affect this integration (see ISS-260509-ha-2026.5-untested — 2026.5.0's Python 3.14 + thread-scheduling changes exposed the v2.3.16 lock race). Currently there is no automated signal that a new HA release has landed; the maintainer learns about it via user issue reports against the new version.

**Proposed shape:**
A separate `.github/workflows/ha-release-watch.yml` workflow on a `schedule:` cron (e.g. weekly Monday 06:00 UTC) that:
1. Fetches the HA blog / releases RSS feed.
2. Diffs against the last-seen version stored as a workflow-readable artefact or a value in `docs/`.
3. If a new minor/major appears, opens a GitHub issue tagged `ha-compat` with the release notes link and a checklist (entity migrations, deprecated APIs, breaking changes for `local_polling`).

**Why a separate workflow, not in `ci.yml`:**
CI runs on PRs/pushes, which is the wrong cadence for external-system watching and bloats per-PR time. A separate scheduled workflow keeps the concern isolated and skippable if quota matters.

**Alternative considered:**
Subscribe to HA RSS in the maintainer's reader / email — zero CI infra, no auditable history. The CI version is preferred if/when this lands because the issues it opens are searchable history for future "when did we know about X" forensics.

**Plan:**
Spec the workflow file, design the issue-template, decide last-seen storage (workflow artifact vs file). Defer until the maintainer has bandwidth — this is purely additive.

---

### ENH-260523-scope-drift-hook — UserPromptSubmit detector for off-plan pivots
**Type:** Enhancement (agent discipline)
**Priority:** Low
**Created:** 2026-05-23
**Status:** 🟡 Proposed

**Need:**
Conversational drift — the agent and user collaboratively pivot away from the current branch's stated scope onto unrelated tangents ("can we also...", "while we're at it..."), expanding the PR diff and obscuring the original change. The sibling `gedcom-tree-parser` project has documented prompt-engineered discipline for this (PLAN.md "Agent discipline" + "STOP-and-ASK triggers" + "Drift corrective input pattern") but it is enforced socially via prompts, not mechanically via a hook. This repo has no equivalent.

**Proposed shape:**
A fourth `.claude/hooks/user-prompt-scope-drift.sh` (UserPromptSubmit) that:
1. Reads the current branch name (`git branch --show-current`).
2. Reads the corresponding CR entry from `docs/CHANGE-REGISTER.md` for that branch slug — the "What Changed" table establishes scope.
3. Heuristically checks the user prompt for off-scope intent markers: "also", "while we're at it", "can we", "let's also", "by the way".
4. If detected AND the prompt does not reference any scope keyword from the CR's "What Changed" rows, surface a one-line inline reminder: "[scope-drift?] Current branch CR scope is X. New ask appears off-scope — capture as ENH-YYMMDD or continue?"

Non-blocking. The user always chooses.

**Why this is hard (and why it's proposed not done):**
False-positive cost is high — "can we" appears in genuine on-scope follow-ups ("can we also add a test for the C901 check?"). The scope-keyword extraction from the CR entry is fuzzy. A poorly-tuned version of this hook would be more annoying than useful.

**Plan:**
- Prototype against a recorded session log (e.g. this very session — it drifted into HA release-notes review and scope-drift discussion while finishing CR-260522).
- Tune the prompt-marker list against false positives.
- Decide whether the hook fires on every prompt or only after N exchanges in the same session.

---

### ISS-260522-ruff-format-drift — 26 files needed reformat under new `line-length=220`
**Type:** Bug (process / tooling)
**Priority:** Medium
**Created:** 2026-05-22
**Status:** 🔴 Closed — bundled into PR #71 (CR-260522)

**Symptom:**
During T2.1 verification of CR-260522, `ruff format --check` reported 26 files in `custom_components/mikrotik_router` + `tests/` as "would reformat". Both local ruff 0.11.4 and pre-commit-pinned ruff v0.9.0 produced the same reformat — no version-skew involved.

**Initial hypothesis (wrong):**
The pre-commit `ruff-format` hook was silently not running on recent commits, so format drift had been accumulating undetected.

**Actual cause (discovered when applying the fix):**
The drift is the direct consequence of CR-260522's new `pyproject.toml` setting `[tool.ruff] line-length = 220`. The previous codebase was formatted against ruff's undeclared default (line-length=88); the wider 220-char setting causes ruff to join shorter lines that were previously kept apart. CI on `dev` is and always was format-clean — the "drift" only appears in PR #71's working state because that's where the line-length config lives.

**Fix:**
Ran `ruff format` once over `custom_components/` and `tests/` on the CR-260522 branch; the 26 reformatted files are committed in the same PR as the config that requires them. `ruff check` continues to pass on every file.

**Why this matters (lesson, not a follow-up):**
Diagnosing a "drift" symptom by jumping to "the hook must not be running" without isolating the variables (e.g. `git checkout dev && ruff format --check`) wasted some time. When two things change together (new config + drift report), test each in isolation before forming a theory about hook health.

---

### ISS-260512-ci-manifest-drift — CI tested against the wrong librouteros version
**Type:** Bug (process / supply chain)
**Priority:** High
**Created:** 2026-05-12
**Status:** 🟡 In Progress — fix in `fix/ci-manifest-drift-guard`

**Symptom:**
External audit found that `.github/workflows/ci.yml` was installing `librouteros` unpinned (`pip install mac-vendor-lookup librouteros`), so CI resolved to whatever PyPI returned — currently `librouteros 4.0.1`. `manifest.json` pins `librouteros>=3.4.1,<4.0` (added in commit b6ad8e0 / v2.3.14 to work around the 4.x `connect()` break). HA therefore installs `<4.0` while every CI run since the hotfix tested against 4.x. The v2.3.14 hotfix was effectively shipped untested against the version it was hotfixing.

**Contributing factors:**
- `requirements.txt`, `requirements_dev.txt`, `requirements_tests.txt` all left `librouteros>=3.4.1` without an upper bound — even if CI installed from one of them, it would still resolve to 4.x.
- No CI guard asserts manifest ↔ requirements consistency, so the drift was invisible.
- `release.yml` builds the zip but no CI job verifies the artefact's HACS root-flat layout — an adjacent latent risk.

**Fix:**
1. Pin `librouteros>=3.4.1,<4.0` in all three `requirements*.txt`.
2. CI `tests` job installs from `manifest.json` (the same pattern already proven in the `dependency-audit` job at lines 106–115).
3. New `manifest-drift` job fails the PR if any `requirements*.txt` diverges from `manifest.json`.
4. New `zip-structure` job builds the release zip the same way `release.yml` does and asserts `manifest.json` is at the zip root.

**Follow-up (separate work):** now tracked as their own entries —
- `ISS-260512-librouteros-concurrency-adr` (Active, below)
- `ENH-260512-librouteros-test-matrix` (Backlog)

---

### ISS-260512-librouteros-concurrency-adr — document the API concurrency model
**Type:** Documentation (ADR)
**Priority:** High
**Created:** 2026-05-12
**Status:** 🔴 Open
**Promoted:** 2026-05-30 — was a follow-up bullet under `ISS-260512-ci-manifest-drift`; filed as its own entry (handoff-gap backfill, config `ISS-260526`).

**Description:**
Write an ADR (model on `docs/decisions/`, ADR-007 shape) documenting the librouteros/API concurrency model that the v2.3.14/15/16 fix sequence exposed as fragile:
1. **Client ownership** — main and tracker coordinators each own a separate `MikrotikAPI` instance (`coordinator.py:146` and `:297`).
2. **Lock scope** — `threading.Lock` in `mikrotikapi.py`, held around all API path operations including the response iteration (post-v2.3.16), shared by service calls / switches / buttons / main poll on the main client.
3. **Timeouts** — current constructor values in `mikrotikapi.py`.
4. **Latency under load** — 10× interfaces, large DHCP lease tables, bridge hosts, wireless registrations.
5. **Failure mode** — when librouteros raises mid-response (the v2.3.14/15/16 history is the case study).

Land as a doc-only PR to `dev`; add a `CR-260512-…-concurrency-adr` entry and resolve to Done on merge.

**Related:** `ISS-260512-ci-manifest-drift` (parent), `ISS-260509-mikrotikapi-concurrency` (the lock fix this documents), `ADR-005-lock-context-managers`.

---

### ISS-260509-mikrotikapi-concurrency — set_value/execute corrupt socket under rapid use
**Type:** Bug
**Priority:** High
**Created:** 2026-05-09
**Status:** 🟡 In Progress — fix in `fix/api-concurrency-lock` (v2.3.16)

**Symptom:**
Rapidly toggling PoE switches in the HA UI causes the integration to disconnect. Traceback shows librouteros' `parse_word` raising `ValueError: not enough values to unpack (expected 3, got 2)` while iterating the response inside `_find_entry`. Subsequent polls then time out with `building list for path /ip/arp : timed out` and the coordinator marks itself disconnected. Reported in #64 (RB5009UPr+S+IN, RouterOS 7.22.2, HA 2026.5.0 / Python 3.14).

**Root cause:**
`MikrotikAPI.set_value()` and `MikrotikAPI.execute()` call `query(path, return_list=False)` which returns the librouteros `Path` object **outside** the API lock. They then call `_find_entry(response, ...)` — which iterates the Path and performs additional socket reads — also **outside** the lock. The 30s coordinator poll (`get_arp`, `get_health`, etc.) acquires the lock and reads from the same TCP socket concurrently. The librouteros parser sees a half-finished sentence from the interleaved reads and raises. `run_script()` already does this correctly (iterates inside the lock), so it was the model for the fix.

**Fix:**
Move `_find_entry` and the subsequent `response.update()` / `response(command, **params)` calls inside the existing `with self.lock:` block in `set_value` and `execute`. No public API changes.

**Why this just surfaced:**
The race has existed since the current `set_value`/`execute` shape was introduced. HA moved to Python 3.14 in [2026.3](https://www.home-assistant.io/blog/2026/03/04/release-20263/#running-on-python-314-), so the runtime change alone doesn't explain the timing — there were no reports of this race during the 2026.3 / 2026.4 windows. The first report (#64) is against 2026.5.0; whether 2026.5.0 changed something specific (service dispatch timing, executor pool sizing, or similar) is still being investigated. Either way the lock fix is correct and the race must be closed regardless of cause. Reporter confirmation requested in the GH thread (rollback test against v2.3.14).

---

### ISS-260509-ha-2026.5-untested — HA 2026.5.0 not yet validated
**Type:** Compatibility
**Priority:** Medium
**Created:** 2026-05-09
**Status:** 🔴 Closed — indirectly resolved. This was a byproduct of diagnosing #64: the "2026.5 breaks the integration" symptom was the `set_value`/`execute` concurrency race (a long-standing bug exposed by py3.14 thread scheduling), **diagnosed and fixed in v2.3.16** (#65) — not a 2026.5-specific incompatibility. Since then the integration runs on HA 2026.x / py3.14 on the live box (v2.3.18) and the **full CI matrix runs py3.13 + py3.14** on every PR with no 2026.5-specific regression. No separate manual-validation deliverable remains; future HA-release regressions are covered by ongoing CI + user reports (proactive watching tracked separately as ENH-260523-ha-release-watch).

**Context:**
HA 2026.5.0 (released 2026-05-06) is the first version where a user (#64) has reported the integration breaking. HA has been on Python 3.14 since [2026.3](https://www.home-assistant.io/blog/2026/03/04/release-20263/#running-on-python-314-), so the runtime alone isn't a sufficient explanation — the race in `set_value`/`execute` was present in 2026.3 and 2026.4 too without prior reports. The integration's CI matrix and local dev environment still target Python 3.13.

**Plan:**
- ✅ Add Python 3.14 to the CI matrix for the test job (done in `chore/sync-v2316-to-dev`)
- 🟡 Validate the integration manually against HA 2026.5.0 (PoE switching, device tracker, sensors, services) — **awaiting hardware/HA instance access**
- 🟡 Diff HA 2026.4 → 2026.5 release notes / commits for service-dispatch or executor-pool changes — **2026.5 release notes searched: no executor or service-dispatch changes called out (notable items were `serialx` migration, entity-ID domain matching, doorbell event standardization, infrared platform); will need to grep HA repo commits between 2026.4 and 2026.5 tags for `executor`, `async_add_executor_job`, `service_call`, `WebSocket` if #64 reproduces on v2.3.16**
- Document any 2026.5.0-specific behaviour in README compatibility notes

---

### ISS-260507-ups-empty-path — Empty `/system/ups` path disconnects the integration
**Type:** Bug
**Priority:** High
**Created:** 2026-05-07
**Status:** 🔴 Closed — fixed in v2.3.15 (PR for `fix/v2.3.15-ups-poe-current`)

**Symptom:**
On routers with the UPS package enabled but no UPS configured, the integration tile shows "Failed setup, will retry: Mikrotik Disconnected" and never loads. Logs:
```
ERROR ... Mikrotik <host> error while path : no such item
DEBUG ... Finished fetching ... data in 3.380 seconds (success: False)
```
Reported in #61 (RouterOS 7.22.1 on CCR2116-12G-4S+).

**Root cause:**
`coordinator.get_ups()` always issued the `/system/ups monitor` query because the parsed `enabled` field defaulted to `True` when `/system/ups` was empty. The `vals` entry for `enabled` uses `source="disabled"` with `reverse=True`; `from_entry_bool` returns `not default` when the source key is missing, so `enabled` becomes `True` for an empty path. RouterOS then rejects `monitor` with "no such item", and `_query_command` treats it as a connection failure.

**Fix:**
Bail out of `get_ups()` early when `/system/ups` returns no entries — clear `ds["ups"]` and skip both `parse_api` and the `monitor` query.

---

### ISS-260507-poe-current-unit — PoE out current displayed 1000× too large
**Type:** Bug
**Priority:** Medium
**Created:** 2026-05-07
**Status:** 🔴 Closed — fixed in v2.3.15 (PR for `fix/v2.3.15-ups-poe-current`)

**Symptom:**
PoE out current sensor displays `~1234.56 mA` for a port drawing ~25 mA (DE locale shows `1.234,56 mA`). Reported in #60 (RB5009UPr+S+IN, RouterOS 7.22.2).

**Root cause:**
`sensor_types.py` declared `poe_out_current` with `native_unit_of_measurement=AMPERE` and `suggested_unit_of_measurement=MILLIAMPERE`. RouterOS reports the value already in milliamperes (test fixtures use raw integers like `180`, `310`), so HA's unit conversion turned `180 A → 180000 mA`.

**Fix:**
Set `native_unit_of_measurement=MILLIAMPERE`; remove `suggested_unit_of_measurement`.

---

### ISS-260417-librouteros-4x-break — librouteros 4.0.1 breaks connection for all users
**Type:** Bug
**Priority:** Critical
**Created:** 2026-04-17
**Status:** 🟡 In Progress — hotfix (v2.3.14) pins `librouteros<4.0`. **Reframed by G0 panel 2026-06-14 (see Correction).** **Fix-first done:** the `login_method` callable kwarg is corrected on `fix/librouteros-login-method` (CR-260614-librouteros-login-method); the `<4.0` cap-lift remains separate (`ENH-260512-librouteros-test-matrix`).

**Correction (G0 panel, 2026-06-14 — verified vs luqasz/librouteros source):**
The `login_methods`→`login_method` (string→callable) change landed in **librouteros 3.0.0, NOT 4.0.x**. So the current code (`login_methods="plain"`, mikrotikapi.py) is wrong across the **whole pinned range** — the unknown kwarg is dropped and `connect()` falls back to the default `plain` callable, so it "works" by accident; **`login_method="token"` users silently get `plain` (latent auth bug)**. librouteros **4.0.0's only API change** is `cmd` made positional-only — **no impact** (the integration always passes the command positionally); `Path`/`query()`/exceptions are byte-identical 3.4.1↔4.0.0; the library is pure-Python (3.14 fine). **Revised plan:** (1) **fix-first** — map the config string to `librouteros.login.plain`/`token` in `MikrotikAPI.__init__` and pass `login_method=` (callable), under the **current `<4.0` pin**; live-validate plain AND token on a real router (CI mocks are blind — 4.0.0 is already installed locally and the mocked suite passes regardless). (2) **then** lift the cap to `librouteros>=4.0,<5` separately. Renumber the salvage-branch `ADR-010` (librouteros) → **ADR-015**. Naming: the fix can ride a `2.3.x`; the floor-bump is the real **v2.4.0** trigger (with the deferred coordinator decomposition).

**Symptom:**
Users on v2.3.13 (or any prior release) see: `connect() got an unexpected keyword argument 'login_methods'. Did you mean 'login_method'?`

**Root cause:**
librouteros 4.0.1 renamed the `connect()` keyword argument `login_methods` → `login_method`. `manifest.json` declared `librouteros>=3.4.1` with no upper bound, so HACS auto-installed 4.0.1 on upgrade. `mikrotikapi.py:102` still passes the old name.

**Related GitHub issues:**
- #55 (reported 2026-04-10) — direct stack trace
- #56 (reported 2026-04-13) — same symptom post-HA-2026.4.2 update; references upstream #477

**Hotfix (v2.3.14):**
- `manifest.json`: pin `librouteros>=3.4.1,<4.0`

**Follow-up (new ISS to be created for future release):**
- Rename kwarg in `mikrotikapi.py` to `login_method`
- Audit remaining librouteros 4.0.1 breaking changes
- Bump floor to `>=4.0`, drop upper bound

**Salvage (circle-back, 2026-06-08):** a migration plan + upstream-engagement notes were drafted on the **retained** branch `claude/review-engagement-requests-dIZVx` (it carries a *stale* `ADR-010-librouteros-4x-migration` — ADR-010 is now claude-tooling-baseline, so renumber on salvage). When this work starts: lift the plan into a correctly-numbered ADR, then drop the `<4.0` cap behind a librouteros version test matrix (`ENH-260512-librouteros-test-matrix`).

---

### ISS-260320-new-device-discovery — New devices require HA restart to appear
**Type:** Feature
**Priority:** Medium
**Created:** 2026-03-20
**Status:** 🟡 In Progress — UID tracking infrastructure done, dispatcher disabled pending entity guard fix

**Done:**
- ✅ `_check_new_uids()` tracks UIDs per entity-relevant data path (`_ENTITY_UID_PATHS`)
- ✅ `_check_entity_exists()` guard improved (early return if entity_id in platform.entities)
- ✅ device_tracker callback ignores dispatches from main coordinator
- ✅ First-run skip prevents redundant entity setup during startup

**Remaining:**
- Harden entity guard: `async_add_entities` still causes "does not generate unique IDs" when called for existing entities even with the guard. Investigate HA's `EntityPlatform.entities` dict timing.
- Re-enable dispatcher once guard is validated in live environment
- Test: add new host mid-run, verify entity created without log errors

---

## Backlog

### ISS-260326-tracker-wireless-detection — Device tracker uses old wireless detection logic
**Type:** Bug
**Priority:** Medium
**Created:** 2026-03-26
**Status:** 🔴 Closed — fixed in feature/v240-issues

**Context:**
`device_tracker.py` lines 157, 169, 199 check `source in ["capsman", "wireless"]` to determine wireless behavior (connection state, icon, attributes). The new `_is_wireless_host()` method in coordinator.py correctly detects wireless clients via bridge host table (fixing hAP ac2), but device_tracker still uses the old check.

**Impact:**
On routers with empty registration tables (hAP ac2 with new WiFi package), wireless clients discovered via bridge table have `source="arp"`, so the device tracker:
- Uses timeout-based `is_connected` instead of registration-based
- Shows wired icon instead of wireless
- Does not show wireless signal/rate attributes

**Fix:**
- Add `is_wireless` bool field to host data in coordinator (set by `_is_wireless_host`)
- Update device_tracker.py to check `self._data.get("is_wireless")` instead of source

---

### ENH-260512-librouteros-test-matrix — explicit librouteros version test matrix
**Type:** Enhancement (CI)
**Priority:** Medium
**Created:** 2026-05-12
**Status:** 🔴 Open
**Promoted:** 2026-05-30 — was a follow-up bullet under `ISS-260512-ci-manifest-drift`; filed as its own entry (handoff-gap backfill, config `ISS-260526`).

**Need:**
Explicit CI jobs covering librouteros `3.4.1`, latest `3.x`, and expected-fail `4.x`. Needed before the `manifest.json` `<4.0` cap can be relaxed — the cap exists because 4.0.1 broke `connect()`. The matrix turns the compatibility boundary into an asserted CI fact rather than a manual pin watched by hand.

**Related:** `ISS-260512-ci-manifest-drift` (parent), `ISS-260417-librouteros-4x-break` (the 4.x break the cap guards).

---

## Completed

### ISS-260320-new-device-discovery — New devices require HA restart to appear
**Type:** Feature | **Priority:** High | **Created:** 2026-03-20
**Status:** 🟡 Partially done — UID tracking in place, dispatcher disabled pending entity guard hardening

### ISS-260320-refactor-dedup — Refactor duplicated patterns
**Type:** Refactoring | **Priority:** Medium | **Created:** 2026-03-20
**Status:** 🔴 Closed — firewall helper extracted (feature/v240-issues), switch toggle extracted (PR #51), apiparser extracted (PR #30). Entity description mixin deferred.

### ISS-260320-test-coverage — Increase test coverage to ≥80%
**Type:** Testing | **Priority:** High | **Created:** 2026-03-20
**Status:** 🔴 Closed — 86% coverage achieved (565 tests, Phase 5 PR)

### ISS-260321-cognitive-complexity — Reduce cognitive complexity to ≤15 per function
**Type:** Quality | **Priority:** High | **Created:** 2026-03-21
**Status:** 🔴 Closed — fixed in refactor/legacy-cleanup (PR #30 + PR #51)

### ISS-260321-silent-failures — Silent failure patterns from security audit
**Type:** Bug/Quality | **Priority:** Medium | **Created:** 2026-03-21
**Status:** 🔴 Closed — fixed in refactor/legacy-cleanup (PR #30 + PR #51)

### ISS-260326-slow-load — Startup bottlenecks blocking HA loading
**Type:** Bug/Performance | **Priority:** High | **Created:** 2026-03-26
**Status:** 🔴 Closed — fixed in v2.3.12 (claude/fix-homeassistant-slow-load)

### ISS-260320-deprecated-datetime — Remaining naive datetime.now() calls
**Type:** Bug | **Priority:** Medium | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.12 (claude/fix-homeassistant-slow-load)

### ISS-260325-attribute-bloat — ~1300 junk attributes on interface and tracker entities
**Type:** Bug/Quality | **Priority:** High | **Created:** 2026-03-25
**Status:** 🔴 Closed — fixed in v2.3.11-beta.1 (feature/attribute-cleanup)

### ISS-260325-mangle-dedup — Mangle rules with different interfaces removed as duplicates
**Type:** Bug | **Priority:** High | **Created:** 2026-03-25
**Status:** 🔴 Closed — fixed in PR #40 (fix/mangle-duplicate-interface)

### ISS-260324-arp-incomplete — ARP "incomplete" status incorrectly shows device as home
**Type:** Bug | **Priority:** High | **Created:** 2026-03-24
**Status:** 🔴 Closed — fixed in v2.3.10 (PR #38)

### ISS-260322-upstream-frs — Port upstream feature requests
**Type:** Feature | **Priority:** High | **Created:** 2026-03-22
**Status:** 🔴 Closed — released in v2.3.9 (PR #32)

### ISS-260320-options-flow-crash — Options flow crash on HA 2025.12+
**Type:** Bug | **Priority:** Critical | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)

### ISS-260320-blocking-io — Blocking I/O in async methods
**Type:** Bug | **Priority:** High | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)

### ISS-260320-deadlock-run-script — Deadlock in mikrotikapi.py run_script
**Type:** Bug | **Priority:** Critical | **Created:** 2026-03-20
**Status:** 🔴 Closed — fixed in v2.3.6 (PR #19)

### ISS-260320-sonarcloud-token — SonarCloud token expired
**Type:** Infrastructure | **Priority:** Medium | **Created:** 2026-03-20
**Status:** 🔴 Closed — burner token set, SonarCloud passing

### ISS-260320-dispatcher-spam — Duplicate entity log errors from update_sensors
**Type:** Bug | **Priority:** High | **Created:** 2026-03-20
**Status:** 🔴 Closed — dispatcher disabled in v2.3.8 (PR #26). Proper fix tracked as ISS-260320-new-device-discovery

### ISS-260320-ruff-migration — Migrate from Black+flake8 to Ruff
**Type:** Quality | **Priority:** Low | **Created:** 2026-03-20
**Status:** 🔴 Closed — completed in PR #29 (feature/tests-and-refactor). CI uses ruff, all files formatted.
