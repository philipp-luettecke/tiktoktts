"""Shared fixtures for the TikTok TTS test suite.

The `pytest_homeassistant_custom_component` plugin provides the `hass`,
`aioclient_mock`, and `enable_custom_integrations` fixtures used throughout.
`auto_enable_custom_integrations` is autouse so every test can load the
`tiktoktts` custom integration without opting in explicitly.
"""

from __future__ import annotations

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
    DOMAIN,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the tiktoktts custom integration for every test."""
    yield


@pytest.fixture
def proxy_data() -> dict:
    """Config-entry data for a proxy-mode entry."""
    return {
        CONF_API_MODE: API_MODE_PROXY,
        CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT,
        CONF_VOICE: DEFAULT_VOICE,
    }


@pytest.fixture
def direct_data() -> dict:
    """Config-entry data for a direct-mode entry."""
    return {
        CONF_API_MODE: API_MODE_DIRECT,
        CONF_ENDPOINT: DIRECT_API_ENDPOINTS[0],
        CONF_SESSION_ID: "sessionid-abc123",
        CONF_VOICE: DEFAULT_VOICE,
    }


@pytest.fixture
def proxy_entry(proxy_data) -> MockConfigEntry:
    """A proxy-mode MockConfigEntry (not yet added to hass)."""
    return MockConfigEntry(domain=DOMAIN, data=proxy_data, title="TikTok TTS (proxy)")


@pytest.fixture
def direct_entry(direct_data) -> MockConfigEntry:
    """A direct-mode MockConfigEntry (not yet added to hass)."""
    return MockConfigEntry(domain=DOMAIN, data=direct_data, title="TikTok TTS (direct)")
