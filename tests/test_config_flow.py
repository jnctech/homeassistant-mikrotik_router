"""Tests for Mikrotik Router config flow."""

from unittest.mock import patch, MagicMock

from homeassistant import data_entry_flow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mikrotik_router.const import (
    DOMAIN,
    CONF_SCAN_INTERVAL,
    CONF_TRACK_IFACE_CLIENTS,
    CONF_TRACK_HOSTS,
    CONF_TRACK_HOSTS_TIMEOUT,
    CONF_SENSOR_PORT_TRACKER,
    CONF_SENSOR_PORT_TRAFFIC,
    CONF_SENSOR_CLIENT_TRAFFIC,
    CONF_SENSOR_CLIENT_CAPTIVE,
    CONF_SENSOR_SIMPLE_QUEUES,
    CONF_SENSOR_NAT,
    CONF_SENSOR_MANGLE,
    CONF_SENSOR_FILTER,
    CONF_SENSOR_KIDCONTROL,
    CONF_SENSOR_PPP,
    CONF_SENSOR_SCRIPTS,
    CONF_SENSOR_ENVIRONMENT,
    CONF_SENSOR_NETWATCH_TRACKER,
    CONF_SENSOR_POE,
)

MOCK_USER_INPUT = {
    CONF_NAME: "Mikrotik",
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "password",
    CONF_PORT: 8728,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
}


def _mock_api(connect_return=True, error=""):
    """Create a mock MikrotikAPI."""
    api = MagicMock()
    api.connect.return_value = connect_return
    api.error = error
    return api


# ---------------------------
#   Config Flow Tests
# ---------------------------


async def test_flow_user_init(hass):
    """Test the user config flow shows the form."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_flow_user_creates_entry(hass):
    """Test a successful user config flow creates an entry."""
    # Patch both import sites: config_flow uses MikrotikAPI for the credential
    # check, and coordinator instantiates it during async_setup_entry that HA
    # runs after CREATE_ENTRY. Without the coordinator patch the real
    # librouteros.connect() reaches the socket layer (HASocketBlockedError).
    with (
        patch(
            "custom_components.mikrotik_router.config_flow.MikrotikAPI",
            return_value=_mock_api(connect_return=True),
        ),
        patch(
            "custom_components.mikrotik_router.coordinator.MikrotikAPI",
            return_value=_mock_api(connect_return=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data=MOCK_USER_INPUT)

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mikrotik"
    assert result["data"] == MOCK_USER_INPUT


async def test_flow_user_connection_error(hass):
    """Test the user config flow handles connection failure."""
    with patch(
        "custom_components.mikrotik_router.config_flow.MikrotikAPI",
        return_value=_mock_api(connect_return=False, error="cannot_connect"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data=MOCK_USER_INPUT)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_flow_user_wrong_login(hass):
    """Test the user config flow handles wrong credentials."""
    with patch(
        "custom_components.mikrotik_router.config_flow.MikrotikAPI",
        return_value=_mock_api(connect_return=False, error="wrong_login"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data=MOCK_USER_INPUT)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "wrong_login"}


async def test_flow_user_ssl_error(hass):
    """Test the user config flow handles SSL errors."""
    with patch(
        "custom_components.mikrotik_router.config_flow.MikrotikAPI",
        return_value=_mock_api(connect_return=False, error="ssl_handshake_failure"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data=MOCK_USER_INPUT)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "ssl_handshake_failure"}


async def test_flow_user_duplicate_name(hass):
    """Test the user config flow rejects duplicate names."""
    # Add an existing entry with the same name
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        title="Mikrotik",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.mikrotik_router.config_flow.MikrotikAPI",
        return_value=_mock_api(connect_return=True),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}, data=MOCK_USER_INPUT)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "name_exists"}


async def test_flow_import(hass):
    """Test the import step delegates to user step."""
    with (
        patch(
            "custom_components.mikrotik_router.config_flow.MikrotikAPI",
            return_value=_mock_api(connect_return=True),
        ),
        patch(
            "custom_components.mikrotik_router.coordinator.MikrotikAPI",
            return_value=_mock_api(connect_return=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"}, data=MOCK_USER_INPUT)

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mikrotik"


# ---------------------------
#   Options Flow Tests
# ---------------------------


async def test_options_flow_init(hass):
    """Test that the options flow shows the basic_options form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "basic_options"


async def test_options_flow_basic_to_sensor_select(hass):
    """Test that submitting basic_options advances to sensor_select."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 60,
            CONF_TRACK_IFACE_CLIENTS: True,
            CONF_TRACK_HOSTS_TIMEOUT: 300,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "sensor_select"


async def test_options_flow_complete(hass):
    """Test the full options flow creates an entry with all options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    # Step 1: basic_options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 45,
            CONF_TRACK_IFACE_CLIENTS: False,
            CONF_TRACK_HOSTS_TIMEOUT: 120,
        },
    )

    assert result["step_id"] == "sensor_select"

    # Step 2: sensor_select
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SENSOR_PORT_TRACKER: True,
            CONF_SENSOR_PORT_TRAFFIC: True,
            CONF_TRACK_HOSTS: True,
            CONF_SENSOR_CLIENT_TRAFFIC: False,
            CONF_SENSOR_CLIENT_CAPTIVE: False,
            CONF_SENSOR_SIMPLE_QUEUES: False,
            CONF_SENSOR_NAT: False,
            CONF_SENSOR_MANGLE: False,
            CONF_SENSOR_FILTER: False,
            CONF_SENSOR_KIDCONTROL: False,
            CONF_SENSOR_NETWATCH_TRACKER: False,
            CONF_SENSOR_PPP: False,
            CONF_SENSOR_SCRIPTS: False,
            CONF_SENSOR_ENVIRONMENT: False,
            CONF_SENSOR_POE: False,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCAN_INTERVAL] == 45
    assert result["data"][CONF_TRACK_IFACE_CLIENTS] is False
    assert result["data"][CONF_TRACK_HOSTS_TIMEOUT] == 120
    assert result["data"][CONF_SENSOR_PORT_TRACKER] is True
    assert result["data"][CONF_SENSOR_PORT_TRAFFIC] is True
    assert result["data"][CONF_TRACK_HOSTS] is True


async def test_options_flow_preserves_existing_options(hass):
    """Test that existing options are used as defaults."""
    existing_options = {
        CONF_SCAN_INTERVAL: 90,
        CONF_TRACK_IFACE_CLIENTS: False,
        CONF_TRACK_HOSTS_TIMEOUT: 500,
        CONF_SENSOR_PORT_TRACKER: True,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        options=existing_options,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "basic_options"

    # Submit basic_options then sensor_select to complete the flow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 90,
            CONF_TRACK_IFACE_CLIENTS: False,
            CONF_TRACK_HOSTS_TIMEOUT: 500,
        },
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SENSOR_PORT_TRACKER: True,
            CONF_SENSOR_PORT_TRAFFIC: False,
            CONF_TRACK_HOSTS: False,
            CONF_SENSOR_CLIENT_TRAFFIC: False,
            CONF_SENSOR_CLIENT_CAPTIVE: False,
            CONF_SENSOR_SIMPLE_QUEUES: False,
            CONF_SENSOR_NAT: False,
            CONF_SENSOR_MANGLE: False,
            CONF_SENSOR_FILTER: False,
            CONF_SENSOR_KIDCONTROL: False,
            CONF_SENSOR_NETWATCH_TRACKER: False,
            CONF_SENSOR_PPP: False,
            CONF_SENSOR_SCRIPTS: False,
            CONF_SENSOR_ENVIRONMENT: False,
            CONF_SENSOR_POE: False,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCAN_INTERVAL] == 90
    assert result["data"][CONF_SENSOR_PORT_TRACKER] is True


async def test_options_flow_no_explicit_config_entry_set(hass):
    """Test that the options flow handler does not manually set config_entry.

    This verifies the fix for HA 2025.12+ where config_entry became a
    read-only property on OptionsFlow.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        options={},
    )
    entry.add_to_hass(hass)

    # This should not raise AttributeError about config_entry property
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
