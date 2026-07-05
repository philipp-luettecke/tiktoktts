"""Tests for the TikTokTTSEntity (tts.py).

The entity is exercised directly (constructed with a MockConfigEntry and the
test ``hass``) rather than through full platform setup, so each network path,
retry, and fallback can be driven precisely with ``aioclient_mock``.
"""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import patch

import aiohttp
from homeassistant.components.tts import Voice
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tiktoktts import tts
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
    ENTITY_ID_TTS_DIRECT,
    ENTITY_ID_TTS_PROXY,
    HASS_DATA_RANDOM_LANGS,
    ISSUE_SESSION_EXPIRED,
    RANDOM_SEED_KEY,
    REQUEST_MAX_RETRIES,
    SUPPORTED_LANGUAGES,
    VOICES_BY_LANGUAGE,
)
from custom_components.tiktoktts.tts import TikTokTTSEntity

AUDIO = b"\xff\xfb\x90fake-mp3-bytes"
B64 = base64.b64encode(AUDIO).decode()
PROXY_URL = f"{DEFAULT_PROXY_ENDPOINT}/api/generation"
DIRECT_URL_0 = f"{DIRECT_API_ENDPOINTS[0]}{DIRECT_API_PATH}"


@pytest.fixture(autouse=True)
def _instant_retries(monkeypatch):
    """Zero the inter-retry delay so retry paths run instantly."""
    monkeypatch.setattr(tts, "REQUEST_RETRY_DELAY", 0)


def _make_entity(hass, data: dict) -> TikTokTTSEntity:
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    entity = TikTokTTSEntity(entry)
    entity.hass = hass
    return entity


def _proxy_entity(hass, **overrides) -> TikTokTTSEntity:
    data = {
        CONF_API_MODE: API_MODE_PROXY,
        CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT,
        CONF_VOICE: DEFAULT_VOICE,
    }
    data.update(overrides)
    return _make_entity(hass, data)


def _direct_entity(hass, **overrides) -> TikTokTTSEntity:
    data = {
        CONF_API_MODE: API_MODE_DIRECT,
        CONF_ENDPOINT: DIRECT_API_ENDPOINTS[0],
        CONF_SESSION_ID: "sessionid-abc123",
        CONF_VOICE: DEFAULT_VOICE,
    }
    data.update(overrides)
    return _make_entity(hass, data)


# ---------------------------------------------------------------------------
# Static / property behaviour
# ---------------------------------------------------------------------------


def test_entity_ids_and_names(hass) -> None:
    proxy = _proxy_entity(hass)
    direct = _direct_entity(hass)
    assert proxy.entity_id == ENTITY_ID_TTS_PROXY
    assert direct.entity_id == ENTITY_ID_TTS_DIRECT
    assert proxy.name == "TikTokTTS Proxy"
    assert direct.name == "TikTokTTS Direct"


def test_unique_id_is_entry_id(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_MODE: API_MODE_PROXY})
    entry.add_to_hass(hass)
    assert TikTokTTSEntity(entry).unique_id == entry.entry_id


def test_endpoint_strips_trailing_slash(hass) -> None:
    ent = _proxy_entity(hass, **{CONF_ENDPOINT: "https://example.com/"})
    assert ent._endpoint == "https://example.com"


def test_supported_languages_and_options(hass) -> None:
    ent = _proxy_entity(hass)
    assert ent.supported_languages == SUPPORTED_LANGUAGES
    assert ent.supported_options == [CONF_VOICE, RANDOM_SEED_KEY]
    assert ent.default_options == {CONF_VOICE: DEFAULT_VOICE}


def test_default_language_from_configured_voice(hass) -> None:
    ent = _proxy_entity(hass, **{CONF_VOICE: "fr_001"})
    assert ent.default_language == "fr"


def test_default_language_fallback_for_unknown_voice(hass) -> None:
    ent = _proxy_entity(hass, **{CONF_VOICE: "not_a_real_voice"})
    assert ent.default_language == SUPPORTED_LANGUAGES[0]


def test_get_supported_voices_known_language(hass) -> None:
    ent = _proxy_entity(hass)
    voices = ent.async_get_supported_voices("en_us")
    assert all(isinstance(v, Voice) for v in voices)
    assert [v.voice_id for v in voices] == VOICES_BY_LANGUAGE["en_us"]


def test_get_supported_voices_unknown_language(hass) -> None:
    ent = _proxy_entity(hass)
    assert ent.async_get_supported_voices("klingon") is None


# ---------------------------------------------------------------------------
# Proxy mode
# ---------------------------------------------------------------------------


async def test_proxy_success(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    ent = _proxy_entity(hass)
    fmt, audio = await ent.async_get_tts_audio(
        "hello", "en_us", {CONF_VOICE: "en_us_001"}
    )
    assert fmt == "mp3"
    assert audio == AUDIO
    assert aioclient_mock.mock_calls[0][2] == {"text": "hello", "voice": "en_us_001"}


async def test_proxy_http_error_raises(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, status=502, text="bad gateway")
    ent = _proxy_entity(hass)
    with pytest.raises(HomeAssistantError):
        await ent.async_get_tts_audio("hello", "en_us", {})
    # Non-200 raises immediately - it is not a retryable condition.
    assert len(aioclient_mock.mock_calls) == 1


async def test_proxy_missing_data_field(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, json={"unexpected": "shape"})
    ent = _proxy_entity(hass)
    with pytest.raises(HomeAssistantError, match="did not contain audio"):
        await ent.async_get_tts_audio("hello", "en_us", {})


async def test_proxy_non_json_response(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, content=b"<html>not json</html>")
    ent = _proxy_entity(hass)
    with pytest.raises(HomeAssistantError, match="non-JSON"):
        await ent.async_get_tts_audio("hello", "en_us", {})


async def test_proxy_corrupt_base64(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": "AAAAA"})  # invalid length
    ent = _proxy_entity(hass)
    with pytest.raises(HomeAssistantError, match="corrupt audio"):
        await ent.async_get_tts_audio("hello", "en_us", {})


async def test_proxy_retries_then_gives_up(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, exc=aiohttp.ClientError())
    ent = _proxy_entity(hass)
    with pytest.raises(HomeAssistantError, match="unreachable"):
        await ent.async_get_tts_audio("hello", "en_us", {})
    assert len(aioclient_mock.mock_calls) == REQUEST_MAX_RETRIES + 1


async def test_proxy_timeout_then_gives_up(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, exc=TimeoutError())
    ent = _proxy_entity(hass)
    with pytest.raises(HomeAssistantError):
        await ent.async_get_tts_audio("hello", "en_us", {})
    assert len(aioclient_mock.mock_calls) == REQUEST_MAX_RETRIES + 1


# ---------------------------------------------------------------------------
# Voice resolution
# ---------------------------------------------------------------------------


async def test_explicit_known_voice_passed_through(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    ent = _proxy_entity(hass)
    await ent.async_get_tts_audio("hi", "en_us", {CONF_VOICE: "en_us_007"})
    assert aioclient_mock.mock_calls[0][2]["voice"] == "en_us_007"


async def test_unknown_voice_passed_through(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    ent = _proxy_entity(hass)
    await ent.async_get_tts_audio("hi", "en_us", {CONF_VOICE: "made_up_voice"})
    assert aioclient_mock.mock_calls[0][2]["voice"] == "made_up_voice"


async def test_default_voice_kept_when_in_requested_language(
    hass, aioclient_mock
) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    ent = _proxy_entity(hass)  # default en_us_001
    await ent.async_get_tts_audio("hi", "en_us", {CONF_VOICE: DEFAULT_VOICE})
    assert aioclient_mock.mock_calls[0][2]["voice"] == DEFAULT_VOICE


async def test_default_voice_replaced_when_not_in_language(
    hass, aioclient_mock
) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    ent = _proxy_entity(hass)  # default en_us_001 (en_us)
    # No explicit voice + a different language -> first voice of that language.
    await ent.async_get_tts_audio("bonjour", "fr", {})
    assert aioclient_mock.mock_calls[0][2]["voice"] == VOICES_BY_LANGUAGE["fr"][0]


async def test_unknown_language_falls_back_to_configured_voice(
    hass, aioclient_mock
) -> None:
    """A language with no voice table entry keeps the configured default voice."""
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    ent = _proxy_entity(hass)
    await ent.async_get_tts_audio("hi", "klingon", {})
    assert aioclient_mock.mock_calls[0][2]["voice"] == DEFAULT_VOICE


async def test_random_voice_picks_from_pool(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    hass.data.setdefault(DOMAIN, {})[HASS_DATA_RANDOM_LANGS] = ["fr"]
    ent = _proxy_entity(hass)
    with patch.object(tts.random, "choice", return_value="fr_002") as choice:
        await ent.async_get_tts_audio(
            "hi", "en_us", {CONF_VOICE: "random", RANDOM_SEED_KEY: "x"}
        )
    # Pool was the fr voices; chosen voice is what was sent.
    assert set(choice.call_args[0][0]) == set(VOICES_BY_LANGUAGE["fr"])
    assert aioclient_mock.mock_calls[0][2]["voice"] == "fr_002"


async def test_random_voice_empty_pool_uses_default(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    hass.data.setdefault(DOMAIN, {})[HASS_DATA_RANDOM_LANGS] = []
    ent = _proxy_entity(hass)
    await ent.async_get_tts_audio("hi", "en_us", {CONF_VOICE: "random"})
    assert aioclient_mock.mock_calls[0][2]["voice"] == DEFAULT_VOICE


async def test_options_dict_not_mutated(hass, aioclient_mock) -> None:
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    ent = _proxy_entity(hass)
    options = {CONF_VOICE: "en_us_007", RANDOM_SEED_KEY: "seed"}
    await ent.async_get_tts_audio("hi", "en_us", options)
    assert options == {CONF_VOICE: "en_us_007", RANDOM_SEED_KEY: "seed"}


# ---------------------------------------------------------------------------
# Direct mode
# ---------------------------------------------------------------------------


async def test_direct_success(hass, aioclient_mock) -> None:
    aioclient_mock.post(DIRECT_URL_0, json={"status_code": 0, "data": {"v_str": B64}})
    ent = _direct_entity(hass)
    fmt, audio = await ent.async_get_tts_audio(
        "test", "en_us", {CONF_VOICE: "en_us_001"}
    )
    assert fmt == "mp3"
    assert audio == AUDIO

    method, url, _data, headers = aioclient_mock.mock_calls[0]
    assert url.query["text_speaker"] == "en_us_001"
    assert url.query["req_text"] == "test"
    assert headers["Cookie"] == "sessionid=sessionid-abc123"


async def test_direct_chunks_long_message(hass, aioclient_mock) -> None:
    aioclient_mock.post(DIRECT_URL_0, json={"status_code": 0, "data": {"v_str": B64}})
    message = "word " * 100  # 500 chars -> several chunks
    expected_chunks = tts._split_text(message, tts.DIRECT_API_CHUNK_SIZE)
    assert len(expected_chunks) > 1

    ent = _direct_entity(hass)
    _fmt, audio = await ent.async_get_tts_audio(
        message, "en_us", {CONF_VOICE: "en_us_001"}
    )
    assert audio == AUDIO * len(expected_chunks)
    assert len(aioclient_mock.mock_calls) == len(expected_chunks)


async def test_direct_invalid_session_raises_and_creates_issue(
    hass, aioclient_mock
) -> None:
    aioclient_mock.post(DIRECT_URL_0, json={"status_code": 4, "status_msg": "expired"})
    ent = _direct_entity(hass)
    with pytest.raises(HomeAssistantError, match="session_id"):
        await ent.async_get_tts_audio("test", "en_us", {CONF_VOICE: "en_us_001"})
    await hass.async_block_till_done()

    # Invalid session is global - it must NOT try the other endpoints.
    assert len(aioclient_mock.mock_calls) == 1
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_SESSION_EXPIRED)
    assert issue is not None


async def test_direct_empty_audio_raises(hass, aioclient_mock) -> None:
    aioclient_mock.post(DIRECT_URL_0, json={"status_code": 0, "data": {"v_str": ""}})
    ent = _direct_entity(hass)
    with pytest.raises(HomeAssistantError, match="empty audio"):
        await ent.async_get_tts_audio("test", "en_us", {CONF_VOICE: "en_us_001"})


async def test_direct_corrupt_base64_raises(hass, aioclient_mock) -> None:
    aioclient_mock.post(
        DIRECT_URL_0, json={"status_code": 0, "data": {"v_str": "AAAAA"}}
    )
    ent = _direct_entity(hass)
    with pytest.raises(HomeAssistantError, match="corrupt audio"):
        await ent.async_get_tts_audio("test", "en_us", {CONF_VOICE: "en_us_001"})


async def test_direct_falls_back_to_next_endpoint(hass, aioclient_mock) -> None:
    # Configured endpoint returns HTTP error; the first fallback succeeds.
    aioclient_mock.post(DIRECT_URL_0, status=500)
    fallback_url = f"{DIRECT_API_ENDPOINTS[1]}{DIRECT_API_PATH}"
    aioclient_mock.post(fallback_url, json={"status_code": 0, "data": {"v_str": B64}})

    ent = _direct_entity(hass)
    _fmt, audio = await ent.async_get_tts_audio(
        "test", "en_us", {CONF_VOICE: "en_us_001"}
    )
    assert audio == AUDIO
    # endpoint[0] (1 attempt, then break) + endpoint[1] (success)
    assert len(aioclient_mock.mock_calls) == 2


async def test_direct_falls_back_after_connection_error(hass, aioclient_mock) -> None:
    """A network error on the configured endpoint falls through to a fallback."""
    aioclient_mock.post(DIRECT_URL_0, exc=aiohttp.ClientError())
    fallback_url = f"{DIRECT_API_ENDPOINTS[1]}{DIRECT_API_PATH}"
    aioclient_mock.post(fallback_url, json={"status_code": 0, "data": {"v_str": B64}})

    ent = _direct_entity(hass)
    _fmt, audio = await ent.async_get_tts_audio(
        "test", "en_us", {CONF_VOICE: "en_us_001"}
    )
    assert audio == AUDIO
    # endpoint[0] gets REQUEST_MAX_RETRIES + 1 attempts (all error), then endpoint[1] succeeds.
    assert len(aioclient_mock.mock_calls) == (REQUEST_MAX_RETRIES + 1) + 1


async def test_direct_remembers_working_endpoint_across_chunks(
    hass, aioclient_mock
) -> None:
    """Once a fallback serves a chunk, later chunks start there directly.

    Without memoization, every chunk would re-probe the dead configured
    endpoint before failing over.
    """
    aioclient_mock.post(DIRECT_URL_0, status=500)
    fallback_url = f"{DIRECT_API_ENDPOINTS[1]}{DIRECT_API_PATH}"
    aioclient_mock.post(fallback_url, json={"status_code": 0, "data": {"v_str": B64}})

    message = "word " * 60  # 300 chars -> exactly 2 chunks
    assert len(tts._split_text(message, tts.DIRECT_API_CHUNK_SIZE)) == 2

    ent = _direct_entity(hass)
    _fmt, audio = await ent.async_get_tts_audio(
        message, "en_us", {CONF_VOICE: "en_us_001"}
    )
    assert audio == AUDIO * 2

    # Chunk 0: configured endpoint (1 non-200 attempt) + fallback success = 2.
    # Chunk 1: goes straight to the remembered fallback = 1. Total 3, not 4.
    assert len(aioclient_mock.mock_calls) == 3
    assert str(aioclient_mock.mock_calls[-1][1]).startswith(DIRECT_API_ENDPOINTS[1])


async def test_direct_total_deadline_caps_slow_messages(
    hass, aioclient_mock, monkeypatch
) -> None:
    """A message that cannot complete within DIRECT_TOTAL_TIMEOUT raises."""
    monkeypatch.setattr(tts, "DIRECT_TOTAL_TIMEOUT", 0.05)

    async def _hang(method, url, data):
        await asyncio.sleep(5)

    aioclient_mock.post(DIRECT_URL_0, side_effect=_hang)
    ent = _direct_entity(hass)
    with pytest.raises(HomeAssistantError, match="timed out"):
        await ent.async_get_tts_audio("test", "en_us", {CONF_VOICE: "en_us_001"})


async def test_direct_all_endpoints_bad_status(hass, aioclient_mock) -> None:
    for ep in DIRECT_API_ENDPOINTS:
        aioclient_mock.post(
            f"{ep}{DIRECT_API_PATH}", json={"status_code": 5, "status_msg": "err"}
        )
    ent = _direct_entity(hass)
    with pytest.raises(HomeAssistantError, match="across all"):
        await ent.async_get_tts_audio("test", "en_us", {CONF_VOICE: "en_us_001"})
    # A non-zero status breaks to the next endpoint, so each is tried once.
    assert len(aioclient_mock.mock_calls) == len(DIRECT_API_ENDPOINTS)


async def test_dispatch_uses_api_mode(hass, aioclient_mock) -> None:
    """Proxy entries hit the proxy URL; direct entries hit the direct URL."""
    aioclient_mock.post(PROXY_URL, json={"data": B64})
    await _proxy_entity(hass).async_get_tts_audio("hi", "en_us", {})
    assert aioclient_mock.mock_calls[-1][1].path == "/api/generation"

    aioclient_mock.post(DIRECT_URL_0, json={"status_code": 0, "data": {"v_str": B64}})
    await _direct_entity(hass).async_get_tts_audio("hi", "en_us", {})
    assert aioclient_mock.mock_calls[-1][1].path == DIRECT_API_PATH
