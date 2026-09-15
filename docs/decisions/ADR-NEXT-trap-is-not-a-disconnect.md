# ADR-NEXT: A refused command (`!trap`) is not a lost connection

**Date:** 2026-09-15
**Status:** Proposed (contributor) — number to be assigned by the maintainer at merge.

## Context

`MikrotikAPI` catches a bare `Exception` around every call it makes and hands it to `disconnect()`.
Two unrelated events arrive through that one path:

- **A transport failure** — the socket died, the router went away, the read timed out. The session
  is gone and reconnecting is the only way forward.
- **A `!trap` reply** — the router received the command, understood it, and refused to run it. The
  session is untouched and the next command on it would work.

librouteros already distinguishes them: a `!trap` sentence becomes `TrapError` (or `MultiTrapError`
for several in one response), both under `ProtocolError`, while a dead socket raises `OSError` or
`ConnectionClosed`.

Treating a refusal as a disconnect is not a cosmetic error, because `_async_update_hwinfo()` ends
the poll with `_raise_disconnected()` whenever `api.connected()` is false. On the first poll after a
restart that raises `ConfigEntryNotReady`: the config entry never loads, **every** entity of the
integration stays `restored`/`unavailable` — device trackers included, so presence-based
automations lose their whole input — and the entry retries every 600 s forever. Nothing in the
message names the command responsible; `_query_command()` reports its location as `path`, so the log
reads `error while path : failure: …`.

This has now cost the integration two bugs of the same shape:

- **#61** — a router with nothing under `/system/ups` returned a trap and the integration reported
  `Mikrotik Disconnected`. Closed by gating the UPS fetch behind capability detection.
- **#144** — `get_lte_firmware()` (2.3.21) sends `/interface/lte firmware-upgrade` to an `lte1`
  interface with no modem behind it, RouterOS answers `failure: Firmware update is not supported on
  this device!`, and the entry stops loading. Observed on a hAP ac² and a hEX S, RouterOS 7.24.2.

The per-command gate that closed #61 was the right fix for that fetch and no fix at all for the
class. Any future command that some board refuses reopens it, and the cost is the whole
integration rather than the one sensor.

## Decision

Split the two cases where the exception is caught, in `mikrotikapi.py`, and route every `except`
that used to call `disconnect()` through one helper:

```python
def _handle_call_error(self, location: str, error: Exception) -> None:
    if isinstance(error, (TrapError, MultiTrapError)):
        ...  # log the refusal, keep the session
        return
    self.disconnect(location, error)
```

- A refusal leaves `_connected` alone and the call returns its ordinary empty value (`None` for a
  query, `False` for `execute` / `arp_ping` / `run_script`), which every caller already handles —
  `get_lte_firmware()`, for one, logs "returned no data" and clears its dataset slot.
- A refusal is logged at WARNING **once per distinct location and message**, at DEBUG thereafter, so
  a permanent refusal on a 4-hourly capability refresh does not fill the log.
- The location string now carries the command and the menu (`command firmware-upgrade on path
  /interface/lte`), so the log says which call was refused.
- Anything that is not a trap still disconnects, unchanged.

## Alternatives Considered

**Gate the LTE firmware probe on the interface being `running`.** Fixes #144 and nothing else; it
is the #61 remedy applied a second time, and the third command to be refused would repeat both.
Worth doing on its own merits — it avoids a call that cannot succeed — but not as the fix.

**Catch the trap inside `get_lte_firmware()`.** Same objection, one level higher, and it spreads the
same `try`/`except` into every fetch that might ever touch unsupported hardware.

**Treat `disconnect()` as advisory and let the next poll reconnect.** Larger change to the
connection lifecycle, and it leaves the first poll after a restart failing, which is exactly the
case that takes the entry down.

## Consequences

- A board that refuses a command keeps every entity it *can* serve, and the refusal is visible in
  the log instead of being cast as a connection problem.
- Capability gates stay worth adding, but they become an optimisation rather than the only thing
  standing between an unusual board and a dead integration.
- A trap that genuinely does mean the session is unusable — none is known — would now be retried
  each poll instead of forcing a reconnect.
- `TrapError` and `MultiTrapError` are imported from `librouteros.exceptions`, which is already a
  hard dependency of the integration; a librouteros 4.x migration (ADR-015, reserved) must keep the
  two names in view.
