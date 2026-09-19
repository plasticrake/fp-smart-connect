# Deluxe Soother Entity Design

## Purpose

This document defines the Home Assistant model for the Fisher-Price Smart Connect Deluxe Soother (DYW47). The integration will use the `fp-soother-lib` package as its BLE and protocol boundary. It should not duplicate encryption, packet construction, bit-field decoding, or connection management.

The device is a single physical unit with three independently controllable light/projection functions and one audio function. Home Assistant should expose those functions as a small set of familiar entities, while retaining access to the device's discrete settings.

## Library contract

The integration depends on these public library capabilities:

- `SootherClient(address, ble_device=..., ble_device_callback=...)` / `SootherClient.open()` and `close()` for the long-lived Home Assistant connection lifecycle. There is no `SootherClient.discover()`; discovery is covered separately below.
- `SootherClient.pair()` for first-use pairing, and the `session_key` / `is_paired` properties for reading the result and deciding whether pairing is needed.
- `SootherClient.refresh_state()` for the initial complete state read.
- `SootherClient.on_state_change()` for BLE notifications, including physical button changes.
- `SootherClient.state` (`SootherState`) for the last known state.
- The typed `set_*` methods for all supported device commands.
- `SootherClient.send_preset(**overrides)` for the composite multi-attribute write (see Presets below).
- The named value mappings in `fp_soother_lib.constants` (e.g. `SOUND_MODES`, `STAR_PROJECTION_SEQUENCES`, `STAR_PROJECTION_SPEEDS`, `ANIMAL_PROJECTION_MODES`, `ANIMAL_PROJECTION_SPEEDS`, `SLEEP_STAGES_MODES`, `TIMER_DURATIONS`, `SLEEP_STAGE_TIMER_DURATIONS`, `SLEEP_TIMER_DURATIONS`, `CAPTIVE_PLAYLIST_TRACKS`, `SOOTHE_PLAYLIST_TRACKS`, `CUSTOM_COLORS`) as the source of truth for entity option labels and their numeric values, instead of the integration inventing or re-deriving its own tables.

Use one client per config entry. Entity methods must not create their own clients or issue raw protocol commands. The library's internal I/O lock serializes read-modify-write commands when several Home Assistant controls change close together.

Confirmed version floor for publishing `fp-soother-lib` so it installs correctly alongside this integration: Python `>=3.14.7` (`pyproject.toml`'s `requires-python`) and Home Assistant `2026.8.3`+ (`hacs.json`'s `homeassistant` key, `pyproject.toml`'s `homeassistant>=2026.9.1` dev dependency). `manifest.json`'s `requirements` is still `[]` pending a published, version-pinned `fp-soother-lib` release -- that's a separate, still-open packaging step, not a version question.

### Discovery is the integration's responsibility, not the library's

`fp_soother_lib` has no `SootherClient.discover()`. Its discovery helpers (`find_soother()`/`scan()` in `fp_soother_lib.scanner`) run a private, fixed-duration `BleakScanner` and are documented as being for standalone/CLI use, not for a host that already owns Bluetooth scanning. `SootherClient` instead accepts `ble_device`/`ble_device_callback` so a caller that already knows how to reach the device, such as Home Assistant's own Bluetooth integration, can hand over an already-resolved `BLEDevice` (or a callback that re-resolves one on each reconnect) instead of triggering the library's internal scan.

Home Assistant's own Bluetooth integration provides everything needed instead:

- `manifest.json` should declare a `bluetooth` matcher on `fp_soother_lib.constants.SERVICE_UUID` (`{"service_uuid": "<uuid>"}`), and add `bluetooth_adapters` to `dependencies` so remote adapters are connected before the integration starts.
- The config flow should implement the `bluetooth` discovery step (triggered automatically by that manifest matcher), and/or call `bluetooth.async_discovered_service_info(hass)` filtered by the same service UUID to list already-seen devices for a user-initiated flow.
- The coordinator should resolve a connectable `BLEDevice` with `bluetooth.async_ble_device_from_address(hass, address, connectable=True)` and pass it as `ble_device`, or wrap that same call in a closure passed as `ble_device_callback` so `SootherClient` re-resolves the current best route on every reconnect. The library's docstring notes that `ble_device_callback` is "re-invoked on every call", so the integration should not cache one resolved device indefinitely.
- Because the device needs an active GATT connection for both state reads and command writes as well as passive advertisement parsing, the coordinator (see "Shared coordinator" below) should build on Home Assistant's `ActiveBluetoothDataUpdateCoordinator` rather than a fully bespoke object.

`fp_soother_lib.scan()`/`find_soother()` must not be called from inside the
integration.

Reference reading for this section before implementation:

- <https://developers.home-assistant.io/docs/bluetooth>
- <https://developers.home-assistant.io/docs/core/bluetooth/bluetooth_fetching_data>
- <https://developers.home-assistant.io/docs/core/bluetooth/api>

## Device and runtime model

### One config entry, one device

Each discovered Deluxe Soother becomes one config entry and one Home Assistant device. The config entry should store:

- Bluetooth address or platform-specific BLE identifier.
- Session key returned by pairing, stored in config-entry data rather than an entity or option.

The device should use the stable identifier supplied by the library, preferably the address/identifier returned by discovery. Suggested device metadata:

- Name: `Deluxe Soother` (allow the user to rename it in Home Assistant).
- Manufacturer: `Fisher-Price`.
- Model: `Deluxe Soother (DYW47)`.
- Configuration URL: omitted; there is no local web interface.

### Shared coordinator

Create a runtime object containing the `SootherClient`, a shared state update mechanism, and connection/availability state, built on Home Assistant's `ActiveBluetoothDataUpdateCoordinator` (see "Discovery is the integration's responsibility" above) rather than a fully bespoke object, even though the device is push-oriented once connected:

1. Open the client during entry setup.
2. Refresh the complete state once connected.
3. Register an `on_state_change` callback.
4. Forward state changes to all entities on the Home Assistant event loop.
5. Mark the device unavailable after an unexpected disconnect.
6. Reconnect using Home Assistant's normal retry/backoff behavior.
7. Close the client during unload.

Commands should update entities from the library's refreshed state, not from an optimistic local value. A failed command should raise the Home Assistant service error and leave the previous state intact.

## Entity inventory

The names below are proposed display names. Entity IDs should be generated from the device name and stable unique IDs based on the config entry/device ID.

### Primary controls

| Platform       | Display name      | State source                                                  | Commands                                                              | Notes                                                                                                                                                                                                                                                                                                                                                                      |
| -------------- | ----------------- | ------------------------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `media_player` | Sound             | `volume_level`, `sound_mode`                                  | `set_volume`, `set_sound_mode`                                        | Playing/paused is derived from `sound_mode` (`0` = paused, `1`-`16` = playing that track) -- confirmed `play_mode` does not reliably track this, so play/pause commands go through `set_sound_mode` too (pause sends `0`; play restores the last non-zero `sound_mode`, defaulting to `1`). Volume is mapped from the device's 0-15 range to Home Assistant's 0-100 range. |
| `light`        | Night Light       | `nightlight_mode`, `nightlight_brightness`                    | `set_nightlight`, `set_nightlight_brightness`                         | Brightness is the native 0-7 range mapped to Home Assistant brightness.                                                                                                                                                                                                                                                                                                    |
| `light`        | Star Projection   | `star_projection_sequence_mode`, `star_projection_brightness` | `set_star_projection_sequence_mode`, `set_star_projection_brightness` | Mode 0 is off; modes 1-4 are effects.                                                                                                                                                                                                                                                                                                                                      |
| `light`        | Animal Projection | `animal_projection_mode`, `animal_projection_brightness`      | `set_animal_projection_mode`, `set_animal_projection_brightness`      | Mode 0 is off; modes 1-3 are effects.                                                                                                                                                                                                                                                                                                                                      |

The `media_player` source list should use stable, human-readable labels for the known sound values:

- Sounds: Pink Noise, Brown Noise, Womb, Ocean, Nature, Wind.
- Settling: It's Raining, It's Pouring; Aurora; Six Little Ducks; Frere Jacques; Brahms: Lullaby.
- Soothing: Somewhere; Daylight; Dreaming Dawn; Motions; Polar Wind.

Only values 1-16 have documented meanings. Unknown values should remain visible as a generic `Mode <n>` source rather than being silently rewritten.

Light effect mappings:

- Star Projection: Rainbow (1), Cool Colors (2), Warm Colors (3), Custom (4).
- Animal Projection: On (1), Lighthouse (2), Candle (3).

The light entities should use brightness as their primary adjustment. Effects are the appropriate Home Assistant representation for these device modes.

### Advanced controls

These entities expose settings that do not fit cleanly into the primary light or media-player models:

| Platform | Display name            | State                        | Command                         | Options                                                                                                |
| -------- | ----------------------- | ---------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `select` | Star Projection Speed   | `star_projection_speed`      | `set_star_projection_speed`     | Slow (0), Normal (1), Fast (2), Very Fast (3); from `fp_soother_lib.constants.STAR_PROJECTION_SPEEDS`. |
| `select` | Animal Projection Speed | `animal_projection_speed`    | `set_animal_projection_speed`   | Slow (1), Fast (2); only meaningful for Lighthouse.                                                    |
| `select` | Music Timer             | `sound_timer_setting`        | `set_sound_timer`               | 5, 10, 15, 20, 25, 30, 60, 90 minutes, Continuous.                                                     |
| `select` | Light Timer             | `light_timer`                | `set_light_timer`               | 5, 10, 15, 20, 25, 30, 60, 90 minutes, Continuous.                                                     |
| `select` | Sleep Stages            | `sleep_stages_mode`          | `set_sleep_stages_mode`         | Off, Settle, Soothe, Sleep.                                                                            |
| `select` | Settle Timer            | `captive_sleep_stage_timer`  | `set_captive_sleep_stage_timer` | 5-50 minutes in 5-minute steps, 60, 90.                                                                |
| `select` | Soothe Timer            | `soothe_sleep_stage_timer`   | `set_soothe_sleep_stage_timer`  | 5-50 minutes in 5-minute steps, 60, 90.                                                                |
| `select` | Sleep Timer             | `sleep_stage_timer`          | `set_sleep_stage_timer`         | 5-50 minutes in 5-minute steps, 60, 90, Continuous.                                                    |
| `sensor` | Settling Playlist       | `captive_playlist_selection` | — (see `set_playlist` action)   | Comma-separated list of the selected settling track names, decoded from the device bitmask.            |
| `sensor` | Soothing Playlist       | `soothe_playlist_selection`  | — (see `set_playlist` action)   | Comma-separated list of the selected soothing track names, decoded from the device bitmask.            |

A Home Assistant `select` cannot naturally represent arbitrary combinations of tracks, so playlists are exposed as read-only `sensor` entities whose state is a comma-separated list of the selected track names (e.g. `Ocean, Nature, Wind`), decoded from the device bitmask using the known track-name mapping. Any reserved/unknown bits should be rendered as a generic `Track <n>` label rather than dropped, consistent with the handling of other undocumented enum values.

Updating a playlist is exposed as a custom Home Assistant action, e.g. `fp_smart_connect.set_playlist`, targeting the device and accepting:

- `playlist`: `settling` or `soothing`.
- `tracks`: a list of tracks, each given either by name or by its numeric track index, validated against the known track mapping for that playlist.

The action resolves the requested track names to the device bitmask and calls `set_captive_playlist_selection` or `set_soothe_playlist_selection` accordingly. Unknown track names must be rejected with a clear validation error rather than silently ignored or partially applied.

### Custom star colors

The protocol supports three custom color slots, each using a fixed palette: Off, Red, Orange, Yellow, Green, Blue, and Purple (`fp_soother_lib.constants.CUSTOM_COLORS`). `SootherState` now exposes these as `star_projection_custom_color0`, `star_projection_custom_color1`, and `star_projection_custom_color2` (decoded from the live device state, not only local defaults), and the library provides `set_star_projection_custom_colors(color0, color1, color2)` to write all three in one command. Custom colors no longer need to be deferred.

Add three `select` entities, `Star Color 1`, `Star Color 2`, and `Star Color 3`, using the `CUSTOM_COLORS` palette names as their options rather than arbitrary RGB colors. Because the device command sets all three slots together, changing one entity's `select` must resend the other two slots' current values from `SootherClient.state`, the same read-modify-write pattern already required elsewhere (e.g. `send_preset`).

### Diagnostics

Add these entities as diagnostic and disabled-by-default unless Home Assistant conventions require otherwise:

| Platform        | Display name       | State                 |
| --------------- | ------------------ | --------------------- |
| `sensor`        | Firmware Version   | `firmware_version`    |
| `sensor`        | Firmware API Level | `firmware_api_level`  |
| `sensor`        | Device Error       | `error`               |
| `binary_sensor` | Sound Expiring     | `sound_mode_expiring` |
| `binary_sensor` | Light Expiring     | `led_expiring`        |

Connection availability belongs on the device/entities themselves and should not be duplicated as a user-facing connection sensor.

## Presets

`fp-soother-lib` exposes `SootherClient.send_preset(**overrides)`, which bundles every settable attribute into a single BLE write (device command 22), mirroring the real app's "favorite"/preset apply. This lets the integration change several attributes atomically in one write, instead of using sequential `set_*` calls, so it should be exposed as a custom action rather than another entity.

Add `fp_smart_connect.apply_preset`, targeting the device, accepting optional keyword parameters for each of the 21 attributes `send_preset` bundles (`PRESET_ATTRS`):

- `play_mode`, `sound_mode`, `volume_level`.
- `animal_projection_mode`, `animal_projection_brightness`, `animal_projection_speed`.
- `star_projection_sequence_mode`, `star_projection_custom_color0`, `star_projection_custom_color1`, `star_projection_custom_color2`, `star_projection_brightness`, `star_projection_speed`.
- `nightlight_mode`, `nightlight_brightness`.
- `sleep_stages_mode`.
- `captive_playlist_selection`, `soothe_playlist_selection`.
- `sound_timer_setting`, `light_timer`.
- `previous_animal_projection_mode`, `previous_star_projection_sequence_mode`.

All parameters are optional. Any field the caller omits must be left for the library to fill from its own live state. `send_preset` already does this internally, so the action must not pre-fill omitted fields from a locally cached snapshot. Enum-like fields (modes, speeds, timers, playlist selections) should accept the same human-readable labels used by the corresponding `select`/`light`/`sensor` entities elsewhere in this document, not raw device integers, and validate against the same known-value mappings. Unknown or out-of-range values must be rejected with a clear validation error rather than partially applied, consistent with `set_playlist`.

The three sleep-stage countdown timers (`captive_sleep_stage_timer`, `soothe_sleep_stage_timer`, `sleep_stage_timer`) are not part of `send_preset`'s attribute set and must not be exposed through this action.

## Pairing and config flow

The config flow should discover Deluxe Soothers through Home Assistant's own Bluetooth discovery, matching on `fp_soother_lib.constants.SERVICE_UUID`, and present the discovered device for selection (see "Discovery is the integration's responsibility" above). Pairing is a user-assisted operation because a new device must already be in its hardware pairing mode.

Proposed flow:

1. Discover supported devices via Home Assistant's Bluetooth integration.
2. Let the user select a device.
3. Construct a `SootherClient` with the stored session key (if present) and the resolved `BLEDevice`/`ble_device_callback`, then `open()` it.
4. If no session key exists (`client.is_paired` is `False`), explain that the device must be in pairing mode and run `client.pair()`.
5. Read the resulting key from `client.session_key`, persist it in config-entry data, and complete setup.
6. Perform the required clock synchronization after a fresh pairing. The library's `pair()` currently owns this protocol concern where applicable; the integration should not construct RTC commands itself.

If the device cannot be reached, the flow should report a retryable connection error. It should not create a config entry with a guessed address or an empty session key.

## Availability and failure behavior

- Initial setup must fail if the device cannot connect or the initial state cannot be read.
- A transient BLE disconnect makes all entities unavailable, while preserving their last state in Home Assistant.
- Reconnection should restore availability and refresh the complete state, including auxiliary sleep timers and infrastructure diagnostics.
- A command failure must be logged at warning/debug level with the entity and library exception, then surfaced to the caller as a failed Home Assistant action.
- Unsupported or undocumented enum values must be preserved and displayed with a fallback label. They must not cause the whole entity to become unavailable.

## Implementation phases

### Phase 1: useful core

- Add the `fp-soother-lib` dependency.
- Implement discovery, pairing, stored session keys, shared client lifecycle, notifications, reconnect, and unload.
- Add the `media_player`, three `light` entities, and timer/sleep-stage selects.
- Add focused tests for state-to-entity mapping and command delegation.

### Phase 2: completeness

- Add the playlist `sensor` entities and the `set_playlist` action.
- Add the `apply_preset` action using `send_preset`.
- Add diagnostic sensors and expiring binary sensors.
- Add the three custom star color `select` entities.

### Phase 3: library-backed extras

- Add presets only after the library supports the device's actual preset commands and state.
- Add firmware/update controls only if the library exposes a safe, supported update API. The integration should not expose raw OTA characteristics.

## Open questions to resolve before implementation

1. Confirm the exact schema for the `set_playlist` action (single unified service vs. one per playlist, and how invalid track names should be reported) before implementation.
2. Confirm whether `previous_animal_projection_mode` and `previous_star_projection_sequence_mode` should really be exposed as `apply_preset` parameters. `SootherState` documents them as read-only status fields, but `send_preset`'s attribute set (`PRESET_ATTRS`) includes them in the composite write.
