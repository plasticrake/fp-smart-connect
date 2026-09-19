"""Light platform for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fp_soother_lib.constants import ANIMAL_PROJECTION_MODES, STAR_PROJECTION_SEQUENCES
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import FpSootherEntity
from .mappings import (
    ANIMAL_PROJECTION_BRIGHTNESS_MAX,
    NIGHTLIGHT_BRIGHTNESS_MAX,
    STAR_PROJECTION_BRIGHTNESS_MAX,
    EnumMapping,
    scale_from_ha_brightness,
    scale_to_ha_brightness,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fp_soother_lib import SootherClient
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )

    from . import FpSootherConfigEntry
    from .coordinator import FpSootherCoordinator

DEFAULT_MODE = 1


@dataclass(frozen=True)
class FpSootherLightDescription:
    """
    Describes a Deluxe Soother light entity.

    set_mode/set_brightness are stored as callables (not plain method names)
    because the underlying commands don't share one argument shape: the
    Night Light's set_nightlight() takes a bool, while the two projection
    lights' mode setters take an int mode.
    """

    key: str
    translation_key: str
    mode_attr: str
    brightness_attr: str
    native_max: int
    set_mode: Callable[[SootherClient, int], Awaitable[None]]
    set_brightness: Callable[[SootherClient, int], Awaitable[None]]
    effect_map: EnumMapping | None = None
    previous_mode_attr: str | None = None


NIGHT_LIGHT = FpSootherLightDescription(
    key="nightlight",
    translation_key="nightlight",
    mode_attr="nightlight_mode",
    brightness_attr="nightlight_brightness",
    native_max=NIGHTLIGHT_BRIGHTNESS_MAX,
    set_mode=lambda client, mode: client.set_nightlight(bool(mode)),
    set_brightness=lambda client, level: client.set_nightlight_brightness(level),
)

STAR_PROJECTION = FpSootherLightDescription(
    key="star_projection",
    translation_key="star_projection",
    mode_attr="star_projection_sequence_mode",
    brightness_attr="star_projection_brightness",
    native_max=STAR_PROJECTION_BRIGHTNESS_MAX,
    set_mode=lambda client, mode: client.set_star_projection_sequence_mode(mode),
    set_brightness=lambda client, level: client.set_star_projection_brightness(level),
    effect_map=EnumMapping.from_source(
        STAR_PROJECTION_SEQUENCES, fallback_prefix="Sequence"
    ),
    previous_mode_attr="previous_star_projection_sequence_mode",
)

ANIMAL_PROJECTION = FpSootherLightDescription(
    key="animal_projection",
    translation_key="animal_projection",
    mode_attr="animal_projection_mode",
    brightness_attr="animal_projection_brightness",
    native_max=ANIMAL_PROJECTION_BRIGHTNESS_MAX,
    set_mode=lambda client, mode: client.set_animal_projection_mode(mode),
    set_brightness=lambda client, level: client.set_animal_projection_brightness(level),
    effect_map=EnumMapping.from_source(ANIMAL_PROJECTION_MODES, fallback_prefix="Mode"),
    previous_mode_attr="previous_animal_projection_mode",
)

LIGHT_DESCRIPTIONS: tuple[FpSootherLightDescription, ...] = (
    NIGHT_LIGHT,
    STAR_PROJECTION,
    ANIMAL_PROJECTION,
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: FpSootherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        FpSootherLight(coordinator, description) for description in LIGHT_DESCRIPTIONS
    )


class FpSootherLight(FpSootherEntity, LightEntity):
    """A light entity backed by one mode + one brightness SootherState attribute."""

    def __init__(
        self, coordinator: FpSootherCoordinator, description: FpSootherLightDescription
    ) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator, description.key)
        self._description = description
        self._attr_translation_key = description.translation_key
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS
        if description.effect_map is not None:
            self._attr_supported_features = LightEntityFeature.EFFECT
            self._attr_effect_list = list(description.effect_map.label_to_raw)

    @property
    def is_on(self) -> bool:
        """Return True if the mode attribute is non-zero (i.e. not off)."""
        return bool(getattr(self._state, self._description.mode_attr))

    @property
    def brightness(self) -> int:
        """Return the current brightness, scaled to Home Assistant's 0-255."""
        native = getattr(self._state, self._description.brightness_attr)
        return scale_to_ha_brightness(native, self._description.native_max)

    @property
    def effect(self) -> str | None:
        """Return the current effect label, or None if off or unsupported."""
        if self._description.effect_map is None:
            return None
        mode = getattr(self._state, self._description.mode_attr)
        if not mode:
            return None
        return self._description.effect_map.label_for(mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on, optionally setting an effect and/or a brightness."""
        client = self.coordinator.client
        if ATTR_EFFECT in kwargs:
            assert self._description.effect_map is not None
            effect = kwargs[ATTR_EFFECT]
            target_mode = self._description.effect_map.raw_for(effect)
            if target_mode is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_effect",
                    translation_placeholders={"effect": effect},
                )
            await self._async_command(self._description.set_mode(client, target_mode))
        elif not self.is_on:
            if self._description.effect_map is not None:
                assert self._description.previous_mode_attr is not None
                prev = (
                    getattr(self._state, self._description.previous_mode_attr)
                    or DEFAULT_MODE
                )
            else:
                prev = DEFAULT_MODE
            await self._async_command(self._description.set_mode(client, prev))

        if ATTR_BRIGHTNESS in kwargs:
            level = scale_from_ha_brightness(
                kwargs[ATTR_BRIGHTNESS], self._description.native_max
            )
            await self._async_command(self._description.set_brightness(client, level))

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off."""
        await self._async_command(
            self._description.set_mode(self.coordinator.client, 0)
        )
