"""TikTok TTS platform - Home Assistant TextToSpeechEntity implementation.

This file defines TikTokTTSEntity, the single TTS entity created by this
integration. It handles:

  - Voice selection and language-to-voice mapping
  - Random voice resolution from a user-configured language pool
  - Routing requests to either the proxy API or the direct TikTok API
  - Text chunking for long messages (direct mode only)
  - Retry logic with configurable attempts and backoff delay
  - Automatic endpoint fallback across multiple regional URLs (direct mode)
  - Structured error logging so problems are easy to diagnose in the HA logs
  - HA repair issue raised on expired session_id (direct mode) so the user
    sees a clear action item in the UI rather than just a log entry

API modes
---------
PROXY mode  - POST to {endpoint}/api/generation with JSON body {"text":..., "voice":...}
              Response is JSON {"data": "<base64-encoded mp3>"}.
              The Weilbyte proxy handles chunking internally, so the full message
              text can be sent in one request regardless of length.

DIRECT mode - POST to {endpoint}/media/api/text/speech/invoke/ with query params.
              Response is JSON {"status_code": 0, "data": {"v_str": "<base64 mp3>"}}.
              TikTok enforces a ~200-character limit per request, so long messages
              are split into sentence/word-boundary chunks by _split_text(), each
              fetched individually and then concatenated into one audio file.
              If the configured endpoint fails, the code automatically falls back
              to the other known regional TikTok API URLs (single, shorter attempt
              each - see FALLBACK_* in const.py).

Error handling
--------------
All failure paths raise HomeAssistantError so the failure surfaces in the HA
UI and automation traces. Detailed per-endpoint diagnostics are still written
to the log before raising.

Random voice mode
-----------------
When voice=random is passed in options, async_get_tts_audio picks a voice at
random from the language pool stored in hass.data[DOMAIN][HASS_DATA_RANDOM_LANGS].
Cache uniqueness is handled by the caller: button.py passes a unique _random_seed
in the options dict for each call, which HA includes in the cache key hash so
every random voice call is a guaranteed cache miss. Note that HA checks its
cache BEFORE calling this entity, so automations that pass voice=random should
also pass cache: false - otherwise repeated identical messages may replay
previously cached audio.

Config is read dynamically on every call
-----------------------------------------
All four config properties (_api_mode, _endpoint, _voice, _session_id) are
@property methods that read live from self._config_entry.data on every access.
This means that after the options flow saves new settings and the integration
reloads, the entity immediately uses the updated values - no further restart needed.

Credits
-------
Original integration: Philipp Luttecke (https://github.com/philipp-luettecke/tiktoktts)
Community TTS proxy:  Weilbyte (https://github.com/Weilbyte/tiktok-tts)
Voice list reference: oscie57 (https://github.com/oscie57/tiktok-voice)
Fork author:          Steven Fox / sfox38 (https://github.com/sfox38/tiktoktts)
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from collections.abc import Mapping
import json
import random
from typing import Any

import aiohttp
from homeassistant.components.tts import TextToSpeechEntity, Voice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
)

from .const import (
    ALL_VOICES,
    API_MODE_DIRECT,
    API_MODE_PROXY,
    ATTRIBUTION,
    AUDIO_FORMAT,
    CONF_API_MODE,
    CONF_ENDPOINT,
    CONF_SESSION_ID,
    CONF_VOICE,
    DEFAULT_VOICE,
    DIRECT_API_AID_VALUE,
    DIRECT_API_CHUNK_SIZE,
    DIRECT_API_ENDPOINTS,
    DIRECT_API_FIELD_AUDIO,
    DIRECT_API_FIELD_DATA,
    DIRECT_API_FIELD_STATUS_CODE,
    DIRECT_API_FIELD_STATUS_MSG,
    DIRECT_API_MAP_TYPE_VALUE,
    DIRECT_API_PARAM_AID,
    DIRECT_API_PARAM_MAP_TYPE,
    DIRECT_API_PARAM_SPEAKER,
    DIRECT_API_PARAM_TEXT,
    DIRECT_API_PATH,
    DIRECT_API_STATUS_INVALID_SESSION,
    DIRECT_API_STATUS_OK,
    DIRECT_API_USER_AGENT,
    DIRECT_TOTAL_TIMEOUT,
    DOMAIN,
    FALLBACK_MAX_RETRIES,
    FALLBACK_TIMEOUT,
    HASS_DATA_RANDOM_LANGS,
    ISSUE_SESSION_EXPIRED,
    LOGGER,
    PROXY_API_FIELD_DATA,
    PROXY_API_FIELD_TEXT,
    PROXY_API_FIELD_VOICE,
    PROXY_API_PATH_GENERATE,
    RANDOM_SEED_KEY,
    RANDOM_VOICE_CODE,
    REQUEST_MAX_RETRIES,
    REQUEST_RETRY_DELAY,
    REQUEST_TIMEOUT,
    SUPPORTED_LANGUAGES,
    VOICES_BY_LANGUAGE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Instantiate and register the TikTokTTSEntity for this config entry.

    Called by HA when the integration is loaded. We create exactly one entity
    per config entry (there is normally only one config entry for this integration).
    """
    async_add_entities([TikTokTTSEntity(config_entry)])


class TikTokTTSEntity(TextToSpeechEntity):
    """TikTok TTS entity - the HA entity that services tts.speak action calls.

    Inherits from TextToSpeechEntity and implements:
      - supported_languages / default_language  - language list and default
      - supported_options / default_options      - "voice" option and its default
      - async_get_supported_voices(language)     - per-language voice list
      - async_get_tts_audio(message, language, options) - the main audio fetch method
    """

    _attr_has_entity_name = False
    _attr_attribution = ATTRIBUTION

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Store references - do not read config here.

        Config values are intentionally NOT cached as instance variables.
        They are read live via @property methods below so that any change
        saved through the options UI is picked up immediately after reload,
        without needing to recreate the entity.

        self.hass is assigned by HA when the entity is added via
        async_add_entities, so it is not set here.

        unique_id uses the config_entry.entry_id (a UUID assigned by HA at
        setup time) so that multiple instances can coexist - e.g. one proxy
        entry and one direct API entry. Using a hardcoded string like DOMAIN
        would cause HA to silently discard any second instance as a duplicate.

        The entity_id is set explicitly below based on the API mode:
          - tts.tiktoktts_proxy  (proxy mode)
          - tts.tiktoktts_direct (direct mode)
        The friendly name is provided by a separate name property.
        """
        self._config_entry = config_entry
        # entry_id is a stable UUID assigned by HA - unique across all entries
        self._attr_unique_id = config_entry.entry_id
        # Lock the entity_id explicitly so it is always derived from the domain
        # and mode suffix - not from the friendly name. This means renaming the
        # friendly name in future will never silently break existing automations.
        mode_suffix = (
            API_MODE_DIRECT
            if config_entry.data.get(CONF_API_MODE) == API_MODE_DIRECT
            else API_MODE_PROXY
        )
        self.entity_id = f"tts.{DOMAIN}_{mode_suffix}"
        # Direct mode: endpoint that most recently served a chunk successfully.
        # Tried first on subsequent chunks/calls so a dead configured endpoint
        # is not re-probed (with full retries) for every chunk of a message.
        self._preferred_endpoint: str | None = None

    @property
    def name(self) -> str:
        """Return the friendly (display) name shown in the HA UI.

        The friendly name and entity ID are intentionally decoupled:
          - Friendly name: "TikTokTTS Direct" / "TikTokTTS Proxy"  (shown in UI)
          - Entity ID:      tts.tiktoktts_direct / tts.tiktoktts_proxy

        The entity_id is fixed in __init__ from the domain and mode suffix,
        so HA never re-derives it from this display name.
        """
        if self._api_mode == API_MODE_DIRECT:
            return "TikTokTTS Direct"
        return "TikTokTTS Proxy"

    # ------------------------------------------------------------------
    # Live config properties - always read from entry.data
    # ------------------------------------------------------------------

    @property
    def _data(self) -> Mapping[str, Any]:
        """Return the live config entry data mapping.

        All other config properties below delegate to this one, so there
        is a single point of access to entry.data throughout this class.
        """
        return self._config_entry.data

    @property
    def _api_mode(self) -> str:
        """Return the configured API mode: API_MODE_PROXY or API_MODE_DIRECT."""
        return self._data.get(CONF_API_MODE, API_MODE_PROXY)

    @property
    def _endpoint(self) -> str:
        """Return the configured endpoint URL as a base URL.

        Trailing slashes are stripped so API paths with a leading slash can
        be appended without creating double-slash URLs. (Direct-mode endpoints
        are constrained to a fixed list by the config flow, and the proxy flow
        saves a sanitised URL, so no further normalisation is needed here.)
        """
        return self._data.get(CONF_ENDPOINT, "").rstrip("/")

    @property
    def _voice(self) -> str:
        """Return the configured default voice identifier."""
        return self._data.get(CONF_VOICE, DEFAULT_VOICE)

    @property
    def _session_id(self) -> str:
        """Return the TikTok session_id cookie (direct mode only)."""
        return self._data.get(CONF_SESSION_ID, "")

    # ------------------------------------------------------------------
    # TextToSpeechEntity interface - required by HA
    # ------------------------------------------------------------------

    @property
    def default_language(self) -> str:
        """Return the default language code, derived from the configured default voice.

        Looks up which language group the configured voice belongs to in
        VOICES_BY_LANGUAGE. If the voice is somehow not found (e.g. after a
        const.py edit), falls back to the first language in the list.
        """
        for lang, voices in VOICES_BY_LANGUAGE.items():
            if self._voice in voices:
                return lang
        return SUPPORTED_LANGUAGES[0]

    @property
    def supported_languages(self) -> list[str]:
        """Return all supported language codes (e.g. 'en_us', 'ja', 'de')."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return the list of option keys accepted by async_get_tts_audio.

        'voice' lets callers override the default voice per-call.
        '_random_seed' is a unique value used to force a cache miss when
        random voice mode is active — HA includes all supported_options
        keys in the TTS cache key hash.
        """
        return [CONF_VOICE, RANDOM_SEED_KEY]

    @property
    def default_options(self) -> dict[str, str]:
        """Return default option values, used to pre-populate the UI dropdowns.

        HA reads this when rendering the tts.speak action form, so the voice
        field starts with the user's configured default rather than being blank.
        """
        return {CONF_VOICE: self._voice}

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return the voices available for a specific language.

        HA calls this when the user selects a language in the Automations editor,
        and uses the result to populate the voice dropdown with only the voices
        relevant to that language. Returns None if the language is unrecognised,
        which tells HA to show no voice options for it.

        Note: the Developer Tools -> Actions UI does NOT call this dynamically -
        it shows all voices regardless of language. Filtering only works in the
        full Automation editor UI.
        """
        voices = VOICES_BY_LANGUAGE.get(language)
        if not voices:
            return None
        return [Voice(voice_id=v, name=v) for v in voices]

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any] | None = None,
    ) -> tuple[str, bytes]:
        """Fetch TTS audio for the given message and return (format, bytes).

        This is the main entry point called by HA for every tts.speak action.
        Returns (AUDIO_FORMAT, mp3_bytes) on success and raises
        HomeAssistantError on failure.

        Voice resolution order:
          1. Explicit voice in options dict (e.g. options={"voice": "en_us_007"}),
             unless it is the configured default voice - HA auto-injects that
             via default_options on every call, so it is treated as "no explicit
             choice" and validated against the requested language (step 3).
          2. "random" sentinel - resolved to a random pool voice (see below)
          3. Configured default voice, if it belongs to the requested language
          4. First voice in VOICES_BY_LANGUAGE for the requested language
          5. Global DEFAULT_VOICE constant as a last resort
        """
        # Copy before mutating - HA owns the dict that is passed in.
        options = dict(options) if options else {}
        options.pop(RANDOM_SEED_KEY, None)

        voice = options.get(CONF_VOICE)

        if voice == RANDOM_VOICE_CODE:
            # Pick a random voice from the configured language pool.
            # Falls back to DEFAULT_VOICE if the pool is empty or not configured.
            langs = self.hass.data.get(DOMAIN, {}).get(HASS_DATA_RANDOM_LANGS, [])
            pool = [v for lang in langs for v in VOICES_BY_LANGUAGE.get(lang, [])]
            if pool:
                voice = random.choice(pool)
                LOGGER.debug("Random voice selected: %s", voice)
            else:
                voice = DEFAULT_VOICE
                LOGGER.warning(
                    "Random voice language pool is empty; using default voice"
                )
        elif not voice or voice == self._voice:
            # No explicit voice, or HA injected the configured default via
            # default_options. Honour the requested language: keep the default
            # voice only if it belongs to that language, otherwise fall back
            # to the first voice of the language.
            lang_voices = VOICES_BY_LANGUAGE.get(language, [])
            if self._voice in lang_voices:
                voice = self._voice
            elif lang_voices:
                voice = lang_voices[0]
                LOGGER.debug(
                    "Default voice '%s' is not in language '%s'; using '%s' instead",
                    self._voice,
                    language,
                    voice,
                )
            else:
                voice = self._voice or DEFAULT_VOICE
                LOGGER.warning(
                    "No voices found for language '%s'; falling back to '%s'",
                    language,
                    voice,
                )
        elif voice not in ALL_VOICES:
            # Unknown voice IDs are passed through so users can test
            # undocumented voices. TikTok silently substitutes its default
            # voice if the ID is invalid, so there is no harm in trying.
            LOGGER.debug(
                "Voice '%s' is not a known voice - sending to API anyway. "
                "If it sounds like the default voice, the ID is not recognised by TikTok.",
                voice,
            )

        if self._api_mode == API_MODE_DIRECT:
            return await self._get_audio_direct(message, voice)
        return await self._get_audio_proxy(message, voice)

    # ------------------------------------------------------------------
    # Proxy API implementation
    # ------------------------------------------------------------------

    async def _get_audio_proxy(self, message: str, voice: str) -> tuple[str, bytes]:
        """Fetch TTS audio from the community proxy endpoint.

        The proxy accepts the full message text regardless of length - it handles
        chunking internally before forwarding to TikTok.

        Request:  POST {endpoint}/api/generation
                  Body: {"text": <message>, "voice": <voice_id>}
        Response: {"data": "<base64-encoded mp3>"}

        Retries up to REQUEST_MAX_RETRIES times with REQUEST_RETRY_DELAY seconds
        between attempts. Raises HomeAssistantError if all attempts fail or the
        proxy returns an unusable response.
        """
        session = async_get_clientsession(self.hass)

        for attempt in range(REQUEST_MAX_RETRIES + 1):
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    async with session.post(
                        f"{self._endpoint}{PROXY_API_PATH_GENERATE}",
                        json={
                            PROXY_API_FIELD_TEXT: message,
                            PROXY_API_FIELD_VOICE: voice,
                        },
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            LOGGER.error(
                                "Proxy API returned HTTP %d from %s: %s",
                                resp.status,
                                self._endpoint,
                                body,
                            )
                            raise HomeAssistantError(
                                f"TikTok TTS proxy returned HTTP {resp.status}"
                            )
                        raw = await resp.read()

                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    LOGGER.error("Proxy API returned non-JSON response: %s", exc)
                    raise HomeAssistantError(
                        "TikTok TTS proxy returned an invalid (non-JSON) response"
                    ) from exc

                if PROXY_API_FIELD_DATA not in payload:
                    LOGGER.error(
                        "Proxy API response is missing the '%s' field. "
                        "The proxy may have returned an error body: %s",
                        PROXY_API_FIELD_DATA,
                        payload,
                    )
                    raise HomeAssistantError(
                        "TikTok TTS proxy response did not contain audio data"
                    )

                try:
                    return AUDIO_FORMAT, base64.b64decode(payload[PROXY_API_FIELD_DATA])
                except binascii.Error as exc:
                    LOGGER.error("Proxy API: base64 decode failed: %s", exc)
                    raise HomeAssistantError(
                        "TikTok TTS proxy returned corrupt audio data"
                    ) from exc

            except asyncio.TimeoutError:
                LOGGER.warning(
                    "Proxy API timed out (attempt %d of %d)",
                    attempt + 1,
                    REQUEST_MAX_RETRIES + 1,
                )
            except aiohttp.ClientError as exc:
                LOGGER.warning(
                    "Proxy API connection error (attempt %d of %d): %s",
                    attempt + 1,
                    REQUEST_MAX_RETRIES + 1,
                    exc,
                )

            if attempt < REQUEST_MAX_RETRIES:
                await asyncio.sleep(REQUEST_RETRY_DELAY)

        LOGGER.error(
            "Proxy API failed after %d attempts against endpoint '%s'. "
            "Check that the endpoint is reachable, or switch to a different "
            "endpoint via Settings -> Devices & Services -> TikTok TTS -> Configure.",
            REQUEST_MAX_RETRIES + 1,
            self._endpoint,
        )
        raise HomeAssistantError(
            f"TikTok TTS proxy unreachable after {REQUEST_MAX_RETRIES + 1} attempts "
            f"({self._endpoint})"
        )

    # ------------------------------------------------------------------
    # Direct TikTok API implementation
    # ------------------------------------------------------------------

    async def _get_audio_direct(self, message: str, voice: str) -> tuple[str, bytes]:
        """Fetch TTS audio by calling TikTok's internal API directly.

        Because TikTok enforces a per-request character limit of DIRECT_API_CHUNK_SIZE,
        long messages are first split into smaller chunks by _split_text(). Each chunk
        is fetched as a separate API call, and the resulting MP3 bytes are concatenated
        into a single audio file before returning.

        If any individual chunk fails (across all retry attempts and all fallback
        endpoints), raises HomeAssistantError to avoid returning truncated audio.
        The whole message is bounded by DIRECT_TOTAL_TIMEOUT so a long message
        during an outage cannot stall the tts.speak call for many minutes while
        every chunk walks the full endpoint list.
        """
        chunks = _split_text(message, DIRECT_API_CHUNK_SIZE)
        LOGGER.debug(
            "Direct API: message split into %d chunk(s) for voice '%s'",
            len(chunks),
            voice,
        )

        audio_parts: list[bytes] = []
        try:
            async with asyncio.timeout(DIRECT_TOTAL_TIMEOUT):
                for i, chunk in enumerate(chunks):
                    part = await self._fetch_direct_chunk(chunk, voice, chunk_index=i)
                    audio_parts.append(part)
        except TimeoutError:
            LOGGER.error(
                "Direct API: message did not complete within %d s "
                "(%d of %d chunks fetched) - giving up",
                DIRECT_TOTAL_TIMEOUT,
                len(audio_parts),
                len(chunks),
            )
            raise HomeAssistantError(
                f"TikTok TTS direct API timed out after {DIRECT_TOTAL_TIMEOUT} s"
            ) from None

        return AUDIO_FORMAT, b"".join(audio_parts)

    async def _fetch_direct_chunk(
        self, text: str, voice: str, chunk_index: int = 0
    ) -> bytes:
        """Fetch a single text chunk from the TikTok direct API.

        Tries the last known-good endpoint first (falling back to the user's
        configured endpoint when none is known) with the full retry budget
        (REQUEST_MAX_RETRIES attempts, REQUEST_TIMEOUT seconds each). If it
        fails (HTTP error, timeout, or a non-zero TikTok status_code), moves
        through the remaining endpoints in DIRECT_API_ENDPOINTS with a single
        shorter attempt each (FALLBACK_MAX_RETRIES, FALLBACK_TIMEOUT). The
        endpoint that serves a chunk successfully is remembered, so later
        chunks (and later calls) do not re-probe a dead configured endpoint
        with full retries every time.

        The one exception is status_code 4 (invalid/expired session_id) - in
        that case we give up immediately across all endpoints, since the session_id
        is a global credential and retrying with it against other regional endpoints
        is pointless. A HA repair issue is also raised so the user sees a clear
        action item in the Settings UI, not just a buried log entry.

        Request:  POST {endpoint}/media/api/text/speech/invoke/
                  Params: text_speaker, req_text, speaker_map_type, aid
                  Headers: User-Agent (spoofed Android app), Cookie (sessionid=...)
        Response: {"status_code": 0, "data": {"v_str": "<base64 mp3>"}}
        """
        session = async_get_clientsession(self.hass)
        headers = {
            "User-Agent": DIRECT_API_USER_AGENT,
            "Cookie": f"sessionid={self._session_id}",
        }
        params = {
            DIRECT_API_PARAM_SPEAKER: voice,
            DIRECT_API_PARAM_TEXT: text,
            DIRECT_API_PARAM_MAP_TYPE: DIRECT_API_MAP_TYPE_VALUE,
            DIRECT_API_PARAM_AID: DIRECT_API_AID_VALUE,
        }

        # Build the ordered endpoint list: last known-good endpoint (or the
        # configured one) first with the full retry budget, then the
        # configured endpoint and remaining fallbacks with one short attempt.
        primary = self._preferred_endpoint or self._endpoint
        fallbacks = [
            ep
            for ep in dict.fromkeys([self._endpoint, *DIRECT_API_ENDPOINTS])
            if ep != primary
        ]
        endpoint_configs = [(primary, REQUEST_MAX_RETRIES, REQUEST_TIMEOUT)] + [
            (ep, FALLBACK_MAX_RETRIES, FALLBACK_TIMEOUT) for ep in fallbacks
        ]

        for endpoint, max_retries, timeout in endpoint_configs:
            for attempt in range(max_retries + 1):
                try:
                    async with asyncio.timeout(timeout):
                        async with session.post(
                            f"{endpoint}{DIRECT_API_PATH}",
                            params=params,
                            headers=headers,
                        ) as resp:
                            if resp.status != 200:
                                LOGGER.warning(
                                    "Direct API: HTTP %d from %s (chunk %d, attempt %d)",
                                    resp.status,
                                    endpoint,
                                    chunk_index,
                                    attempt + 1,
                                )
                                break  # Non-200 from this endpoint - skip to next one

                            payload = await resp.json()

                        status_code = payload.get(DIRECT_API_FIELD_STATUS_CODE)

                        if status_code == DIRECT_API_STATUS_OK:
                            vstr = payload.get(DIRECT_API_FIELD_DATA, {}).get(
                                DIRECT_API_FIELD_AUDIO, ""
                            )
                            if not vstr:
                                LOGGER.error(
                                    "Direct API returned status OK but empty audio "
                                    "data for chunk %d",
                                    chunk_index,
                                )
                                raise HomeAssistantError(
                                    f"TikTok TTS direct API returned empty audio for chunk {chunk_index}"
                                )
                            try:
                                audio = base64.b64decode(vstr)
                            except binascii.Error as exc:
                                LOGGER.error(
                                    "Direct API: base64 decode failed for chunk %d: %s",
                                    chunk_index,
                                    exc,
                                )
                                raise HomeAssistantError(
                                    f"TikTok TTS direct API returned corrupt audio for chunk {chunk_index}"
                                ) from exc
                            self._preferred_endpoint = endpoint
                            return audio

                        # Non-zero TikTok status codes indicate API-level errors
                        status_msg = payload.get(DIRECT_API_FIELD_STATUS_MSG, "unknown")

                        if status_code == DIRECT_API_STATUS_INVALID_SESSION:
                            # Session ID is invalid or has expired globally -
                            # no other endpoint will accept it either, so we
                            # raise immediately to avoid wasting time hitting
                            # more endpoints that will all return the same error.
                            LOGGER.error(
                                "Direct API: session_id is invalid or has expired. "
                                "Go to Settings -> Devices & Services -> TikTok TTS "
                                "-> Configure to update your TikTok session_id."
                            )
                            async_create_issue(
                                self.hass,
                                DOMAIN,
                                ISSUE_SESSION_EXPIRED,
                                is_fixable=False,
                                severity=IssueSeverity.ERROR,
                                translation_key=ISSUE_SESSION_EXPIRED,
                            )
                            raise HomeAssistantError(
                                "TikTok TTS session_id is invalid or has expired. "
                                "Update it via Settings -> Devices & Services -> TikTok TTS -> Configure."
                            )

                        LOGGER.warning(
                            "Direct API: TikTok returned status %d ('%s') "
                            "for chunk %d at endpoint %s - trying next endpoint",
                            status_code,
                            status_msg,
                            chunk_index,
                            endpoint,
                        )
                        break  # Non-zero status from this endpoint - try the next one

                except asyncio.TimeoutError:
                    LOGGER.warning(
                        "Direct API: request timed out at %s (chunk %d, attempt %d)",
                        endpoint,
                        chunk_index,
                        attempt + 1,
                    )
                except aiohttp.ClientError as exc:
                    LOGGER.warning(
                        "Direct API: connection error at %s (chunk %d, attempt %d): %s",
                        endpoint,
                        chunk_index,
                        attempt + 1,
                        exc,
                    )

                if attempt < max_retries:
                    await asyncio.sleep(REQUEST_RETRY_DELAY)

        LOGGER.error(
            "Direct API: chunk %d failed across all %d known endpoints. "
            "TikTok may have changed their internal API, or your session_id "
            "may be invalid. Check the HA logs for per-endpoint error details.",
            chunk_index,
            len(endpoint_configs),
        )
        raise HomeAssistantError(
            f"TikTok TTS direct API failed for chunk {chunk_index} "
            f"across all {len(endpoint_configs)} known endpoints"
        )


# ------------------------------------------------------------------
# Text chunking helper
# ------------------------------------------------------------------


def _split_text(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks of at most chunk_size characters.

    Used by the direct API path because TikTok's internal API enforces a
    per-request character limit (DIRECT_API_CHUNK_SIZE = 200).

    Split priority:
      1. Sentence boundary - looks for the last '. ', '! ', or '? ' within
         the allowed window and splits after the punctuation mark. Using
         delimiter+space avoids false splits on abbreviations (Dr., U.S.),
         numbers (3.14), and URLs. Produces the most natural-sounding audio
         since each chunk ends at a complete sentence.
      2. Word boundary - if no sentence boundary exists, splits at the last
         space within the window. Avoids cutting words in half.
      3. Hard split - last resort if the text contains no spaces or punctuation
         within the window (e.g. a very long URL or foreign-language text without
         spaces). Splits at exactly chunk_size characters.

    Returns a list of chunks. Input that fits within chunk_size is returned
    unchanged as a single-element list (so empty input yields [""]); text
    that needed splitting always produces non-empty chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    remaining = text.strip()

    while len(remaining) > chunk_size:
        window = remaining[:chunk_size]
        split_pos = -1

        # Look for sentence-ending punctuation followed by a space, so we
        # don't split on periods in abbreviations ("Dr."), decimals ("3.14"),
        # or URLs ("example.com").
        for delimiter in (". ", "! ", "? "):
            pos = window.rfind(delimiter)
            if pos > split_pos:
                split_pos = pos

        # Also check if the window ends exactly on punctuation
        if split_pos < 0 and window[-1] in ".!?":
            split_pos = len(window) - 1

        if split_pos > 0:
            chunks.append(remaining[: split_pos + 1].strip())
            remaining = remaining[split_pos + 1 :].strip()
        else:
            # No sentence boundary - try splitting on the last space
            space_pos = window.rfind(" ")
            if space_pos > 0:
                chunks.append(remaining[:space_pos].strip())
                remaining = remaining[space_pos:].strip()
            else:
                # No natural split point - hard cut at chunk_size
                chunks.append(remaining[:chunk_size])
                remaining = remaining[chunk_size:]

    if remaining:
        chunks.append(remaining)

    return chunks
