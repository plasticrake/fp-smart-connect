# Fisher-Price Smart Connect Home Assistant Integration

The **Fisher-Price Smart Connect** integration connects Home Assistant to [Fisher-Price Smart Connect](https://www.fisher-price.com/) devices over Bluetooth Low Energy (BLE). Fisher-Price Smart Connect devices are app-controlled baby soothers and nurseries products; this integration talks to them directly over BLE, allowing Home Assistant to automate and monitor them. It currently supports only the Deluxe Soother (DYW47), exposing its night light, star projection, animal projection, and sound machine as entities.

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

## Entities

- **Sound** (media player): play/pause, volume, and the sound as its source.
- **Night Light**, **Star Projection**, **Animal Projection** (lights): on/off and brightness. The projections expose their modes as effects.
- **Selects**: Star Projection Speed, Animal Projection Speed, Music Timer, Light Timer, Sleep Stages, Settle Timer, Soothe Timer, Sleep Timer, and Star Color 1-3 (the colors used by the Custom star effect).
- **Settling Playlist**, **Soothing Playlist** (sensors): the tracks selected in each playlist, also available as a `tracks` list attribute. Change them with the `set_playlist` action.
- **Diagnostics** (disabled by default): Firmware Version, Firmware API Level, Device Error, Sound Expiring, and Light Expiring.

## Actions

### `fp_smart_connect.set_playlist`

Replaces the tracks selected in one playlist.

| Field       | Description                                                                                                                                                                                                                                       |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `device_id` | The Deluxe Soother to control.                                                                                                                                                                                                                    |
| `playlist`  | `settling` or `soothing`.                                                                                                                                                                                                                         |
| `tracks`    | One or more tracks, each by name or by track number (1-5) within the playlist. Settling: It's Raining, It's Pouring; Aurora; Six Little Ducks; Frere Jacques; Brahms: Lullaby. Soothing: Somewhere; Daylight; Dreaming Dawn; Motions; Polar Wind. |

Unknown tracks are rejected and nothing is changed.

```yaml
action: fp_smart_connect.set_playlist
data:
  device_id: 0123456789abcdef0123456789abcdef
  playlist: settling
  tracks:
    - Aurora
    - Six Little Ducks
```

### `fp_smart_connect.apply_preset`

Changes several settings at once in a single write. Every field except `device_id` is optional, but at least one is required, and any field you leave out keeps its current value. Modes, speeds, timers, and colors use the same labels as the entities above (modes also accept `Off`). Brightness and volume use the device's native ranges: `volume_level` and `animal_projection_brightness` are 0-15, and `star_projection_brightness` and `nightlight_brightness` are 0-7. `captive_playlist_selection` (settling) and `soothe_playlist_selection` (soothing) take the same track lists as `set_playlist`. See the action's fields in **Developer tools → Actions** for the full list.

```yaml
action: fp_smart_connect.apply_preset
data:
  device_id: 0123456789abcdef0123456789abcdef
  sound_mode: Ocean
  volume_level: 6
  nightlight_mode: true
  nightlight_brightness: 3
  star_projection_sequence_mode: "Off"
  light_timer: 30 Minutes
```

## Removal

Removing this integration follows the standard Home Assistant procedure: go to **Settings → Devices & Services**, find the Fisher-Price Smart Connect integration entry, and select **Delete**. This removes the device and its entities from Home Assistant; no other cleanup is required.

## AI Usage

Portions of this project (code, documentation, and/or reverse-engineering analysis) were developed with the assistance of AI tools. All AI-assisted contributions are reviewed by a human before being merged.

## Legal / Disclaimer

This is an independent, open-source project not affiliated with Fisher-Price or Mattel. Reverse engineering for interoperability purposes is generally permitted under applicable law (e.g. EU Software Directive, US DMCA §1201(f)). This project does not redistribute any Fisher-Price code or assets. Use at your own risk. "Fisher-Price" and "Deluxe Soother" are trademarks of their respective owners.

## License

MIT - see [LICENSE](LICENSE).
