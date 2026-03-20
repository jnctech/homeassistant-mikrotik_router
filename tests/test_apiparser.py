"""Tests for apiparser helper functions."""

from datetime import datetime, timezone
from custom_components.mikrotik_router.apiparser import (
    from_entry,
    from_entry_bool,
    get_uid,
    generate_keymap,
    matches_only,
    can_skip,
    fill_defaults,
    fill_vals,
    fill_ensure_vals,
    fill_vals_proc,
    utc_from_timestamp,
)


# --- from_entry ---


class TestFromEntry:
    def test_simple_key(self):
        assert from_entry({"name": "ether1"}, "name") == "ether1"

    def test_missing_key_returns_default(self):
        assert from_entry({"name": "ether1"}, "missing") == ""

    def test_custom_default(self):
        assert from_entry({}, "missing", default="fallback") == "fallback"

    def test_nested_path(self):
        entry = {"level1": {"level2": "deep_value"}}
        assert from_entry(entry, "level1/level2") == "deep_value"

    def test_nested_path_missing(self):
        entry = {"level1": {"other": "val"}}
        assert from_entry(entry, "level1/level2", default="nope") == "nope"

    def test_nested_path_not_dict(self):
        entry = {"level1": "not_a_dict"}
        assert from_entry(entry, "level1/level2", default="nope") == "nope"

    def test_int_value_preserved(self):
        assert from_entry({"port": 8728}, "port", default=0) == 8728

    def test_float_rounded(self):
        result = from_entry({"temp": 45.678}, "temp", default=0.0)
        assert result == 45.68

    def test_long_string_truncated(self):
        long_str = "x" * 300
        result = from_entry({"val": long_str}, "val")
        assert len(result) == 255

    def test_short_string_not_truncated(self):
        result = from_entry({"val": "short"}, "val")
        assert result == "short"


# --- from_entry_bool ---


class TestFromEntryBool:
    def test_true_bool(self):
        assert from_entry_bool({"enabled": True}, "enabled") is True

    def test_false_bool(self):
        assert from_entry_bool({"enabled": False}, "enabled") is False

    def test_string_yes(self):
        assert from_entry_bool({"val": "yes"}, "val") is True

    def test_string_Yes(self):
        assert from_entry_bool({"val": "Yes"}, "val") is True

    def test_string_on(self):
        assert from_entry_bool({"val": "on"}, "val") is True

    def test_string_up(self):
        assert from_entry_bool({"val": "up"}, "val") is True

    def test_string_no(self):
        assert from_entry_bool({"val": "no"}, "val") is False

    def test_string_off(self):
        assert from_entry_bool({"val": "off"}, "val") is False

    def test_string_down(self):
        assert from_entry_bool({"val": "down"}, "val") is False

    def test_missing_key_returns_default(self):
        assert from_entry_bool({}, "missing") is False

    def test_missing_key_custom_default(self):
        assert from_entry_bool({}, "missing", default=True) is True

    def test_reverse(self):
        assert from_entry_bool({"enabled": True}, "enabled", reverse=True) is False

    def test_reverse_false(self):
        assert from_entry_bool({"enabled": False}, "enabled", reverse=True) is True

    def test_non_bool_non_string_returns_default(self):
        assert from_entry_bool({"val": 42}, "val") is False

    def test_nested_path(self):
        entry = {"l1": {"l2": True}}
        assert from_entry_bool(entry, "l1/l2") is True

    def test_nested_path_missing(self):
        entry = {"l1": {"other": True}}
        assert from_entry_bool(entry, "l1/l2", default=True) is True


# --- get_uid ---


class TestGetUid:
    def test_primary_key(self):
        entry = {"mac-address": "AA:BB:CC:DD:EE:FF"}
        assert get_uid(entry, "mac-address", None, None, None) == "AA:BB:CC:DD:EE:FF"

    def test_primary_key_missing_uses_secondary(self):
        entry = {"name": "ether1"}
        assert get_uid(entry, "mac-address", "name", None, None) == "ether1"

    def test_both_keys_missing(self):
        entry = {"other": "val"}
        assert get_uid(entry, "mac-address", "name", None, None) is None

    def test_secondary_key_empty_value(self):
        entry = {"name": ""}
        assert get_uid(entry, "mac-address", "name", None, None) is None

    def test_key_search_with_keymap(self):
        entry = {"name": "ether1"}
        keymap = {"ether1": "uid-123"}
        assert get_uid(entry, None, None, "name", keymap) == "uid-123"

    def test_key_search_no_match(self):
        entry = {"name": "ether1"}
        keymap = {"ether2": "uid-456"}
        assert get_uid(entry, None, None, "name", keymap) is None

    def test_key_search_no_keymap(self):
        entry = {"name": "ether1"}
        assert get_uid(entry, None, None, "name", None) is None


# --- generate_keymap ---


class TestGenerateKeymap:
    def test_creates_keymap(self):
        data = {
            "uid1": {"name": "ether1"},
            "uid2": {"name": "ether2"},
        }
        result = generate_keymap(data, "name")
        assert result == {"ether1": "uid1", "ether2": "uid2"}

    def test_no_key_search_returns_none(self):
        assert generate_keymap({"uid1": {"name": "ether1"}}, None) is None

    def test_skips_entries_without_key(self):
        data = {
            "uid1": {"name": "ether1"},
            "uid2": {"other": "val"},
        }
        result = generate_keymap(data, "name")
        assert result == {"ether1": "uid1"}


# --- matches_only ---


class TestMatchesOnly:
    def test_all_match(self):
        entry = {"type": "ether", "running": True}
        only = [{"key": "type", "value": "ether"}, {"key": "running", "value": True}]
        assert matches_only(entry, only) is True

    def test_partial_match(self):
        entry = {"type": "ether", "running": False}
        only = [{"key": "type", "value": "ether"}, {"key": "running", "value": True}]
        assert matches_only(entry, only) is False

    def test_missing_key(self):
        entry = {"type": "ether"}
        only = [{"key": "missing", "value": "val"}]
        assert matches_only(entry, only) is False

    def test_single_match(self):
        entry = {"type": "ether"}
        only = [{"key": "type", "value": "ether"}]
        assert matches_only(entry, only) is True


# --- can_skip ---


class TestCanSkip:
    def test_matching_value_skips(self):
        entry = {"disabled": True}
        skip = [{"name": "disabled", "value": True}]
        assert can_skip(entry, skip) is True

    def test_no_match_no_skip(self):
        entry = {"disabled": False}
        skip = [{"name": "disabled", "value": True}]
        assert can_skip(entry, skip) is False

    def test_missing_key_with_empty_value_skips(self):
        entry = {"other": "val"}
        skip = [{"name": "missing", "value": ""}]
        assert can_skip(entry, skip) is True

    def test_missing_key_with_nonempty_value_no_skip(self):
        entry = {"other": "val"}
        skip = [{"name": "missing", "value": "something"}]
        assert can_skip(entry, skip) is False

    def test_multiple_skip_first_matches(self):
        entry = {"dynamic": True, "disabled": False}
        skip = [
            {"name": "dynamic", "value": True},
            {"name": "disabled", "value": True},
        ]
        assert can_skip(entry, skip) is True


# --- fill_defaults ---


class TestFillDefaults:
    def test_fills_missing_str_default(self):
        data = {}
        vals = [{"name": "host", "default": "unknown"}]
        result = fill_defaults(data, vals)
        assert result["host"] == "unknown"

    def test_preserves_existing_value(self):
        data = {"host": "myhost"}
        vals = [{"name": "host", "default": "unknown"}]
        result = fill_defaults(data, vals)
        assert result["host"] == "myhost"

    def test_fills_missing_bool_default(self):
        data = {}
        vals = [{"name": "enabled", "type": "bool", "default": True}]
        result = fill_defaults(data, vals)
        assert result["enabled"] is True

    def test_bool_reverse_default(self):
        data = {}
        vals = [{"name": "enabled", "type": "bool", "default": True, "reverse": True}]
        result = fill_defaults(data, vals)
        assert result["enabled"] is False


# --- fill_vals ---


class TestFillVals:
    def test_fills_str_value_with_uid(self):
        data = {"uid1": {}}
        entry = {"name": "ether1"}
        vals = [{"name": "name"}]
        result = fill_vals(data, entry, "uid1", vals)
        assert result["uid1"]["name"] == "ether1"

    def test_fills_str_value_without_uid(self):
        data = {}
        entry = {"name": "ether1"}
        vals = [{"name": "name"}]
        result = fill_vals(data, entry, None, vals)
        assert result["name"] == "ether1"

    def test_fills_bool_value(self):
        data = {"uid1": {}}
        entry = {"disabled": True}
        vals = [{"name": "enabled", "source": "disabled", "type": "bool", "reverse": True}]
        result = fill_vals(data, entry, "uid1", vals)
        assert result["uid1"]["enabled"] is False

    def test_fills_with_default(self):
        data = {"uid1": {}}
        entry = {}
        vals = [{"name": "host", "default": "unknown"}]
        result = fill_vals(data, entry, "uid1", vals)
        assert result["uid1"]["host"] == "unknown"

    def test_utc_timestamp_conversion(self):
        data = {"uid1": {}}
        entry = {"last-seen": 1700000000}
        vals = [{"name": "last-seen", "convert": "utc_from_timestamp"}]
        result = fill_vals(data, entry, "uid1", vals)
        assert isinstance(result["uid1"]["last-seen"], datetime)
        assert result["uid1"]["last-seen"].tzinfo == timezone.utc

    def test_utc_timestamp_milliseconds_converted(self):
        data = {"uid1": {}}
        entry = {"last-seen": 1700000000000}
        vals = [{"name": "last-seen", "convert": "utc_from_timestamp"}]
        result = fill_vals(data, entry, "uid1", vals)
        assert isinstance(result["uid1"]["last-seen"], datetime)


# --- fill_ensure_vals ---


class TestFillEnsureVals:
    def test_adds_missing_key_with_uid(self):
        data = {"uid1": {}}
        ensure_vals = [{"name": "bridge", "default": ""}]
        result = fill_ensure_vals(data, "uid1", ensure_vals)
        assert result["uid1"]["bridge"] == ""

    def test_preserves_existing_with_uid(self):
        data = {"uid1": {"bridge": "br0"}}
        ensure_vals = [{"name": "bridge", "default": ""}]
        result = fill_ensure_vals(data, "uid1", ensure_vals)
        assert result["uid1"]["bridge"] == "br0"

    def test_adds_missing_key_without_uid(self):
        data = {}
        ensure_vals = [{"name": "bridge", "default": "none"}]
        result = fill_ensure_vals(data, None, ensure_vals)
        assert result["bridge"] == "none"

    def test_preserves_existing_without_uid(self):
        data = {"bridge": "br0"}
        ensure_vals = [{"name": "bridge", "default": ""}]
        result = fill_ensure_vals(data, None, ensure_vals)
        assert result["bridge"] == "br0"


# --- fill_vals_proc ---


class TestFillValsProc:
    def test_combine_keys(self):
        data = {"uid1": {"chain": "forward", "action": "accept"}}
        vals_proc = [
            [
                {"name": "uniq-id"},
                {"action": "combine"},
                {"key": "chain"},
                {"text": ","},
                {"key": "action"},
            ]
        ]
        result = fill_vals_proc(data, "uid1", vals_proc)
        assert result["uid1"]["uniq-id"] == "forward,accept"

    def test_combine_missing_key_uses_unknown(self):
        data = {"uid1": {"chain": "forward"}}
        vals_proc = [
            [
                {"name": "uniq-id"},
                {"action": "combine"},
                {"key": "chain"},
                {"text": ","},
                {"key": "missing"},
            ]
        ]
        result = fill_vals_proc(data, "uid1", vals_proc)
        assert result["uid1"]["uniq-id"] == "forward,unknown"

    def test_combine_without_uid(self):
        data = {"chain": "srcnat", "action": "masquerade"}
        vals_proc = [
            [
                {"name": "uniq-id"},
                {"action": "combine"},
                {"key": "chain"},
                {"text": "-"},
                {"key": "action"},
            ]
        ]
        result = fill_vals_proc(data, None, vals_proc)
        assert result["uniq-id"] == "srcnat-masquerade"

    def test_no_name_and_action_breaks(self):
        data = {"uid1": {"val": "x"}}
        vals_proc = [[{"other": "junk"}]]
        result = fill_vals_proc(data, "uid1", vals_proc)
        assert "uniq-id" not in result["uid1"]


# --- utc_from_timestamp ---


class TestUtcFromTimestamp:
    def test_returns_utc_datetime(self):
        result = utc_from_timestamp(1700000000)
        assert result.tzinfo == timezone.utc
        assert isinstance(result, datetime)

    def test_specific_timestamp(self):
        result = utc_from_timestamp(0)
        assert result == datetime(1970, 1, 1, tzinfo=timezone.utc)
