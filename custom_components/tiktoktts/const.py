"""Constants for tiktoktts."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

# ---------------------------------------------------------------------------
# Integration identity
# ---------------------------------------------------------------------------

DOMAIN = "tiktoktts"

# ---------------------------------------------------------------------------
# Attribution & credits
# Shown as the 'attribution' attribute on the TTS entities.
# Community TTS proxy by Weilbyte - https://github.com/Weilbyte/tiktok-tts
# ---------------------------------------------------------------------------

ORIGINAL_AUTHOR = "Philipp Lüttecke (@philipp-luettecke)"
ORIGINAL_REPO = "https://github.com/philipp-luettecke/tiktoktts"

FORK_AUTHOR = "Steven Fox (@sfox38)"
FORK_REPO = "https://github.com/sfox38/tiktoktts"

# Community TTS proxy project (used in config-flow description placeholders).
WEILBYTE_REPO = "https://github.com/Weilbyte/tiktok-tts"

ATTRIBUTION = (
    f"Originally by {ORIGINAL_AUTHOR} ({ORIGINAL_REPO}). "
    f"Forked and extended by {FORK_AUTHOR} ({FORK_REPO})."
)

# ---------------------------------------------------------------------------
# Config entry keys
# ---------------------------------------------------------------------------

CONF_ENDPOINT = "api_endpoint"
CONF_VOICE = "voice"
CONF_SESSION_ID = "session_id"
CONF_API_MODE = "api_mode"

# ---------------------------------------------------------------------------
# API modes
# ---------------------------------------------------------------------------

API_MODE_PROXY = "proxy"
API_MODE_DIRECT = "direct"

# ---------------------------------------------------------------------------
# Proxy API
# ---------------------------------------------------------------------------

# Default community proxy - operated by Weilbyte, may be unreliable.
# Users can self-host from: https://github.com/Weilbyte/tiktok-tts
DEFAULT_PROXY_ENDPOINT = "https://tiktok-tts.weilnet.workers.dev"

PROXY_API_PATH_GENERATE = "/api/generation"
PROXY_API_PATH_STATUS = "/api/status"
PROXY_API_FIELD_TEXT = "text"
PROXY_API_FIELD_VOICE = "voice"
PROXY_API_FIELD_DATA = "data"
PROXY_API_FIELD_AVAILABLE = "available"

# ---------------------------------------------------------------------------
# Direct TikTok API (unofficial, reverse-engineered)
# ---------------------------------------------------------------------------

# Known regional endpoints - the configured one is tried first,
# remaining ones are used as automatic fallback in the order listed.
#
# Endpoint naming convention: api{version}-{type}-{region}.tiktokv.com
#   version : 16, 19, 22 - TikTok server generation (higher = newer)
#   type    : normal, core - server role within the cluster
#   region  : useast1a, useast2a, useast5 (US), alisg (Singapore)
#
# Regional notes:
#   useast*  - US East servers, most commonly referenced in the community
#   alisg    - Singapore, lowest latency for Southeast Asia and Oceania
#
# Higher-generation endpoints (api19, api22) may support newer voices
# that api16 endpoints do not. Unresponsive endpoints are skipped
# automatically by the retry/fallback logic in tts.py.
DIRECT_API_ENDPOINTS = [
    # --- US East (primary, most reliable) ---
    "https://api16-normal-c-useast1a.tiktokv.com",
    "https://api16-normal-useast5.us.tiktokv.com",
    "https://api16-core-useast5.us.tiktokv.com",
    "https://api16-core-c-useast1a.tiktokv.com",
    "https://api16-normal-c-useast2a.tiktokv.com",
    # --- US East (newer API generations) ---
    "https://api19-normal-c-useast1a.tiktokv.com",
    "https://api19-core-c-useast1a.tiktokv.com",
    "https://api22-core-c-alisg.tiktokv.com",
    # --- Generic / load-balanced ---
    "https://api16-core.tiktokv.com",
    "https://api-core.tiktokv.com",
    "https://api-normal.tiktokv.com",
    # --- Singapore (best for Southeast Asia / Oceania) ---
    "https://api16-normal-c-alisg.tiktokv.com",
    "https://api16-core-c-alisg.tiktokv.com",
]

DIRECT_API_PATH = "/media/api/text/speech/invoke/"

# Spoofed Android User-Agent required by TikTok's internal API
DIRECT_API_USER_AGENT = (
    "com.zhiliaoapp.musically/2022600030 "
    "(Linux; U; Android 7.1.2; es_ES; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)"
)

# TikTok API request parameter names
DIRECT_API_PARAM_SPEAKER = "text_speaker"
DIRECT_API_PARAM_TEXT = "req_text"
DIRECT_API_PARAM_MAP_TYPE = "speaker_map_type"
DIRECT_API_PARAM_AID = "aid"

# TikTok API fixed parameter values
DIRECT_API_MAP_TYPE_VALUE = 0
DIRECT_API_AID_VALUE = 1233

# TikTok API response field names
DIRECT_API_FIELD_STATUS_CODE = "status_code"
DIRECT_API_FIELD_STATUS_MSG = "status_msg"
DIRECT_API_FIELD_DATA = "data"
DIRECT_API_FIELD_AUDIO = "v_str"

# TikTok API status codes
DIRECT_API_STATUS_OK = 0
DIRECT_API_STATUS_INVALID_SESSION = 4

# Max characters per API request (TikTok enforced limit).
# Note: the limit is counted in characters per community findings, but the
# request is URL-encoded, so multibyte text (e.g. Japanese, Korean) produces
# much longer encoded requests. If direct-mode requests for multibyte
# languages are rejected, lower this value.
DIRECT_API_CHUNK_SIZE = 200

# HA repair issue ID raised when the direct API session_id is rejected
ISSUE_SESSION_EXPIRED = "direct_api_session_expired"

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

AUDIO_FORMAT = "mp3"

# ---------------------------------------------------------------------------
# Request behaviour
#
# REQUEST_* values apply to the proxy API and to the user's configured
# direct endpoint. FALLBACK_* values apply to the automatic direct-mode
# fallback endpoints - a single, shorter attempt each, so that a dead
# session or regional outage doesn't stall TTS for minutes while every
# endpoint is retried in full.
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 20  # seconds
REQUEST_MAX_RETRIES = 2  # retries after the first attempt
REQUEST_RETRY_DELAY = 1.5  # seconds between retries

FALLBACK_TIMEOUT = 10  # seconds, per fallback endpoint
FALLBACK_MAX_RETRIES = 0  # single attempt per fallback endpoint

# Overall deadline for one direct-mode message (all chunks, all endpoint
# fallbacks combined). Without this cap, a long message during a full outage
# could stall a tts.speak call for many minutes while every chunk walks the
# entire endpoint list.
DIRECT_TOTAL_TIMEOUT = 120  # seconds

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_VOICE = "en_us_001"
DEFAULT_LANG = "en_us"

# ---------------------------------------------------------------------------
# Supported voices
# All voices confirmed working as of early 2026 (duplicates removed).
# Sources:
#   https://github.com/oscie57/tiktok-voice
#   https://github.com/oscie57/tiktok-voice/issues/1
#   https://github.com/mark-rez/TikTok-Voice-TTS
# ---------------------------------------------------------------------------


# Maps language codes to voices - used by async_get_supported_voices() to
# filter the voice dropdown in the Automations editor when a language is selected.
VOICES_BY_LANGUAGE: dict[str, list[str]] = {
    "en_us": [
        "en_female_betty",
        "en_female_grandma",
        "en_female_makeup",
        "en_female_pansino",
        "en_female_richgirl",
        "en_female_samc",
        "en_female_shenna",
        "en_male_cody",
        "en_male_cupid",
        "en_male_deadpool",
        "en_male_funny",
        "en_male_grinch",
        "en_male_jomboy",
        "en_male_narration",
        "en_male_santa",
        "en_male_santa_effect",
        "en_male_santa_narration",
        "en_male_trevor",
        "en_male_wizard",
        "en_us_001",
        "en_us_006",
        "en_us_007",
        "en_us_009",
        "en_us_010",
    ],
    "en_uk": [
        "en_female_emotional",
        "en_male_ashmagic",
        "en_male_jarvis",
        "en_male_olantekkers",
        "en_male_ukbutler",
        "en_male_ukneighbor",
        "en_uk_001",
        "en_uk_003",
    ],
    "en_au": [
        "en_au_001",
        "en_au_002",
    ],
    "disney": [
        "en_female_madam_leota",
        "en_male_ghosthost",
        "en_male_pirate",
        "en_us_c3po",
        "en_us_chewbacca",
        "en_us_ghostface",
        "en_us_rocket",
        "en_us_stitch",
        "en_us_stormtrooper",
    ],
    "music": [
        "en_female_f08_salut_damour",
        "en_female_f08_twinkle",
        "en_female_f08_warmy_breeze",
        "en_female_ht_f08_glorious",
        "en_female_ht_f08_halloween",
        "en_female_ht_f08_newyear",
        "en_female_ht_f08_wonderful_world",
        "en_male_m03_classical",
        "en_male_m03_lobby",
        "en_male_m03_sunshine_soon",
        "en_male_m2_xhxs_m03_christmas",
        "en_male_m2_xhxs_m03_silly",
        "en_male_sing_deep_jingle",
        "en_male_sing_funny_it_goes_up",
        "en_male_sing_funny_thanksgiving",
    ],
    "fr": ["fr_001", "fr_002"],
    "it": ["it_male_m18"],
    "es": ["es_002", "es_female_f6", "es_female_fp1", "es_male_m3"],
    "es_mx": ["es_mx_002", "es_mx_female_supermom"],
    "de": ["de_001", "de_002"],
    "pt_br": [
        "bp_female_ivete",
        "bp_female_ludmilla",
        "br_003",
        "br_004",
        "br_005",
    ],
    "pt_pt": ["pt_female_laizza", "pt_female_lhays", "pt_male_bueno"],
    "id": ["id_female_icha", "id_female_noor", "id_male_darma", "id_male_putra"],
    "ja": [
        "jp_001",
        "jp_003",
        "jp_005",
        "jp_006",
        "jp_female_fujicochan",
        "jp_female_hasegawariona",
        "jp_female_kaorishoji",
        "jp_female_machikoriiita",
        "jp_female_oomaeaika",
        "jp_female_rei",
        "jp_female_shirou",
        "jp_female_yagishaki",
        "jp_male_hikakin",
        "jp_male_keiichinakano",
        "jp_male_matsudake",
        "jp_male_matsuo",
        "jp_male_osada",
        "jp_male_shuichiro",
        "jp_male_tamawakazuki",
        "jp_male_yujinchigusa",
    ],
    "ko": ["kr_002", "kr_003", "kr_004"],
    "vi": ["BV074_streaming", "BV075_streaming"],
}

SUPPORTED_LANGUAGES = list(VOICES_BY_LANGUAGE.keys())

# Flat list of every supported voice code across all languages
ALL_VOICES: list[str] = [v for codes in VOICES_BY_LANGUAGE.values() for v in codes]


# ---------------------------------------------------------------------------
# Friendly name mappings for UI display
# Used by select.py to show human-readable labels in the language and voice
# dropdowns instead of raw API codes.
# ---------------------------------------------------------------------------

LANGUAGE_NAMES: dict[str, str] = {
    "en_us": "🇺🇸 English (US)",
    "en_uk": "🇬🇧 English (UK)",
    "en_au": "🇦🇺 English (AU)",
    "disney": "🎭 Disney / Character",
    "music": "🎵 Music / Singing",
    "fr": "🇫🇷 French",
    "it": "🇮🇹 Italian",
    "es": "🇪🇸 Spanish",
    "es_mx": "🇲🇽 Spanish (Mexico)",
    "de": "🇩🇪 German",
    "pt_br": "🇧🇷 Portuguese (Brazil)",
    "pt_pt": "🇵🇹 Portuguese (Portugal)",
    "id": "🇮🇩 Indonesian",
    "ja": "🇯🇵 Japanese",
    "ko": "🇰🇷 Korean",
    "vi": "🇻🇳 Vietnamese",
}

VOICE_NAMES: dict[str, str] = {
    "bp_female_ivete": "Ivete Sangalo",
    "bp_female_ludmilla": "Ludmilla",
    "br_003": "Júlia",
    "br_004": "Ana",
    "br_005": "Lucas",
    "BV074_streaming": "Vietnamese - Female",
    "BV075_streaming": "Vietnamese - Male",
    "de_001": "German - Female",
    "de_002": "German - Male",
    "en_au_001": "Metro",
    "en_au_002": "Smooth",
    "en_female_betty": "Bae",
    "en_female_emotional": "Peaceful",
    "en_female_f08_salut_damour": "Cottagecore",
    "en_female_f08_twinkle": "Pop Lullaby",
    "en_female_f08_warmy_breeze": "Open Mic",
    "en_female_grandma": "Granny",
    "en_female_ht_f08_glorious": "Euphoric",
    "en_female_ht_f08_halloween": "Opera",
    "en_female_ht_f08_newyear": "NYE 2023",
    "en_female_ht_f08_wonderful_world": "Melodrama",
    "en_female_madam_leota": "Madame Leota",
    "en_female_makeup": "Beauty Guru",
    "en_female_pansino": "Varsity",
    "en_female_richgirl": "Bestie",
    "en_female_samc": "Empathetic",
    "en_female_shenna": "Debutante",
    "en_male_ashmagic": "Ash Magic",
    "en_male_cody": "Serious",
    "en_male_cupid": "Cupid",
    "en_male_deadpool": "Mr. GoodGuy",
    "en_male_funny": "Wacky",
    "en_male_ghosthost": "Ghost Host",
    "en_male_grinch": "Trickster",
    "en_male_jarvis": "Alfred",
    "en_male_jomboy": "Game On",
    "en_male_m03_classical": "Classic Electric",
    "en_male_m03_lobby": "Jingle",
    "en_male_m03_sunshine_soon": "Toon Beat",
    "en_male_m2_xhxs_m03_christmas": "Cozy",
    "en_male_m2_xhxs_m03_silly": "Quirky Time",
    "en_male_narration": "Story Teller",
    "en_male_olantekkers": "Olan Tekkers",
    "en_male_pirate": "Pirate",
    "en_male_santa": "Santa",
    "en_male_santa_effect": "Santa (with effect)",
    "en_male_santa_narration": "Author",
    "en_male_sing_deep_jingle": "Caroler",
    "en_male_sing_funny_it_goes_up": "Hypetrain",
    "en_male_sing_funny_thanksgiving": "Thanksgiving",
    "en_male_trevor": "Marty",
    "en_male_ukbutler": "Mr. Meticulous",
    "en_male_ukneighbor": "Lord Cringe",
    "en_male_wizard": "Magician",
    "en_uk_001": "Narrator",
    "en_uk_003": "Male English UK",
    "en_us_001": "Jessie",
    "en_us_006": "Joey",
    "en_us_007": "Professor",
    "en_us_009": "Scientist",
    "en_us_010": "Confidence",
    "en_us_c3po": "C3PO",
    "en_us_chewbacca": "Chewbacca",
    "en_us_ghostface": "Scream",
    "en_us_rocket": "Rocket",
    "en_us_stitch": "Stitch",
    "en_us_stormtrooper": "Stormtrooper",
    "es_002": "Spanish - Male",
    "es_female_f6": "Alejandra",
    "es_female_fp1": "Mariana",
    "es_male_m3": "Julio",
    "es_mx_002": "Álex",
    "es_mx_female_supermom": "Super Mamá",
    "fr_001": "French - Male 1",
    "fr_002": "French - Male 2",
    "id_female_icha": "Icha",
    "id_female_noor": "Noor",
    "id_male_darma": "Darma",
    "id_male_putra": "Putra",
    "it_male_m18": "Italian Male",
    "jp_001": "Miho (美穂)",
    "jp_003": "Keiko (恵子)",
    "jp_005": "Sakura (さくら)",
    "jp_006": "Naoki (直樹)",
    "jp_female_fujicochan": "りーさ",
    "jp_female_hasegawariona": "世羅鈴",
    "jp_female_kaorishoji": "庄司果織",
    "jp_female_machikoriiita": "まちこりーた",
    "jp_female_oomaeaika": "夏絵ココ",
    "jp_female_rei": "丸山礼",
    "jp_female_shirou": "四郎",
    "jp_female_yagishaki": "八木沙季",
    "jp_male_hikakin": "ヒカキン",
    "jp_male_keiichinakano": "Morio's Kitchen",
    "jp_male_matsudake": "マツダ家の日常",
    "jp_male_matsuo": "モジャオ",
    "jp_male_osada": "モリスケ",
    "jp_male_shuichiro": "修一朗",
    "jp_male_tamawakazuki": "玉川寿紀",
    "jp_male_yujinchigusa": "低音ボイス",
    "kr_002": "Korean - Male 1",
    "kr_003": "Korean - Female",
    "kr_004": "Korean - Male 2",
    "pt_female_laizza": "Laizza",
    "pt_female_lhays": "Lhays Macedo",
    "pt_male_bueno": "Galvão Bueno",
}

# ---------------------------------------------------------------------------
# Shared entity names and IDs
# ---------------------------------------------------------------------------

ENTITY_NAME_LANGUAGE = "TikTokTTS Language"
ENTITY_NAME_VOICE = "TikTokTTS Voice"
ENTITY_NAME_DEVICE = "TikTokTTS Device"
ENTITY_NAME_MESSAGE = "TikTokTTS Message"
ENTITY_NAME_SPEAK = "TikTokTTS Speak"

ENTITY_ID_LANGUAGE = f"select.{DOMAIN}_language"
ENTITY_ID_VOICE = f"select.{DOMAIN}_voice"
ENTITY_ID_DEVICE = f"select.{DOMAIN}_device"
ENTITY_ID_MESSAGE = f"text.{DOMAIN}_message"
ENTITY_ID_SPEAK = f"button.{DOMAIN}_speak"

ENTITY_ID_TTS_PROXY = f"tts.{DOMAIN}_{API_MODE_PROXY}"
ENTITY_ID_TTS_DIRECT = f"tts.{DOMAIN}_{API_MODE_DIRECT}"

# Unique IDs for singleton entities
UNIQUE_ID_LANGUAGE = f"{DOMAIN}_language"
UNIQUE_ID_VOICE = f"{DOMAIN}_voice"
UNIQUE_ID_DEVICE = f"{DOMAIN}_device"
UNIQUE_ID_MESSAGE = f"{DOMAIN}_message"
UNIQUE_ID_SPEAK = f"{DOMAIN}_speak"

# Entry ID of the config entry that forwarded the shared select/text/button
# platforms and therefore owns the shared entities. Claimed in
# async_setup_entry; cleared on unload so a surviving entry can re-home them.
HASS_DATA_SHARED_OWNER = "shared_owner_entry_id"

# hass.data[DOMAIN] keys for random voice store
HASS_DATA_RANDOM_STORE = "random_voice_store"
HASS_DATA_RANDOM_LANGS = "random_voice_languages"

# Raw language code currently selected in the language dropdown. Written by
# LanguageSelectEntity, read by VoiceSelectEntity on startup so the two
# entities never need direct references to each other.
HASS_DATA_CURRENT_LANGUAGE = "current_language_code"

# Dispatcher signals (helpers.dispatcher) used between the integration and
# the shared select entities. Payloads:
#   SIGNAL_LANGUAGE_CHANGED     - the new raw language code (str)
#   SIGNAL_RANDOM_POOL_UPDATED  - no payload; re-read HASS_DATA_RANDOM_LANGS
SIGNAL_LANGUAGE_CHANGED = f"{DOMAIN}_language_changed"
SIGNAL_RANDOM_POOL_UPDATED = f"{DOMAIN}_random_pool_updated"

# Random voice feature constants
RANDOM_VOICE_CODE = "random"
RANDOM_VOICE_NAME = "Random Voice"
RANDOM_VOICE_LANG_NAME = "🎲 Random Voice"

# Custom service for updating the random voice language set
SERVICE_SET_RANDOM_VOICES = "set_random_voices"

# Placeholder shown in device/voice dropdowns before data is loaded
PLACEHOLDER_LOADING = "(loading...)"

# Key added to supported_options so HA includes it in the TTS cache key hash.
# A unique value per call forces a cache miss for random voice mode.
RANDOM_SEED_KEY = "_random_seed"

# ---------------------------------------------------------------------------
# TTS service call constants
# ---------------------------------------------------------------------------

TTS_SERVICE_DOMAIN = "tts"
TTS_SERVICE_SPEAK = "speak"
TTS_SERVICE_FIELD_PLAYER = "media_player_entity_id"
TTS_SERVICE_FIELD_MESSAGE = "message"
TTS_SERVICE_FIELD_CACHE = "cache"
TTS_SERVICE_FIELD_OPTIONS = "options"
TTS_SERVICE_FIELD_VOICE = "voice"

# Special "all languages" option for the language select dropdown.
# When selected, the voice dropdown shows every voice from all languages.
LANGUAGE_ALL_CODE = "all"
LANGUAGE_ALL_NAME = "🌐 All Languages"
