"""Tests for the sensor platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import format_mac

from custom_components.fp_smart_connect.const import DOMAIN

from .conftest import TEST_ADDRESS

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

DIAGNOSTIC_SENSORS = [
    ("firmware_version", "firmware_version", 11),
    ("firmware_api_level", "firmware_api_level", 3),
    ("device_error", "error", 0),
]


def _refresh(entry: MockConfigEntry) -> None:
    entry.runtime_data.async_update_listeners()


def _entity_id_for(entity_registry: er.EntityRegistry, key: str) -> str:
    result = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{format_mac(TEST_ADDRESS)}_{key}"
    )
    assert result is not None
    return result


@pytest.mark.parametrize(("key", "state_attr", "value"), DIAGNOSTIC_SENSORS)
async def test_diagnostic_sensors_disabled_by_default(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    key: str,
    state_attr: str,
    value: int,
) -> None:
    """Diagnostic sensors are registered disabled, in the diagnostic category."""
    entry = entity_registry.async_get(_entity_id_for(entity_registry, key))
    assert entry is not None
    assert entry.disabled
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize(("key", "state_attr", "value"), DIAGNOSTIC_SENSORS)
async def test_diagnostic_sensor_values(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    key: str,
    state_attr: str,
    value: int,
) -> None:
    """Diagnostic sensors report unknown until read, then the device value."""
    entity_id = _entity_id_for(entity_registry, key)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"

    setattr(mock_client.state, state_attr, value)
    _refresh(setup_integration)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == str(value)
