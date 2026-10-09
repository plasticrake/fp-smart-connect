"""Tests for the select platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.helpers.device_registry import format_mac

from custom_components.fp_smart_connect.const import DOMAIN
from custom_components.fp_smart_connect.select import (
    CUSTOM_COLOR_ATTRS,
    SELECT_DESCRIPTIONS,
)

from .conftest import TEST_ADDRESS

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

# The three aux-timer attributes are int | None until the first successful
# aux-state read.
AUX_TIMER_ATTRS = {
    "captive_sleep_stage_timer",
    "soothe_sleep_stage_timer",
    "sleep_stage_timer",
}


# The client method each single-value select delegates to. The star color
# selects share set_star_projection_custom_colors instead; see _assert_sent.
SET_METHODS = {
    "star_projection_speed": "set_star_projection_speed",
    "animal_projection_speed": "set_animal_projection_speed",
    "music_timer": "set_sound_timer",
    "light_timer": "set_light_timer",
    "sleep_stages": "set_sleep_stages_mode",
    "settle_timer": "set_captive_sleep_stage_timer",
    "soothe_timer": "set_soothe_sleep_stage_timer",
    "sleep_timer": "set_sleep_stage_timer",
}


def _assert_sent(mock_client: MagicMock, description, raw: int) -> None:
    """Assert the select sent raw through the right client method."""
    if description.state_attr in CUSTOM_COLOR_ATTRS:
        colors = [getattr(mock_client.state, attr) for attr in CUSTOM_COLOR_ATTRS]
        colors[CUSTOM_COLOR_ATTRS.index(description.state_attr)] = raw
        mock_client.set_star_projection_custom_colors.assert_awaited_once_with(*colors)
    else:
        getattr(mock_client, SET_METHODS[description.key]).assert_awaited_once_with(raw)


def _refresh(entry: MockConfigEntry) -> None:
    entry.runtime_data.async_update_listeners()


def _entity_id_for(entity_registry: er.EntityRegistry, key: str) -> str:
    result = entity_registry.async_get_entity_id(
        "select", DOMAIN, f"{format_mac(TEST_ADDRESS)}_{key}"
    )
    assert result is not None
    return result


@pytest.mark.parametrize("description", SELECT_DESCRIPTIONS, ids=lambda d: d.key)
async def test_known_and_fallback_option_mapping(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    description,
) -> None:
    """current_option and options handle both known and unknown raw values."""
    entity_id = _entity_id_for(entity_registry, description.key)
    known_option, known_raw = next(iter(description.value_map.option_to_raw.items()))

    setattr(mock_client.state, description.state_attr, known_raw)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == known_option
    assert known_option in state.attributes["options"]

    unknown_raw = max(description.value_map.raw_to_option) + 100
    setattr(mock_client.state, description.state_attr, unknown_raw)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    fallback_option = description.value_map.option_for(unknown_raw)
    assert state.state == fallback_option
    assert fallback_option in state.attributes["options"]


@pytest.mark.parametrize("description", SELECT_DESCRIPTIONS, ids=lambda d: d.key)
async def test_select_option_delegation(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    description,
) -> None:
    """Selecting a known option calls the right client method with the right value."""
    entity_id = _entity_id_for(entity_registry, description.key)
    option, raw = next(iter(description.value_map.option_to_raw.items()))

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": option},
        blocking=True,
    )
    _assert_sent(mock_client, description, raw)


@pytest.mark.parametrize("description", SELECT_DESCRIPTIONS, ids=lambda d: d.key)
async def test_reselecting_fallback_option_round_trips(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    description,
) -> None:
    """Re-selecting the current, unmapped raw value's fallback option sends that raw value back."""
    entity_id = _entity_id_for(entity_registry, description.key)
    unknown_raw = max(description.value_map.raw_to_option) + 100
    setattr(mock_client.state, description.state_attr, unknown_raw)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    fallback_option = description.value_map.option_for(unknown_raw)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": fallback_option},
        blocking=True,
    )
    _assert_sent(mock_client, description, unknown_raw)


@pytest.mark.parametrize(
    "description",
    [d for d in SELECT_DESCRIPTIONS if d.state_attr in AUX_TIMER_ATTRS],
    ids=lambda d: d.key,
)
async def test_aux_timer_none_before_first_read(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    description,
) -> None:
    """An aux-timer attribute that is still None reports unknown, not unavailable."""
    entity_id = _entity_id_for(entity_registry, description.key)
    setattr(mock_client.state, description.state_attr, None)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["options"]


def test_set_methods_cover_every_single_value_select() -> None:
    """SET_METHODS stays in step with SELECT_DESCRIPTIONS."""
    assert set(SET_METHODS) == {
        d.key for d in SELECT_DESCRIPTIONS if d.state_attr not in CUSTOM_COLOR_ATTRS
    }


async def test_star_color_resends_other_slots(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Changing one star color resends the other two slots' live values."""
    mock_client.state.star_projection_custom_color0 = 1
    mock_client.state.star_projection_custom_color1 = 2
    mock_client.state.star_projection_custom_color2 = 3
    _refresh(setup_integration)
    await hass.async_block_till_done()
    entity_id = _entity_id_for(entity_registry, "star_color_2")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "orange"
    assert state.name == "Deluxe Soother Star Color 2"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "blue"},
        blocking=True,
    )

    mock_client.set_star_projection_custom_colors.assert_awaited_once_with(1, 5, 3)
