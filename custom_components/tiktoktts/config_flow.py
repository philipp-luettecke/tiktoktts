"""Config flow for TikTok TTS.

This file implements two HA flow classes:

  TikTokTTSConfigFlow  - the initial setup wizard, shown when the user clicks
                         "+ Add Integration" and selects TikTok TTS.
                         Steps: user (choose mode) -> proxy or direct (configure).

  TikTokTTSOptionsFlow - the reconfigure screen, shown when the user clicks the
                         gear icon on an already-configured integration.
                         Single step: init (edit endpoint/session_id/voice).

Both flows perform a live connection test before saving, so failures are caught
at setup time with a user-friendly error message rather than silently at runtime.

Storage convention
------------------
All settings are stored in entry.data (not entry.options). This is intentional -
it keeps a single source of truth that tts.py reads from via self._config_entry.data.
The options flow writes changes back to entry.data via async_update_entry(), then
returns an empty async_create_entry() to close the flow. The update listener in
__init__.py detects the data change and reloads the integration automatically.

Error key -> UI message mapping is defined in strings.json / translations/en.json.
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import async_delete_issue
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .const import (
    ALL_VOICES,
    API_MODE_DIRECT,
    API_MODE_PROXY,
    CONF_API_MODE,
    CONF_ENDPOINT,
    CONF_SESSION_ID,
    CONF_VOICE,
    DEFAULT_PROXY_ENDPOINT,
    DEFAULT_VOICE,
    DIRECT_API_AID_VALUE,
    DIRECT_API_ENDPOINTS,
    DIRECT_API_FIELD_STATUS_CODE,
    DIRECT_API_MAP_TYPE_VALUE,
    DIRECT_API_PARAM_AID,
    DIRECT_API_PARAM_MAP_TYPE,
    DIRECT_API_PARAM_SPEAKER,
    DIRECT_API_PARAM_TEXT,
    DIRECT_API_PATH,
    DIRECT_API_STATUS_OK,
    DIRECT_API_USER_AGENT,
    DOMAIN,
    FORK_REPO,
    ISSUE_SESSION_EXPIRED,
    LOGGER,
    ORIGINAL_REPO,
    PROXY_API_FIELD_AVAILABLE,
    PROXY_API_PATH_STATUS,
    WEILBYTE_REPO,
)

# Timeout (seconds) used only during connection tests in this file.
# The runtime request timeout for actual TTS generation is REQUEST_TIMEOUT in const.py.
_TEST_TIMEOUT = 10

# Masks the TikTok session_id in the setup and options forms - it is a
# credential and should not be echoed on screen.
_SESSION_ID_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


# ---------------------------------------------------------------------------
# Connection test helpers
# ---------------------------------------------------------------------------


async def _test_proxy_endpoint(hass: HomeAssistant, endpoint: str) -> str | None:
    """Check that a proxy endpoint is reachable and reports itself as available.

    Calls GET {endpoint}/api/status and inspects the JSON response.
    The Weilbyte proxy returns {"data": {"available": true}} when healthy.

    Returns None on success, or an error key string that maps to a translated
    error message in strings.json on failure.
    """
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(_TEST_TIMEOUT):
            async with session.get(f"{endpoint}{PROXY_API_PATH_STATUS}") as resp:
                if resp.status != 200:
                    return "endpoint_bad_status"
                data = await resp.json()
        if data.get("data", {}).get(PROXY_API_FIELD_AVAILABLE) is True:
            return None  # Success - endpoint is up and available
        return "endpoint_unavailable"
    except asyncio.TimeoutError:
        return "endpoint_timeout"
    except aiohttp.ClientError:
        return "endpoint_connection_error"
    except Exception:  # noqa: BLE001 - catch-all so the flow never crashes
        LOGGER.exception("Unexpected error testing proxy endpoint %s", endpoint)
        return "endpoint_unknown_error"


async def _test_direct_endpoint(
    hass: HomeAssistant, endpoint: str, session_id: str
) -> str | None:
    """Check that a TikTok direct API endpoint accepts our session_id.

    Sends a minimal real TTS request (single word, known-good voice) and checks
    the TikTok status_code in the response JSON. A status_code of 0 means success.

    Returns None on success, or an error key string on failure. Error keys map to
    translated messages in strings.json.

    Note: This fires an actual TTS request to TikTok's servers, which is the only
    reliable way to validate a session_id before saving it.
    """
    session = async_get_clientsession(hass)
    headers = {
        "User-Agent": DIRECT_API_USER_AGENT,
        "Cookie": f"sessionid={session_id}",
    }
    # Minimal payload - single word to keep the test fast and cheap
    params = {
        DIRECT_API_PARAM_SPEAKER: DEFAULT_VOICE,
        DIRECT_API_PARAM_TEXT: "test",
        DIRECT_API_PARAM_MAP_TYPE: DIRECT_API_MAP_TYPE_VALUE,
        DIRECT_API_PARAM_AID: DIRECT_API_AID_VALUE,
    }
    try:
        async with asyncio.timeout(_TEST_TIMEOUT):
            async with session.post(
                f"{endpoint}{DIRECT_API_PATH}",
                params=params,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    return "endpoint_bad_status"
                data = await resp.json()
        if data.get(DIRECT_API_FIELD_STATUS_CODE) == DIRECT_API_STATUS_OK:
            return None  # Success - endpoint accepted the session_id
        LOGGER.debug("Direct API test rejected: %s", data.get("status_msg", "unknown"))
        return "direct_api_rejected"
    except asyncio.TimeoutError:
        return "endpoint_timeout"
    except aiohttp.ClientError:
        return "endpoint_connection_error"
    except Exception:  # noqa: BLE001 - catch-all so the flow never crashes
        LOGGER.exception("Unexpected error testing direct endpoint %s", endpoint)
        return "endpoint_unknown_error"


# ---------------------------------------------------------------------------
# Initial setup flow
# ---------------------------------------------------------------------------


class TikTokTTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Multi-step config flow for initial integration setup.

    Step 1 - async_step_user:   user chooses proxy or direct mode.
    Step 2a - async_step_proxy: user enters proxy URL and default voice.
    Step 2b - async_step_direct: user enters TikTok endpoint, session_id, and voice.

    The VERSION class attribute controls config entry migration. Increment it
    and add an async_migrate_entry() function in __init__.py if you ever change
    the structure of the data dict stored in entry.data.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Ask the user which connection mode they want.

        user_input is None on the first render (HA is displaying the form).
        When the user submits the form, HA calls this method again with their
        selections in user_input, and we branch to the appropriate next step.
        """
        if user_input is not None:
            if user_input[CONF_API_MODE] == API_MODE_PROXY:
                return await self.async_step_proxy()
            return await self.async_step_direct()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_MODE, default=API_MODE_PROXY): vol.In(
                        {
                            API_MODE_PROXY: "Community Proxy (recommended, no account needed)",
                            API_MODE_DIRECT: (
                                "Direct TikTok API (requires TikTok account session ID - "
                                "may violate TikTok ToS)"
                            ),
                        }
                    )
                }
            ),
            description_placeholders={
                "weilbyte_url": WEILBYTE_REPO,
                "original_url": ORIGINAL_REPO,
                "fork_url": FORK_REPO,
            },
        )

    async def async_step_proxy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2a: Configure the community proxy endpoint.

        Tests the endpoint before saving. If the test fails, re-renders the
        form with the appropriate error message from strings.json.
        On success, creates the config entry and closes the flow.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            endpoint = user_input[CONF_ENDPOINT].rstrip("/")
            if not endpoint.lower().startswith(("http://", "https://")):
                errors["base"] = "invalid_url_scheme"
            else:
                error = await _test_proxy_endpoint(self.hass, endpoint)
                if error:
                    errors["base"] = error
                else:
                    for entry in self.hass.config_entries.async_entries(DOMAIN):
                        if entry.data.get(CONF_API_MODE) == API_MODE_PROXY:
                            return self.async_abort(reason="already_configured")
                    return self.async_create_entry(
                        title=f"TikTok TTS (proxy: {endpoint})",
                        data={
                            CONF_API_MODE: API_MODE_PROXY,
                            CONF_ENDPOINT: endpoint,
                            CONF_VOICE: user_input[CONF_VOICE],
                        },
                    )

        return self.async_show_form(
            step_id="proxy",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENDPOINT, default=DEFAULT_PROXY_ENDPOINT
                    ): cv.string,
                    vol.Required(CONF_VOICE, default=DEFAULT_VOICE): vol.In(ALL_VOICES),
                }
            ),
            errors=errors,
            description_placeholders={
                "default_endpoint": DEFAULT_PROXY_ENDPOINT,
                "weilbyte_url": WEILBYTE_REPO,
            },
        )

    async def async_step_direct(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2b: Configure the direct TikTok API connection.

        Validates the session_id by sending a live test request to TikTok
        before saving. If TikTok rejects it, the user sees a clear error
        rather than a silent failure at runtime.
        On success, creates the config entry and closes the flow.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            endpoint = user_input[CONF_ENDPOINT].rstrip("/")
            session_id = user_input[CONF_SESSION_ID].strip()
            error = await _test_direct_endpoint(self.hass, endpoint, session_id)
            if error:
                errors["base"] = error
            else:
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.data.get(CONF_API_MODE) == API_MODE_DIRECT:
                        return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title="TikTok TTS (direct API)",
                    data={
                        CONF_API_MODE: API_MODE_DIRECT,
                        CONF_ENDPOINT: endpoint,
                        CONF_SESSION_ID: session_id,
                        CONF_VOICE: user_input[CONF_VOICE],
                    },
                )

        return self.async_show_form(
            step_id="direct",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENDPOINT, default=DIRECT_API_ENDPOINTS[0]
                    ): vol.In(DIRECT_API_ENDPOINTS),
                    vol.Required(CONF_SESSION_ID): _SESSION_ID_SELECTOR,
                    vol.Required(CONF_VOICE, default=DEFAULT_VOICE): vol.In(ALL_VOICES),
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TikTokTTSOptionsFlow:
        """Tell HA which class handles the options (gear icon) flow for this entry."""
        return TikTokTTSOptionsFlow()


# ---------------------------------------------------------------------------
# Options (reconfigure) flow
# ---------------------------------------------------------------------------


class TikTokTTSOptionsFlow(OptionsFlow):
    """Reconfigure flow shown when the user clicks the gear icon.

    Single step (init) that lets the user change the endpoint URL, session_id
    (direct mode only), or default voice - without having to delete and re-add
    the integration.

    Important HA quirk: do NOT define __init__ or assign self.config_entry here.
    In modern HA the base OptionsFlow class injects self.config_entry automatically.
    Defining your own __init__ that sets it causes a 500 error when the gear
    icon is clicked.

    Storage convention: saves directly to entry.data (not entry.options) via
    async_update_entry(), so tts.py always reads from one place. See the module
    docstring for the full explanation.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display and process the options form.

        Pre-fills all fields from the current entry.data values so the user
        sees their existing settings rather than blanks.

        On submit:
          1. Runs the same connection test as the setup wizard.
          2. On success, merges user_input into the existing entry.data dict
             (preserving CONF_API_MODE and any other keys not shown in the form),
             writes it back via async_update_entry(), then closes the flow with
             an empty async_create_entry().
          3. The update listener in __init__.py detects the data change and
             reloads the integration, picking up the new values immediately.
        """
        errors: dict[str, str] = {}

        # entry.data is always the source of truth - read current values from there
        current = self.config_entry.data
        api_mode = current.get(CONF_API_MODE, API_MODE_PROXY)

        if user_input is not None:
            endpoint = user_input[CONF_ENDPOINT].rstrip("/")

            if not endpoint.lower().startswith(("http://", "https://")):
                errors["base"] = "invalid_url_scheme"
            else:
                if api_mode == API_MODE_PROXY:
                    error = await _test_proxy_endpoint(self.hass, endpoint)
                    session_id = None
                else:
                    session_id = user_input.get(CONF_SESSION_ID, "").strip()
                    error = await _test_direct_endpoint(self.hass, endpoint, session_id)

                if error:
                    errors["base"] = error
                else:
                    # Build sanitized data: merge current with sanitized values
                    # (do NOT spread raw user_input - it may contain unsanitized strings)
                    sanitized: dict = {
                        **current,
                        CONF_ENDPOINT: endpoint,
                        CONF_VOICE: user_input[CONF_VOICE],
                    }
                    if session_id is not None:
                        sanitized[CONF_SESSION_ID] = session_id
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=sanitized
                    )
                    # Clear the session-expired repair issue if a direct-mode
                    # test just succeeded - the user has provided a valid session_id.
                    if api_mode == API_MODE_DIRECT:
                        async_delete_issue(self.hass, DOMAIN, ISSUE_SESSION_EXPIRED)
                    return self.async_create_entry(title="", data={})

        # Build the form schema, choosing fields appropriate to the current mode.
        # Proxy mode shows: endpoint URL + voice.
        # Direct mode shows: endpoint selector + session_id + voice.
        if api_mode == API_MODE_PROXY:
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_ENDPOINT,
                        default=current.get(CONF_ENDPOINT, DEFAULT_PROXY_ENDPOINT),
                    ): cv.string,
                    vol.Required(
                        CONF_VOICE,
                        default=current.get(CONF_VOICE, DEFAULT_VOICE),
                    ): vol.In(ALL_VOICES),
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_ENDPOINT,
                        default=current.get(CONF_ENDPOINT, DIRECT_API_ENDPOINTS[0]),
                    ): vol.In(DIRECT_API_ENDPOINTS),
                    vol.Required(
                        CONF_SESSION_ID,
                        default=current.get(CONF_SESSION_ID, ""),
                    ): _SESSION_ID_SELECTOR,
                    vol.Required(
                        CONF_VOICE,
                        default=current.get(CONF_VOICE, DEFAULT_VOICE),
                    ): vol.In(ALL_VOICES),
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
