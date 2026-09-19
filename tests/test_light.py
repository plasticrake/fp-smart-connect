"""Tests for the light platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import format_mac

from custom_components.fp_smart_connect.const import DOMAIN

from .conftest import TEST_ADDRESS

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

NIGHTLIGHT = ("nightlight", "nightlight_mode", "nightlight_brightness", 7)
STAR = (
    "star_projection",
    "star_projection_sequence_mode",
    "star_projection_brightness",
    7,
)
ANIMAL = (
    "animal_projection",
    "animal_projection_mode",
    "animal_projection_brightness",
    15,
)


def _refresh(entry: MockConfigEntry) -> None:
    entry.runtime_data.async_update_listeners()


def _entity_id_for(entity_registry: er.EntityRegistry, key: str) -> str:
    result = entity_registry.async_get_entity_id(
        "light", DOMAIN, f"{format_mac(TEST_ADDRESS)}_{key}"
    )
    assert result is not None
    return result


@pytest.mark.parametrize(
    ("key", "mode_attr", "brightness_attr", "native_max"), [NIGHTLIGHT, STAR, ANIMAL]
)
async def test_on_off_and_brightness_mapping(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    key: str,
    mode_attr: str,
    brightness_attr: str,
    native_max: int,
) -> None:
    """is_on and brightness reflect the mode/brightness attributes at their boundaries."""
    entity_id = _entity_id_for(entity_registry, key)

    setattr(mock_client.state, mode_attr, 0)
    setattr(mock_client.state, brightness_attr, 0)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    setattr(mock_client.state, mode_attr, 1)
    setattr(mock_client.state, brightness_attr, native_max)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 255


async def test_star_projection_effect_mapping(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A known mode maps to its effect label; mode 0 has no effect."""
    entity_id = _entity_id_for(entity_registry, "star_projection")

    mock_client.state.star_projection_sequence_mode = 1
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["effect"] == "Rainbow"

    mock_client.state.star_projection_sequence_mode = 0
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["effect"] is None


async def test_nightlight_brightness_only_turn_on_does_not_touch_mode(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Adjusting brightness while already on calls only the brightness setter."""
    entity_id = _entity_id_for(entity_registry, "nightlight")
    mock_client.state.nightlight_mode = 1
    _refresh(setup_integration)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "brightness": 255},
        blocking=True,
    )
    mock_client.set_nightlight_brightness.assert_awaited_once_with(7)
    mock_client.set_nightlight.assert_not_called()


async def test_nightlight_bare_turn_on_from_off_sets_mode(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A bare turn_on while off turns the mode on."""
    entity_id = _entity_id_for(entity_registry, "nightlight")
    mock_client.state.nightlight_mode = 0
    _refresh(setup_integration)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    mock_client.set_nightlight.assert_awaited_once_with(True)


async def test_nightlight_turn_off(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Turning off calls set_nightlight(False)."""
    entity_id = _entity_id_for(entity_registry, "nightlight")
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    mock_client.set_nightlight.assert_awaited_once_with(False)


async def test_star_projection_explicit_effect_turn_on(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Turning on with an explicit effect calls the mode setter with that effect's value."""
    entity_id = _entity_id_for(entity_registry, "star_projection")
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entity_id, "effect": "Cool Colors"},
        blocking=True,
    )
    mock_client.set_star_projection_sequence_mode.assert_awaited_once_with(2)


async def test_star_projection_unknown_effect_is_rejected(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Turning on with an effect name the device doesn't know raises, not silently sent."""
    entity_id = _entity_id_for(entity_registry, "star_projection")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_id, "effect": "Not A Real Effect"},
            blocking=True,
        )
    mock_client.set_star_projection_sequence_mode.assert_not_called()


async def test_star_projection_bare_turn_on_resumes_previous_effect(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A bare turn_on while off resumes the device's previous effect."""
    entity_id = _entity_id_for(entity_registry, "star_projection")
    mock_client.state.star_projection_sequence_mode = 0
    mock_client.state.previous_star_projection_sequence_mode = 3
    _refresh(setup_integration)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    mock_client.set_star_projection_sequence_mode.assert_awaited_once_with(3)


async def test_star_projection_bare_turn_on_defaults_when_no_previous_effect(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A bare turn_on with no recorded previous effect defaults to the first effect."""
    entity_id = _entity_id_for(entity_registry, "star_projection")
    mock_client.state.star_projection_sequence_mode = 0
    mock_client.state.previous_star_projection_sequence_mode = 0
    _refresh(setup_integration)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    mock_client.set_star_projection_sequence_mode.assert_awaited_once_with(1)
