# Fisher-Price Smart Connect Home Assistant Integration

The **Fisher-Price Smart Connect** integration connects Home Assistant to [Fisher-Price Smart Connect](https://www.fisher-price.com/) devices over Bluetooth Low Energy (BLE). These are app-controlled baby soothers and nursery products. The integration talks to them directly over BLE, so Home Assistant can automate and monitor them. It supports only the Deluxe Soother (DYW47) for now, and exposes its night light, star projection, animal projection, and sound machine as entities.

State updates are pushed over a persistent BLE connection (`local_push`). The integration does not use a cloud account or app pairing beyond the one-time BLE pairing handshake described below.

## Supported Devices

- Deluxe Soother (DYW47) (Tested firmware versions: v8, v11)

## Prerequisites

- A Home Assistant host with Bluetooth support, using either a local Bluetooth adapter or [Bluetooth proxies](https://www.home-assistant.io/integrations/bluetooth/#remote-adapters-bluetooth-proxies) in range of the device.
- The Deluxe Soother must be in hardware pairing mode the first time it is added. Press and hold the on/off button until the chime plays. Pairing then establishes a session key that Home Assistant stores and reuses for later connections, so this is needed only once per device.

## Installation

### HACS (recommended)

1. In HACS, add this repository as a [custom repository](https://www.hacs.xyz/docs/faq/custom_repositories/) (category: Integration): `https://github.com/plasticrake/fp-smart-connect`.
2. Install "Fisher-Price Smart Connect" from HACS.
3. Restart Home Assistant.

### Manual

1. Copy the `custom_components/fp_smart_connect` directory from this repository into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

### Configuration

Once installed, put the Deluxe Soother into pairing mode. Home Assistant should discover it automatically via Bluetooth and prompt you to set it up; otherwise, go to **Settings → Devices & Services → Add Integration** and search for "Fisher-Price Smart Connect".

## Supported functionality

### Deluxe Soother (DYW47)

#### Media Players

- **Sound**: play/pause, volume, and the sound as its source.
  - **Sources**:
    - pink_noise
    - brown_noise
    - womb
    - ocean
    - nature
    - wind
    - its_raining_its_pouring
    - aurora
    - six_little_ducks
    - frere_jacques
    - brahms_lullaby
    - somewhere
    - daylight
    - dreaming_dawn
    - motions
    - polar_wind

#### Lights

- **Animal Projection**: on/off, brightness, and effects.
- **Night Light**: on/off and brightness.
- **Star Projection**: on/off, brightness, and effects.

#### Selects

- **Animal Projection Speed**
  - **Options**: slow, fast
- **Star Projection Speed**
  - **Options**: slow, medium, fast, very_fast
- **Music Timer**
  - **Options**: \<number\>_minutes, continuous
- **Light Timer**
  - **Options**: \<number\>_minutes, continuous
- **Sleep Stages**
  - **Options**: settle, soothe, sleep.
- **Settle Timer**
  - **Options**: \<number\>_minutes
- **Soothe Timer**
  - **Options**: \<number\>_minutes
- **Sleep Timer**
  - **Options**: \<number\>_minutes, continuous
- **Star Color 1**, **Star Color 2**, **Star Color 3**: the colors used by the **custom** Star Projection effect
  - **Options**: red, orange, yellow, green, blue, purple.

#### Sensors

- **Settling Playlist**, **Soothing Playlist**: the tracks selected in each playlist, also available as a `tracks` list attribute. Change them with the `set_playlist` action.

- **Diagnostics** (disabled by default):
  - **Firmware Version**
  - **Firmware API Level**
  - **Device Error**
  - **Sound Expiring** (Binary Sensor)
  - **Light Expiring** (Binary Sensor)

### Actions

#### `fp_smart_connect.set_playlist`

Replaces the tracks selected in one playlist.

| Field       | Description                                                                                                                                                                                                                                                                                        |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `device_id` | The Deluxe Soother to control.                                                                                                                                                                                                                                                                     |
| `playlist`  | `settling` or `soothing`.                                                                                                                                                                                                                                                                          |
| `tracks`    | One or more tracks, each by name (in any case, or as a key like `brahms_lullaby`) or by track number (1-5) within the playlist. Settling: It's Raining, It's Pouring; Aurora; Six Little Ducks; Frere Jacques; Brahms: Lullaby. Soothing: Somewhere; Daylight; Dreaming Dawn; Motions; Polar Wind. |

Unknown tracks are rejected and nothing is changed.

```yaml
action: fp_smart_connect.set_playlist
data:
  device_id: 0123456789abcdef0123456789abcdef
  playlist: settling
  tracks:
    - Aurora # display name
    - six_little_ducks # key
    - 5 # track number (Brahms: Lullaby)
```

##### `fp_smart_connect.apply_preset`

Changes several settings at once in a single write. Every field except `device_id` is optional, but at least one is required, and any field you leave out keeps its current value. Modes, speeds, timers, and colors use the same option values as the entities above, which are lowercase keys such as `ocean`, `very_fast`, `30_minutes`, or `blue` (modes also accept `off`). The display names shown in the UI also work, so `30 Minutes` and `30_minutes` mean the same thing. Brightness and volume use the device's native ranges: `volume_level` is 0-15, `animal_projection_brightness` is 0-10, `nightlight_brightness` is 0-7, and `star_projection_brightness` is 0-6. `captive_playlist_selection` (settling) and `soothe_playlist_selection` (soothing) take the same track lists as `set_playlist`. See the action's fields in **Developer tools → Actions** for the full list.

```yaml
action: fp_smart_connect.apply_preset
data:
  device_id: 0123456789abcdef0123456789abcdef
  sound_mode: ocean
  volume_level: 6
  nightlight_mode: true
  nightlight_brightness: 3
  star_projection_sequence_mode: "off"
  light_timer: 30_minutes
```

## Data Updates

The integration does not poll. When it is set up, it opens a Bluetooth connection to the device, reads the full device state once, and keeps the connection open. After that, the device pushes a notification whenever its state changes, including changes made with its physical buttons, and Home Assistant updates the entities right away. Commands sent from Home Assistant update the entities from the state the device reports back, not from an assumed value.

If the connection drops, or the device stops advertising over Bluetooth, all entities become unavailable. The integration tries to reconnect the next time Home Assistant receives a Bluetooth advertisement from the device. Once it reconnects, it reads the full state again and the entities become available.

## Examples

The examples below use the default entity IDs for a device named "Deluxe Soother". If you renamed the device or its entities, replace them with yours.

### Start a bedtime routine

Every evening, start brown noise at a low volume, dim the night light, and turn on the star projection with warm colors. All of these settings change in a single write with `apply_preset`, and the sound and lights turn off by themselves after an hour.

```yaml
automation:
  - alias: "Nursery: bedtime"
    triggers:
      - trigger: time
        at: "19:30:00"
    actions:
      - action: fp_smart_connect.apply_preset
        data:
          device_id: 0123456789abcdef0123456789abcdef
          sound_mode: brown_noise
          volume_level: 4
          sound_timer_setting: 60_minutes
          nightlight_mode: true
          nightlight_brightness: 2
          star_projection_sequence_mode: warm_colors
          star_projection_brightness: 2
          light_timer: 60_minutes
```

### Turn everything off in the morning

Use the standard entity actions to stop the sound and turn off all three lights.

```yaml
automation:
  - alias: "Nursery: morning"
    triggers:
      - trigger: time
        at: "07:00:00"
    actions:
      - action: media_player.media_pause
        target:
          entity_id: media_player.deluxe_soother_sound
      - action: light.turn_off
        target:
          entity_id:
            - light.deluxe_soother_night_light
            - light.deluxe_soother_star_projection
            - light.deluxe_soother_animal_projection
```

## Known Limitations

This integration relies on a stable Bluetooth connection to the device. If the connection is lost, the entities will become unavailable until the device is back in range and the connection is re-established. This integration does not provide the ability to update device firmware.

## Troubleshooting

If you encounter issues with the integration:

- Ensure the device is within Bluetooth range.
- Check the Home Assistant logs (Tools → System → Logs) for any error messages related to the integration.
- [Enable debug logging](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics) for the integration in Home Assistant to gather more detailed information.

## Removal

To remove the integration, go to **Settings → Devices & Services**, find the Fisher-Price Smart Connect integration entry, and select **Delete**. This removes the device and its entities from Home Assistant.

## AI Usage

Portions of this project (code, documentation, and/or reverse-engineering analysis) were developed with the assistance of AI tools. All AI-assisted contributions are reviewed by a human before being merged.

## Legal / Disclaimer

This is an independent, open-source project not affiliated with Fisher-Price or Mattel. Reverse engineering for interoperability purposes is generally permitted under applicable law (e.g. EU Software Directive, US DMCA §1201(f)). This project does not redistribute any Fisher-Price code or assets. Use at your own risk. "Fisher-Price" and "Deluxe Soother" are trademarks of their respective owners.

## License

MIT - see [LICENSE](LICENSE).
