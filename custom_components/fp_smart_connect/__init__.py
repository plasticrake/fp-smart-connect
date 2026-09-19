"""The Fisher-Price Smart Connect integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fp_soother_lib import SootherClient, SootherCommandError, SootherConnectionError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SESSION_KEY, DOMAIN, LOGGER
from .coordinator import FpSootherCoordinator

if TYPE_CHECKING:
    from fp_soother_lib import BLEDevice
    from homeassistant.core import HomeAssistant

_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.LIGHT, Platform.SELECT]

type FpSootherConfigEntry = ConfigEntry[FpSootherCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FpSootherConfigEntry) -> bool:
    """Set up a Deluxe Soother from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    session_key = bytes.fromhex(entry.data[CONF_SESSION_KEY])

    def _resolve_ble_device() -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        )
        if device is None:
            msg = f"Could not resolve a BLE route to {address}"
            raise SootherConnectionError(msg)
        return device

    client = SootherClient(
        address, session_key=session_key, ble_device_callback=_resolve_ble_device
    )
    coordinator = FpSootherCoordinator(hass, LOGGER, address=address, client=client)

    try:
        await coordinator.async_setup()
    except (SootherConnectionError, SootherCommandError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"address": address, "error": str(err)},
        ) from err

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FpSootherConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
