"""API parser for JSON APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from logging import getLogger

from homeassistant.components.diagnostics import async_redact_data

from .const import TO_REDACT

_LOGGER = getLogger(__name__)


def utc_from_timestamp(timestamp: float) -> datetime:
    """Return a UTC time from a timestamp."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


_NOT_FOUND = object()


def _traverse_entry(entry, param):
    """Walk a '/' separated path through nested dicts. Returns _NOT_FOUND if not found."""
    if "/" in param:
        for part in param.split("/"):
            if isinstance(entry, dict) and part in entry:
                entry = entry[part]
            else:
                return _NOT_FOUND
        return entry

    if param in entry:
        return entry[param]

    return _NOT_FOUND


def from_entry(entry, param, default="") -> str:
    """Validate and return str value from an API dict."""
    ret = _traverse_entry(entry, param)
    if ret is _NOT_FOUND:
        return default

    if default != "" and isinstance(ret, float):
        ret = round(ret, 2)

    return ret[:255] if isinstance(ret, str) and len(ret) > 255 else ret


_TRUTHY_STRINGS = frozenset({"on", "yes", "up"})
_FALSY_STRINGS = frozenset({"off", "no", "down"})


def from_entry_bool(entry, param, default=False, reverse=False) -> bool:
    """Validate and return a bool value from an API dict."""
    ret = _traverse_entry(entry, param)
    if ret is _NOT_FOUND:
        return not default if reverse else default

    if isinstance(ret, str):
        lowered = ret.lower()
        if lowered in _TRUTHY_STRINGS:
            ret = True
        elif lowered in _FALSY_STRINGS:
            ret = False

    if not isinstance(ret, bool):
        ret = default

    return not ret if reverse else ret


def _set_data(data, uid, name, value):
    """Set a value in data dict, handling uid-keyed or flat dicts."""
    if uid:
        data[uid][name] = value
    else:
        data[name] = value


def _get_data(data, uid, name):
    """Get a value from data dict, handling uid-keyed or flat dicts."""
    return data[uid][name] if uid else data[name]


def parse_api(
    data=None,
    source=None,
    key=None,
    key_secondary=None,
    key_search=None,
    vals=None,
    val_proc=None,
    ensure_vals=None,
    only=None,
    skip=None,
) -> dict:
    """Get data from API."""
    if isinstance(source, dict):
        source = [source]

    if not source:
        if not key and not key_search:
            data = fill_defaults(data, vals)
        return data

    debug = _LOGGER.getEffectiveLevel() == 10
    if debug:
        _LOGGER.debug("Processing source %s", async_redact_data(source, TO_REDACT))

    keymap = generate_keymap(data, key_search)
    for entry in source:
        uid = _process_source_entry(data, entry, key, key_secondary, key_search, keymap, only, skip, debug)
        if uid is _NOT_FOUND:
            continue

        if vals:
            fill_vals(data, entry, uid, vals)

        if ensure_vals:
            fill_ensure_vals(data, uid, ensure_vals)

        if val_proc:
            fill_vals_proc(data, uid, val_proc)

    return data


def _process_source_entry(data, entry, key, key_secondary, key_search, keymap, only, skip, debug):
    """Process a single source entry. Returns uid (or None for flat) or _NOT_FOUND to skip."""
    if only and not matches_only(entry, only):
        return _NOT_FOUND

    if skip and can_skip(entry, skip):
        return _NOT_FOUND

    uid = None
    if key or key_search:
        uid = get_uid(entry, key, key_secondary, key_search, keymap)
        if not uid:
            return _NOT_FOUND
        if uid not in data:
            data[uid] = {}

    if debug:
        _LOGGER.debug("Processing entry %s", async_redact_data(entry, TO_REDACT))

    return uid


def get_uid(entry, key, key_secondary, key_search, keymap) -> str | None:
    """Get UID for data list."""
    if not key_search:
        return _get_uid_from_keys(entry, key, key_secondary)

    if keymap and key_search in entry and entry[key_search] in keymap:
        return keymap[entry[key_search]]

    return None


def _get_uid_from_keys(entry, key, key_secondary) -> str | None:
    """Resolve UID from primary or secondary key."""
    if key in entry:
        return entry[key] or None

    if key_secondary and key_secondary in entry:
        return entry[key_secondary] or None

    return None


def generate_keymap(data, key_search) -> dict | None:
    """Generate keymap."""
    return {data[uid][key_search]: uid for uid in data if key_search in data[uid]} if key_search else None


def matches_only(entry, only) -> bool:
    """Return True if all variables are matched."""
    return all(val["key"] in entry and entry[val["key"]] == val["value"] for val in only)


def can_skip(entry, skip) -> bool:
    """Return True if at least one variable matches."""
    for val in skip:
        if val["name"] in entry and entry[val["name"]] == val["value"]:
            return True
        if val["value"] == "" and val["name"] not in entry:
            return True
    return False


def _resolve_str_default(val) -> str:
    """Get string default from a val descriptor."""
    default = val.get("default", "")
    if "default_val" in val and val["default_val"] in val:
        default = val[val["default_val"]]
    return default


def fill_defaults(data, vals) -> dict:
    """Fill defaults if source is not present."""
    for val in vals:
        name = val["name"]
        if name in data:
            continue

        vtype = val.get("type", "str")
        if vtype == "str":
            data[name] = from_entry([], val.get("source", name), default=_resolve_str_default(val))
        elif vtype == "bool":
            data[name] = from_entry_bool(
                [],
                val.get("source", name),
                default=val.get("default", False),
                reverse=val.get("reverse", False),
            )

    return data


def _fill_val_str(data, entry, uid, val) -> None:
    """Fill a single string-typed value."""
    source = val.get("source", val["name"])
    default = _resolve_str_default(val)
    _set_data(data, uid, val["name"], from_entry(entry, source, default=default))


def _fill_val_bool(data, entry, uid, val) -> None:
    """Fill a single bool-typed value."""
    source = val.get("source", val["name"])
    _set_data(
        data,
        uid,
        val["name"],
        from_entry_bool(
            entry,
            source,
            default=val.get("default", False),
            reverse=val.get("reverse", False),
        ),
    )


def _convert_timestamp(data, uid, name) -> None:
    """Convert an integer value to UTC datetime if applicable."""
    value = _get_data(data, uid, name)
    if not isinstance(value, int) or value <= 0:
        return
    if value > 100000000000:
        value = value / 1000
    _set_data(data, uid, name, utc_from_timestamp(value))


def fill_vals(data, entry, uid, vals) -> dict:
    """Fill all data from a source entry."""
    for val in vals:
        vtype = val.get("type", "str")
        if vtype == "str":
            _fill_val_str(data, entry, uid, val)
        elif vtype == "bool":
            _fill_val_bool(data, entry, uid, val)

        if val.get("convert") == "utc_from_timestamp":
            _convert_timestamp(data, uid, val["name"])

    return data


def fill_ensure_vals(data, uid, ensure_vals) -> dict:
    """Add required keys which are not available in data."""
    for val in ensure_vals:
        target = data[uid] if uid else data
        if val["name"] not in target:
            target[val["name"]] = val.get("default", "")

    return data


def _process_val_sub(val_sub, _data) -> tuple[str | None, str | None]:
    """Process a single val_proc sub-entry and return (name, computed_value)."""
    name = None
    action = None
    value = None

    for val in val_sub:
        if "name" in val:
            name = val["name"]
            continue
        if "action" in val:
            action = val["action"]
            continue
        if not name or not action:  # need both before processing value entries
            break

        if action == "combine":
            value = _apply_combine(val, _data, value)

    return name, value


def _apply_combine(val, _data, current_value) -> str | None:
    """Apply a combine action step to build a string value."""
    if "key" in val:
        tmp = _data.get(val["key"], "unknown")
        return f"{current_value}{tmp}" if current_value else tmp

    if "text" in val:
        tmp = val["text"]
        return f"{current_value}{tmp}" if current_value else tmp

    return current_value


def fill_vals_proc(data, uid, vals_proc) -> dict:
    """Add custom keys built from val_proc descriptors."""
    _data = data[uid] if uid else data
    for val_sub in vals_proc:
        name, value = _process_val_sub(val_sub, _data)
        if name and value:
            _set_data(data, uid, name, value)

    return data
