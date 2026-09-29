"""Service actions for the Fisher-Price Smart Connect integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DOMAIN
from .mappings import (
    ANIMAL_PROJECTION_BRIGHTNESS_MAX,
    ANIMAL_PROJECTION_EFFECT_MAP,
    ANIMAL_PROJECTION_SPEED_MAP,
    CUSTOM_COLOR_MAP,
    NIGHTLIGHT_BRIGHTNESS_MAX,
    SETTLING_PLAYLIST_MAP,
    SLEEP_STAGES_MODE_MAP,
    SOOTHING_PLAYLIST_MAP,
    SOUND_MODE_MAP,
    STAR_PROJECTION_BRIGHTNESS_MAX,
    STAR_PROJECTION_EFFECT_MAP,
    STAR_PROJECTION_SPEED_MAP,
    TIMER_DURATION_MAP,
    VOLUME_MAX,
    EnumMapping,
    PlaylistMapping,
    UnknownTracksError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fp_soother_lib import SootherClient
    from homeassistant.core import HomeAssistant, ServiceCall

    from . import FpSootherConfigEntry
    from .coordinator import FpSootherCoordinator

SERVICE_SET_PLAYLIST = "set_playlist"
SERVICE_APPLY_PRESET = "apply_preset"

ATTR_PLAYLIST = "playlist"
ATTR_TRACKS = "tracks"


@dataclass(frozen=True)
class Playlist:
    """One of the device's two track playlists."""

    mapping: PlaylistMapping
    set_fn: Callable[[SootherClient, int], Awaitable[None]]


PLAYLISTS: dict[str, Playlist] = {
    "settling": Playlist(
        mapping=SETTLING_PLAYLIST_MAP,
        set_fn=lambda client, mask: client.set_captive_playlist_selection(mask),
    ),
    "soothing": Playlist(
        mapping=SOOTHING_PLAYLIST_MAP,
        set_fn=lambda client, mask: client.set_soothe_playlist_selection(mask),
    ),
}

_TRACK_LIST = vol.All(cv.ensure_list, vol.Length(min=1), [cv.string])


def _tracks_to_mask(mapping: PlaylistMapping, tracks: list[str]) -> int:
    """Resolve validated track names/indexes to a bitmask, or raise vol.Invalid."""
    try:
        return mapping.mask_for(tracks)
    except UnknownTracksError as err:
        known = ", ".join(mapping.label_to_bit)
        msg = (
            f"{err}. Expected one of: {known}, "
            f"or a track number from 1 to {len(mapping.label_to_bit)}"
        )
        raise vol.Invalid(msg, path=[ATTR_TRACKS]) from err


def _playlist_tracks(mapping: PlaylistMapping) -> Callable[[Any], int]:
    """Validate a list of tracks for one playlist, returning its bitmask."""

    def validate(value: Any) -> int:
        return _tracks_to_mask(mapping, _TRACK_LIST(value))

    return validate


def _label(mapping: EnumMapping) -> vol.All:
    """Validate a known label, returning its raw device value."""
    return vol.All(vol.In(list(mapping.label_to_raw)), mapping.label_to_raw.__getitem__)


def _level(native_max: int) -> vol.All:
    """Validate a native 0..native_max level."""
    return vol.All(vol.Coerce(int), vol.Range(min=0, max=native_max))


_FLAG = vol.All(cv.boolean, int)


def _resolve_set_playlist(data: dict[str, Any]) -> dict[str, Any]:
    """Resolve the tracks against the chosen playlist's own track mapping."""
    playlist = PLAYLISTS[data[ATTR_PLAYLIST]]
    return {**data, ATTR_TRACKS: _tracks_to_mask(playlist.mapping, data[ATTR_TRACKS])}


SET_PLAYLIST_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Required(ATTR_PLAYLIST): vol.In(list(PLAYLISTS)),
            vol.Required(ATTR_TRACKS): _TRACK_LIST,
        }
    ),
    _resolve_set_playlist,
)

# The attributes fp_soother_lib's send_preset() bundles (PRESET_ATTRS), keyed
# by their SootherState field names. Enum-like fields accept the same labels
# as the matching light/media_player/select/sensor entities; levels use the
# device's native ranges. Mode fields where 0 means off also accept "Off".
PRESET_FIELDS: dict[str, Any] = {
    "play_mode": _FLAG,
    "sound_mode": _label(SOUND_MODE_MAP.with_off()),
    "volume_level": _level(VOLUME_MAX),
    "animal_projection_mode": _label(ANIMAL_PROJECTION_EFFECT_MAP.with_off()),
    "animal_projection_brightness": _level(ANIMAL_PROJECTION_BRIGHTNESS_MAX),
    "animal_projection_speed": _label(ANIMAL_PROJECTION_SPEED_MAP),
    "star_projection_sequence_mode": _label(STAR_PROJECTION_EFFECT_MAP.with_off()),
    "star_projection_custom_color0": _label(CUSTOM_COLOR_MAP),
    "star_projection_custom_color1": _label(CUSTOM_COLOR_MAP),
    "star_projection_custom_color2": _label(CUSTOM_COLOR_MAP),
    "star_projection_brightness": _level(STAR_PROJECTION_BRIGHTNESS_MAX),
    "star_projection_speed": _label(STAR_PROJECTION_SPEED_MAP),
    "nightlight_mode": _FLAG,
    "nightlight_brightness": _level(NIGHTLIGHT_BRIGHTNESS_MAX),
    "sleep_stages_mode": _label(SLEEP_STAGES_MODE_MAP),
    "captive_playlist_selection": _playlist_tracks(SETTLING_PLAYLIST_MAP),
    "soothe_playlist_selection": _playlist_tracks(SOOTHING_PLAYLIST_MAP),
    "sound_timer_setting": _label(TIMER_DURATION_MAP),
    "light_timer": _label(TIMER_DURATION_MAP),
    "previous_animal_projection_mode": _label(ANIMAL_PROJECTION_EFFECT_MAP.with_off()),
    "previous_star_projection_sequence_mode": _label(
        STAR_PROJECTION_EFFECT_MAP.with_off()
    ),
}

APPLY_PRESET_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
            **{
                vol.Optional(name): validator
                for name, validator in PRESET_FIELDS.items()
            },
        }
    ),
    cv.has_at_least_one_key(*PRESET_FIELDS),
)


def _coordinator_for(call: ServiceCall) -> FpSootherCoordinator:
    """Return the coordinator for the call's target device."""
    entry: FpSootherConfigEntry
    _device, entry = service.async_get_device_and_config_entry(
        call.hass, DOMAIN, call.data[ATTR_DEVICE_ID]
    )
    return entry.runtime_data


async def _async_set_playlist(call: ServiceCall) -> None:
    """Replace the tracks selected in one playlist."""
    coordinator = _coordinator_for(call)
    playlist = PLAYLISTS[call.data[ATTR_PLAYLIST]]
    await coordinator.async_command(
        playlist.set_fn(coordinator.client, call.data[ATTR_TRACKS])
    )


async def _async_apply_preset(call: ServiceCall) -> None:
    """
    Apply several attributes in one write.

    Only the fields the caller gave are passed on; send_preset() fills the
    rest from the client's live state itself.
    """
    coordinator = _coordinator_for(call)
    overrides = {
        name: value for name, value in call.data.items() if name in PRESET_FIELDS
    }
    await coordinator.async_command(coordinator.client.send_preset(**overrides))


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's service actions."""
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PLAYLIST, _async_set_playlist, schema=SET_PLAYLIST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_APPLY_PRESET, _async_apply_preset, schema=APPLY_PRESET_SCHEMA
    )
