"""Tests for MikrotikAPI — lock management, error handling, connection logic."""

from __future__ import annotations

from threading import Lock
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from custom_components.mikrotik_router.mikrotikapi import MikrotikAPI


def make_api(**kwargs) -> MikrotikAPI:
    """Create a MikrotikAPI with sensible test defaults."""
    defaults = {
        "host": "10.0.0.1",
        "username": "admin",
        "password": "admin",
        "port": 8728,
        "use_ssl": False,
        "ssl_verify": False,
    }
    defaults.update(kwargs)
    return MikrotikAPI(**defaults)


# --- __init__ ---


class TestInit:
    def test_default_port_ssl(self):
        api = MikrotikAPI("10.0.0.1", "admin", "pass", port=0, use_ssl=True)
        assert api._port == 8729

    def test_default_port_no_ssl(self):
        api = MikrotikAPI("10.0.0.1", "admin", "pass", port=0, use_ssl=False)
        assert api._port == 8728

    def test_custom_port_preserved(self):
        api = MikrotikAPI("10.0.0.1", "admin", "pass", port=9999)
        assert api._port == 9999

    def test_initial_state(self):
        api = make_api()
        assert api._connected is False
        assert api._reconnected is True
        assert api.error is None
        assert api.connection_error_reported is False
        assert api.disable_health is False


# --- error_to_strings ---


class TestErrorToStrings:
    def test_generic_error(self):
        api = make_api()
        api.error_to_strings("some random error")
        assert api.error == "cannot_connect"

    def test_wrong_login(self):
        api = make_api()
        api.error_to_strings("invalid user name or password (6)")
        assert api.error == "wrong_login"

    def test_ssl_handshake(self):
        api = make_api()
        api.error_to_strings("ALERT_HANDSHAKE_FAILURE occurred")
        assert api.error == "ssl_handshake_failure"

    def test_ssl_verify(self):
        api = make_api()
        api.error_to_strings("CERTIFICATE_VERIFY_FAILED check")
        assert api.error == "ssl_verify_failure"


# --- has_reconnected ---


class TestHasReconnected:
    def test_returns_true_and_clears(self):
        api = make_api()
        api._reconnected = True
        assert api.has_reconnected() is True
        assert api._reconnected is False

    def test_returns_false_when_not_reconnected(self):
        api = make_api()
        api._reconnected = False
        assert api.has_reconnected() is False


# --- connected ---


class TestConnected:
    def test_returns_connected_state(self):
        api = make_api()
        assert api.connected() is False
        api._connected = True
        assert api.connected() is True


# --- disconnect ---


class TestDisconnect:
    def test_resets_state(self):
        api = make_api()
        api._connected = True
        api._connection = MagicMock()
        api.disconnect("test", "error msg")
        assert api._connected is False
        assert api._connection is None
        assert api._connection_epoch == 0

    def test_logs_error_once(self):
        api = make_api()
        api.disconnect("test", "error")
        assert api.connection_error_reported is True
        # Second call should not log again (we just verify state)
        api.disconnect("test", "error")
        assert api.connection_error_reported is True

    def test_unknown_location(self):
        api = make_api()
        api.disconnect()
        assert api.connection_error_reported is True


# --- connection_check ---


class TestConnectionCheck:
    def test_connected_returns_true(self):
        api = make_api()
        api._connected = True
        api._connection = MagicMock()
        assert api.connection_check() is True

    def test_not_connected_within_retry_returns_false(self):
        api = make_api()
        api._connected = False
        # Set epoch to current time so retry window hasn't passed
        from time import time
        api._connection_epoch = time()
        assert api.connection_check() is False


# --- connect ---


class TestConnect:
    @patch("custom_components.mikrotik_router.mikrotikapi.librouteros")
    def test_successful_connect(self, mock_lib):
        api = make_api()
        mock_lib.connect.return_value = MagicMock()
        result = api.connect()
        assert result is True
        assert api._connected is True
        assert api._reconnected is True

    @patch("custom_components.mikrotik_router.mikrotikapi.librouteros")
    def test_connect_failure(self, mock_lib):
        api = make_api()
        mock_lib.connect.side_effect = Exception("connection refused")
        result = api.connect()
        assert result is False
        assert api._connected is False
        assert api.error == "cannot_connect"

    @patch("custom_components.mikrotik_router.mikrotikapi.librouteros")
    def test_connect_lock_released_on_failure(self, mock_lib):
        api = make_api()
        mock_lib.connect.side_effect = Exception("fail")
        api.connect()
        # Lock should be released — verify by acquiring it
        assert api.lock.acquire(timeout=1) is True
        api.lock.release()

    @patch("custom_components.mikrotik_router.mikrotikapi.librouteros")
    def test_connect_lock_released_on_success(self, mock_lib):
        api = make_api()
        mock_lib.connect.return_value = MagicMock()
        api.connect()
        assert api.lock.acquire(timeout=1) is True
        api.lock.release()

    @patch("custom_components.mikrotik_router.mikrotikapi.librouteros")
    def test_reconnect_clears_error_flag(self, mock_lib):
        api = make_api()
        api.connection_error_reported = True
        mock_lib.connect.return_value = MagicMock()
        api.connect()
        assert api.connection_error_reported is False


# --- query ---


class TestQuery:
    def _connected_api(self):
        api = make_api()
        api._connected = True
        api._connection = MagicMock()
        return api

    def test_health_disabled_returns_none(self):
        api = self._connected_api()
        api.disable_health = True
        assert api.query("/system/health") is None

    def test_not_connected_returns_none(self):
        api = make_api()
        api._connected = False
        # Force connection_check to fail
        from time import time
        api._connection_epoch = time()
        assert api.query("/interface") is None

    def test_query_returns_list(self):
        api = self._connected_api()
        mock_path = MagicMock()
        mock_path.__iter__ = MagicMock(return_value=iter([{"name": "ether1"}]))
        mock_path.__bool__ = MagicMock(return_value=True)
        api._connection.path.return_value = mock_path
        result = api.query("/interface")
        assert result == [{"name": "ether1"}]

    def test_query_path_exception_disconnects(self):
        api = self._connected_api()
        api._connection.path.side_effect = Exception("path error")
        result = api.query("/interface")
        assert result is None
        assert api._connected is False

    def test_query_lock_released_on_path_exception(self):
        api = self._connected_api()
        api._connection.path.side_effect = Exception("fail")
        api.query("/interface")
        assert api.lock.acquire(timeout=1) is True
        api.lock.release()

    def test_query_empty_response_returns_none(self):
        api = self._connected_api()
        mock_path = MagicMock()
        mock_path.__iter__ = MagicMock(return_value=iter([]))
        mock_path.__bool__ = MagicMock(return_value=False)
        api._connection.path.return_value = mock_path
        result = api.query("/interface")
        assert result is None

    def test_health_no_such_command_disables(self):
        api = self._connected_api()
        mock_path = MagicMock()
        mock_path.__bool__ = MagicMock(return_value=True)
        mock_path.__iter__ = MagicMock(
            side_effect=Exception("no such command prefix")
        )
        api._connection.path.return_value = mock_path
        result = api.query("/system/health")
        assert result is None
        assert api.disable_health is True


# --- set_value ---


class TestSetValue:
    def _connected_api_with_query(self, query_result):
        api = make_api()
        api._connected = True
        api._connection = MagicMock()
        # Mock query to return a mock response object
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter(query_result))
        mock_response.__bool__ = MagicMock(return_value=bool(query_result))
        api._connection.path.return_value = mock_response
        return api, mock_response

    def test_not_connected_returns_false(self):
        api = make_api()
        api._connected = False
        from time import time
        api._connection_epoch = time()
        assert api.set_value("/ip/address", "address", "10.0.0.1", "disabled", True) is False

    def test_entry_not_found_returns_true(self):
        api, _ = self._connected_api_with_query([{"name": "other", ".id": "*1"}])
        result = api.set_value("/interface", "name", "nonexistent", "disabled", True)
        assert result is True

    def test_lock_released_after_set(self):
        api, mock_resp = self._connected_api_with_query(
            [{"name": "ether1", ".id": "*1"}]
        )
        api.set_value("/interface", "name", "ether1", "disabled", True)
        assert api.lock.acquire(timeout=1) is True
        api.lock.release()


# --- run_script ---


class TestRunScript:
    def test_not_connected_returns_false(self):
        api = make_api()
        api._connected = False
        from time import time
        api._connection_epoch = time()
        assert api.run_script("test_script") is False

    def test_script_not_found_returns_true_no_deadlock(self):
        """Regression test: run_script must release lock when script not found."""
        api = make_api()
        api._connected = True
        api._connection = MagicMock()
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(
            return_value=iter([{"name": "other_script", ".id": "*1"}])
        )
        mock_response.__bool__ = MagicMock(return_value=True)
        api._connection.path.return_value = mock_response
        result = api.run_script("missing_script")
        assert result is True
        # Critical: lock must be released
        assert api.lock.acquire(timeout=1) is True
        api.lock.release()

    def test_script_found_executes(self):
        api = make_api()
        api._connected = True
        api._connection = MagicMock()
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(
            return_value=iter([{"name": "my_script", ".id": "*5"}])
        )
        mock_response.__bool__ = MagicMock(return_value=True)
        mock_run = MagicMock()
        mock_run.__iter__ = MagicMock(return_value=iter([]))
        mock_response.return_value = mock_run
        api._connection.path.return_value = mock_response
        result = api.run_script("my_script")
        assert result is True
        assert api.lock.acquire(timeout=1) is True
        api.lock.release()


# --- is_accounting_and_local_traffic_enabled ---


class TestAccounting:
    def test_not_connected(self):
        api = make_api()
        api._connected = False
        from time import time
        api._connection_epoch = time()
        assert api.is_accounting_and_local_traffic_enabled() == (False, False)

    def test_accounting_disabled(self):
        api = make_api()
        api._connected = True
        api._connection = MagicMock()
        mock_path = MagicMock()
        mock_path.__iter__ = MagicMock(
            return_value=iter([{"enabled": False}])
        )
        mock_path.__bool__ = MagicMock(return_value=True)
        api._connection.path.return_value = mock_path
        assert api.is_accounting_and_local_traffic_enabled() == (False, False)

    def test_accounting_enabled_no_local(self):
        api = make_api()
        api._connected = True
        api._connection = MagicMock()
        mock_path = MagicMock()
        mock_path.__iter__ = MagicMock(
            return_value=iter([{"enabled": True, "account-local-traffic": False}])
        )
        mock_path.__bool__ = MagicMock(return_value=True)
        api._connection.path.return_value = mock_path
        assert api.is_accounting_and_local_traffic_enabled() == (True, False)


# --- _current_milliseconds ---


class TestCurrentMilliseconds:
    def test_returns_int(self):
        result = MikrotikAPI._current_milliseconds()
        assert isinstance(result, int)
        assert result > 0
