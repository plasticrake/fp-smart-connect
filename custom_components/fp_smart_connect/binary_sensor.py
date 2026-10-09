"""Binary sensor platform for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .entity import FpSootherEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )

    from . import FpSootherConfigEntry
    from .coordinator import FpSootherCoordinator

PARALLEL_UPDATES = 0


class FpSootherBinarySensorDescription(
    BinarySensorEntityDescription, frozen_or_thawed=True
):
    """Describes a Deluxe Soother binary sensor entity."""

    state_attr: str


BINARY_SENSOR_DESCRIPTIONS: tuple[FpSootherBinarySensorDescription, ...] = (
    FpSootherBinarySensorDescription(
        key="sound_expiring",
        translation_key="sound_expiring",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_attr="sound_mode_expiring",
    ),
    FpSootherBinarySensorDescription(
        key="light_expiring",
        translation_key="light_expiring",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_attr="led_expiring",
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: FpSootherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        FpSootherBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class FpSootherBinarySensor(FpSootherEntity, BinarySensorEntity):
    """A binary sensor entity backed by one SootherState flag."""

    entity_description: FpSootherBinarySensorDescription

    def __init__(
        self,
        coordinator: FpSootherCoordinator,
        description: FpSootherBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return True if the flag is set."""
        return bool(getattr(self._state, self.entity_description.state_attr))
