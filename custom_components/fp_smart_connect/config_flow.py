"""Config flow for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from bleak.exc import BleakError
from fp_soother_lib import SootherClient, SootherCommandError, SootherConnectionError
from fp_soother_lib.constants import SERVICE_UUID
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_SESSION_KEY, DEFAULT_NAME, DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak


async def _async_try_pair(discovery_info: BluetoothServiceInfoBleak) -> str:
    """
    Pair with a device already in its hardware pairing mode.

    Returns the resulting session key, hex-encoded for JSON-serializable
    config-entry storage. Raises SootherConnectionError (device unreachable),
    SootherCommandError (a pairing write was rejected, e.g. the device refused
    the key request), or TimeoutError (the device never replied to the key
    request) on failure. The latter two most likely mean the device is not
    actually in pairing mode.

    pair() owns its own connection lifecycle, so no open() beforehand: an
    extra connection would just be torn down by pair() straight away.
    """
    client = SootherClient(discovery_info.address, ble_device=discovery_info.device)
    try:
        await client.pair()
    except BleakError as exc:
        # fp-soother-lib lets GATT errors from the key-request write escape
        # unwrapped (e.g. the device answering with an ATT error).
        msg = f"Pairing write rejected: {exc}"
        raise SootherCommandError(msg) from exc
    finally:
        await client.close()
    assert client.session_key is not None
    return client.session_key.hex()


def _title_for(address: str) -> str:
    """Return a config-entry title disambiguated by address."""
    return f"{DEFAULT_NAME} ({format_mac(address)})"


class FpSootherConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Fisher-Price Smart Connect integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """
        Handle a discovery via Home Assistant's bluetooth integration.

        The manifest's service_uuid matcher already filtered this to
        supported devices; no further filtering is needed here.
        """
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": _title_for(discovery_info.address)
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm pairing mode, then pair, with a discovered device."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info

        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(step_id="bluetooth_confirm")

        try:
            session_key_hex = await _async_try_pair(discovery_info)
        except SootherConnectionError:
            return self.async_show_form(
                step_id="bluetooth_confirm", errors={"base": "cannot_connect"}
            )
        except SootherCommandError, TimeoutError:
            LOGGER.exception("Pairing failed for %s", discovery_info.address)
            return self.async_show_form(
                step_id="bluetooth_confirm", errors={"base": "pairing_failed"}
            )

        return self.async_create_entry(
            title=_title_for(discovery_info.address),
            data={
                CONF_ADDRESS: discovery_info.address,
                CONF_SESSION_KEY: session_key_hex,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated setup, picking from already-seen devices."""
        errors: dict[str, str] = {}

        if user_input is not None and CONF_ADDRESS in user_input:
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            await self.async_set_unique_id(
                format_mac(discovery_info.address), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            try:
                session_key_hex = await _async_try_pair(discovery_info)
            except SootherConnectionError:
                errors["base"] = "cannot_connect"
            except SootherCommandError, TimeoutError:
                LOGGER.exception("Pairing failed for %s", discovery_info.address)
                errors["base"] = "pairing_failed"
            else:
                return self.async_create_entry(
                    title=_title_for(discovery_info.address),
                    data={
                        CONF_ADDRESS: discovery_info.address,
                        CONF_SESSION_KEY: session_key_hex,
                    },
                )

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass):
            if (
                format_mac(discovery_info.address) in current_addresses
                or discovery_info.address in self._discovered_devices
                or SERVICE_UUID.lower()
                not in {uuid.lower() for uuid in discovery_info.service_uuids}
            ):
                continue
            self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            # No hard abort here: re-showing this form (instead of ending the
            # flow) is what lets the user put the device into pairing mode
            # and retry the scan by resubmitting, without restarting setup.
            errors.setdefault("base", "no_devices_found")
            self._set_confirm_only()
            return self.async_show_form(step_id="user", errors=errors)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: _title_for(address)
                            for address in self._discovered_devices
                        }
                    )
                }
            ),
            errors=errors,
        )
