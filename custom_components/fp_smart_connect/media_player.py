"""Media player platform for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fp_soother_lib.constants import SOUND_MODES
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import FpSootherEntity
from .mappings import EnumMapping, volume_from_ha, volume_to_ha

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )

    from . import FpSootherConfigEntry
    from .coordinator import FpSootherCoordinator

SOUND_MODE_MAP = EnumMapping.from_source(
    SOUND_MODES,
    fallback_prefix="Mode",
    overrides={
        "its_raining_its_pouring": "It's Raining, It's Pouring",
        "brahms_lullaby": "Brahms: Lullaby",
    },
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: FpSootherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player platform."""
    async_add_entities([FpSootherMediaPlayer(entry.runtime_data)])


class FpSootherMediaPlayer(FpSootherEntity, MediaPlayerEntity):
    """The Deluxe Soother's sound entity."""

    _attr_translation_key = "sound"
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, coordinator: FpSootherCoordinator) -> None:
        """Initialize the media player entity."""
        super().__init__(coordinator, "sound")
        self._last_sound_mode = 1

    @property
    def state(self) -> MediaPlayerState:
        """Return the current playback state.

        sound_mode == 0 means no track is selected (paused); any other value
        is actively playing that track. play_mode does not reliably track
        this (confirmed against the device), so it's not used here.
        """
        return (
            MediaPlayerState.PLAYING
            if self._state.sound_mode
            else MediaPlayerState.PAUSED
        )

    @property
    def volume_level(self) -> float:
        """Return the current volume, scaled to Home Assistant's 0.0-1.0."""
        return volume_to_ha(self._state.volume_level)

    @property
    def source(self) -> str | None:
        """Return the current sound mode's label, or None when paused (sound_mode == 0)."""
        if not self._state.sound_mode:
            return None
        return SOUND_MODE_MAP.label_for(self._state.sound_mode)

    @property
    def source_list(self) -> list[str]:
        """Return the selectable sound mode labels. 0 (off/paused) is not
        a source -- it's reached via pause, not source selection."""
        raw = self._state.sound_mode
        if not raw:
            return list(SOUND_MODE_MAP.label_to_raw)
        return SOUND_MODE_MAP.options_for(raw)

    async def async_media_play(self) -> None:
        """Resume the last-selected sound."""
        await self._async_command(
            self.coordinator.client.set_sound_mode(self._last_sound_mode)
        )

    async def async_media_pause(self) -> None:
        """Stop playback."""
        if self._state.sound_mode:
            self._last_sound_mode = self._state.sound_mode
        await self._async_command(self.coordinator.client.set_sound_mode(0))

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume."""
        await self._async_command(
            self.coordinator.client.set_volume(volume_from_ha(volume))
        )

    async def async_select_source(self, source: str) -> None:
        """Select a sound mode."""
        raw = SOUND_MODE_MAP.raw_for(source)
        if raw is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_source",
                translation_placeholders={"source": source},
            )
        await self._async_command(self.coordinator.client.set_sound_mode(raw))
