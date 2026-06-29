# ADR-018 — Netwatch entity naming by `name`, with name→comment→static precedence

**Status:** Accepted — implemented on `feature/netwatch-naming` (CR-260615-netwatch-naming).
**Date:** 2026-06-15
**Supersedes/relates:** `ENH-260608-netwatch-naming` ([jnctech #70](https://github.com/jnctech/homeassistant-mikrotik_router/issues/70)). Realises the follow-up pre-authored in ADR-013 §Out-of-scope. Gold quality-scale *entity-naming*.
**Numbering note:** ADR-014 = entity-golden-tests, ADR-017 = poe-energy-accumulation (both on `dev`). **ADR-015 (librouteros salvage renumber) and ADR-016 (coordinator decomposition) are reserved** per `docs/ISSUES.md`. ADR-017 is highest on disk → this takes **018**.

## Context

[#70](https://github.com/jnctech/homeassistant-mikrotik_router/issues/70): a user with 50+ netwatch entries sees many entities show the same display name, because the integration names netwatch entities **comment-first** and the user shares one `comment` across entries while setting a distinct netwatch `name` per entry (ROS 7.22.3). They want the `name` shown.

Two distinct "roll-up" phenomena exist; only **A** is what #70 reports. Both verified live against a RouterOS 7.22 router in the planning session.

### A — display-name collapse (#70's root)
Distinct `host` values → distinct uids → distinct entities, but `custom_name` returns the shared `comment` (`entity.py:342-343`, fired because the netwatch descriptor set `data_name_comment=True`), so the entities *look* identical. **Live evidence:** a live netwatch entity reported `friendly_name = "<inst> Netwatch <comment>"` — i.e. the device name (`<inst> Netwatch`) + the shared comment. Root = comment-first naming.

### B — true entity collapse (NOT #70, deferred)
`get_netwatch` keys on `host` (`coordinator.py:1690`), which is **not unique**: two probes on the same host overwrite each other in `data[uid]` (`apiparser.py:143`, `_get_uid_from_keys` returns `entry["host"]`) → genuinely one HA entity. **Live evidence:** a live router had two netwatch entries (`.id` `*1`/`*2`) on the same `host`, surfacing as a single HA entity. Naming cannot fix this. `key_secondary` is an absent-key fallback, not a composite (`apiparser.py:163-171`), so it can't separate them. Tracked as **ENH-260615-netwatch-host-key-collision** (re-keying needs a `unique_id` migration).

### has_entity_name interaction (decides "no suffix")
`_attr_has_entity_name = True` (`entity.py:284`); the netwatch device is named `f"{self._inst} {dev_group}"` = `<inst> Netwatch` (`entity.py:419`, else branch, `ha_group="Netwatch"`). HA renders `{device} {entity}`. Because the device group is itself "Netwatch", composing the entity name as `"{name} Netwatch"` would render `"<inst> Netwatch <name> Netwatch"` — "Netwatch" twice. So the entity name must be the **bare** `name` (unlike ADR-013's DHCP `"dhcp88 DHCP server"`, where the device is the board name and carries no "DHCP server" token).

### RouterOS `name` availability
Live: `:put [/tool netwatch get 0 name]` returns empty without error → `name` is a real property, `""` when unset. With `{"name":"name"}` in `vals`, `from_entry` returns `default=""` for absent/empty (`apiparser.py:39-43`), covering older ROS that lacks the property. No `ensure_vals` needed.

## Decision

For descriptors carrying a new `data_name_prefer: bool = False` flag, `custom_name` resolves the display name as **`data_name` (non-empty) → `comment` (non-empty) → static `entity_description.name`**, returning the value **bare** (no composition). Set `data_name_prefer=True` on netwatch only; drop its `data_name_comment=True`. Parse `name` in `get_netwatch`; add `name` to `DEVICE_ATTRIBUTES_NETWATCH`. Keep `data_uid`/`data_reference="host"` so `unique_id` is unchanged.

**Why a new flag, not a reorder:** the 5 firewall/container switches that carry `data_name_comment=True` (`switch_types.py:173/191/209/227/314`) require comment-first ordering; generalising the comment branch would rename them. A narrow opt-in flag avoids that.

**Why not `data_name_compose`:** with `data_reference="host" != data_name="name"`, the `entity.py:351` equality shortcut never fires, so `data_name_compose` is a no-op for netwatch.

**Final fallback is the static label, not the host** (maintainer decision): keeps scope tight to #70 and avoids surprise renames / poor IPv6/DNS display names for name-less+comment-less entries. Those stay as they are today.

## Consequences

**Non-breaking (verified):**
- `unique_id = f"{inst}-netwatch-{slugify(host)}"` (`entity.py:359-362`, keyed on `data_reference="host"`) is **invariant** under the `data_name` change → existing entity_ids and automations untouched; no registry or config-entry migration.
- Only the friendly name updates. Who sees a change: (a) entries with a `name` set → now show the name (the fix); (b) name-less but comment-set → unchanged (still the comment); (c) name-less + comment-less → unchanged (static "Netwatch").

**Known residuals (documented, not fixed here):**
- Two entries with the same `name` on different hosts collide on display name but stay distinct entities (host-derived `unique_id`). Symmetric to the shared-comment footgun; mitigated by setting distinct names.
- Names refresh on **reload, not live** — `_attr_name` is computed once in `__init__` (`entity.py:303`); `_handle_coordinator_update` refreshes only `self._data`. Pre-existing for all entities.
- Roll-up B (same-host collapse) → ENH-260615.

## Implementation (applied on `feature/netwatch-naming`)
1. `coordinator.py` `get_netwatch` (`:1685`): add `{"name": "name"}` to `vals`.
2. `binary_sensor_types.py`: add `data_name_prefer: bool = False` to `MikrotikBinarySensorEntityDescription`; add `"name"` to `DEVICE_ATTRIBUTES_NETWATCH`; netwatch descriptor `data_name="name"`, `data_name_prefer=True`, drop `data_name_comment`.
3. `entity.py`: the whitespace-stripped prefer check (`if value and value.strip()`) tipped the in-place `custom_name` to 16 cognitive complexity, so the uid-path naming was extracted into `_compose_uid_name` per ADR-007. `custom_name` is now a thin dispatcher (complexity 4); `_compose_uid_name` holds the prefer block (first branch, `getattr`-guarded) + the legacy comment/compose/static logic (complexity 12). The `MikrotikClientTrafficSensor.custom_name` override is unaffected (it never calls the helper).

## Testing (behaviour, real-typed per ENH-260608-test-suite-hardening)
- Netwatch precedence, parametrized from the **real `MikrotikBinarySensorEntityDescription`**: name beats a shared comment (positive assertion); name with comment-key absent; name empty → comment; name empty + comment empty/absent → static "Netwatch".
- `unique_id` host-derived and name-independent, incl. an IPv6 host; duplicate-name-across-hosts residual pinned (distinct unique_ids).
- Scope guards prove the prefer branch stays **off** for `data_name_comment` switches and `data_name_compose` dhcp sensors (the dhcp guard uses a row with both `name` and a `comment` so a leaked prefer branch would change the output).
- Coordinator: `name` parsed when present (siblings intact); `""` when absent or present-empty.
- Live QA via `validate-live-sensors` against a box with a netwatch `name` set before cutting the beta.

## Out of scope
- Per-host *devices* (the issue title says "device names"; the body asks for the name shown — delivered via entity naming under the shared device). Registry/migration change; not requested in the body.
- Roll-up B / `host`-key collision → ENH-260615.

## Provenance
All facts cite code `file:line` on `feature/netwatch-naming` (post `dev` merge of ADR-014/017) or live SSH/recorder queries against a RouterOS 7.22 router, 2026-06-15.
