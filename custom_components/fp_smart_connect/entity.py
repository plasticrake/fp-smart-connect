"""Shared entity base class for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.helpers.device_registry import format_mac

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from fp_soother_lib import SootherState

    from .coordinator import FpSootherCoordinator


class FpSootherEntity(PassiveBluetoothCoordinatorEntity["FpSootherCoordinator"]):
    """Base entity for all Deluxe Soother entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FpSootherCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{format_mac(coordinator.address)}_{key}"
        self._attr_device_info = coordinator.device_info

    @property
    def _state(self) -> SootherState:
        """Return the last known device state."""
        return self.coordinator.client.state

    async def _async_command(
        self,
        coro: Awaitable[None],
        *,
        translation_key: str = "command_failed",
    ) -> None:
        """Run a SootherClient command, translating library errors to HA errors."""
        await self.coordinator.async_command(coro, translation_key=translation_key)
