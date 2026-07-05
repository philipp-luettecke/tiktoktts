# TikTok TTS : Home Assistant Custom Integration

[![Tests](https://github.com/sfox38/tiktoktts/actions/workflows/tests.yml/badge.svg)](https://github.com/sfox38/tiktoktts/actions/workflows/tests.yml)
[![Validate](https://github.com/sfox38/tiktoktts/actions/workflows/validate.yml/badge.svg)](https://github.com/sfox38/tiktoktts/actions/workflows/validate.yml)

A Home Assistant custom integration that provides Text-to-Speech using TikTok's voice engine, supporting a wide range of languages and expressive voices.

<img src="https://raw.githubusercontent.com/sfox38/tiktoktts/main/examples/dash-custom-v1.2.jpg" width="50%" alt="TikTok TTS dashboard card">


## Credits & Attribution

| Role | Person / Project | Link |
|---|---|---|
| **Original integration author** | Philipp Lüttecke | [philipp-luettecke/tiktoktts](https://github.com/philipp-luettecke/tiktoktts) |
| **Community TTS proxy** | Weilbyte | [Weilbyte/tiktok-tts](https://github.com/Weilbyte/tiktok-tts) |
| **Voice list reference** | oscie57 | [oscie57/tiktok-voice](https://github.com/oscie57/tiktok-voice) |
| **Fork author** | Steven Fox | [sfox38/tiktoktts](https://github.com/sfox38/tiktoktts) |

> [!NOTE]
> This fork modernises the original integration for current Home Assistant versions, fixes several bugs, adds a UI config flow, more than triple the voices, direct API mode with endpoint fallback, automatic text chunking, a Random Voice feature, helper entities plus a custom dashboard card, improved error handling, and improved documentation.

---

## Installation

<details><summary>

## Important: Click here if you are upgrading from the original Integration!
</summary>

  
If you were using [philipp-luettecke/tiktoktts](https://github.com/philipp-luettecke/tiktoktts), this fork has **breaking changes** that require a clean removal before installing. You cannot simply overwrite the old files. You can [skip this section](#configuration) if you have not installed the previous integration.

### Breaking Changes

| What changed | Original | This fork |
|---|---|---|
| **Configuration method** | `configuration.yaml` | UI config flow (Settings -> Devices & Services) |
| **Entity ID** | May vary | `tts.tiktoktts_proxy` (proxy mode) or `tts.tiktoktts_direct` (direct mode) |
| **Default language** | `de` (German) | `en_us` (English US) |
| **Default voice** | `de_001` | `en_us_001` |
| **`platform:` entry in YAML** | Required | **Must be removed** |

### Step 1: Remove the `platform:` entry from `configuration.yaml`

Open your `configuration.yaml` and delete the TikTok TTS platform entry. It will look something like this - remove the whole block:

```yaml
tts:
  - platform: tiktoktts
    api_endpoint: https://tiktok-tts.weilnet.workers.dev
    voice: en_us_001
```

If `tts:` was only used for TikTok TTS, remove the entire `tts:` section. If you have other TTS platforms listed under `tts:`, remove only the `tiktoktts` entry and leave the others.

### Step 2: Delete the Old Integration Files

In your `config/custom_components/` directory, delete the entire `tiktoktts/` folder and everything inside it.

### Step 3: Clear the Old TTS Cache

HA caches generated audio files and sometimes holds on to old entity state. Go to **Developer Tools -> States** and confirm no `tiktoktts` entities remain. If any do, click each one and use the delete (bin) icon to remove them.

### Step 4: Restart Home Assistant

Go to **Settings -> System -> Restart** and do a full restart (not Quick Reload).

### Step 5: Install This Fork and Reconfigure

Follow the [Installation](#installation) steps below. When you reach **Settings -> Devices & Services -> Add Integration**, you will go through the new UI setup wizard to reconfigure your endpoint and default voice.

> [!NOTE]
> Any automations that used the deprecated `tts.tiktoktts_say` service call will need to be updated to use the `tts.speak` action format shown in the [Usage](#usage) section below.
</details>


### HACS (Recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Click the three-dot menu (top right) and choose **Custom repositories**.
3. Paste `https://github.com/sfox38/tiktoktts` and select **Integration** as the category.
4. Click **Add**, then find **tiktoktts** in the HACS Integration list and click **Download**.
5. Restart Home Assistant.

### Manual Installation

1. Download the latest release zip from this repository and unpack it.
2. Copy the `tiktoktts` folder into your `config/custom_components/` directory. The result should be `config/custom_components/tiktoktts/`.
3. Restart Home Assistant.

---

## Configuration

After restarting, go to **Settings -> Devices & Services -> Add Integration** and search for **TikTok TTS**.

### Connection Modes

#### Community Proxy (recommended)
Uses the open-source proxy by [Weilbyte](https://github.com/Weilbyte/tiktok-tts). No TikTok account required. The default endpoint is `https://tiktok-tts.weilnet.workers.dev`.

For better reliability, you can self-host your own proxy instance and enter its URL during setup. See the [Weilbyte repo](https://github.com/Weilbyte/tiktok-tts) for instructions.

> [!NOTE]
> **Privacy:** In proxy mode, your message text and chosen voice are sent to the proxy server (Weilbyte or your self-hosted instance) in plain text. The proxy forwards the request to TikTok on your behalf. If privacy is a concern, self-host your own proxy instance.

If both proxy and direct API modes are configured, **proxy mode takes priority** for the Speak button and automations that do not specify an entity ID.

#### Direct API ⚠️
Calls TikTok's internal API directly using your TikTok session cookie.

> [!IMPORTANT]
> This uses TikTok's undocumented API and may violate TikTok's Terms of Service. Use at your own risk.

Requires a `sessionid` cookie from a logged-in TikTok browser session:
1. **Log in** to TikTok in your browser (you must have a TikTok account)
2. Open Developer Tools (F12) -> Application -> Cookies
3. Copy the value of the `sessionid` cookie

The integration will automatically try multiple regional TikTok endpoints if the primary one fails. You must input a valid `sessionid` cookie value or you will not be able to proceed.

---

## Usage

### Entity Names

Each configured instance creates its own entity with a fixed ID based on the connection mode:

| Mode | Friendly Name | Entity ID |
|---|---|---|
| Community Proxy | TikTokTTS Proxy | `tts.tiktoktts_proxy` |
| Direct API | TikTokTTS Direct | `tts.tiktoktts_direct` |

Both entities can coexist if you have configured both modes. Use the appropriate entity ID in your automations depending on which connection you want to use.

The integration also creates these **shared** helper entities (one set regardless of how many instances you have configured). They are only used by the Home Assistant UI and dashboard cards, you generally won't need to manage them yourself:

| Entity ID | Purpose |
|---|---|
| `select.tiktoktts_language` | Language selector dropdown |
| `select.tiktoktts_voice` | Voice selector dropdown (filtered by language) |
| `select.tiktoktts_device` | Output device selector (auto-populated from your media players) |
| `text.tiktoktts_message` | Text input field for the message to speak |
| `button.tiktoktts_speak` | Speak button - reads the above entities and calls tts.speak |

### tts.speak action

**Proxy mode:**
```yaml
action: tts.speak
target:
  entity_id: tts.tiktoktts_proxy
data:
  media_player_entity_id: media_player.your_speaker
  message: "Hello, this is TikTok TTS"
  language: en_us
  options:
    voice: en_us_007
```

**Direct API mode:**
```yaml
action: tts.speak
target:
  entity_id: tts.tiktoktts_direct
data:
  media_player_entity_id: media_player.your_speaker
  message: "Hello, this is TikTok TTS"
  language: en_us
  options:
    voice: en_us_007
```

The `language` field filters available voices in the Automations editor UI, however it is recommended to leave this blank. The `options.voice` field selects the specific voice. If you omit `options.voice`, the integration uses your configured default voice if it belongs to the requested language, or falls back to the first available voice for that language.

### Random Voice

You can configure a pool of language groups to draw from randomly on each `tts.speak` call. Press the 🎲 dice button next to the Speak button in the dashboard card to open the Random Voice settings panel. Tick the language groups you want included in the pool and press "Save and close". Once at least one language is selected, `🎲 Random Voice` appears as an option in the language dropdown with a single `Random Voice` voice option beneath it.

A different voice is picked on every call. The Speak button automatically bypasses HA's TTS cache when random voice is active.

To use random voice in an automation, pass `voice: random` in the options:

```yaml
action: tts.speak
target:
  entity_id: tts.tiktoktts_proxy
data:
  media_player_entity_id: media_player.your_speaker
  message: "Hello, this is TikTok TTS"
  options:
    voice: random
```

> [!NOTE]
> When calling `tts.speak` directly from an automation with `voice: random`, add `cache: false` to the action data. Home Assistant checks its audio file cache **before** calling the integration, so without `cache: false` a repeated message may replay previously cached audio rather than generating a new random voice.

### Voice Examples

These samples were generated using TikTok TTS with a selection of English voices.
> [!NOTE]
> GitHub doesn't support inline audio playback - you will need to download these MP3 files first.

| Sample | Voice ID |
|---|---|
| [▶ Listen](https://raw.githubusercontent.com/sfox38/tiktoktts/main/examples/joke1.mp3) | `en_us_rocket` |
| [▶ Listen](https://raw.githubusercontent.com/sfox38/tiktoktts/main/examples/joke2.mp3) | `en_male_narration` |
| [▶ Listen](https://raw.githubusercontent.com/sfox38/tiktoktts/main/examples/joke3.mp3) | `en_us_ghostface` |
| [▶ Listen](https://raw.githubusercontent.com/sfox38/tiktoktts/main/examples/joke4.mp3) | `en_us_006` |
| [▶ Listen](https://raw.githubusercontent.com/sfox38/tiktoktts/main/examples/joke5.mp3) | `en_male_m03_lobby` |
| [▶ Listen](https://raw.githubusercontent.com/sfox38/tiktoktts/main/examples/joke6.mp3) | `en_female_emotional` | 


### Dashboard Cards

This integration creates a set of shared helper entities plus a custom dashboard card which all work together as a TTS control panel. You can use this card to easily preview voices, or to send impromptu messages to speakers around your home. The dashboard card will look like the one shown at the top of this page.

You don't need to install this dashboard card separately, it is automatically installed along with this integration. To add this card to any dashboard - search for `TikTokTTS` when adding a new card using the wizard, or just create an empty dashboard card with the following text:

```yaml
type: custom:tiktoktts-card
```

Alternatively, you can create a standard dashboard card using only the TikTok TTS entities:

```yaml
type: entities
title: TikTok TTS
entities:
  - select.tiktoktts_language
  - select.tiktoktts_voice
  - text.tiktoktts_message
  - select.tiktoktts_device
  - button.tiktoktts_speak
```

**How it works:**

1. Select a language from `select.tiktoktts_language` - the voice list filters automatically. Select `🎲 Random Voice` to use the random voice feature.
2. Select a voice from `select.tiktoktts_voice`
3. Type your message in `text.tiktoktts_message` (maximum 255 characters)
4. Select your output speaker from `select.tiktoktts_device` - auto-populated from all available media players in your HA instance, and updates automatically when new devices come online
5. Press the Speak button - reads all fields and calls `tts.speak` server-side
6. Press the 🎲 dice button next to Speak to open the Random Voice settings panel, where you can select which language groups to include in the random voice pool

> [!NOTE]
> All selections are remembered across HA restarts. The device list automatically refreshes when media players become available, including late-loading integrations like browser_mod.

## Supported Languages & Voices

The **Voice ID** is the value to use in the `options.voice` field of the `tts.speak` action.
Click any language group to expand its full voice list.

<details>
<summary>🇺🇸 English (US) &nbsp;-&nbsp; <code>en_us</code> &nbsp;(24 voices)</summary>

| Voice ID | Description |
|---|---|
| `en_male_santa_narration` | Author |
| `en_female_betty` | Bae |
| `en_female_makeup` | Beauty Guru |
| `en_female_richgirl` | Bestie |
| `en_us_010` | Confidence |
| `en_male_cupid` | Cupid |
| `en_female_shenna` | Debutante |
| `en_female_samc` | Empathetic |
| `en_male_jomboy` | Game On |
| `en_female_grandma` | Granny |
| `en_us_001` | Jessie |
| `en_us_006` | Joey |
| `en_male_wizard` | Magician |
| `en_male_trevor` | Marty |
| `en_male_deadpool` | Mr. GoodGuy |
| `en_us_007` | Professor |
| `en_male_santa` | Santa |
| `en_male_santa_effect` | Santa (with effect) |
| `en_us_009` | Scientist |
| `en_male_cody` | Serious |
| `en_male_narration` | Story Teller |
| `en_male_grinch` | Trickster |
| `en_female_pansino` | Varsity |
| `en_male_funny` | Wacky |

</details>

<details>
<summary>🇬🇧 English (UK) &nbsp;-&nbsp; <code>en_uk</code> &nbsp;(8 voices)</summary>

| Voice ID | Description |
|---|---|
| `en_male_jarvis` | Alfred |
| `en_male_ashmagic` | Ash Magic |
| `en_male_ukneighbor` | Lord Cringe |
| `en_uk_003` | Male English UK |
| `en_male_ukbutler` | Mr. Meticulous |
| `en_uk_001` | Narrator |
| `en_male_olantekkers` | Olan Tekkers |
| `en_female_emotional` | Peaceful |

</details>

<details>
<summary>🇦🇺 English (AU) &nbsp;-&nbsp; <code>en_au</code> &nbsp;(2 voices)</summary>

| Voice ID | Description |
|---|---|
| `en_au_001` | Metro |
| `en_au_002` | Smooth |

</details>

<details>
<summary>🎭 Disney / Character &nbsp;-&nbsp; <code>disney</code> &nbsp;(9 voices)</summary>

| Voice ID | Description |
|---|---|
| `en_us_c3po` | C3PO |
| `en_us_chewbacca` | Chewbacca |
| `en_male_ghosthost` | Ghost Host |
| `en_female_madam_leota` | Madame Leota |
| `en_male_pirate` | Pirate |
| `en_us_rocket` | Rocket |
| `en_us_ghostface` | Scream |
| `en_us_stitch` | Stitch |
| `en_us_stormtrooper` | Stormtrooper |

</details>

<details>
<summary>🎵 Music / Singing &nbsp;-&nbsp; <code>music</code> &nbsp;(15 voices)</summary>

These voices are optimised for musical or expressive text rather than natural speech.

| Voice ID | Description |
|---|---|
| `en_male_sing_deep_jingle` | Caroler |
| `en_male_m03_classical` | Classic Electric |
| `en_female_f08_salut_damour` | Cottagecore |
| `en_male_m2_xhxs_m03_christmas` | Cozy |
| `en_female_ht_f08_glorious` | Euphoric |
| `en_male_sing_funny_it_goes_up` | Hypetrain |
| `en_male_m03_lobby` | Jingle |
| `en_female_ht_f08_wonderful_world` | Melodrama |
| `en_female_ht_f08_newyear` | NYE 2023 |
| `en_female_f08_warmy_breeze` | Open Mic |
| `en_female_ht_f08_halloween` | Opera |
| `en_female_f08_twinkle` | Pop Lullaby |
| `en_male_m2_xhxs_m03_silly` | Quirky Time |
| `en_male_sing_funny_thanksgiving` | Thanksgiving |
| `en_male_m03_sunshine_soon` | Toon Beat |

</details>

<details>
<summary>🇫🇷 French &nbsp;-&nbsp; <code>fr</code> &nbsp;(2 voices)</summary>

| Voice ID | Description |
|---|---|
| `fr_001` | French - Male 1 |
| `fr_002` | French - Male 2 |

</details>

<details>
<summary>🇮🇹 Italian &nbsp;-&nbsp; <code>it</code> &nbsp;(1 voice)</summary>

| Voice ID | Description |
|---|---|
| `it_male_m18` | Italian Male |

</details>

<details>
<summary>🇪🇸 Spanish &nbsp;-&nbsp; <code>es</code> &nbsp;(4 voices)</summary>

| Voice ID | Description |
|---|---|
| `es_female_f6` | Alejandra |
| `es_male_m3` | Julio |
| `es_female_fp1` | Mariana |
| `es_002` | Spanish - Male |

</details>

<details>
<summary>🇲🇽 Spanish (Mexico) &nbsp;-&nbsp; <code>es_mx</code> &nbsp;(2 voices)</summary>

| Voice ID | Description |
|---|---|
| `es_mx_female_supermom` | Super Mamá |
| `es_mx_002` | Álex |

</details>

<details>
<summary>🇩🇪 German &nbsp;-&nbsp; <code>de</code> &nbsp;(2 voices)</summary>

| Voice ID | Description |
|---|---|
| `de_001` | German - Female |
| `de_002` | German - Male |

</details>

<details>
<summary>🇧🇷 Portuguese (Brazil) &nbsp;-&nbsp; <code>pt_br</code> &nbsp;(5 voices)</summary>

| Voice ID | Description |
|---|---|
| `br_004` | Ana |
| `bp_female_ivete` | Ivete Sangalo |
| `br_003` | Júlia |
| `br_005` | Lucas |
| `bp_female_ludmilla` | Ludmilla |

</details>

<details>
<summary>🇵🇹 Portuguese (Portugal) &nbsp;-&nbsp; <code>pt_pt</code> &nbsp;(3 voices)</summary>

| Voice ID | Description |
|---|---|
| `pt_male_bueno` | Galvão Bueno |
| `pt_female_laizza` | Laizza |
| `pt_female_lhays` | Lhays Macedo |

</details>

<details>
<summary>🇮🇩 Indonesian &nbsp;-&nbsp; <code>id</code> &nbsp;(4 voices)</summary>

| Voice ID | Description |
|---|---|
| `id_male_darma` | Darma |
| `id_female_icha` | Icha |
| `id_female_noor` | Noor |
| `id_male_putra` | Putra |

</details>

<details>
<summary>🇯🇵 Japanese &nbsp;-&nbsp; <code>ja</code> &nbsp;(20 voices)</summary>

| Voice ID | Description |
|---|---|
| `jp_003` | Keiko (恵子) |
| `jp_001` | Miho (美穂) |
| `jp_male_keiichinakano` | Morio's Kitchen |
| `jp_006` | Naoki (直樹) |
| `jp_005` | Sakura (さくら) |
| `jp_female_machikoriiita` | まちこりーた |
| `jp_female_fujicochan` | りーさ |
| `jp_male_hikakin` | ヒカキン |
| `jp_male_matsudake` | マツダ家の日常 |
| `jp_male_matsuo` | モジャオ |
| `jp_male_osada` | モリスケ |
| `jp_female_hasegawariona` | 世羅鈴 |
| `jp_female_rei` | 丸山礼 |
| `jp_male_yujinchigusa` | 低音ボイス |
| `jp_male_shuichiro` | 修一朗 |
| `jp_female_yagishaki` | 八木沙季 |
| `jp_female_shirou` | 四郎 |
| `jp_female_oomaeaika` | 夏絵ココ |
| `jp_female_kaorishoji` | 庄司果織 |
| `jp_male_tamawakazuki` | 玉川寿紀 |

</details>

<details>
<summary>🇰🇷 Korean &nbsp;-&nbsp; <code>ko</code> &nbsp;(3 voices)</summary>

| Voice ID | Description |
|---|---|
| `kr_003` | Korean - Female |
| `kr_002` | Korean - Male 1 |
| `kr_004` | Korean - Male 2 |

</details>

<details>
<summary>🇻🇳 Vietnamese &nbsp;-&nbsp; <code>vi</code> &nbsp;(2 voices)</summary>

| Voice ID | Description |
|---|---|
| `BV074_streaming` | Vietnamese - Female |
| `BV075_streaming` | Vietnamese - Male |

</details>


> [!NOTE]
> The voices currently supported by this integration represent the entire confirmed working set as of early 2026. TikTok's internal API supports additional voices beyond this list, but their exact API IDs are not publicly documented. Further, some voices may be locale specific, so you may not be able to use certain voices in your region, although in my own tests they all seem to work when using proxy mode. If you discover a working voice ID that is not already in our list, please [submit a new Issue here](https://github.com/sfox38/tiktoktts/issues) and I can add it to the next release.

### Changing the Default Voice

Go to **Settings -> Devices & Services -> TikTok TTS -> Configure** (gear icon). Changes take effect immediately after saving, no restart required.

---

## Troubleshooting

### Proxy endpoint is unreliable
The community Weilbyte proxy is a free, volunteer-run service and may occasionally be unavailable. For a more reliable setup, self-host your own proxy instance. See [Weilbyte/tiktok-tts](https://github.com/Weilbyte/tiktok-tts).

### Direct API: session_id expired
TikTok session IDs expire periodically. If you see errors about an invalid or expired session ID, go to the integration options and update the value from your browser cookies.

### Message too long error
The message text entity has a maximum length of 255 characters, which is enforced by HA's text entity platform. The dashboard card enforces this limit in the textarea. If you are calling `tts.speak` from an automation with a longer message, the integration automatically splits it into chunks of up to 200 characters (direct API mode) or sends the full text in one request (proxy mode, which handles chunking server-side). Only the HA text entity has the 255-character restriction.

### Check the logs
Go to **Settings -> System -> Logs** and filter for `tiktoktts` to find detailed error messages.

---

## Changelog

### v1.2.5
- **Fix:** Selecting the `(loading...)` placeholder in the device dropdown (shown when no media players are available yet) no longer crashes the `select.select_option` service call with an `IndexError`
- **Fix:** Calling `tiktoktts.set_random_voices` after the last config entry was unloaded (e.g. the entry is disabled) no longer crashes with a `KeyError`; the pool is still validated and persisted
- **Refactor:** The shared select/text/button entities are now forwarded by a single owning config entry instead of every entry, deleting the per-platform singleton guards and per-entry bookkeeping flags. Re-homing the shared entities to a surviving entry (when the owner is unloaded while another entry remains) now runs as a tracked Home Assistant task that is skipped during shutdown and no-ops when the owner was merely reloaded - replacing a raw `call_soon` hook that could race HA shutdown
- **Refactor:** The language and voice dropdowns no longer hold direct references to each other. They coordinate through dispatcher signals plus one `hass.data` key, which removes the startup readiness event, its 10-second timeout, and the entity object previously stashed in `hass.data` for the service handler. Behaviour (restore on restart, default-voice preservation, random-voice handling) is unchanged and covered by tests
- **Perf:** Direct API mode now remembers the endpoint that last served a request and tries it first, so when the configured endpoint is down, a multi-chunk message no longer re-probes it (with full retries) for every chunk
- **Perf:** Direct API mode now has an overall per-message deadline (120 s) so a long message during an outage cannot stall a `tts.speak` call for many minutes while every chunk walks the whole endpoint fallback list
- **Perf:** The device dropdown's media-player discovery now filters state events inside Home Assistant's event dispatch (`event_filter`), so routine attribute updates from active players never wake the integration at all
- **Perf:** Static assets (card JS, icon) are now served with cache headers; the card URL already carries a `?v=<version>` cache-buster so upgrades still load the new card immediately
- **Security:** The TikTok `session_id` field in the setup and options forms is now a masked password input instead of plain text
- **Fix:** Connection-test responses in the config flow are now properly released via context managers, and unexpected connection-test failures are logged with a traceback instead of being silently reported as "unknown error"
- **Meta:** `manifest.json` now declares `integration_type: service` and `iot_class: cloud_push` (matching core TTS integrations)
- **Tests:** 133 tests (up from 118); new coverage for the two crash fixes above, endpoint memoization, the per-message deadline, device selection and restore-wait behaviour, Speak-button guard paths, the options-save reload cycle, and config-flow unknown-error branches. The frontend tests now read the version from `manifest.json` instead of hardcoding it, so version bumps no longer break the suite
- **CI:** Added `ruff check` and `ruff format --check` to the test workflow; the codebase is now Ruff-formatted

### v1.2.4
- **Fix:** Dashboard card no longer crashes with `the name "tiktoktts-card" has already been used with this registry` after upgrading. Older versions registered the card as a Lovelace dashboard resource; the current version registers it via the frontend module API, so on upgrade both could load the card and define the element twice. The card now guards against double-registration. If you upgraded, you can also remove the leftover `/tiktoktts/tiktoktts-card.js` entry under Settings -> Dashboards -> Resources.

### v1.2.3
- **Fix:** Configured default voice is now preserved on a fresh start - the voice dropdown no longer reset to the first voice of the language (alphabetically) when there was no restored state to apply
- **Fix:** Unloading or disabling one config entry when multiple exist no longer triggers an endless reload cascade between entries - only the entry that owns the shared select/text/button entities re-homes them to a surviving entry
- **Fix:** The Disney / Character group could not be added to the Random Voice pool from the dashboard card - a friendly-name/emoji mismatch sent the label instead of the API code, which was then rejected. The card now reads language codes directly from the language entity (`language_options` attribute), so every language adds correctly regardless of its label
- **Fix:** Replaced a startup sleep-poll (waited up to 5 s for the voice entity to be ready) with event-driven coordination, so a restored language/voice is applied without the delay
- **Fix:** The shared select/text helper entities are now non-polling (they are push-based), removing a redundant periodic update cycle
- **Refactor:** Replaced the Lovelace card registration, which relied on Home Assistant's private Lovelace resources internals (and could break on a core update), with the supported `frontend.add_extra_js_url` helper. This also removes the resource-load polling loop and now works in YAML dashboard mode too
- **Refactor:** Extracted the shared select/text/button lifecycle bookkeeping into a dedicated `shared.py` module and flattened the setup/unload logic for readability - no behaviour change (proxy + direct can still run as two entries)
- **Refactor:** The voice dropdown now maps friendly labels to API codes via a dictionary instead of two index-aligned lists, removing a class of mismatch bug
- **Perf:** The device dropdown no longer rebuilds on every media-player attribute tick (volume, position); it refreshes only when a player appears, disappears, or changes availability
- **Cleanup:** Removed an unused import, de-duplicated the voice list via the existing `ALL_VOICES` constant, and tightened type hints
- **Doc:** Added mesa_profile.json

### v1.2.2
- **Fix:** Lovelace card resource is now removed only on true integration deletion, not on every reload or options save (was wiping the card resource on every settings change)
- **Fix:** Language-aware voice fallback - if the configured default voice is not available for the requested language, the integration now correctly falls back to the first voice of that language (matches the documented behaviour)
- **Fix:** Direct API retry tuning - the configured endpoint gets 3 attempts × 20 s; each automatic fallback endpoint gets 1 attempt × 10 s (was using the same retry count for all endpoints)
- **Fix:** All failure paths now raise `HomeAssistantError` so errors surface in the HA UI and automation traces instead of silently returning empty audio
- **Fix:** `aiohttp` sessions are now properly closed via `async with` context managers (previously leaked connections on errors)
- **Fix:** Options flow now saves sanitized values (trailing slashes stripped from endpoint, whitespace stripped from session_id) instead of raw user input
- **Fix:** `async_delete_issue` is now called after a successful direct-API options save, clearing the expired-session repair issue
- **Fix:** Voice dropdown no longer resets on every random-voice pool save - only resets when the language actually changes
- **Fix:** Restored voice is now correctly re-applied after restart even when the restored language differs from the startup default
- **Fix:** `button.tiktoktts_speak` now guards against speaking the literal strings "unavailable" or "unknown"
- **Fix:** `ConfigEntryState` import moved to module level in button.py
- **Fix:** Redundant `native_value` property removed from `MessageTextEntity` (base class handles `_attr_native_value`)
- **Fix:** JS card - Speak button now cancels any pending debounce and flushes the current message to HA before pressing the button, preventing a race where the last typed characters could be missed
- **Fix:** `services.yaml` - `languages` field now uses a proper multi-select selector with all 16 language codes instead of a bare `object` selector
- **Fix:** Dead `"unknown"` error key removed from `strings.json` and `translations/en.json`
- **Fix:** Lovelace resource URL match tightened to exact path equality (was `startsWith`, could match unrelated resources)
- **Fix:** `manifest.json` version now read lazily via executor job in `frontend/__init__.py` to avoid blocking I/O on the event loop at import time
- **Docs:** README corrected - cache limitation for `voice: random` in automations, chunking behaviour, proxy privacy note, proxy-wins-over-direct note, GitHub capitalisation, image tag attributes

---

## Disclaimer

This integration is not affiliated with, endorsed by, or connected to TikTok or ByteDance in any way. The direct API mode uses an unofficial, reverse-engineered endpoint. Use of the direct API mode may violate TikTok's Terms of Service.

