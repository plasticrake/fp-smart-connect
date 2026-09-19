"""Tests for the select platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.helpers.device_registry import format_mac

from custom_components.fp_smart_connect.const import DOMAIN
from custom_components.fp_smart_connect.select import SELECT_DESCRIPTIONS

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
    known_label, known_raw = next(iter(description.value_map.label_to_raw.items()))

    setattr(mock_client.state, description.state_attr, known_raw)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == known_label
    assert known_label in state.attributes["options"]

    unknown_raw = max(description.value_map.raw_to_label) + 100
    setattr(mock_client.state, description.state_attr, unknown_raw)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    fallback_label = description.value_map.label_for(unknown_raw)
    assert state.state == fallback_label
    assert fallback_label in state.attributes["options"]


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
    label, raw = next(iter(description.value_map.label_to_raw.items()))

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": label},
        blocking=True,
    )
    set_method = getattr(mock_client, description.set_method)
    set_method.assert_awaited_once_with(raw)


@pytest.mark.parametrize("description", SELECT_DESCRIPTIONS, ids=lambda d: d.key)
async def test_reselecting_fallback_option_round_trips(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    description,
) -> None:
    """Re-selecting the current, unmapped raw value's fallback label sends that raw value back."""
    entity_id = _entity_id_for(entity_registry, description.key)
    unknown_raw = max(description.value_map.raw_to_label) + 100
    setattr(mock_client.state, description.state_attr, unknown_raw)
    _refresh(setup_integration)
    await hass.async_block_till_done()
    fallback_label = description.value_map.label_for(unknown_raw)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": fallback_label},
        blocking=True,
    )
    set_method = getattr(mock_client, description.set_method)
    set_method.assert_awaited_once_with(unknown_raw)


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
