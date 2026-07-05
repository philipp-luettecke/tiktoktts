"""Tests for the config and options flows (config_flow.py).

Covers the user/proxy/direct setup steps, every connection-test failure
branch, the already-configured guards, and the options (reconfigure) flow
for both modes - including session-id sanitising and repair-issue cleanup.
"""

from __future__ import annotations

from unittest.mock import patch

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tiktoktts.const import (
    API_MODE_DIRECT,
    API_MODE_PROXY,
    CONF_API_MODE,
    CONF_ENDPOINT,
    CONF_SESSION_ID,
    CONF_VOICE,
    DEFAULT_PROXY_ENDPOINT,
    DEFAULT_VOICE,
    DIRECT_API_ENDPOINTS,
    DIRECT_API_PATH,
    DOMAIN,
    ISSUE_SESSION_EXPIRED,
)

from .helpers import setup_proxy

STATUS_URL = f"{DEFAULT_PROXY_ENDPOINT}/api/status"
DIRECT_URL_0 = f"{DIRECT_API_ENDPOINTS[0]}{DIRECT_API_PATH}"


async def _start_proxy_form(hass):
    """Advance the config flow to the proxy form and return the result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_MODE: API_MODE_PROXY}
    )
    assert result["step_id"] == "proxy"
    return result


async def _start_direct_form(hass):
    """Advance the config flow to the direct form and return the result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_MODE: API_MODE_DIRECT}
    )
    assert result["step_id"] == "direct"
    return result


# ---------------------------------------------------------------------------
# User step
# ---------------------------------------------------------------------------


async def test_user_step_shows_form(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


# ---------------------------------------------------------------------------
# Proxy setup
# ---------------------------------------------------------------------------


async def test_proxy_setup_success(hass, aioclient_mock) -> None:
    aioclient_mock.get(STATUS_URL, json={"data": {"available": True}})
    form = await _start_proxy_form(hass)
    with patch("custom_components.tiktoktts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"],
            {CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT, CONF_VOICE: DEFAULT_VOICE},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_API_MODE: API_MODE_PROXY,
        CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT,
        CONF_VOICE: DEFAULT_VOICE,
    }


async def test_proxy_setup_strips_trailing_slash(hass, aioclient_mock) -> None:
    aioclient_mock.get(STATUS_URL, json={"data": {"available": True}})
    form = await _start_proxy_form(hass)
    with patch("custom_components.tiktoktts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"],
            {CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT + "/", CONF_VOICE: DEFAULT_VOICE},
        )
    assert result["data"][CONF_ENDPOINT] == DEFAULT_PROXY_ENDPOINT


async def test_proxy_invalid_url_scheme(hass) -> None:
    form = await _start_proxy_form(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {CONF_ENDPOINT: "ftp://nope", CONF_VOICE: DEFAULT_VOICE}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url_scheme"}


@pytest.mark.parametrize(
    ("mock_kwargs", "expected_error"),
    [
        ({"json": {"data": {"available": False}}}, "endpoint_unavailable"),
        ({"status": 503}, "endpoint_bad_status"),
        ({"exc": aiohttp.ClientError()}, "endpoint_connection_error"),
        ({"exc": TimeoutError()}, "endpoint_timeout"),
        ({"exc": ValueError("unexpected")}, "endpoint_unknown_error"),
    ],
)
async def test_proxy_connection_test_failures(
    hass, aioclient_mock, mock_kwargs, expected_error
) -> None:
    aioclient_mock.get(STATUS_URL, **mock_kwargs)
    form = await _start_proxy_form(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT, CONF_VOICE: DEFAULT_VOICE},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_proxy_already_configured(hass, aioclient_mock) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_MODE: API_MODE_PROXY, CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT},
    ).add_to_hass(hass)
    aioclient_mock.get(STATUS_URL, json={"data": {"available": True}})
    form = await _start_proxy_form(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT, CONF_VOICE: DEFAULT_VOICE},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Direct setup
# ---------------------------------------------------------------------------


async def test_direct_setup_success_and_strips_session(hass, aioclient_mock) -> None:
    aioclient_mock.post(DIRECT_URL_0, json={"status_code": 0})
    form = await _start_direct_form(hass)
    with patch("custom_components.tiktoktts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"],
            {
                CONF_ENDPOINT: DIRECT_API_ENDPOINTS[0],
                CONF_SESSION_ID: "  my-session  ",
                CONF_VOICE: DEFAULT_VOICE,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_MODE] == API_MODE_DIRECT
    assert result["data"][CONF_SESSION_ID] == "my-session"  # whitespace stripped


@pytest.mark.parametrize(
    ("mock_kwargs", "expected_error"),
    [
        ({"json": {"status_code": 4, "status_msg": "bad"}}, "direct_api_rejected"),
        ({"status": 500}, "endpoint_bad_status"),
        ({"exc": aiohttp.ClientError()}, "endpoint_connection_error"),
        ({"exc": TimeoutError()}, "endpoint_timeout"),
        ({"exc": ValueError("unexpected")}, "endpoint_unknown_error"),
    ],
)
async def test_direct_connection_test_failures(
    hass, aioclient_mock, mock_kwargs, expected_error
) -> None:
    aioclient_mock.post(DIRECT_URL_0, **mock_kwargs)
    form = await _start_direct_form(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_ENDPOINT: DIRECT_API_ENDPOINTS[0],
            CONF_SESSION_ID: "sess",
            CONF_VOICE: DEFAULT_VOICE,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_direct_already_configured(hass, aioclient_mock) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_MODE: API_MODE_DIRECT, CONF_ENDPOINT: DIRECT_API_ENDPOINTS[0]},
    ).add_to_hass(hass)
    aioclient_mock.post(DIRECT_URL_0, json={"status_code": 0})
    form = await _start_direct_form(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_ENDPOINT: DIRECT_API_ENDPOINTS[0],
            CONF_SESSION_ID: "sess",
            CONF_VOICE: DEFAULT_VOICE,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Options (reconfigure) flow
# ---------------------------------------------------------------------------


async def test_options_flow_proxy_updates_data(
    hass, aioclient_mock, proxy_data
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=proxy_data)
    entry.add_to_hass(hass)
    aioclient_mock.get(STATUS_URL, json={"data": {"available": True}})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    assert CONF_SESSION_ID not in str(result["data_schema"].schema)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT, CONF_VOICE: "en_us_007"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_VOICE] == "en_us_007"
    assert entry.data[CONF_API_MODE] == API_MODE_PROXY  # preserved


async def test_options_flow_direct_updates_and_clears_issue(
    hass, aioclient_mock, direct_data
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=direct_data)
    entry.add_to_hass(hass)
    # Pretend the session previously expired so the repair issue exists.
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_SESSION_EXPIRED,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_SESSION_EXPIRED,
    )
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_SESSION_EXPIRED) is not None

    aioclient_mock.post(DIRECT_URL_0, json={"status_code": 0})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert CONF_SESSION_ID in str(result["data_schema"].schema)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENDPOINT: DIRECT_API_ENDPOINTS[0],
            CONF_SESSION_ID: "fresh-session",
            CONF_VOICE: DEFAULT_VOICE,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_SESSION_ID] == "fresh-session"
    # A successful direct test must clear the expired-session repair issue.
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_SESSION_EXPIRED) is None


async def test_options_flow_invalid_scheme(hass, proxy_data) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=proxy_data)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ENDPOINT: "ftp://bad", CONF_VOICE: DEFAULT_VOICE}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url_scheme"}


async def test_options_flow_test_failure_keeps_data(
    hass, aioclient_mock, proxy_data
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=proxy_data)
    entry.add_to_hass(hass)
    aioclient_mock.get(STATUS_URL, json={"data": {"available": False}})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT, CONF_VOICE: "en_us_007"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "endpoint_unavailable"}
    assert entry.data[CONF_VOICE] == DEFAULT_VOICE  # unchanged


async def test_options_save_reloads_entry_end_to_end(hass, aioclient_mock) -> None:
    """Saving options on a fully set-up entry triggers the update listener,
    which reloads the entry so the new settings take effect immediately."""
    entry = await setup_proxy(hass)
    assert entry.state is ConfigEntryState.LOADED

    aioclient_mock.get(STATUS_URL, json={"data": {"available": True}})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT, CONF_VOICE: "en_us_007"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_VOICE] == "en_us_007"
    # The update listener reloaded the entry back into the LOADED state.
    assert entry.state is ConfigEntryState.LOADED
