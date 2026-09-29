"""Sensor platform for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory

from .entity import FpSootherEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from fp_soother_lib import SootherState
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )
    from homeassistant.helpers.typing import StateType

    from . import FpSootherConfigEntry
    from .coordinator import FpSootherCoordinator


class FpSootherSensorDescription(SensorEntityDescription, frozen_or_thawed=True):
    """Describes a Deluxe Soother sensor entity."""

    value_fn: Callable[[SootherState], StateType]


SENSOR_DESCRIPTIONS: tuple[FpSootherSensorDescription, ...] = (
    FpSootherSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.firmware_version,
    ),
    FpSootherSensorDescription(
        key="firmware_api_level",
        translation_key="firmware_api_level",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.firmware_api_level,
    ),
    FpSootherSensorDescription(
        key="device_error",
        translation_key="device_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.error,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: FpSootherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        FpSootherSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class FpSootherSensor(FpSootherEntity, SensorEntity):
    """A read-only sensor entity derived from SootherState."""

    entity_description: FpSootherSensorDescription

    def __init__(
        self, coordinator: FpSootherCoordinator, description: FpSootherSensorDescription
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the sensor's value, or None if not yet known."""
        return self.entity_description.value_fn(self._state)
