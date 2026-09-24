"""Tests for the media_player platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import STATE_PAUSED, STATE_PLAYING
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import format_mac

from custom_components.fp_smart_connect.const import DOMAIN

from .conftest import TEST_ADDRESS

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
async def entity_id(
    setup_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> str:
    """Return the media_player entity's entity_id."""
    result = entity_registry.async_get_entity_id(
        "media_player", DOMAIN, f"{format_mac(TEST_ADDRESS)}_sound"
    )
    assert result is not None
    return result


def _refresh(setup_integration: MockConfigEntry) -> None:
    setup_integration.runtime_data.async_update_listeners()


async def test_play_pause_state_mapping(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entity_id: str,
    mock_client: MagicMock,
) -> None:
    """The state reflects sound_mode, not play_mode."""
    mock_client.state.sound_mode = 1
    mock_client.state.play_mode = 0
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_PLAYING

    mock_client.state.sound_mode = 0
    mock_client.state.play_mode = 1
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_PAUSED


async def test_volume_mapping(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entity_id: str,
    mock_client: MagicMock,
) -> None:
    """volume_level scales the native 0-15 range to Home Assistant's 0.0-1.0."""
    mock_client.state.volume_level = 15
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["volume_level"] == pytest.approx(1.0)

    mock_client.state.volume_level = 0
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["volume_level"] == pytest.approx(0.0)


async def test_known_source_label(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entity_id: str,
    mock_client: MagicMock,
) -> None:
    """A known sound_mode value maps to its documented label."""
    mock_client.state.sound_mode = 1
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["source"] == "Pink Noise"
    assert "Pink Noise" in state.attributes["source_list"]


async def test_unmapped_source_fallback_label(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entity_id: str,
    mock_client: MagicMock,
) -> None:
    """An unmapped, non-zero sound_mode value falls back to a generic
    label, never dropped."""
    mock_client.state.sound_mode = 17
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["source"] == "Mode 17"
    assert "Mode 17" in state.attributes["source_list"]


async def test_paused_has_no_source(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entity_id: str,
    mock_client: MagicMock,
) -> None:
    """sound_mode == 0 (paused/off) is not exposed as a source, and isn't
    offered as a selectable option -- it's reached via pause, not
    select_source."""
    mock_client.state.sound_mode = 0
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert "source" not in state.attributes or state.attributes["source"] is None
    assert "Mode 0" not in state.attributes["source_list"]


async def test_play_pause_delegation(
    hass: HomeAssistant,
    entity_id: str,
    mock_client: MagicMock,
) -> None:
    """play/pause go through set_sound_mode: play restores the last
    non-zero sound_mode (defaulting to 1), pause sends 0."""
    mock_client.state.sound_mode = 4
    await hass.services.async_call(
        "media_player", "media_pause", {"entity_id": entity_id}, blocking=True
    )
    mock_client.set_sound_mode.assert_awaited_once_with(0)

    mock_client.state.sound_mode = 0
    await hass.services.async_call(
        "media_player", "media_play", {"entity_id": entity_id}, blocking=True
    )
    mock_client.set_sound_mode.assert_awaited_with(4)
    mock_client.set_volume.assert_not_called()


async def test_play_defaults_to_mode_one_without_prior_sound(
    hass: HomeAssistant,
    entity_id: str,
    mock_client: MagicMock,
) -> None:
    """play with no prior non-zero sound_mode observed falls back to 1."""
    mock_client.state.sound_mode = 0
    await hass.services.async_call(
        "media_player", "media_play", {"entity_id": entity_id}, blocking=True
    )
    mock_client.set_sound_mode.assert_awaited_once_with(1)


async def test_set_volume_delegation(
    hass: HomeAssistant, entity_id: str, mock_client: MagicMock
) -> None:
    """Setting volume calls set_volume with the correctly scaled int."""
    await hass.services.async_call(
        "media_player",
        "volume_set",
        {"entity_id": entity_id, "volume_level": 1.0},
        blocking=True,
    )
    mock_client.set_volume.assert_awaited_once_with(15)
    mock_client.set_sound_mode.assert_not_called()


async def test_select_source_delegation(
    hass: HomeAssistant, entity_id: str, mock_client: MagicMock
) -> None:
    """Selecting a known source calls set_sound_mode with the exact right int."""
    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": entity_id, "source": "Ocean"},
        blocking=True,
    )
    mock_client.set_sound_mode.assert_awaited_once_with(4)


async def test_select_source_unknown_source_is_rejected(
    hass: HomeAssistant, entity_id: str, mock_client: MagicMock
) -> None:
    """Selecting a source name the device doesn't know raises, not silently sent."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "media_player",
            "select_source",
            {"entity_id": entity_id, "source": "Not A Real Sound"},
            blocking=True,
        )
    mock_client.set_sound_mode.assert_not_called()


async def test_pause_while_paused_keeps_last_sound(
    hass: HomeAssistant,
    entity_id: str,
    mock_client: MagicMock,
) -> None:
    """A second pause while already paused doesn't forget the sound to resume."""
    mock_client.state.sound_mode = 4
    await hass.services.async_call(
        "media_player", "media_pause", {"entity_id": entity_id}, blocking=True
    )
    mock_client.state.sound_mode = 0
    await hass.services.async_call(
        "media_player", "media_pause", {"entity_id": entity_id}, blocking=True
    )
    await hass.services.async_call(
        "media_player", "media_play", {"entity_id": entity_id}, blocking=True
    )
    mock_client.set_sound_mode.assert_awaited_with(4)
