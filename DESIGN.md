# Deluxe Soother Entity Design

## Purpose

This document defines the Home Assistant model for the Fisher-Price Smart Connect Deluxe Soother (DYW47). The integration uses the `fp-soother-lib` package as its BLE and protocol boundary and should not duplicate encryption, packet construction, bit-field decoding, or connection management.

The device is a single physical unit with three independently controllable light/projection functions and one audio function. Home Assistant should expose these as a small set of familiar entities and still give access to the device's discrete settings.

## Library contract

The integration depends on these public library capabilities:

- `SootherClient(address, ble_device=..., ble_device_callback=...)` / `SootherClient.open()` and `close()` for the long-lived Home Assistant connection lifecycle. There is no `SootherClient.discover()`; discovery is covered separately below.
- `SootherClient.pair()` for first-use pairing, and the `session_key` / `is_paired` properties for reading the result and deciding whether pairing is needed.
- `SootherClient.refresh_state()` for the initial complete state read.
- `SootherClient.on_state_change()` for BLE notifications, including physical button changes.
- `SootherClient.state` (`SootherState`) for the last known state.
- The typed `set_*` methods for all supported device commands.
- `SootherClient.send_preset(**overrides)` for the composite multi-attribute write (see Presets below).
- The named value mappings in `fp_soother_lib.constants` (e.g. `SOUND_MODES`, `STAR_PROJECTION_SEQUENCES`, `STAR_PROJECTION_SPEEDS`, `ANIMAL_PROJECTION_MODES`, `ANIMAL_PROJECTION_SPEEDS`, `SLEEP_STAGES_MODES`, `TIMER_DURATIONS`, `SLEEP_STAGE_TIMER_DURATIONS`, `SLEEP_TIMER_DURATIONS`, `CAPTIVE_PLAYLIST_TRACKS`, `SOOTHE_PLAYLIST_TRACKS`, `CUSTOM_COLORS`) as the source of truth for entity options and their numeric values. The integration does not keep its own copies of these tables.

Use one client per config entry. Entity methods must not create their own clients or issue raw protocol commands. The library's internal I/O lock serializes read-modify-write commands when several Home Assistant controls change close together.

The integration requires Python `>=3.14.2` (`pyproject.toml`'s `requires-python`) and Home Assistant `2026.9.1` or later (`hacs.json`'s `homeassistant` key, matching `pyproject.toml`'s `homeassistant>=2026.9.1` dev dependency). `fp-soother-lib` `>=1.1.0` is installed from PyPI and declared in both `manifest.json`'s `requirements`, which is what Home Assistant installs for users, and `pyproject.toml`'s `dependencies`, which covers the dev environment and tests.

### Discovery through Home Assistant Bluetooth

`fp_soother_lib` has no `SootherClient.discover()`. Its discovery helpers (`find_soother()`/`scan()` in `fp_soother_lib.scanner`) run a private, fixed-duration `BleakScanner` and are documented for standalone or CLI use, which does not suit a host that already owns Bluetooth scanning. `SootherClient` accepts `ble_device`/`ble_device_callback` so that a caller that already knows how to reach the device, such as Home Assistant's Bluetooth integration, can pass in a resolved `BLEDevice` (or a callback that re-resolves one on each reconnect) and skip the library's internal scan.

Home Assistant's Bluetooth integration covers the rest:

- `manifest.json` should declare a `bluetooth` matcher on `fp_soother_lib.constants.SERVICE_UUID` (`{"service_uuid": "<uuid>"}`), and add `bluetooth_adapters` to `dependencies` so remote adapters are connected before the integration starts.
- The config flow should implement the `bluetooth` discovery step, which that manifest matcher triggers automatically, and/or call `bluetooth.async_discovered_service_info(hass)` filtered by the same service UUID to list already-seen devices for a user-initiated flow.
- The coordinator should resolve a connectable `BLEDevice` with `bluetooth.async_ble_device_from_address(hass, address, connectable=True)` and pass it as `ble_device`, or wrap that call in a closure passed as `ble_device_callback` so `SootherClient` re-resolves the current best route on every reconnect. The library's docstring says `ble_device_callback` is "re-invoked on every call", so the integration should not cache one resolved device indefinitely.
- The device needs an active GATT connection for state reads and command writes as well as passive advertisement parsing, so the coordinator (see "Shared coordinator" below) should build on Home Assistant's `ActiveBluetoothDataUpdateCoordinator`.

`fp_soother_lib.scan()`/`find_soother()` must not be called from inside the integration.

Read these before changing discovery:

- <https://developers.home-assistant.io/docs/bluetooth>
- <https://developers.home-assistant.io/docs/core/bluetooth/bluetooth_fetching_data>
- <https://developers.home-assistant.io/docs/core/bluetooth/api>

## Device and runtime model

### One config entry, one device

Each discovered Deluxe Soother becomes one config entry and one Home Assistant device. The config entry should store:

- Bluetooth address or platform-specific BLE identifier.
- Session key returned by pairing, kept in config-entry data and not in an entity or option.

The device should use the stable identifier supplied by the library, preferably the address/identifier returned by discovery. Suggested device metadata:

- Name: `Deluxe Soother` (the user can rename it in Home Assistant).
- Manufacturer: `Fisher-Price`.
- Model: `Deluxe Soother (DYW47)`.
- Configuration URL: omitted, since there is no local web interface.

### Shared coordinator

Create a runtime object that holds the `SootherClient`, a shared state update mechanism, and connection/availability state. It builds on Home Assistant's `ActiveBluetoothDataUpdateCoordinator` (see "Discovery through Home Assistant Bluetooth" above), even though the device pushes its state once connected. Its lifecycle:

1. Open the client during entry setup.
2. Refresh the complete state once connected.
3. Register an `on_state_change` callback.
4. Forward state changes to all entities on the Home Assistant event loop.
5. Mark the device unavailable after an unexpected disconnect.
6. Reconnect using Home Assistant's normal retry/backoff behavior.
7. Close the client during unload.

Commands should update entities from the library's refreshed state, not from an optimistic local value. A failed command should raise the Home Assistant service error and leave the previous state intact.

## Entity inventory

The names below are proposed display names. Entity IDs should be generated from the device name, with stable unique IDs based on the config entry/device ID.

### Primary controls

| Platform       | Display name      | State source                                                  | Commands                                                              | Notes                                                                                                                                                                                                                                                                                                                                                                          |
| -------------- | ----------------- | ------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `media_player` | Sound             | `volume_level`, `sound_mode`                                  | `set_volume`, `set_sound_mode`                                        | Playing/paused is derived from `sound_mode` (`0` = paused, `1`-`16` = playing that track). `play_mode` has been confirmed not to track this reliably, so play and pause also go through `set_sound_mode`: pause sends `0`, and play restores the last non-zero `sound_mode`, defaulting to `1`. Volume is mapped from the device's 0-15 range to Home Assistant's 0-100 range. Uses the `speaker` device class. |
| `light`        | Night Light       | `nightlight_mode`, `nightlight_brightness`                    | `set_nightlight`, `set_nightlight_brightness`                         | Brightness is the native 0-7 range mapped to Home Assistant brightness.                                                                                                                                                                                                                                                                                                        |
| `light`        | Star Projection   | `star_projection_sequence_mode`, `star_projection_brightness` | `set_star_projection_sequence_mode`, `set_star_projection_brightness` | Mode 0 is off; modes 1-4 are effects.                                                                                                                                                                                                                                                                                                                                          |
| `light`        | Animal Projection | `animal_projection_mode`, `animal_projection_brightness`      | `set_animal_projection_mode`, `set_animal_projection_brightness`      | Mode 0 is off; modes 1-3 are effects.                                                                                                                                                                                                                                                                                                                                          |

### Option values

Every enum-like value (select options, light effects, media player sources, and the matching `apply_preset` fields) uses the library's own snake_case key from `fp_soother_lib.constants` as its state or attribute value, for example `very_fast`, `10_minutes`, `cool_colors`, or `its_raining_its_pouring`. These keys are stable across languages and are what automations, scripts, and actions use. The human-readable names below are display names only: `strings.json` translates them under `entity.select.<key>.state`, `entity.light.<key>.state_attributes.effect.state`, `entity.media_player.sound.state_attributes.source.state`, and `selector.<key>.options` for the action fields. Keyed options also let `icons.json` give individual states their own icons, which hassfest only allows for slug-shaped values.

Undocumented raw values get a generic fallback option, `<prefix>_<n>` (for example `mode_17` or `setting_12`). These have no translation, so the UI shows the raw option.

Track names in the playlist sensors and in `set_playlist`'s `tracks` (and the two `apply_preset` playlist fields) are not enum options. The sensors show human-readable names, so a track's playlist name matches its sound source's display name. The actions accept either that name or the library key, as described under Value formats.

The `media_player` source display names for the known sound values are:

- Sounds: Pink Noise, Brown Noise, Womb, Ocean, Nature, Wind.
- Settling: It's Raining, It's Pouring; Aurora; Six Little Ducks; Frere Jacques; Brahms: Lullaby.
- Soothing: Somewhere; Daylight; Dreaming Dawn; Motions; Polar Wind.

Only values 1-16 have documented meanings. Unknown values should appear as a generic `mode_<n>` source so they stay visible.

Light effect display names:

- Star Projection: Rainbow (1), Cool Colors (2), Warm Colors (3), Custom (4).
- Animal Projection: On (1), Lighthouse (2), Candle (3).

The light entities should use brightness as their primary adjustment and represent the device modes as Home Assistant effects.

### Advanced controls

These entities expose settings that do not fit cleanly into the primary light or media-player models:

| Platform | Display name            | State                        | Command                          | Options                                                                                                |
| -------- | ----------------------- | ---------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `select` | Star Projection Speed   | `star_projection_speed`      | `set_star_projection_speed`      | Slow (0), Normal (1), Fast (2), Very Fast (3); from `fp_soother_lib.constants.STAR_PROJECTION_SPEEDS`. |
| `select` | Animal Projection Speed | `animal_projection_speed`    | `set_animal_projection_speed`    | Slow (1), Fast (2); only meaningful for Lighthouse.                                                    |
| `select` | Music Timer             | `sound_timer_setting`        | `set_sound_timer`                | 5, 10, 15, 20, 25, 30, 60, 90 minutes, Continuous.                                                     |
| `select` | Light Timer             | `light_timer`                | `set_light_timer`                | 5, 10, 15, 20, 25, 30, 60, 90 minutes, Continuous.                                                     |
| `select` | Sleep Stages            | `sleep_stages_mode`          | `set_sleep_stages_mode`          | Off, Settle, Soothe, Sleep.                                                                            |
| `select` | Settle Timer            | `captive_sleep_stage_timer`  | `set_captive_sleep_stage_timer`  | 5-50 minutes in 5-minute steps, 60, 90.                                                                |
| `select` | Soothe Timer            | `soothe_sleep_stage_timer`   | `set_soothe_sleep_stage_timer`   | 5-50 minutes in 5-minute steps, 60, 90.                                                                |
| `select` | Sleep Timer             | `sleep_stage_timer`          | `set_sleep_stage_timer`          | 5-50 minutes in 5-minute steps, 60, 90, Continuous.                                                    |
| `sensor` | Settling Playlist       | `captive_playlist_selection` | None (see `set_playlist` action) | Comma-separated list of the selected settling track names, decoded from the device bitmask.            |
| `sensor` | Soothing Playlist       | `soothe_playlist_selection`  | None (see `set_playlist` action) | Comma-separated list of the selected soothing track names, decoded from the device bitmask.            |

A Home Assistant `select` cannot represent arbitrary combinations of tracks, so playlists are read-only `sensor` entities whose state is a comma-separated list of the selected track names (e.g. `Ocean, Nature, Wind`), decoded from the device bitmask using the known track-name mapping. Reserved or unknown bits should be rendered as a generic `Track <n>` label instead of being dropped, matching how other undocumented enum values are handled.

The custom action `fp_smart_connect.set_playlist` updates a playlist. It targets the device and accepts:

- `playlist`: `settling` or `soothing`.
- `tracks`: a list of tracks, each given either by name or by its numeric track index, validated against the known track mapping for that playlist.

The action resolves the requested track names to the device bitmask and calls `set_captive_playlist_selection` or `set_soothe_playlist_selection`. Unknown track names must be rejected with a clear validation error, so nothing is ignored or partially applied.

### Custom star colors

The protocol supports three custom color slots, each using a fixed palette: Off, Red, Orange, Yellow, Green, Blue, and Purple (`fp_soother_lib.constants.CUSTOM_COLORS`). `SootherState` exposes them as `star_projection_custom_color0`, `star_projection_custom_color1`, and `star_projection_custom_color2`, decoded from the live device state, and `set_star_projection_custom_colors(color0, color1, color2)` writes all three in one command.

Add three `select` entities, `Star Color 1`, `Star Color 2`, and `Star Color 3`, whose options are the `CUSTOM_COLORS` palette names. They do not accept arbitrary RGB colors. The device command sets all three slots together, so changing one entity's `select` must resend the other two slots' current values from `SootherClient.state`. This is the same read-modify-write pattern required elsewhere (e.g. `send_preset`).

### Diagnostics

Add these entities as diagnostic and disabled by default unless Home Assistant conventions require otherwise:

| Platform        | Display name       | State                 |
| --------------- | ------------------ | --------------------- |
| `sensor`        | Firmware Version   | `firmware_version`    |
| `sensor`        | Firmware API Level | `firmware_api_level`  |
| `sensor`        | Device Error       | `error`               |
| `binary_sensor` | Sound Expiring     | `sound_mode_expiring` |
| `binary_sensor` | Light Expiring     | `led_expiring`        |

Connection availability belongs on the device and its entities. Do not add a separate user-facing connection sensor.

Firmware update controls are out of scope unless the library exposes a safe, supported update API. The integration must never expose the raw OTA characteristic.

## Presets

`fp-soother-lib` exposes `SootherClient.send_preset(**overrides)`, which bundles every settable attribute into a single BLE write (device command 22), the same way the official app applies a "favorite" or preset. The integration can use it to change several attributes atomically instead of through sequential `set_*` calls. It is exposed as a custom action.

The library says its command-22 frame was reconstructed from the app, not from a live capture. `apply_preset` has been confirmed working on real devices running firmware v8 (shared-key frame layout) and v11 (unique-key layout).

Add `fp_smart_connect.apply_preset`, which targets the device and accepts an optional keyword parameter for each of the 21 attributes `send_preset` bundles (`PRESET_ATTRS`):

- `play_mode`, `sound_mode`, `volume_level`.
- `animal_projection_mode`, `animal_projection_brightness`, `animal_projection_speed`.
- `star_projection_sequence_mode`, `star_projection_custom_color0`, `star_projection_custom_color1`, `star_projection_custom_color2`, `star_projection_brightness`, `star_projection_speed`.
- `nightlight_mode`, `nightlight_brightness`.
- `sleep_stages_mode`.
- `captive_playlist_selection`, `soothe_playlist_selection`.
- `sound_timer_setting`, `light_timer`.
- `previous_animal_projection_mode`, `previous_star_projection_sequence_mode`.

Any field the caller omits is left for the library to fill from its own live state. `send_preset` already does this internally, so the action must not pre-fill omitted fields from a locally cached snapshot. Enum-like fields (modes, speeds, timers, colors) should accept the same options as the corresponding `select`/`light`/`media_player` entities (see Option values) instead of raw device integers, and playlist selections the same track names as the playlist sensors. Both validate against the same known-value mappings. As with `set_playlist`, unknown or out-of-range values must be rejected with a clear validation error, and nothing is partially applied.

Value formats, as implemented in `services.py`:

- Mode fields where 0 means off (`sound_mode`, `animal_projection_mode`, `star_projection_sequence_mode`, and the two `previous_*` modes) accept the entity options plus `off`.
- Enum fields also accept an option's English display name, in any case (`Very Fast`, `30 minutes`, `It's Raining, It's Pouring`). Input is normalized by lowercasing, dropping apostrophes, and collapsing other non-alphanumeric runs to `_` before validation, so labels and options can be mixed freely in one call. `tests/test_translations.py` checks that every English display name normalizes to its own option, so a display name that breaks this rule fails the tests. This applies only to `apply_preset`: Home Assistant validates `select.select_option`, light effects, and media player sources against the entity's own option list before the integration sees them.
- `play_mode` and `nightlight_mode` are booleans.
- Levels (`volume_level` and the three brightness fields) use the device's native ranges (0-15, 0-10, 0-7, or 0-6) instead of Home Assistant's 0-255 or 0.0-1.0 scales, so a preset round-trips exactly.
- Playlist selections take the same track list as `set_playlist`.
- Every parameter is optional, but at least one field is required.

The three sleep-stage countdown timers (`captive_sleep_stage_timer`, `soothe_sleep_stage_timer`, `sleep_stage_timer`) are not part of `send_preset`'s attribute set and must not be exposed through this action.

## Pairing and config flow

The config flow should discover Deluxe Soothers through Home Assistant's Bluetooth discovery, matching on `fp_soother_lib.constants.SERVICE_UUID`, and present the discovered device for selection (see "Discovery through Home Assistant Bluetooth" above). Pairing needs the user's help, because a new device must already be in its hardware pairing mode.

Proposed flow:

1. Discover supported devices via Home Assistant's Bluetooth integration.
2. Let the user select a device.
3. Construct a `SootherClient` with the stored session key (if present) and the resolved `BLEDevice`/`ble_device_callback`, then `open()` it.
4. If no session key exists (`client.is_paired` is `False`), explain that the device must be in pairing mode and run `client.pair()`.
5. Read the resulting key from `client.session_key`, persist it in config-entry data, and complete setup.
6. Perform the required clock synchronization after a fresh pairing. The library's `pair()` handles this where applicable; the integration should not construct RTC commands itself.

If the device cannot be reached, the flow should report a retryable connection error. It should not create a config entry with a guessed address or an empty session key.

## Availability and failure behavior

- Initial setup must fail if the device cannot connect or the initial state cannot be read.
- A transient BLE disconnect makes all entities unavailable while preserving their last state in Home Assistant.
- Reconnection should restore availability and refresh the complete state, including auxiliary sleep timers and infrastructure diagnostics.
- A command failure must be logged at warning/debug level with the entity and library exception, then surfaced to the caller as a failed Home Assistant action.
- Unsupported or undocumented enum values must be preserved and displayed with a fallback option. They must not make the whole entity unavailable.

## Resolved questions

1. `set_playlist` is a single unified action taking `device_id`, `playlist` (`settling` or `soothing`), and `tracks`. A track is either its name or its 1-based track number within the playlist, which selects bit `n - 1` of the mask. Names and the `playlist` value go through the same normalization as `apply_preset`'s enum fields (see Value formats), so `Brahms: Lullaby`, `brahms lullaby`, and the library key `brahms_lullaby` are the same track, and `Settling` is the same as `settling`. At least one track is required. Invalid input fails schema validation (`vol.Invalid`) with a message that names every unknown track and lists the valid choices, so nothing is partially applied.
2. `previous_animal_projection_mode` and `previous_star_projection_sequence_mode` are exposed as `apply_preset` parameters because `send_preset` writes them as part of the composite command. They accept the same effect options as the matching light, plus `off`.
