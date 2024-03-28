"""Support for the TikTokTTS service."""
from __future__ import annotations

import logging
import json
import base64
import asyncio
from http import HTTPStatus

import voluptuous as vol
import aiohttp
import async_timeout

from homeassistant.components.tts import CONF_LANG, PLATFORM_SCHEMA, TextToSpeechEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENDPOINT,
    CONF_VOICE,
    DEFAULT_ENDPOINT,
    DEFAULT_LANG,
    DEFAULT_VOICE,
    SUPPORTED_LANGUAGES,
    SUPPORTED_OPTIONS,
    SUPPORTED_VOICES,
    DEFAULT_VOICES
    )


_LOGGER = logging.getLogger(__name__)

# Platform schema for configuration via configuration.yml
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ENDPOINT, default=DEFAULT_ENDPOINT): cv.string,
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): vol.In(SUPPORTED_VOICES),
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORTED_LANGUAGES),
    }
)


def get_engine(hass, config, discovery_info=None):
    """Set up TikTokTTS speech component."""
    return TikTokTTSProvider(hass, config)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TikTok text-to-speech."""
    #provider: TikTokTTSProvider = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            TikTokTTSProvider(hass, config_entry)
        ]
    )
    _LOGGER.debug("Entity added")

class TikTokTTSProvider(TextToSpeechEntity):
    """TikTokTTS speech api provider."""

    def __init__(self, hass: HomeAssistant, conf: ConfigEntry):
        """Init TikTokTTS TTS service."""
        self.hass = hass
        self.name = "TikTokTTS"
        self._endpoint = conf.data.get(CONF_ENDPOINT)
        self._voice = conf.data.get(CONF_VOICE)
        self._language = conf.data.get(CONF_LANG)

        self._attr_name = self.name.lower()
        self._attr_unique_id = f"{conf.entry_id}-tts"

    @property
    def supported_languages(self):
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def default_language(self):
        """Return the default language."""
        return self._language

    @property
    def supported_options(self):
        """Return list of supported options."""
        return SUPPORTED_OPTIONS

    async def async_get_tts_audio(self, message, language, options=None):
        """Load TTS from TikTokTTS."""

        websession = async_get_clientsession(self.hass)
        # actual_language = language
        options = options or {}

        try:
            async with async_timeout.timeout(20):
                if (language is not None):
                    voice = DEFAULT_VOICES[language]
                else:
                    voice = options.get(CONF_VOICE, self._voice)
                post_data = {
                    "text": message,
                    "voice": voice,
                }

                request = await websession.post(
                    url=self._endpoint + "/api/generation", json=post_data
                )
                _LOGGER.debug("Received answer from REST Endpoint")

                if request.status != HTTPStatus.OK:
                    _LOGGER.error(
                        "Error %d on load URL %s", request.status, request.url
                    )
                    _LOGGER.error(request)
                    return (None, None)

                data = await request.read()
                audio = json.loads(data.decode("utf8"))
                data = base64.b64decode(audio["data"])
                audiotype = "mp3"
                _LOGGER.debug("Decoding worked fine - will now return this data")

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout for TikTokTTS API")
            return (None, None)
        return audiotype, data

    async def service_available(self):
        """Check for availability of the service."""
        websession = async_get_clientsession(self.hass)
        request = await websession.get(
            url=self._endpoint + "/api/status"
        )
        result = await request.read()
        result = result.json()
        if result["data"]:
           if result["data"]["available"] is True:
               _LOGGER.info("Service available")
           else:
               _LOGGER.error("Service unavailable")
               return None, None
