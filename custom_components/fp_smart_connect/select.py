"""Select platform for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .entity import FpSootherEntity
from .mappings import (
    ANIMAL_PROJECTION_SPEED_MAP,
    SLEEP_STAGE_TIMER_MAP,
    SLEEP_STAGES_MODE_MAP,
    SLEEP_TIMER_MAP,
    STAR_PROJECTION_SPEED_MAP,
    TIMER_DURATION_MAP,
    EnumMapping,
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


class FpSootherSelectDescription(SelectEntityDescription, frozen_or_thawed=True):
    """
    Describes a Deluxe Soother select entity.

    set_fn is a callable (not a plain method name), like the light
    descriptions' setters, so a select can wrap a command that takes more
    than the selected value.
    """

    state_attr: str
    set_fn: Callable[[SootherClient, int], Awaitable[None]]
    value_map: EnumMapping


SELECT_DESCRIPTIONS: tuple[FpSootherSelectDescription, ...] = (
    FpSootherSelectDescription(
        key="star_projection_speed",
        translation_key="star_projection_speed",
        state_attr="star_projection_speed",
        set_fn=lambda client, raw: client.set_star_projection_speed(raw),
        value_map=STAR_PROJECTION_SPEED_MAP,
    ),
    FpSootherSelectDescription(
        key="animal_projection_speed",
        translation_key="animal_projection_speed",
        state_attr="animal_projection_speed",
        set_fn=lambda client, raw: client.set_animal_projection_speed(raw),
        value_map=ANIMAL_PROJECTION_SPEED_MAP,
    ),
    FpSootherSelectDescription(
        key="music_timer",
        translation_key="music_timer",
        state_attr="sound_timer_setting",
        set_fn=lambda client, raw: client.set_sound_timer(raw),
        value_map=TIMER_DURATION_MAP,
    ),
    FpSootherSelectDescription(
        key="light_timer",
        translation_key="light_timer",
        state_attr="light_timer",
        set_fn=lambda client, raw: client.set_light_timer(raw),
        value_map=TIMER_DURATION_MAP,
    ),
    FpSootherSelectDescription(
        key="sleep_stages",
        translation_key="sleep_stages",
        state_attr="sleep_stages_mode",
        set_fn=lambda client, raw: client.set_sleep_stages_mode(raw),
        value_map=SLEEP_STAGES_MODE_MAP,
    ),
    FpSootherSelectDescription(
        key="settle_timer",
        translation_key="settle_timer",
        state_attr="captive_sleep_stage_timer",
        set_fn=lambda client, raw: client.set_captive_sleep_stage_timer(raw),
        value_map=SLEEP_STAGE_TIMER_MAP,
    ),
    FpSootherSelectDescription(
        key="soothe_timer",
        translation_key="soothe_timer",
        state_attr="soothe_sleep_stage_timer",
        set_fn=lambda client, raw: client.set_soothe_sleep_stage_timer(raw),
        value_map=SLEEP_STAGE_TIMER_MAP,
    ),
    FpSootherSelectDescription(
        key="sleep_timer",
        translation_key="sleep_timer",
        state_attr="sleep_stage_timer",
        set_fn=lambda client, raw: client.set_sleep_stage_timer(raw),
        value_map=SLEEP_TIMER_MAP,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: FpSootherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        FpSootherSelect(coordinator, description) for description in SELECT_DESCRIPTIONS
    )


class FpSootherSelect(FpSootherEntity, SelectEntity):
    """A select entity backed by one SootherState attribute."""

    entity_description: FpSootherSelectDescription

    def __init__(
        self, coordinator: FpSootherCoordinator, description: FpSootherSelectDescription
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option, or None if not yet known."""
        raw = getattr(self._state, self.entity_description.state_attr)
        if raw is None:
            return None
        return self.entity_description.value_map.label_for(raw)

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        raw = getattr(self._state, self.entity_description.state_attr)
        if raw is None:
            return list(self.entity_description.value_map.label_to_raw)
        return self.entity_description.value_map.options_for(raw)

    async def async_select_option(self, option: str) -> None:
        """Select a new option."""
        raw = self.entity_description.value_map.raw_for(option)
        assert raw is not None  # `option` always comes from our own `options` list
        await self._async_command(
            self.entity_description.set_fn(self.coordinator.client, raw)
        )
