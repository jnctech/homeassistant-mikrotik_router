"""Tests for apiparser helper functions."""

from datetime import datetime, timezone
from custom_components.mikrotik_router.apiparser import (
    _traverse_entry,
    _NOT_FOUND,
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
        """When source is absent, reverse is applied to default (bug fix)."""
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


# --- _traverse_entry ---


class TestTraverseEntry:
    def test_simple_key_found(self):
        assert _traverse_entry({"name": "ether1"}, "name") == "ether1"

    def test_simple_key_missing(self):
        assert _traverse_entry({"name": "ether1"}, "missing") is _NOT_FOUND

    def test_nested_path_found(self):
        entry = {"level1": {"level2": "deep_value"}}
        assert _traverse_entry(entry, "level1/level2") == "deep_value"

    def test_nested_path_missing_intermediate(self):
        entry = {"level1": {"other": "val"}}
        assert _traverse_entry(entry, "level1/level2") is _NOT_FOUND

    def test_nested_path_not_dict(self):
        entry = {"level1": "string_value"}
        assert _traverse_entry(entry, "level1/level2") is _NOT_FOUND

    def test_none_value_preserved(self):
        """None values should be returned, not treated as missing."""
        assert _traverse_entry({"comment": None}, "comment") is None

    def test_nested_none_value_preserved(self):
        entry = {"a": {"b": None}}
        assert _traverse_entry(entry, "a/b") is None


# --- from_entry_bool case-insensitive ---


class TestFromEntryBoolCaseInsensitive:
    def test_mixed_case_yes(self):
        assert from_entry_bool({"enabled": "yEs"}, "enabled") is True

    def test_mixed_case_no(self):
        assert from_entry_bool({"enabled": "nO"}, "enabled") is False

    def test_mixed_case_on(self):
        assert from_entry_bool({"status": "oN"}, "status") is True

    def test_mixed_case_off(self):
        assert from_entry_bool({"status": "oFf"}, "status") is False

    def test_mixed_case_up(self):
        assert from_entry_bool({"link": "uP"}, "link") is True

    def test_mixed_case_down(self):
        assert from_entry_bool({"link": "dOwN"}, "link") is False

    def test_none_value_returns_default(self):
        """API entries with None values should return the default."""
        assert from_entry_bool({"flag": None}, "flag") is False

    def test_none_value_returns_custom_default(self):
        assert from_entry_bool({"flag": None}, "flag", default=True) is True


# --- from_entry None handling ---


class TestFromEntryNoneHandling:
    def test_none_value_returned_as_is(self):
        """None in the API response is a valid value, not 'missing'."""
        result = from_entry({"comment": None}, "comment")
        assert result is None

    def test_none_value_with_non_empty_default(self):
        """None bypasses the type coercion since it's not str/int/float."""
        result = from_entry({"comment": None}, "comment", default="fallback")
        assert result is None


# --- from_entry_bool reverse bug fix ---


class TestFromEntryBoolReverseBugFix:
    """Regression tests for the from_entry_bool reverse quirk.

    When 'disabled' field is absent from API response (common for dynamic DHCP
    leases), from_entry_bool must apply reverse to the default value.
    """

    def test_missing_disabled_with_reverse_returns_true(self):
        """DHCP lease without 'disabled' field should be enabled=True."""
        result = from_entry_bool({}, "disabled", default=False, reverse=True)
        assert result is True

    def test_missing_disabled_without_reverse_returns_false(self):
        result = from_entry_bool({}, "disabled", default=False, reverse=False)
        assert result is False

    def test_missing_with_reverse_and_default_true(self):
        result = from_entry_bool({}, "disabled", default=True, reverse=True)
        assert result is False

    def test_present_disabled_false_with_reverse(self):
        """When disabled=False present, enabled should be True (reverse)."""
        result = from_entry_bool({"disabled": False}, "disabled", default=False, reverse=True)
        assert result is True

    def test_present_disabled_true_with_reverse(self):
        """When disabled=True present, enabled should be False (reverse)."""
        result = from_entry_bool({"disabled": True}, "disabled", default=False, reverse=True)
        assert result is False


# --- from_entry identity coercion removal ---


class TestFromEntryIdentityCoercionRemoved:
    """Verify that str/int values are not unnecessarily re-wrapped."""

    def test_str_returned_directly(self):
        result = from_entry({"name": "ether1"}, "name", default="x")
        assert result == "ether1"
        assert type(result) is str

    def test_int_returned_directly(self):
        result = from_entry({"port": 8728}, "port", default=0)
        assert result == 8728
        assert type(result) is int


# --- _set_data / _get_data helpers ---


class TestDataHelpers:
    def test_set_data_with_uid(self):
        from custom_components.mikrotik_router.apiparser import _set_data, _get_data

        data = {"u1": {}}
        _set_data(data, "u1", "name", "ether1")
        assert data["u1"]["name"] == "ether1"
        assert _get_data(data, "u1", "name") == "ether1"

    def test_set_data_without_uid(self):
        from custom_components.mikrotik_router.apiparser import _set_data, _get_data

        data = {}
        _set_data(data, None, "name", "ether1")
        assert data["name"] == "ether1"
        assert _get_data(data, None, "name") == "ether1"


# --- _resolve_str_default ---


class TestResolveStrDefault:
    def test_explicit_default(self):
        from custom_components.mikrotik_router.apiparser import _resolve_str_default

        assert _resolve_str_default({"name": "x", "default": "fallback"}) == "fallback"

    def test_no_default(self):
        from custom_components.mikrotik_router.apiparser import _resolve_str_default

        assert _resolve_str_default({"name": "x"}) == ""

    def test_default_val_reference(self):
        from custom_components.mikrotik_router.apiparser import _resolve_str_default

        val = {"name": "name", "default_val": "default-name", "default-name": "ether1"}
        assert _resolve_str_default(val) == "ether1"


# --- _convert_timestamp ---


class TestConvertTimestamp:
    def test_converts_seconds_timestamp(self):
        from custom_components.mikrotik_router.apiparser import (
            _convert_timestamp,
            _get_data,
        )

        data = {"u1": {"ts": 1700000000}}
        _convert_timestamp(data, "u1", "ts")
        result = _get_data(data, "u1", "ts")
        assert hasattr(result, "tzinfo")

    def test_converts_milliseconds_timestamp(self):
        from custom_components.mikrotik_router.apiparser import (
            _convert_timestamp,
            _get_data,
        )

        data = {"u1": {"ts": 1700000000000}}
        _convert_timestamp(data, "u1", "ts")
        result = _get_data(data, "u1", "ts")
        assert hasattr(result, "tzinfo")

    def test_skips_non_int(self):
        from custom_components.mikrotik_router.apiparser import (
            _convert_timestamp,
            _get_data,
        )

        data = {"u1": {"ts": "not-a-number"}}
        _convert_timestamp(data, "u1", "ts")
        assert _get_data(data, "u1", "ts") == "not-a-number"

    def test_skips_zero(self):
        from custom_components.mikrotik_router.apiparser import (
            _convert_timestamp,
            _get_data,
        )

        data = {"u1": {"ts": 0}}
        _convert_timestamp(data, "u1", "ts")
        assert _get_data(data, "u1", "ts") == 0


# --- get_uid refactored ---


class TestGetUidRefactored:
    def test_primary_key_empty_value_returns_none(self):
        """Entry with key present but empty value should return None."""
        assert get_uid({"name": ""}, "name", None, None, None) is None

    def test_secondary_key_used_when_primary_missing(self):
        result = get_uid({"alt": "eth0"}, "name", "alt", None, None)
        assert result == "eth0"

    def test_secondary_key_empty_returns_none(self):
        assert get_uid({"alt": ""}, "name", "alt", None, None) is None


# --- _process_val_sub / _apply_combine ---


class TestFillValsProcExtracted:
    def test_combine_keys(self):
        from custom_components.mikrotik_router.apiparser import _process_val_sub

        val_sub = [
            {"name": "result"},
            {"action": "combine"},
            {"key": "a"},
            {"text": "-"},
            {"key": "b"},
        ]
        name, value = _process_val_sub(val_sub, {"a": "hello", "b": "world"})
        assert name == "result"
        assert value == "hello-world"

    def test_combine_missing_key_uses_unknown(self):
        from custom_components.mikrotik_router.apiparser import _process_val_sub

        val_sub = [
            {"name": "result"},
            {"action": "combine"},
            {"key": "missing"},
        ]
        _name, value = _process_val_sub(val_sub, {})
        assert value == "unknown"

    def test_no_name_returns_none(self):
        from custom_components.mikrotik_router.apiparser import _process_val_sub

        val_sub = [{"action": "combine"}, {"key": "a"}]
        name, _value = _process_val_sub(val_sub, {"a": "x"})
        assert name is None
