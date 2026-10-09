"""Diagnostics support for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from homeassistant.components import bluetooth
from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_SESSION_KEY

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import FpSootherConfigEntry

TO_REDACT = {CONF_SESSION_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FpSootherConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    client = coordinator.client

    # raw_state holds the undescrambled CHAR_STATE plaintext, including the
    # rolling command-auth token, so it is left out along with the session key.
    state = dataclasses.asdict(client.state)
    state.pop("raw_state", None)

    service_info = bluetooth.async_last_service_info(
        hass, coordinator.address, connectable=True
    )

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "coordinator": {"available": coordinator.available},
        "client": {
            "is_connected": client.is_connected,
            "uses_shared_key": client.uses_shared_key,
            "peripheral_type": client.peripheral_type,
        },
        "advertisement": None
        if service_info is None
        else {
            "source": service_info.source,
            "rssi": service_info.rssi,
            "connectable": service_info.connectable,
        },
        "state": state,
    }
