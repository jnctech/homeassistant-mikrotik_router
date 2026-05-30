# Change Register — Mikrotik Router HACS Integration

Changes listed in reverse chronological order.

---

## CR-260530-tracking-visibility-and-handoff-backfill — document public/private tracking + promote 2 librouteros follow-ups

**Date:** 2026-05-30
**Branch:** `docs/iss-260526-mikrotik-backfill`
**Status:** Docs only — no integration code or behaviour change.

### What Changed

| Area | Change |
|------|--------|
| `CLAUDE.md` | New **Tracking visibility (public vs private)** section: integration-facing trackers (`docs/ISSUES.md`, `CHANGE-REGISTER.md`, `FEATURE-POLL.md`, `architecture.md`, `decisions/ADR-*`) are public; sensitive/internal (tokens, MACs, hostnames, captures, session meta) goes in gitignored `docs/internal/`. |
| `docs/ISSUES.md` | Promoted two follow-ups of `ISS-260512-ci-manifest-drift` from body bullets to their own entries: `ISS-260512-librouteros-concurrency-adr` (Active, High) and `ENH-260512-librouteros-test-matrix` (Backlog, Medium). |

### Why

Part of the cross-repo handoff-gap backfill (config `ISS-260526`) — a one-time sweep promoting un-filed commitments referenced in session handoffs into their owning repo's tracker. The two librouteros follow-ups were named in the 2026-05-12 handoff and listed as bullets under the (now-closed) ci-manifest-drift entry, but never filed as their own trackable entries, so they were invisible to the tracker. Both verified still-live: no concurrency ADR exists (ADR-005 is a narrower lock-context-manager refactor, not the client-ownership/lock-scope/timeout/failure-mode model), and CI has no librouteros version matrix. The CLAUDE.md rule was added because this is a public fork — the public/private split already existed in `.gitignore` but was undocumented.

---

## CR-260525-issue-68-capsman-detection — CAPsMAN disabled for 7.13+ routers on the legacy `wireless` package

**Date:** 2026-05-25
**Branch:** `claude/modest-einstein-0Ulby`
**Status:** In Review — pending @fuecy validation on a `dev` pre-release before version bump/tag

### What Changed

| Area | Change |
|------|--------|
| `custom_components/mikrotik_router/coordinator.py` | `_has_wifi_package()` now returns `False` when an enabled legacy `wireless` package is present, *before* the `>=7.13` version heuristic. An explicitly enabled `wifi`/`wifi-qcom`/`wifi-qcom-ac` package still wins first. |
| `custom_components/mikrotik_router/coordinator.py` | `_detect_capabilities_v7()` else-branch now sets `_wifimodule = "wireless"` explicitly and drops the dead `support_wireless = bool(self.minor_fw_version < 13)` line (a no-op in its only reachable path that, under the corrected routing, would have wrongly disabled wireless support for 7.13+ legacy boxes). |
| `tests/test_coordinator.py` | New detection test group (11 tests) covering `_detect_capabilities_v7` and `_has_wifi_package` across wifiwave2 / wifi-qcom / wifi-qcom-ac / legacy-wireless-on-7.13+ / no-package-on-7.13+ / no-package-on-7.5 / both-packages, plus the legacy-wireless regression pin. |
| `docs/ISSUES.md` | New ISS-260525-issue-68-capsman-detection entry; #68 priority note updated. |

### Why

The v2.3.17 dual-endpoint fallback (CR-260523) only runs when `support_capsman` is `True` — it is gated by `_run_if_enabled(self.get_capsman_hosts, requires=self.support_capsman)`. @fuecy is on RouterOS 7.21.4 still running the legacy `wireless` package, so `_has_wifi_package()` returned `True` on the version heuristic alone, setting `support_capsman=False` **and** `_wifimodule="wifi"`. Result: the entire CAPsMAN fetch (and therefore the v2.3.17 fallback) was skipped, and wireless interface enrichment queried the empty `/interface/wifi*` endpoints. His manual `support_capsman=True` patch confirmed the diagnosis but only fixed half — interface enrichment was still mis-routed.

The fix is package-driven: an enabled legacy `wireless` package routes both `support_capsman` and `_wifimodule` to the CAPsMAN-capable `/interface/wireless` path regardless of firmware version. The version heuristic remains the correct fallback for genuine 7.13+ boxes using the built-in wifi driver (no separate `wifi*` package to detect).

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint + `C901` | All checks passed (custom_components + tests) | ✅ |
| Cognitive complexity | `_detect_capabilities_v7` ≈6, `_has_wifi_package` ≈5 (≤15) | ✅ |
| Pytest | 235 passed locally (incl. 16 detection tests) | ✅ |
| coordinator-reviewer | Logic verified across all 6 scenarios; ADR-004/005/006/007/009 clean | ✅ |

### Release ops

Retired the stale `v2.4.0-beta.3` pre-release + git tag (2026-03-27, manifest 2.3.13, commit `3f813ae`). Its headline feature (dispatcher-based device discovery) was subsequently disabled on `dev` pending an entity-guard fix (ISS-260320 reopened), and it carried no commits not already reachable via `dev`. Release page + tag deleted by the maintainer; the `v2.4.0-beta` name is now free for the #59 PoE-energy beta.

**Date:** 2026-05-23
**Branch:** `feature/issue-68-capsman-interface`
**Status:** In Review (targeting `dev`)

### What Changed

| Area | Change |
|------|--------|
| `custom_components/mikrotik_router/coordinator.py` | `get_capsman_hosts()` rewritten to probe endpoints in preference order via new helpers `_capsman_endpoints_to_probe()` + `_fetch_capsman_table()`. v7.13+ → wifi first, caps-man fallback (closes ENH-260523); v6 / v7 ≤ 12 → caps-man only. First endpoint returning rows wins; transition logged at INFO. Per-endpoint field lists: full payload on `/caps-man/`, conservative 3-field shape on `/interface/wifi/`. `rx-signal` is renamed to `signal-strength` post-`parse_api`. |
| `custom_components/mikrotik_router/coordinator.py` | `_merge_capsman_hosts()` rewritten as two paths via extracted helpers (`_write_capsman_claim`, `_write_capsman_overlay`, `_copy_capsman_metrics`): new hosts get full claim; existing hosts get a `capsman-interface` overlay + wireless metrics without overwriting `source` or `interface`. Removes the `elif source != "capsman": continue` early-skip that hid the AP identity from any DHCP/ARP/bridge-claimed host. |
| `custom_components/mikrotik_router/device_tracker_types.py` | `"capsman-interface"` added to `DEVICE_ATTRIBUTES_HOST`. `copy_attrs` omits it on non-capsman hosts since the key is simply absent from their data. |
| `custom_components/mikrotik_router/manifest.json` | Bump version 2.3.16 → 2.3.17 |
| `README.md`, `info.md` | v2.3.17 release notes |
| `docs/decisions/ADR-011-capsman-attributes.md` (new) | Decision record: additive `capsman-interface`, no source flip, no merge-order change. Documents the @fuecy endpoint-mismatch finding and the deferred ENH for endpoint fallback. |
| `docs/decisions/README.md` | ADR-011 added to index. |
| `docs/data-schema.md` | New `capsman-interface` field documented on the host composite. |
| `docs/ISSUES.md` | #68 status updated; new ENH-260523-capsman-endpoint-fallback entry. |
| `tests/test_coordinator.py` | Extended `test_capsman_hosts_v6` to cover the full v6 payload and the rx-signal → signal-strength rename. Rewrote `test_merge_capsman_hosts_returns_detected` to assert `capsman-interface` is written on the claim path. Replaced `test_merge_capsman_hosts_skips_existing_non_capsman` with the ADR-011 regression test `test_merge_capsman_hosts_overlay_on_dhcp_host` and added `test_merge_capsman_hosts_overlay_updates_availability_for_capsman_source`. |

### Why

Issue #68 (reporter @fuecy): `device_tracker.<mac>.attributes.interface` showed the bridge name, not the AP-virtual interface (`Slaapkamer`, `Zolder`, etc.) for CAPsMAN clients. Independent exploration confirmed (and disproved) the prior feasibility analysis: the bug is NOT merge ordering; it's that `_merge_capsman_hosts()` early-continued for any host already claimed by DHCP/ARP/bridge. Persistent DHCP leases mean DHCP almost always claims first, so the AP identity was never recorded for those hosts.

ADR-011 captures the design — additive attribute, no behavioural changes to `source` / `interface`, preserves automations that filter on them.

### @fuecy's specific case — fixed in this PR via dual-endpoint fallback

The first-pass of this work would have left @fuecy on RouterOS 7.21.4 unfixed because his version routes to `/interface/wifi/registration-table` which his router returns empty. Rather than ship a partial fix and defer ENH-260523-capsman-endpoint-fallback to v2.3.18, the fallback is folded into this PR: `get_capsman_hosts()` probes endpoints in preference order (v7.13+ → wifi → caps-man; v6/v7≤12 → caps-man only) and uses whichever returns data. ENH-260523 is now Closed.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint (E/F/W) | All checks passed (custom_components + tests) | ✅ |
| Ruff `C901` on custom_components | All checks passed — `_merge_capsman_hosts` and helpers all under complexity 15 | ✅ |
| Test syntax | `python -m py_compile tests/test_coordinator.py` passes | ✅ |
| Pytest | Requires Docker on Windows — CI gates it | ⏳ |
| Manual: live HACS install on a CAPsMAN router | Pending — @fuecy beta after merge | ⏳ |

### Follow-up (not in this PR)

- v7.13+ field schema discovery — the conservative 3-field shape on the wifi endpoint is intentionally minimal until a real payload is observed. We can extend the v7.13+ field list once a user with the new WiFi package shares a `/rest/interface/wifi/registration-table` response.
- No debug logging was added to this PR (originally planned), so no `dev` → `master` strip step is needed.

---

## CR-260522-claude-tooling-modernisation — Claude Code tooling baseline + mechanical quality gates via pyproject.toml

**Date:** 2026-05-22
**Branch:** `feature/claude-tooling-modernisation`
**Status:** In Review (targeting `dev`)

### What Changed

| Area | Change |
|------|--------|
| `pyproject.toml` (new) | Single-source-of-truth tool config. `[tool.ruff]` line-length=220, py313, exclude `librouteros_custom`. `[tool.ruff.lint]` select E/F/W/C90, ignore W293. `[tool.ruff.lint.mccabe]` `max-complexity = 15` — mechanical enforcement of ADR-007. `[tool.ruff.lint.per-file-ignores]` C901 disabled for tests. `[tool.pytest.ini_options]` integration marker (moved from setup.cfg). `[tool.coverage.run]` source = custom_components/mikrotik_router. `[tool.coverage.report]` `fail_under = 80` — mechanical enforcement of the 80% target. |
| `setup.cfg` (deleted) | All config moved to pyproject.toml. Stale `[flake8]` + `[pylint]` blocks (superseded by ruff in ADR-003) eliminated. |
| `Pipfile` (deleted) | Legacy artifact; no CI/tooling consumed it. |
| `AGENTS.md` (deleted, was untracked) | Near-duplicate of CLAUDE.md with stale "Codex Sonnet/Opus" branding from earlier toolchain. Removed per gedcom-tree-parser/PLAN.md L498 precedent. |
| `.claude/settings.json` (new, committed) | Team-shared permission allowlist (read-only Bash wildcards: ruff, pytest, pre-commit, bandit, git read-only ops, jq, manifest read) + hook declarations (PreToolUse, PostToolUse, UserPromptSubmit). Personal overrides remain in gitignored `settings.local.json`. |
| `.claude/hooks/pre-bash-force-push-guard.sh` (new) | PreToolUse Bash hook. Blocks `git push --force` targeting master/main with exit 2. Dev/feature branches pass through. |
| `.claude/hooks/post-edit-ruff.sh` (new) | PostToolUse Edit/Write/MultiEdit hook. Runs `ruff check --fix` on Python files immediately after edit. Non-blocking. Tight-feedback-loop pattern per Ultimate Claude Code Guide §9.5. |
| `.claude/hooks/user-prompt-smart-suggest.sh` (new) | UserPromptSubmit hook. Detects "create PR" intent and surfaces the pre-PR checklist as an inline reminder unless the prompt already references it. Non-blocking. |
| `.claude/commands/pre-pr-check.md` (new) | Slash command running the full pre-PR sequence: ruff lint+format, pytest with coverage, doc-update checks (CHANGE-REGISTER entry, ISSUES.md updates, ADR if applicable), version-triplet check, PR-target sanity. |
| `.claude/commands/release-bump.md` (new) | Atomic version bump across manifest.json + README.md + info.md + CHANGE-REGISTER.md staged entry. Mechanises the three-file lockstep that CR-260417 / CR-260507 / CR-260509 repeatedly tripped on. |
| `.claude/agents/coordinator-reviewer.md` (new) | Specialised review agent (Sonnet) for `coordinator.py` changes. Checks ADR-007 helper-extraction, ADR-009 attribute filtering, lock discipline (ISS-260509), HA async patterns, UID stability, coverage. |
| `.claude/skills/claude-md-sizing/SKILL.md` (new) | Audit skill encoding the Ultimate Guide's "120 lines hard limit + pointer strategy" rule. CLAUDE.md is currently 48 lines (safe) but will drift as the repo grows. |
| `docs/decisions/ADR-010-claude-tooling-baseline.md` (new) | Decision record covering all of the above. Index updated in `docs/decisions/README.md`. |
| `docs/ISSUES.md` | New: ISS-260522-ruff-format-drift (discovered during T2.1 verification — see below). |
| `.github/workflows/ci.yml` | Pin `ruff==0.9.0` to match `.pre-commit-config.yaml` rev. Added in response to code-review finding: the new C901 complexity gate would otherwise sit on top of unpinned-ruff drift between CI and pre-commit. |

### Why

Quality bars (SonarCloud Grade A, complexity ≤15, ≥80% coverage, zero ruff errors) were documented in CLAUDE.md but enforced *socially* — by reviewer attention. ISS-260512-ci-manifest-drift exposed that "documentation as enforcement" is fragile: the v2.3.14 hotfix shipped untested against the version it was hotfixing because two sources of truth diverged.

This PR converts the documented bars into mechanical gates (pyproject.toml C901 + coverage fail_under), removes three drift surfaces (AGENTS.md duplicate, Pipfile, stale setup.cfg config blocks), and adds Claude-Code-level guardrails (`.claude/` scaffolding per Ultimate Claude Code Guide best practices). The "drift" framing here comes from the user's own audit work (`jnctech/config` audit findings, paraphrased in the sibling `gedcom-tree-parser` project's PLAN.md "Agent discipline" section) — the Ultimate Guide supplied the `.claude/` shape, not the drift philosophy.

### New finding (resolved in-PR)

**ISS-260522-ruff-format-drift** — During T2.1 verification, ruff 0.11.4 reported 26 files in `custom_components/mikrotik_router` + `tests/` needing reformatting. Pre-commit's pinned ruff v0.9.0 *also* wants to reformat them.

**Original hypothesis (incorrect):** the pre-commit `ruff-format` hook was not running on recent commits, so drift accumulated silently.

**Actual cause (discovered when applying the fix):** the drift is the direct consequence of *this PR's* new `pyproject.toml` setting `line-length = 220`. The previous codebase was formatted against ruff's undeclared default (line-length=88), so the wider line-length flags 26 files as "would reformat" — they were never drifted against any prior config. CI on `dev` is format-clean and has been throughout.

**Fix (bundled into this PR):** ran `ruff format` once over `custom_components/` and `tests/`; the reformat is the necessary companion to the line-length config change in the same PR. Style-only; `ruff check` still passes on all 26 files. ISS-260522 closed.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint (`E,F,W,C90`) | All checks passed (custom_components + tests) | ✅ |
| Ruff `C901` on custom_components | All checks passed — zero functions exceed complexity 15 | ✅ — validates ADR-007 retroactively |
| Ruff format | 26 files reformatted in-PR (consequence of new `line-length=220`); 39 files clean afterward | ✅ |
| Pytest | pending — requires Docker test container | ⏳ |
| Pre-commit | ruff hook passed; ruff-format hook auto-modified files (see ISS-260522) | ⏳ partial |

### Code-review fixes (applied in this PR before merge)

Both review agents (pr-review-toolkit:code-reviewer + independent high-effort sub-agent) ran on the draft and surfaced findings consolidated and addressed in-PR:

- **BLOCKER:** `$ARGUMENTS_0` is not valid Claude Code slash-command syntax (release-bump.md, claude-md-sizing/SKILL.md) → changed to `$1`.
- **NEEDS-CHANGE:** All three hooks would fail closed if `jq` is missing → added `command -v jq >/dev/null 2>&1 || exit 0` guard before any jq invocation. Force-push guard now fails *open* (lets command through) when jq missing rather than blocking every Bash call.
- **NEEDS-CHANGE:** `.claude/settings.json` allowlist included destructive git verbs (`checkout:*`, `restore:*`, `switch:*`) which can silently discard uncommitted work → removed, replaced with narrower read-only patterns (`rev-parse`, `ls-files`, `check-ignore`, `branch --show-current`, `branch -a`).
- **NEEDS-CHANGE:** CI ruff was unpinned; C901 gate would sit on top of version drift → pinned `ruff==0.9.0` in `.github/workflows/ci.yml` matching pre-commit `rev:`.
- **NIT:** PR-intent regex matched `pr` as a substring (false positives on "project", "presentation") → added `\bpr\b` word boundary.
- **NIT:** ADR-010 cited specific line numbers in a sibling repo (`gedcom-tree-parser/PLAN.md L498/L508-511`) which would drift → replaced with paraphrased quotes that survive the source file evolving.
- **NIT:** `docs/ISSUES.md` Current Priorities had duplicate `1.` numbering → renumbered.
- **DOCUMENTED:** Force-push guard limitation (bare `git push --force` with no ref while on master) added to hook header comment.
- **DOCUMENTED:** `.gitignore` re-include pattern got an inline comment explaining how to share new `.claude/<dir>/` subdirectories.

### Follow-up (not in this PR)

- (Optional) Run `pre-commit install` locally so the `ruff-format` hook fires on every commit going forward — the post-edit Claude hook already runs `ruff format`, but pre-commit catches non-Claude edits too.
- Consider Claudeception / Claude Reflect System if PR throughput grows.
- Consider expanding ruff selected rules (currently E/F/W/C90) to include I (isort), B (bugbear), UP (pyupgrade) — needs validation that current code passes.

---

## CR-260512-ci-manifest-drift-guard — CI installs runtime deps from manifest; add drift + zip-structure guards

**Date:** 2026-05-12
**Branch:** `fix/ci-manifest-drift-guard`
**Status:** In Review (targeting `dev`)

### What Changed

| Area | Change |
|------|--------|
| `.github/workflows/ci.yml` (tests job) | Replace bare `pip install mac-vendor-lookup librouteros` with `pip install -r /tmp/runtime-requirements.txt` generated from `manifest.json`. CI now installs exactly what HA installs. |
| `.github/workflows/ci.yml` | New job `manifest-drift` asserts runtime entries in `requirements.txt`, `requirements_dev.txt`, and `requirements_tests.txt` match `manifest.json` exactly. Fails the PR if they diverge. |
| `.github/workflows/ci.yml` | New job `zip-structure` builds the release zip with the same `cd custom_components/mikrotik_router && zip -r ../../...` command used by `release.yml`, then asserts `manifest.json` is at the zip root (no nested `mikrotik_router/` directory). |
| `requirements.txt`, `requirements_dev.txt`, `requirements_tests.txt` | Pin `librouteros>=3.4.1,<4.0` to match the manifest cap introduced in v2.3.14. |

### Why

External audit (Codex, 2026-05-12) found that CI was installing `librouteros` unpinned, resolving to `4.0.1`, while `manifest.json` correctly pinned `<4.0` since the v2.3.14 hotfix. The shipped-vs-tested dependency boundary diverged: the integration was shipping on `<4.0` but every CI run since the hotfix had been testing against 4.x. The hotfix itself was effectively shipped untested against the version it was hotfixing.

The drift guard ensures this class of failure cannot silently regress: any change to `manifest.json` requirements without a matching update to all three `requirements*.txt` files now fails CI. The zip-structure guard closes a separate latent risk: HACS root-flat packaging bugs are easy to reintroduce, and `release.yml` had no artefact-shape verification.

### Why this surfaced now

The `<4.0` cap was added in commit b6ad8e0 (v2.3.14, 4 weeks ago) to work around the librouteros 4.0.0/4.0.1 `connect()` kwarg break. The three `requirements*.txt` files were not updated at the same time, and `ci.yml` was using bare unpinned installs predating the cap. The audit identified the inconsistency by reading all four files together.

### Test Plan

- [ ] CI `tests` job log shows `librouteros>=3.4.1,<4.0` in `cat /tmp/runtime-requirements.txt`
- [ ] `manifest-drift` job passes on this PR
- [ ] `zip-structure` job lists `manifest.json` near the top of the zip and reports `OK`
- [ ] Full pytest suite still passes on Python 3.13 and 3.14

### Follow-up (not in this PR)

- ADR documenting the librouteros API concurrency model — see `ISS-260512-librouteros-concurrency-adr`
- Explicit librouteros version test matrix (`3.4.1`, latest `3.x`, expected-fail `4.x`) before relaxing the `<4.0` cap — see `ENH-260512-librouteros-test-matrix`
- Cleanup PR: delete `Pipfile`, strip flake8/pylint from `setup.cfg`, move ruff config to `pyproject.toml`

---

## CR-260509-fix-api-concurrency-lock — v2.3.16: hold API lock around set_value/execute response iteration

**Date:** 2026-05-09
**Branch:** `fix/api-concurrency-lock`
**Status:** In Review (targeting master)

### What Changed

| Area | Change |
|------|--------|
| `mikrotikapi.py` | `set_value()` and `execute()` now wrap `_find_entry()` and the subsequent `response.update()` / `response(command, **params)` call inside the existing `with self.lock:` block. Previously the iteration ran outside the lock and could interleave with concurrent coordinator polls reading from the same TCP socket. |
| `manifest.json` | Bump version 2.3.15 → 2.3.16 |
| `tests/test_mikrotikapi.py` | 2 new regression tests verifying `_find_entry` runs while the API lock is held in both `set_value` and `execute` |
| `README.md`, `info.md` | v2.3.16 release notes; note HA 2026.5.0 / Python 3.14 not yet validated |
| `docs/ISSUES.md` | Open ISS-260509-mikrotikapi-concurrency (the bug fix) |
| `docs/ISSUES.md` | Open ISS-260509-ha-2026.5-untested (compatibility tracking) |

### Why

Reported in #64: rapidly toggling PoE switches on a `RB5009UPr+S+IN` running HA 2026.5.0 caused librouteros' `parse_word` to raise `ValueError: not enough values to unpack` mid-iteration, followed by `Mikrotik Disconnected`. Root cause is a pre-existing race in `set_value`/`execute`: both methods iterated the librouteros `Path` object — which performs further socket reads — outside the API lock. A concurrent coordinator poll could then read from the same socket and the parser saw a half-finished sentence. `run_script()` already followed the correct pattern.

### Why this surfaced now

The race has existed for many releases but was rarely triggered on Python 3.13. HA 2026.5.0 shipped with Python 3.14, which retuned thread scheduling and GIL release granularity. Races that were rare on 3.13 are now easy to hit on 3.14 — particularly under workloads that issue rapid switch toggles.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | pending | ⏳ (CI) |
| Ruff format | pending | ⏳ (CI) |
| Tests | 2 new regression tests, full suite via CI | ⏳ (CI) |

---

## CR-260507-hotfix-ups-poe-current — v2.3.15 hotfix: empty UPS path + PoE current unit

**Date:** 2026-05-07
**Branch:** `fix/v2.3.15-ups-poe-current`
**Status:** In Review (targeting master)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | `get_ups()` short-circuits when `/system/ups` returns no entries — clears `ds["ups"]` and skips the `monitor` query that would otherwise fail with "no such item" and disconnect the integration |
| `sensor_types.py` | `poe_out_current` native unit changed from `AMPERE` to `MILLIAMPERE` (matches the raw API value); `suggested_unit_of_measurement` removed |
| `manifest.json` | Bump version 2.3.14 → 2.3.15 |
| `tests/test_coordinator.py` | 2 new tests: `get_ups` no-config skip path, `get_ups` runs monitor when UPS present |
| `tests/test_sensor.py` | 1 new test: `poe_out_current` description uses `MILLIAMPERE` |
| `README.md`, `info.md` | v2.3.15 release notes |
| `docs/ISSUES.md` | Open ISS-260507-ups-empty-path, ISS-260507-poe-current-unit (both closed in this PR) |

### Why

Two bugs reported against v2.3.14:

- **#61 (ISS-260507-ups-empty-path):** `get_ups()` always issued the `/system/ups monitor` query because the `enabled` field defaulted to `True` when no UPS entries existed (the `reverse=True` flag inverted the missing-source default). RouterOS rejected the monitor with "no such item", and `_query_command` treated that as a connection failure → "Mikrotik Disconnected" for the whole integration. The router worked fine; it just didn't have a UPS.
- **#60 (ISS-260507-poe-current-unit):** `native_unit_of_measurement` was set to `AMPERE` while the API returns the value already in mA. HA's unit-conversion path then displayed the raw mA value as if it were amps converted to mA, giving values 1000× too large (e.g. `1234.56 mA` for a 25 mA load on a `RB5009UPr+S+IN`).

Both are minimal, low-risk fixes that don't touch shared paths. Bundled into a single hotfix to ship them together.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ (CI-verified) |
| Ruff format | 0 reformats needed | ✅ (CI-verified) |
| Tests | 3 new, full suite green via CI | ✅ |

---

## CR-260417-hotfix-librouteros-4x-pin — v2.3.14 hotfix: pin librouteros<4.0

**Date:** 2026-04-17
**Branch:** `fix/librouteros-4x-pin`
**Status:** Released (master, v2.3.14)

### What Changed

| Area | Change |
|------|--------|
| `manifest.json` | Pin `librouteros>=3.4.1,<4.0`; bump version to 2.3.14 |
| `README.md` | Add v2.3.14 section explaining the pin |
| `info.md` | Add v2.3.14 entry |
| `docs/ISSUES.md` | Add ISS-260417-librouteros-4x-break |

### Why

librouteros 4.0.1 (released before 2026-04-10) renamed the `connect()` kwarg `login_methods` → `login_method`. Every new or upgrading install of v2.3.13 pulls 4.0.1 (no upper bound in manifest) and fails on first connection attempt with `connect() got an unexpected keyword argument 'login_methods'`. Reported in #55 (2026-04-10) and #56 (2026-04-13).

The pin is a minimum-risk stopgap: it restores the prior working state for all users by blocking 4.x until proper migration lands. No code changes in the integration itself, so behaviour is identical to v2.3.13 for users already on librouteros 3.x.

### Follow-up

Open a new ISS to migrate to librouteros 4.x: rename `login_methods` → `login_method` in `mikrotikapi.py:102`, audit other 4.0.1 breaking changes, then drop the upper pin.

### Quality Gate Results

Docs/config-only change; no code touched. No tests added.

---

## CR-260327-v240-issues — v2.4.0 feature completion (3 issues + SonarCloud)

**Date:** 2026-03-27
**Branch:** `feature/v240-issues`
**Status:** In Review (targeting dev)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | **New device discovery:** `_has_new_uids()` tracks UIDs per data path; dispatcher re-enabled with guard — only fires when new UIDs appear. `_known_uids` dict added to coordinator init. |
| `entity.py` | **Entity guard fix:** `_check_entity_exists()` now skips entities already in `platform.entities` before attempting `async_add_entities`, preventing duplicate registration errors. |
| `coordinator.py` | **Wireless detection:** `async_process_host()` sets `is_wireless` bool on each host using `_is_wireless_host()`. Added to `_HOST_DEFAULTS`. |
| `device_tracker.py` | **Wireless detection:** Replaced 3 `source in ["capsman", "wireless"]` checks with `is_wireless` field — fixes hAP ac2 bridge-discovered wireless clients showing wired behaviour. |
| `coordinator.py` | **Firewall refactor:** Extracted `_get_firewall_rules()` helper, `_ENABLED_VAL` and `_SKIP_DYNAMIC_JUMP` constants. get_nat/mangle/filter/raw now delegate to shared method. |
| `coordinator.py` | **SonarCloud:** Extracted `_PPP_NOT_CONNECTED` constant (S1192 "not connected" duplication). |
| `tests/` | 8 new tests: `_has_new_uids` (6), `async_process_host_sets_is_wireless` (1), bridge wireless tracker behaviour (1). 573 total passing. |
| `docs/ISSUES.md` | Closed ISS-260320-new-device-discovery, ISS-260320-refactor-dedup, ISS-260326-tracker-wireless-detection |

### Why

Three backlog issues required for v2.4.0 release:
- ISS-260320-new-device-discovery: New network devices required HA restart to appear. Dispatcher was disabled in v2.3.8 due to log spam.
- ISS-260326-tracker-wireless-detection: hAP ac2 wireless clients discovered via bridge table were treated as wired (wrong icon, wrong connection logic).
- ISS-260320-refactor-dedup: Firewall rule methods shared ~30 LOC of boilerplate (parse_api + dedup call).

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 573 passed, 5 skipped | ✅ |

---

## CR-260327-phase5-tests — Phase 5 integration tests and coverage gap closure

**Date:** 2026-03-27
**Branch:** `feature/phase5-integration-tests`
**Status:** In Review (targeting dev)

### What Changed

| Area | Change |
|------|--------|
| `tests/test_init.py` | Rewrote with 44 tests (was 4): async_setup_entry, async_unload_entry, async_reload_entry lifecycle; service handlers (cleanup_entities, cleanup_stale_hosts) with orphan removal, dry run, error paths; all helper functions (_build_valid_unique_ids, _collect_ids_for_desc, _get_mikrotik_data, _find_host_by_mac_slug, _classify_host_entity); _collect_all_descriptions platform coverage; diagnostics |
| `docs/ISSUES.md` | Closed ISS-260320-test-coverage (86% achieved); updated priorities |
| `docs/CHANGE-REGISTER.md` | Added CR-260327-phase5-tests |

### Why

ISS-260320-test-coverage Phase 5: `__init__.py` was at 96% coverage with only 4 migration/device-removal tests. The lifecycle functions (setup, unload, reload), service handlers, and helper functions were completely untested. Phase 5 brings `__init__.py` to 100% and `diagnostics.py` from 0% to 100%. Total project coverage: 86% (565 tests).

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | pending | ⏳ |
| Ruff format | pending | ⏳ |
| Tests | 565 passed, 5 skipped | ✅ |
| Coverage | 86% | ✅ (target ≥80%) |

---

## CR-260327-legacy-cleanup — SonarCloud remediation, complexity reduction, modernisation

**Date:** 2026-03-27
**Branch:** `refactor/legacy-cleanup`
**Status:** In Review (targeting dev)

### What Changed

| Area | Change |
|------|--------|
| `apiparser.py` | **Bug fix:** `from_entry_bool` now applies `reverse` to default when field absent — fixes DHCP leases/servers incorrectly showing disabled |
| `apiparser.py` | Removed identity type coercions (`str(str)`, `int(int)`) in `from_entry()` |
| `apiparser.py` | Extracted 8 helpers to reduce complexity: `_fill_val_str`, `_fill_val_bool`, `_convert_timestamp`, `_resolve_str_default`, `_process_source_entry`, `_get_uid_from_keys`, `_process_val_sub`, `_apply_combine` |
| `mikrotikapi.py` | Extracted `_query_list`, `_query_command` from `query()` (18→≤15 complexity) |
| `mikrotikapi.py` | Extracted `_find_entry` dedup helper, used by `set_value`, `execute`, `run_script` |
| `mikrotikapi.py` | **Bug fix:** `set_value`/`execute`/`run_script` now return `False` (not `True`) when entry not found |
| `mikrotikapi.py` | Added type hints to all public methods, extracted `_ensure_ssl_wrapper`, removed banner comments |
| `coordinator.py` | Extracted 15+ helpers for complexity reduction: `_detect_capabilities_v6/v7`, `_has_wifi_package`, `_async_update_client_traffic`, `_calculate_interface_traffic`, `_process_interface_metadata`, `_process_bonding`, `_arp_matches_interface`, `_match_arp_clients`, `_fallback_client_ip`, `_normalize_dhcp_lease`, `_resolve_dhcp_interface`, `_count_leases_per_server`, `_parse_queue_values`, `_parse_queue_pair` |
| `coordinator.py` | Tracker: extracted `_ensure_host_defaults`, `_first_run_availability`, `_should_ping_host`, `_ping_host` |
| `coordinator.py` | Fixed f-string in logging (S3457), removed unnecessary `list()` |
| `coordinator.py` | Queue parsing now catches `ValueError`/`IndexError` per entry |
| `coordinator.py` | Firmware version parse failure logged as warning with consequence message |
| `coordinator.py` | Fixed `default: True` + `reverse: True` in filter/raw rules (was relying on buggy from_entry_bool) |
| `switch.py` | **Silent failure fix:** `_require_write_access()` raises `HomeAssistantError` instead of silent return |
| `switch.py` | **Silent failure fix:** NAT/Mangle/Filter/Raw/Queue switches log error when rule not found (value=None) |
| `switch.py` | `MikrotikPortSwitch` uses `.get()` for `about` and `port-mac-address` |
| `switch.py` | Extracted `_CAPSMAN_MANAGED`, `_RULE_NOT_FOUND_ENABLE/DISABLE` constants |
| `entity.py` | `_handle_coordinator_update` guards against `KeyError` when entity UID disappears |
| `sensor_types.py` | Extracted 5 icon constants (S1192) |
| `config_flow.py` | Set comprehension (S7494) |
| `__init__.py` | Extracted `_collect_ids_for_desc` helper, prefixed unused params, NOSONAR on intentional `list()` |
| `tests/` | 41 new tests (apiparser helpers, mikrotikapi _find_entry/return-false, from_entry_bool reverse regression) |

### Why

SonarCloud v2.3.13 report: 29 code smells (13 CRITICAL complexity, 6 string duplication, 4 MAJOR, 8 MINOR). All pre-existing upstream patterns. Also fixes tracked issues: ISS-260321-cognitive-complexity (13 functions), ISS-260321-silent-failures (8 items), from_entry_bool reverse quirk.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 525 passed, 5 skipped | ✅ |

---

## CR-260326-wireless-client-count — Fix wireless client detection via bridge table

**Date:** 2026-03-26
**Branch:** `fix/wireless-client-count`
**Status:** Merged to dev (v2.3.13-beta.1)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | New `_is_wireless_host()` method: detects wireless clients via source, direct interface match, or bridge host table lookup |
| `coordinator.py` | `async_process_host` uses `_is_wireless_host()` instead of inline source check for client counting |
| `tests/test_coordinator.py` | 8 new tests: source wireless/capsman, direct interface, bridge lookup, wired, no wireless interfaces, hAP ac2 integration scenario |

### Why

On routers with empty WiFi registration tables (e.g. hAP ac2 with new WiFi package), all clients were counted as wired because the old check only looked at `source in ["capsman", "wireless"]`. ARP-discovered clients on wireless interfaces were missed. The new method checks the bridge host table to correctly identify wireless clients.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 484 passed, 5 skipped | ✅ |

---

## CR-260326-dhcp-server-sensors — DHCP server status and lease count sensors

**Date:** 2026-03-26
**Branch:** `feature/dhcp-server-sensors`
**Status:** Merged to dev (v2.3.13-beta.1)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Extended `get_dhcp_server()` with address-pool, enabled (from reversed `disabled`), comment, status, lease-count fields |
| `coordinator.py` | Added lease counting loop in `get_dhcp()` — tallies active leases per DHCP server |
| `coordinator.py` | Added `get_dhcp_server` to update loop before `get_dhcp` (correct order for lease counting) |
| `sensor_types.py` | New `DEVICE_ATTRIBUTES_DHCP_SERVER` attribute list |
| `sensor_types.py` | Two new sensor entity descriptions: `dhcp_server_status`, `dhcp_server_lease_count` |
| `tests/test_coordinator.py` | 7 new tests: enriched fields, defaults, status running/disabled, lease count, unknown server ignored |

### Why

DHCP server monitoring was limited to internal use (interface lookup for DHCP leases). Users want to see per-server status and lease counts for network utilization monitoring and pool exhaustion detection. Implements gap analysis item A5.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 483 passed, 5 skipped | ✅ |

---

## CR-260326-fix-slow-load — Eliminate startup bottlenecks that block HA loading

**Date:** 2026-03-26
**Branch:** `claude/fix-homeassistant-slow-load-EzXf3`
**Status:** Released (v2.3.12)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | First-run host tracking uses ARP table instead of sequential pings — eliminates O(n) blocking startup delay |
| `coordinator.py` | MAC vendor lookups parallelised via `asyncio.gather` + `_resolve_manufacturer` helper |
| `coordinator.py` | `_async_update_hwinfo` returns `bool` to skip duplicate `get_system_resource` call on hwinfo cycles |
| `coordinator.py` | `_async_run_if_connected` → `_run_if_enabled` with `requires` kwarg, reducing boilerplate |
| `coordinator.py` | All `datetime.now()` replaced with HA's `dt_now()` (timezone-aware); `last_hwinfo_update` initialised with `tzinfo=timezone.utc` |
| `coordinator.py` | Fixed chained comparison bug: `elif 0 < self.major_fw_version >= 7` → `elif self.major_fw_version >= 7` |
| `coordinator.py` | `get_system_resource` now uses `_run_if_enabled` guard (caught by silent-failure audit) |
| `apiparser.py` | Fixed `voluptuous.Optional(str)` misused as type hint → `str \| None` (PEP 604) |
| `__init__.py` | New `cleanup_entities` service: removes orphaned entities with no backing router data |
| `__init__.py` | New `cleanup_stale_hosts` service: reports/removes stale device tracker entities (dry_run default) |
| `__init__.py` | Services registered in `async_setup_entry` (not `async_setup` which is skipped for config-flow integrations) |
| `services.yaml` | Service descriptions for cleanup_entities and cleanup_stale_hosts |
| `strings.json`, `translations/en.json` | Service translation strings |
| `*.py` (6 files) | Added `from __future__ import annotations` per HA coding standards |
| `tests/` | 4 new `_resolve_manufacturer` tests (error, concurrent failure, parallel success, unknown MAC skip); `AsyncMock` for mac_lookup |

### Why

ISS-260326-slow-load: The integration was blocking HA startup by sequentially pinging every tracked host on first load. With many hosts, this added 10+ seconds to HA boot time. ARP-based first-run detection provides immediate availability data, with pings starting on the next 10s tracker cycle.

ISS-260320-deprecated-datetime: All remaining naive `datetime.now()` calls replaced with timezone-aware equivalents per HA coding standards.

Entity cleanup services address long-standing user pain point: orphaned entities from removed interfaces, deleted firewall rules, or stale DHCP hosts that accumulate over time and require manual registry editing to remove.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 465 passed, 5 skipped | ✅ |
| Code review | No bugs found | ✅ |
| Silent-failure audit | 2 fixes applied (resource guard, ARP logging) | ✅ |
| HA live test | Services working, zero errors in logs | ✅ |

---

## CR-260325-attribute-cleanup — Remove junk attributes from interface and tracker entities

**Date:** 2026-03-25
**Branch:** `feature/attribute-cleanup`
**Status:** Released (v2.3.11)

### What Changed

| Area | Change |
|------|--------|
| `entity.py` | `MikrotikInterfaceEntityMixin` now uses exclusive SFP/copper attribute selection based on `sfp-shutdown-temperature` value (not key existence); adds `client-ip/mac` and `poe-out` conditionally; `copy_attrs` gains `skip_junk` parameter to filter "unknown"/"none"/"N/A"/None values |
| `switch.py` | `MikrotikPortSwitch` now inherits `MikrotikInterfaceEntityMixin` instead of duplicating attribute logic (-41 lines) |
| `iface_attributes.py` | Moved `client-ip-address`/`client-mac-address` to new `DEVICE_ATTRIBUTES_IFACE_CLIENT` list; removed `poe-out` from `DEVICE_ATTRIBUTES_IFACE_ETHER` |
| `switch_types.py` | Eliminated 4 duplicated attribute lists — now imports from `iface_attributes.py` (-66 lines) |
| `device_tracker.py` | Wireless attrs (`signal-strength`, `tx-ccq`, `tx/rx-rate`) only added for wireless/capsman hosts |
| `device_tracker_types.py` | Split `DEVICE_ATTRIBUTES_HOST_WIRELESS` from `DEVICE_ATTRIBUTES_HOST` |
| `tests/` | 10 new tests (SFP/copper exclusivity, skip_junk, poe-out conditional, client filtering, wireless tracker attrs); 472 total |

### Why

Entity attributes were polluted with ~1,300 meaningless defaults across 3 tested devices (rb4011, hapax3, hapac2/csr310). Root cause: `parse_api` adds all declared fields with defaults, then `copy_attrs` unconditionally includes them. Key examples:
- 16 SFP attributes (all "unknown") on every copper ethernet port
- `poe_out: "N/A"` on every non-PoE port
- `client_ip_address: "unknown"` on loopback, vlan, pppoe, wireguard, bonding interfaces
- `signal_strength`, `tx_ccq` on wired device tracker hosts

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 472 passed, 5 skipped | ✅ |

---

## CR-260325-mangle-interface-dedup — Include interface fields in mangle rule unique ID

**Date:** 2026-03-25
**Branch:** `fix/mangle-duplicate-interface`
**PR:** #40 (targeting dev)
**Status:** In Review

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Added `in-interface` and `out-interface` to mangle `uniq-id` formula and API query fields |
| `switch_types.py` | Added `in-interface` and `out-interface` to `DEVICE_ATTRIBUTES_MANGLE` |
| `tests/` | New test: `test_mangle_interface_differentiates_rules` |

### Why

Mangle rules differing only by `in-interface`/`out-interface` (e.g. MSS clamping for inbound vs outbound PPPoE) generated identical unique IDs, causing the duplicate detection to silently remove both rules.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 472 passed, 5 skipped | ✅ |

---

## CR-260324-arp-incomplete-filtering — Treat ARP "incomplete" as unreachable

**Date:** 2026-03-24
**Branch:** `claude/fix-device-tracker-incomplete-nYKrC`
**Status:** Released (v2.3.10)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | `_merge_arp_hosts()` now excludes both `"failed"` and `"incomplete"` ARP statuses from the detected set via `_ARP_UNREACHABLE_STATUSES` frozenset |
| `tests/test_coordinator.py` | Updated existing tests and added new test for `"incomplete"` status |
| `docs/decisions/ADR-001` | Updated to cover `"incomplete"` status alongside `"failed"` |

### Why

Devices with ARP status `"incomplete"` (ARP request sent, no reply received) were incorrectly shown as "home" in the device tracker. Only `"failed"` was being filtered. Both statuses indicate the device is unreachable and should result in `not_home`.

---

## CR-260322-port-upstream-frs — Port upstream feature requests (#310, #321, #334, #298)

**Date:** 2026-03-22
**Branch:** `feature/port-upstream-frs`
**PR:** (targeting dev)
**Status:** In Review

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | New `get_raw()` method for `/ip/firewall/raw` with dedup logic; new `get_container()` method for `/container` with running status derivation; enriched `get_dhcp_client()` with gateway, dns-server, dhcp-server, expires-after, comment; new option properties and capability detection |
| `switch.py` | New `MikrotikRawSwitch` class (enable/disable via set_value); new `MikrotikContainerSwitch` class (start/stop via execute) |
| `switch_types.py` | `DEVICE_ATTRIBUTES_RAW`, `DEVICE_ATTRIBUTES_CONTAINER`, 2 new switch entity descriptions |
| `sensor_types.py` | `DEVICE_ATTRIBUTES_DHCP_CLIENT`, 2 new sensor entity descriptions (dhcp_client_status, dhcp_client_address) |
| `button.py` | `async_refresh()` after script execution for environment variable updates |
| `const.py` | New config constants: `CONF_SENSOR_RAW`, `CONF_SENSOR_CONTAINER` |
| `config_flow.py` | New option toggles for RAW and Container in sensor_select step |
| `strings.json` / `en.json` | Translations for new options |
| `tests/` | 20 new tests (coordinator, switch, button, sensor) — 461 total |
| `docs/decisions/` | ADR-008: Upstream Feature Port |

### Why

Four upstream feature requests implemented to keep the fork current while upstream is quiet:
- tomaae#334: Container monitoring and control (RouterOS 7.4+)
- tomaae#310: Firewall RAW rule enable/disable switches
- tomaae#321: DHCP client sensors for WAN monitoring
- tomaae#298: Environment refresh after script execution

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | pending | ⏳ |
| Ruff format | pending | ⏳ |
| Tests | 461 passed, 5 skipped | ✅ |

---

## CR-260321-phase4-integration-tests — Entity-level integration tests for all platform types

**Date:** 2026-03-21
**Branch:** `feature/phase4-integration-tests`
**PR:** #31 (targeting dev)
**Status:** Merged

### What Changed

| Area | Change |
|------|--------|
| `tests/conftest.py` | Added `make_mock_coordinator()`, `make_mock_entity_description()`, `patch_coordinator_entity_init()` shared helpers |
| `tests/test_init.py` | New: 4 tests for `async_migrate_entry` (v1→v2, noop, data preservation) and `async_remove_config_entry_device` |
| `tests/test_entity.py` | Extended: 15 new tests for `MikrotikEntity` class (init, custom_name, unique_id, device_info, extra_state_attributes, `_handle_coordinator_update`) |
| `tests/test_sensor.py` | New: 7 tests for `MikrotikSensor` (native_value, native_unit_of_measurement, ClientTrafficSensor.custom_name) |
| `tests/test_binary_sensor.py` | New: 10 tests for binary sensor is_on, icon branches, PPP disabled guard, PortBinarySensor 3-state icon |
| `tests/test_switch.py` | New: 19 tests for 5 switch classes — turn_on/off, write access guard, CAPsMAN guard, PoE side-effects, NAT/Queue UID lookup, Kidcontrol resume/pause |
| `tests/test_button.py` | New: 3 tests for Button no-op, ScriptButton run_script, ApiEntryNotFound handling |
| `tests/test_device_tracker.py` | New: 12 tests for is_connected (tracking disabled, wireless, capsman, ARP timeout), state, extra_state_attributes |
| `tests/test_update.py` | Extended: 8 new tests for RouterOS/RouterBOARD install (with/without backup), version properties |
| `docs/ISSUES.md` | Updated ISS-260320-test-coverage with Phase 4 completion |

### Why

ISS-260320-test-coverage Phase 4: entity-level tests cover all 6 platform entity types and the MikrotikEntity base class. Previous phases covered helpers and coordinator data methods but the actual entity behaviour (properties, actions, state) was untested. 80 new tests bring total to 441.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 441 passed, 5 skipped | ✅ |

---

## CR-260321-complexity-reduction — Cognitive complexity reduction across coordinator, entity, apiparser

**Date:** 2026-03-21
**Branch:** `feature/complexity-reduction`
**PR:** #30 (targeting dev)
**Status:** Merged

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Extracted 11 helpers from `async_process_host()` (136→~10 each): `_merge_capsman_hosts`, `_merge_wireless_hosts`, `_merge_dhcp_hosts`, `_merge_arp_hosts`, `_recover_hass_hosts`, `_ensure_host_defaults`, `_update_host_availability`, `_update_host_address`, `_resolve_hostname`, `_dhcp_comment_for_host`, `_update_captive_portal` |
| `coordinator.py` | Extracted `_async_update_hwinfo` and `_run_if_enabled` from `_async_update_data()` (65→~15), plus optional sensor loop tables |
| `coordinator.py` | Extracted `_init_accounting_hosts`, `_classify_accounting_traffic`, `_check_accounting_threshold`, `_apply_accounting_throughput` from `process_accounting()` (48→~10 each) |
| `coordinator.py` | Extracted `_monitor_ethernet_port` with SFP/copper/PoE monitor val constants from `get_interface()` (27→~10) |
| `entity.py` | Split `_skip_sensor()` into `_skip_interface_traffic`, `_skip_binary_sensor`, `_skip_device_tracker`, `_skip_poe_sensor` (23→~5 each) |
| `switch.py` | Replaced inline attribute loops with shared `copy_attrs` from entity.py (21→~5) |
| `apiparser.py` | Extracted `_traverse_entry` helper with `_NOT_FOUND` sentinel, case-insensitive bool matching via frozensets (18→~8) |
| `coordinator.py` | Further extracted `_hostname_from_dns`, `_hostname_from_dhcp`, `_add_traffic_bytes` to bring two remaining functions under threshold |
| `coordinator.py` | Silent-failure fixes: username guard in `get_access`, debug logging on MAC lookup, ValueError guard on `_address_part_of_local_network` |
| `coordinator.py` | Restored independent `connected()` check between `get_wireless`/`get_wireless_hosts`; guarded `_apply_accounting_throughput` against zero `time_diff` |
| `tests/` | 58 new tests covering all extracted helpers (361 total, up from 303) |
| `docs/decisions/` | ADR-007: Cognitive Complexity Reduction via Helper Extraction |
| `docs/ISSUES.md` | Added ISS-260321-silent-failures tracking remaining audit findings |

### Why

ISS-260321-cognitive-complexity: SonarCloud quality target is ≤15 cognitive complexity per function. Seven of the worst offenders (totalling 358 complexity points) are now refactored into focused helpers, each well under the threshold. Silent-failure audit (pr-review-toolkit) identified 12 issues; 3 critical/high fixed, 8 pre-existing tracked.

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 361 passed, 5 skipped | ✅ |

---

## CR-260320-tests-and-refactor — Test suite, devcontainer, CI/CD alignment, ruff migration

**Date:** 2026-03-20
**Branch:** `feature/tests-and-refactor`
**PR:** [#29](https://github.com/jnctech/homeassistant-mikrotik_router/pull/29)
**Status:** In Review (targeting dev)

### What Changed

| Area | Change |
|------|--------|
| `tests/` | 151+ tests across 7 files: apiparser (52), mikrotikapi (30), helper (13), coordinator (80), entity (30), update (8) |
| `.devcontainer/` | Python 3.13 devcontainer with pytest-homeassistant-custom-component, Ruff, Pylance |
| `.github/workflows/` | CI/CD aligned to gold standard: SHA-pinned actions, Ruff replaces Black+flake8, gitleaks, pip-audit, actionlint, dependency-review, scorecard added |
| `.github/dependabot.yml` | Dependabot configured for GitHub Actions and pip |
| `requirements_dev.txt` | New: all dev/test dependencies |
| `requirements_tests.txt` | Modernised from 2019-era pinned versions to match CI |
| `apiparser.py` | `type() == dict` → `isinstance(source, dict)` (E721) |
| `*.py` (14 files) | Ruff: remove 43 unused imports (F401), reformat 4 files |
| `docs/quality-gates.md` | Black/flake8 → Ruff references, local dev setup instructions |
| `docs/ISSUES.md` | Test coverage plan, refactor backlog, status updates |

### Why

1. Test coverage was ~11% — well below the 80% SonarCloud target
2. No local dev environment — tests could only run in CI
3. CI was using unpinned actions and legacy linters (Black+flake8)
4. Ruff migration tracked as ISS-260320-ruff-migration — now completed

### Quality Gate Results

| Metric | Value | Gate |
|--------|-------|------|
| Ruff lint | 0 errors | ✅ |
| Ruff format | 0 reformats needed | ✅ |
| Tests | 151+ (CI pending) | ⏳ |

### Post-Deploy Actions

- [ ] Open in devcontainer and verify `pytest tests/ -v` passes
- [ ] Confirm CI passes on dev branch
- [ ] Measure coverage and compare against 80% target

---

## CR-260320-dispatcher-spam — Disable update_sensors dispatcher to fix log spam

**Date:** 2026-03-20
**Branch:** `fix/disable-dispatcher-spam-v2`
**PR:** [#26](https://github.com/jnctech/homeassistant-mikrotik_router/pull/26)
**Status:** Merged (v2.3.8)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Disable `async_dispatcher_send("update_sensors")` that caused "does not generate unique IDs" log errors every 30s |

### Why

The dispatcher re-enabled in v2.3.6 for new device discovery caused thousands of log errors because `_check_entity_exists()` doesn't guard against re-adding existing entities. Proper fix tracked as ISS-260320-new-device-discovery.

---

## CR-260320-arp-failed-filter — ARP failed-status filtering for device tracking

**Date:** 2026-03-20
**Branch:** `fix/arp-failed-filter-v2`
**PR:** [#23](https://github.com/jnctech/homeassistant-mikrotik_router/pull/23)
**Status:** Merged (v2.3.7)

### What Changed

| Area | Change |
|------|--------|
| `coordinator.py` | Move ARP failed-status filtering from `get_arp()` to `async_process_host()` |

### Why

ARP entries with `status: failed` were causing devices to show as home when they were unreachable. Failed entries are now excluded from `arp_detected` but kept in `ds["arp"]` for bridge-interface lookups. Fixes [#17](https://github.com/jnctech/homeassistant-mikrotik_router/issues/17).

---

## CR-260320-ha-compliance-blocking-io — HA compliance: deadlocks, blocking I/O, options flow crash

**Date:** 2026-03-20
**Branch:** `fix/ha-compliance-blocking-io-deadlocks`
**PR:** [#19](https://github.com/jnctech/homeassistant-mikrotik_router/pull/19)
**Status:** Merged (v2.3.6)

### What Changed

| Area | Change |
|------|--------|
| `mikrotikapi.py` | Replace all manual `lock.acquire()`/`release()` with `with self.lock:` context managers — fixes critical deadlock in `run_script()` |
| `mikrotikapi.py` | Fix wrong `voluptuous.Optional` import → `list \| None`; fix return type `(bool, bool)` → `tuple[bool, bool]` |
| `config_flow.py` | Remove broken `__init__` from `OptionsFlowWithConfigEntry` subclass — fixes #470, #471 |
| `config_flow.py` | Wrap blocking `api.connect()` in `async_add_executor_job` |
| `switch.py` | Wrap all blocking `set_value`/`execute` calls in `async_add_executor_job` |
| `switch.py` | Remove dead sync `turn_on`/`turn_off` stubs |
| `button.py` | Wrap blocking `run_script` in `async_add_executor_job` |
| `update.py` | Wrap blocking `execute` calls in `async_add_executor_job` (RouterOS + RouterBOARD) |
| `entity.py` | Replace deprecated `default_name`/`default_manufacturer`/`default_model` with `name`/`manufacturer`/`model` |
| `strings.json` | Add missing `sensor_poe` translation entry |
| `CLAUDE.md` | New project CLAUDE.md with quality targets and linked standards |
| `docs/` | New: `ha-coding-standards.md`, `quality-gates.md`, `architecture.md`, `ISSUES.md`, `CHANGE-REGISTER.md` |

### Why

Multiple HA best-practice violations discovered during HACS compliance audit:
1. Options flow crash reported by users on HA 2025.12+ (GitHub #470, #471)
2. Blocking network I/O on the event loop freezing HA UI
3. Critical deadlock bug in `run_script()` that permanently freezes the integration
4. Deprecated APIs that will be removed in future HA releases

### Post-Deploy Actions

- [x] Validate options flow opens without error on HA
- [x] Toggle a switch and verify no UI freeze
- [x] Run a script button and verify no deadlock
- [ ] Comment on upstream issues #470, #471
