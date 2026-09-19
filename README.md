# Fisher-Price Smart Connect Home Assistant Integration

The **Fisher-Price Smart Connect** integration connects Home Assistant to [Fisher-Price Smart Connect](https://www.fisher-price.com/) devices over Bluetooth Low Energy (BLE). Fisher-Price Smart Connect devices are app-controlled baby soothers and nurseries products; this integration talks to them directly over BLE, allowing Home Assistant to automate and monitor them. It currently supports only the Deluxe Soother (DYW47), exposing its night light, star projection, animal projection, and sound machine as entities.

State updates are pushed over a persistent BLE connection (`local_push`). The integration does not use a cloud account or app pairing beyond the one-time BLE pairing handshake described below.

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

## Removal

Removing this integration follows the standard Home Assistant procedure: go to **Settings → Devices & Services**, find the Fisher-Price Smart Connect integration entry, and select **Delete**. This removes the device and its entities from Home Assistant; no other cleanup is required.

## AI Usage

Portions of this project (code, documentation, and/or reverse-engineering analysis) were developed with the assistance of AI tools. All AI-assisted contributions are reviewed by a human before being merged.

## Legal / Disclaimer

This is an independent, open-source project not affiliated with Fisher-Price or Mattel. Reverse engineering for interoperability purposes is generally permitted under applicable law (e.g. EU Software Directive, US DMCA §1201(f)). This project does not redistribute any Fisher-Price code or assets. Use at your own risk. "Fisher-Price" and "Deluxe Soother" are trademarks of their respective owners.

## License

MIT - see [LICENSE](LICENSE).
