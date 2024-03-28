"""ConfigFlow for the TikTokTTS integration."""

import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.components.tts import CONF_LANG
from .const import (
    CONF_ENDPOINT,
    CONF_VOICE,
    DEFAULT_ENDPOINT,
    DEFAULT_LANG,
    DEFAULT_VOICE,
    SUPPORTED_LANGUAGES,
    SUPPORTED_VOICES,
    DOMAIN,
    UUID
)

class TikTokTTSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """TikTokTTS config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, info):
        """Start User Interaction."""
        await self.async_set_unique_id(UUID)
        self._abort_if_unique_id_configured()

        if info is not None:
            valid = await self.is_valid(info)
            if valid:
                return self.async_create_entry(
                    title="TikTokTTS",
                    data={
                        CONF_ENDPOINT: info[CONF_ENDPOINT],
                        CONF_LANG: info[CONF_LANG],
                        CONF_VOICE: info[CONF_VOICE]
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ENDPOINT, default=DEFAULT_ENDPOINT): cv.string,
                    vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): vol.In(SUPPORTED_VOICES),
                    vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES)
                }
                )
        )

    async def is_valid(self, user_input=None):
        """Validate user input."""
        # TODO: build real validation
        if user_input is not None:
            return True
        return False
