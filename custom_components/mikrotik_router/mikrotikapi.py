"""Mikrotik API for Mikrotik Router."""

from __future__ import annotations

import logging
import ssl
from time import time
from threading import Lock

from .const import (
    DEFAULT_LOGIN_METHOD,
    DEFAULT_ENCODING,
)

import librouteros

_LOGGER = logging.getLogger(__name__)


class MikrotikAPI:
    """Handle all communication with the Mikrotik API."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 0,
        use_ssl: bool = True,
        ssl_verify: bool = True,
        login_method: str = DEFAULT_LOGIN_METHOD,
        encoding: str = DEFAULT_ENCODING,
    ) -> None:
        """Initialize the Mikrotik Client."""
        self._host = host
        self._use_ssl = use_ssl
        self._ssl_verify = ssl_verify
        self._port = port
        self._username = username
        self._password = password
        self._login_method = login_method
        self._encoding = encoding
        self._ssl_wrapper = None
        self.lock = Lock()

        self._connection = None
        self._connected = False
        self._reconnected = True
        self._connection_epoch: float = 0
        self._connection_retry_sec = 58
        self.error: str = ""
        self.connection_error_reported = False
        self.client_traffic_last_run: int | None = None
        self.disable_health = False

        if not self._port:
            self._port = 8729 if self._use_ssl else 8728

    def has_reconnected(self) -> bool:
        """Check if mikrotik has reconnected."""
        if self._reconnected:
            self._reconnected = False
            return True
        return False

    def connection_check(self) -> bool:
        """Check if mikrotik is connected."""
        if not self._connected or not self._connection:
            if self._connection_epoch > time() - self._connection_retry_sec:
                return False
            if not self.connect():
                return False
        return True

    def disconnect(self, location: str = "unknown", error: object = None) -> None:
        """Disconnect from Mikrotik device."""
        if not error:
            error = "unknown"

        if not self.connection_error_reported:
            if location == "unknown":
                _LOGGER.error("Mikrotik %s connection closed", self._host)
            else:
                _LOGGER.error("Mikrotik %s error while %s : %s", self._host, location, error)
            self.connection_error_reported = True

        self._reconnected = False
        self._connected = False
        self._connection = None
        self._connection_epoch = 0

    def connect(self) -> bool:
        """Connect to Mikrotik device."""
        self.error = ""
        self._connected = False
        self._connection_epoch = time()

        kwargs = {
            "encoding": self._encoding,
            "login_methods": self._login_method,
            "port": self._port,
        }

        with self.lock:
            try:
                if self._use_ssl:
                    self._ensure_ssl_wrapper()
                    kwargs["ssl_wrapper"] = self._ssl_wrapper
                self._connection = librouteros.connect(self._host, self._username, self._password, **kwargs)
            except Exception as e:
                if not self.connection_error_reported:
                    _LOGGER.error("Mikrotik %s error while connecting: %s", self._host, e)
                    self.connection_error_reported = True
                self.error_to_strings(f"{e}")
                self._connection = None
                return False
            else:
                if self.connection_error_reported:
                    _LOGGER.warning("Mikrotik Reconnected to %s", self._host)
                    self.connection_error_reported = False
                else:
                    _LOGGER.debug("Mikrotik Connected to %s", self._host)
                self._connected = True
                self._reconnected = True

        return self._connected

    def _ensure_ssl_wrapper(self) -> None:
        """Create SSL wrapper if not already initialised."""
        if self._ssl_wrapper is not None:
            return
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        if self._ssl_verify:
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            ssl_context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        else:
            ssl_context.verify_mode = ssl.CERT_NONE
        self._ssl_wrapper = ssl_context.wrap_socket

    def error_to_strings(self, error: str) -> None:
        """Translate error output to error string."""
        self.error = "cannot_connect"
        if error == "invalid user name or password (6)":
            self.error = "wrong_login"
        if "ALERT_HANDSHAKE_FAILURE" in error:
            self.error = "ssl_handshake_failure"
        if "CERTIFICATE_VERIFY_FAILED" in error:
            self.error = "ssl_verify_failure"

    def connected(self) -> bool:
        """Return connected boolean."""
        return self._connected

    def query(
        self,
        path: str,
        command: str | None = None,
        args: dict | None = None,
        return_list: bool = True,
    ) -> list | None:
        """Retrieve data from Mikrotik API."""
        if path == "/system/health" and self.disable_health:
            return None

        if args is None:
            args = {}

        if not self.connection_check():
            return None

        with self.lock:
            try:
                _LOGGER.debug("API query: %s", path)
                response = self._connection.path(path)
            except Exception as e:
                self.disconnect("path", e)
                return None

            if command:
                return self._query_command(response, path, command, args)
            if return_list:
                return self._query_list(response, path)

        return response or None

    def _query_list(self, response, path: str) -> list | None:
        """Build list from API response. Must be called inside self.lock."""
        try:
            return list(response) or None
        except Exception as e:
            if path == "/system/health" and "no such command prefix" in str(e):
                self.disable_health = True
                return None
            self.disconnect(f"building list for path {path}", e)
            return None

    def _query_command(self, response, path: str, command: str, args: dict) -> list | None:
        """Execute command on API path. Must be called inside self.lock."""
        _LOGGER.debug("API query: %s, %s, %s", path, command, args)
        try:
            return list(response(command, **args)) or None
        except Exception as e:
            self.disconnect("path", e)
            return None

    @staticmethod
    def _find_entry(response, param: str, value: str) -> str | None:
        """Find .id of entry matching param=value in an API response."""
        for item in response:
            if item.get(param) == value:
                return item.get(".id")
        return None

    def set_value(
        self,
        path: str,
        param: str,
        value: str,
        mod_param: str,
        mod_value: object,
    ) -> bool:
        """Modify a parameter."""
        if not self.connection_check():
            return False

        response = self.query(path, return_list=False)
        if response is None:
            return False

        with self.lock:
            try:
                entry_found = self._find_entry(response, param, value)
                if not entry_found:
                    _LOGGER.error(
                        "Mikrotik %s set_value parameter %s with value %s not found",
                        self._host,
                        param,
                        value,
                    )
                    return False
                response.update(**{".id": entry_found, mod_param: mod_value})
            except Exception as e:
                self.disconnect("set_value", e)
                return False

        return True

    def execute(
        self,
        path: str,
        command: str,
        param: str,
        value: str,
        attributes: dict | None = None,
    ) -> bool:
        """Execute a command."""
        if not self.connection_check():
            return False

        response = self.query(path, return_list=False)
        if response is None:
            return False

        with self.lock:
            try:
                params: dict = {}
                if param:
                    entry_found = self._find_entry(response, param, value)
                    if not entry_found:
                        _LOGGER.error(
                            "Mikrotik %s Execute %s parameter %s with value %s not found",
                            self._host,
                            command,
                            param,
                            value,
                        )
                        return False
                    params[".id"] = entry_found

                if attributes:
                    params.update(attributes)

                tuple(response(command, **params))
            except Exception as e:
                self.disconnect("execute", e)
                return False

        return True

    def run_script(self, name: str) -> bool:
        """Run script."""
        if not self.connection_check():
            return False

        response = self.query("/system/script", return_list=False)
        if response is None:
            return False

        with self.lock:
            entry_found = self._find_entry(response, "name", name)
            if not entry_found:
                _LOGGER.error("Mikrotik %s Script %s not found", self._host, name)
                return False

            try:
                run = response("run", **{".id": entry_found})
                tuple(run)
            except Exception as e:
                self.disconnect("run_script", e)
                return False

        return True

    def arp_ping(self, address: str, interface: str) -> bool:
        """Check arp ping response traffic stats."""
        if not self.connection_check():
            return False

        response = self.query("/ping", return_list=False)
        if response is None:
            return False

        args = {
            "arp-ping": "no",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": address,
        }
        with self.lock:
            try:
                ping = response("/ping", **args)
            except Exception as e:
                self.disconnect("arp_ping", e)
                return False

            try:
                ping = list(ping)
            except Exception as e:
                self.disconnect("arp_ping", e)
                return False

        for tmp in ping:
            if "received" in tmp and tmp["received"] > 0:
                _LOGGER.debug("Ping host success: %s", args["address"])
                return True

        _LOGGER.debug("Ping host failure: %s", args["address"])
        return False

    @staticmethod
    def _current_milliseconds() -> int:
        return int(round(time() * 1000))

    def is_accounting_and_local_traffic_enabled(self) -> tuple[bool, bool]:
        """Check if accounting and local traffic are enabled."""
        if not self.connection_check():
            return False, False

        response = self.query("/ip/accounting")
        if response is None:
            return False, False

        for item in response:
            if "enabled" not in item:
                continue
            if not item["enabled"]:
                return False, False

        for item in response:
            if "account-local-traffic" not in item:
                continue
            if not item["account-local-traffic"]:
                return True, False

        return True, True

    def take_client_traffic_snapshot(self, use_accounting: bool) -> float:
        """Take accounting snapshot and return time diff."""
        if not self.connection_check():
            return 0

        if use_accounting:
            accounting = self.query("/ip/accounting", return_list=False)

            with self.lock:
                try:
                    take = accounting("snapshot/take")
                except Exception as e:
                    self.disconnect("accounting_snapshot", e)
                    return 0

                try:
                    list(take)
                except Exception as e:
                    self.disconnect("accounting_snapshot", e)
                    return 0

        if not self.client_traffic_last_run:
            self.client_traffic_last_run = self._current_milliseconds()
            return 0

        time_diff = self._current_milliseconds() - self.client_traffic_last_run
        self.client_traffic_last_run = self._current_milliseconds()
        return time_diff / 1000
