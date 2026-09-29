"""Tests for the set_playlist and apply_preset service actions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import voluptuous as vol
import yaml
from fp_soother_lib import SootherCommandError
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.fp_smart_connect import services
from custom_components.fp_smart_connect.const import DOMAIN
from custom_components.fp_smart_connect.mappings import (
    ANIMAL_PROJECTION_EFFECT_MAP,
    ANIMAL_PROJECTION_SPEED_MAP,
    CUSTOM_COLOR_MAP,
    SETTLING_PLAYLIST_MAP,
    SLEEP_STAGES_MODE_MAP,
    SOOTHING_PLAYLIST_MAP,
    SOUND_MODE_MAP,
    STAR_PROJECTION_EFFECT_MAP,
    STAR_PROJECTION_SPEED_MAP,
    TIMER_DURATION_MAP,
)

from .conftest import TEST_ADDRESS

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

SOOTHING_MOTIONS = {"playlist": "soothing", "tracks": ["Motions"]}

SERVICES_YAML = (Path(services.__file__).parent / "services.yaml").read_text(
    encoding="utf-8"
)


def _device_id(hass: HomeAssistant) -> str:
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    device = dr.async_get(hass).async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, dr.format_mac(TEST_ADDRESS)), entry.entry_id
    )
    assert device is not None
    return device.id


async def _call(hass: HomeAssistant, service: str, data: dict[str, Any]) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"device_id": _device_id(hass), **data}, blocking=True
    )


@pytest.mark.parametrize(
    ("playlist", "tracks", "method", "mask"),
    [
        (
            "settling",
            ["Aurora", "Brahms: Lullaby"],
            "set_captive_playlist_selection",
            0b10010,
        ),
        ("settling", "aurora", "set_captive_playlist_selection", 0b00010),
        ("soothing", [1, "3", "Polar Wind"], "set_soothe_playlist_selection", 0b10101),
    ],
)
async def test_set_playlist(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    playlist: str,
    tracks: Any,
    method: str,
    mask: int,
) -> None:
    """Track names and numbers resolve to the playlist's bitmask."""
    await _call(hass, "set_playlist", {"playlist": playlist, "tracks": tracks})

    getattr(mock_client, method).assert_awaited_once_with(mask)


@pytest.mark.parametrize(
    ("playlist", "tracks"),
    [
        ("settling", ["Aurora", "Nope"]),
        ("settling", ["Somewhere"]),
        ("soothing", [6]),
        ("soothing", [0]),
        ("soothing", []),
        ("bedtime", ["Aurora"]),
    ],
)
async def test_set_playlist_rejects_invalid_tracks(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    playlist: str,
    tracks: list[Any],
) -> None:
    """Unknown tracks or playlists are rejected, and nothing is sent."""
    with pytest.raises(vol.Invalid):
        await _call(hass, "set_playlist", {"playlist": playlist, "tracks": tracks})

    mock_client.set_captive_playlist_selection.assert_not_awaited()
    mock_client.set_soothe_playlist_selection.assert_not_awaited()


async def test_set_playlist_error_names_unknown_tracks(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The validation error names every unknown track and the valid choices."""
    with pytest.raises(vol.Invalid, match="Unknown tracks: Nope, 9") as exc_info:
        await _call(
            hass,
            "set_playlist",
            {"playlist": "soothing", "tracks": ["Nope", "Motions", 9]},
        )

    assert "Polar Wind" in str(exc_info.value)


async def test_command_failure_is_translated(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A library error surfaces as the translated command_failed error."""
    mock_client.set_soothe_playlist_selection.side_effect = SootherCommandError(
        "rejected"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call(hass, "set_playlist", SOOTHING_MOTIONS)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "command_failed"


async def test_unknown_device_is_rejected(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """A device id that doesn't exist is a validation error."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_playlist",
            {"device_id": "missing", **SOOTHING_MOTIONS},
            blocking=True,
        )


async def test_unloaded_entry_is_rejected(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Targeting a device whose entry isn't loaded is a validation error."""
    device_id = _device_id(hass)
    await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_playlist",
            {"device_id": device_id, **SOOTHING_MOTIONS},
            blocking=True,
        )
    mock_client.set_soothe_playlist_selection.assert_not_awaited()


def _yaml_options(service: str, field: str) -> list[str]:
    selector = yaml.safe_load(SERVICES_YAML)[service]["fields"][field]["selector"]
    return selector["select"]["options"]


def test_services_yaml_playlist_tracks_cover_both_playlists() -> None:
    """set_playlist's track picker offers every track from both playlists."""
    assert _yaml_options("set_playlist", "tracks") == [
        *SETTLING_PLAYLIST_MAP.label_to_bit,
        *SOOTHING_PLAYLIST_MAP.label_to_bit,
    ]
    assert _yaml_options("set_playlist", "playlist") == list(services.PLAYLISTS)


async def test_apply_preset(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Labels resolve to raw values, and only the given fields are sent."""
    await _call(
        hass,
        "apply_preset",
        {
            "sound_mode": "Ocean",
            "volume_level": 8,
            "nightlight_mode": True,
            "star_projection_sequence_mode": "Off",
            "star_projection_custom_color1": "Blue",
            "captive_playlist_selection": ["Aurora", 1],
            "light_timer": "Continuous",
        },
    )

    mock_client.send_preset.assert_awaited_once_with(
        sound_mode=4,
        volume_level=8,
        nightlight_mode=1,
        star_projection_sequence_mode=0,
        star_projection_custom_color1=5,
        captive_playlist_selection=0b00011,
        light_timer=15,
    )


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"sound_mode": "Mode 20"},
        {"sound_mode": 4},
        {"volume_level": 16},
        {"nightlight_brightness": -1},
        {"animal_projection_speed": "Very Fast"},
        {"soothe_playlist_selection": ["Aurora"]},
        {"captive_sleep_stage_timer": "5 Minutes"},
    ],
)
async def test_apply_preset_rejects_invalid_data(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    data: dict[str, Any],
) -> None:
    """Missing, unknown, or out-of-range fields are rejected, and nothing is sent."""
    with pytest.raises(vol.Invalid):
        await _call(hass, "apply_preset", data)

    mock_client.send_preset.assert_not_awaited()


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("sound_mode", list(SOUND_MODE_MAP.with_off().label_to_raw)),
        (
            "animal_projection_mode",
            list(ANIMAL_PROJECTION_EFFECT_MAP.with_off().label_to_raw),
        ),
        ("animal_projection_speed", list(ANIMAL_PROJECTION_SPEED_MAP.label_to_raw)),
        (
            "star_projection_sequence_mode",
            list(STAR_PROJECTION_EFFECT_MAP.with_off().label_to_raw),
        ),
        ("star_projection_custom_color0", list(CUSTOM_COLOR_MAP.label_to_raw)),
        ("star_projection_custom_color1", list(CUSTOM_COLOR_MAP.label_to_raw)),
        ("star_projection_custom_color2", list(CUSTOM_COLOR_MAP.label_to_raw)),
        ("star_projection_speed", list(STAR_PROJECTION_SPEED_MAP.label_to_raw)),
        ("sleep_stages_mode", list(SLEEP_STAGES_MODE_MAP.label_to_raw)),
        ("captive_playlist_selection", list(SETTLING_PLAYLIST_MAP.label_to_bit)),
        ("soothe_playlist_selection", list(SOOTHING_PLAYLIST_MAP.label_to_bit)),
        ("sound_timer_setting", list(TIMER_DURATION_MAP.label_to_raw)),
        ("light_timer", list(TIMER_DURATION_MAP.label_to_raw)),
        (
            "previous_animal_projection_mode",
            list(ANIMAL_PROJECTION_EFFECT_MAP.with_off().label_to_raw),
        ),
        (
            "previous_star_projection_sequence_mode",
            list(STAR_PROJECTION_EFFECT_MAP.with_off().label_to_raw),
        ),
    ],
)
def test_services_yaml_options_match_mappings(field: str, expected: list[str]) -> None:
    """The UI's option lists match the labels the schema accepts."""
    assert _yaml_options("apply_preset", field) == expected


def test_services_yaml_declares_every_preset_field() -> None:
    """services.yaml and the apply_preset schema declare the same fields."""
    fields = yaml.safe_load(SERVICES_YAML)["apply_preset"]["fields"]
    assert set(fields) == {"device_id", *services.PRESET_FIELDS}
