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
    SETTLING_PLAYLIST_MAP,
    SOOTHING_PLAYLIST_MAP,
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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's service actions."""
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PLAYLIST, _async_set_playlist, schema=SET_PLAYLIST_SCHEMA
    )
