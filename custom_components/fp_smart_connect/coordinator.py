"""
The shared coordinator for the Fisher-Price Smart Connect integration.

Reconciles ActiveBluetoothDataUpdateCoordinator's connect-poll-disconnect
model (verified against the installed homeassistant.components.bluetooth
source) with a device that actually wants one persistent, push-notified GATT
connection for its whole lifetime:

- async_setup() performs the one required eager connection: it is the only
  path that can raise (surfaced by __init__.py as ConfigEntryNotReady), since
  the base class's own debounced poll mechanism deliberately swallows poll
  errors (see _async_poll in active_update_coordinator.py) so a single failed
  reconnect attempt can't crash the bluetooth manager.
- client.on_state_change()/on_disconnect() are registered exactly once, ever,
  in async_setup() -- SootherClient never clears these callback lists across
  close()/open() cycles, so re-registering on every reconnect would silently
  accumulate duplicate callbacks.
- "Poll" is repurposed as "reconnect": _needs_poll returns True whenever we
  don't currently hold a live connection, and the poll method's job is to
  (re)open the client and do a full state refresh, not a periodic read of an
  otherwise-idle link.
- available is overridden to AND the base class's own advertisement-presence
  tracking (self._available, true as long as the device is still advertising
  at all) with our own connection-health flag -- without this, a device that
  is still advertising but whose GATT link silently dropped would incorrectly
  report available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fp_soother_lib import SootherCommandError, SootherConnectionError
from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)

from .const import DEFAULT_NAME, MANUFACTURER, MODEL

if TYPE_CHECKING:
    import logging

    from fp_soother_lib import SootherClient, SootherState
    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
    from homeassistant.core import HomeAssistant


class FpSootherCoordinator(ActiveBluetoothDataUpdateCoordinator[None]):
    """Coordinates the long-lived SootherClient connection for one device."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        address: str,
        client: SootherClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger,
            address=address,
            mode=BluetoothScanningMode.ACTIVE,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_poll_soother,
            connectable=True,
        )
        self.client = client
        self.device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, format_mac(address))},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=DEFAULT_NAME,
        )
        self._connection_ready = False

    async def async_setup(self) -> None:
        """
        Open the connection and read the initial state.

        Called once from async_setup_entry. Raises SootherConnectionError or
        SootherCommandError on failure; the caller wraps that in
        ConfigEntryNotReady.
        """
        await self.client.open()
        await self.client.refresh_state()
        self.client.on_state_change(self._handle_state_change)
        self.client.on_disconnect(self._handle_disconnect)
        self._connection_ready = True

    async def async_shutdown(self) -> None:
        """Close the connection. Not covered by async_start()'s own unsub."""
        await self.client.close()

    @callback
    def _handle_state_change(self, _state: SootherState) -> None:
        """Handle a pushed state notification (including physical buttons)."""
        self.async_update_listeners()

    @callback
    def _handle_disconnect(self) -> None:
        """Handle an unexpected disconnect."""
        self.logger.warning("%s: disconnected unexpectedly", self.address)
        self._connection_ready = False
        self.async_update_listeners()

    def _needs_poll(
        self,
        _service_info: BluetoothServiceInfoBleak,
        _seconds_since_last_poll: float | None,
    ) -> bool:
        """Reconnect whenever we don't currently hold a live connection."""
        return not self._connection_ready

    async def _async_poll_soother(
        self, _service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Reconnect (if needed) and do a full state refresh."""
        try:
            if not self.client.is_connected:
                await self.client.open()
            await self.client.refresh_state()
        except SootherConnectionError, SootherCommandError:
            self._connection_ready = False
            raise
        self._connection_ready = True

    @property
    def available(self) -> bool:
        """Return True only if still advertising AND our GATT link is up."""
        return super().available and self._connection_ready
