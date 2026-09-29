"""Tests for the binary sensor platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.helpers.device_registry import format_mac

from custom_components.fp_smart_connect.const import DOMAIN

from .conftest import TEST_ADDRESS

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

BINARY_SENSORS = [
    ("sound_expiring", "sound_mode_expiring"),
    ("light_expiring", "led_expiring"),
]


def _entity_id_for(entity_registry: er.EntityRegistry, key: str) -> str:
    result = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{format_mac(TEST_ADDRESS)}_{key}"
    )
    assert result is not None
    return result


@pytest.mark.parametrize(("key", "state_attr"), BINARY_SENSORS)
async def test_disabled_by_default(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    key: str,
    state_attr: str,
) -> None:
    """Expiring flags are registered disabled, in the diagnostic category."""
    entry = entity_registry.async_get(_entity_id_for(entity_registry, key))
    assert entry is not None
    assert entry.disabled
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize(("key", "state_attr"), BINARY_SENSORS)
async def test_flag_mapping(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    key: str,
    state_attr: str,
) -> None:
    """The binary sensor follows its SootherState flag."""
    entity_id = _entity_id_for(entity_registry, key)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    setattr(mock_client.state, state_attr, 1)
    setup_integration.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
