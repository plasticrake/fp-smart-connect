"""Sensor platform for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory

from .entity import FpSootherEntity
from .mappings import (
    NO_TRACKS_LABEL,
    SETTLING_PLAYLIST_MAP,
    SOOTHING_PLAYLIST_MAP,
    PlaylistMapping,
)

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

PARALLEL_UPDATES = 0

ATTR_TRACKS = "tracks"


class FpSootherSensorDescription(SensorEntityDescription, frozen_or_thawed=True):
    """Describes a Deluxe Soother sensor entity."""

    value_fn: Callable[[SootherState], StateType]
    attributes_fn: Callable[[SootherState], dict[str, Any]] | None = None


def _playlist_description(
    key: str, state_attr: str, playlist: PlaylistMapping
) -> FpSootherSensorDescription:
    """
    Describe a read-only playlist sensor.

    The state is the selected track names joined with ", ", which can be
    ambiguous for names that contain a comma, so the same names are also
    exposed as a list attribute.
    """
    return FpSootherSensorDescription(
        key=key,
        translation_key=key,
        value_fn=lambda state: (
            ", ".join(playlist.labels_for(getattr(state, state_attr)))
            or NO_TRACKS_LABEL
        ),
        attributes_fn=lambda state: {
            ATTR_TRACKS: playlist.labels_for(getattr(state, state_attr))
        },
    )


SENSOR_DESCRIPTIONS: tuple[FpSootherSensorDescription, ...] = (
    _playlist_description(
        "settling_playlist", "captive_playlist_selection", SETTLING_PLAYLIST_MAP
    ),
    _playlist_description(
        "soothing_playlist", "soothe_playlist_selection", SOOTHING_PLAYLIST_MAP
    ),
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
    @override
    def native_value(self) -> StateType:
        """Return the sensor's value, or None if not yet known."""
        return self.entity_description.value_fn(self._state)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return any extra state attributes."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self._state)
