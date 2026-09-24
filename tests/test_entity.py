"""Tests for the shared entity behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fp_soother_lib import SootherCommandError, SootherConnectionError
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac

from custom_components.fp_smart_connect.const import DOMAIN

from .conftest import TEST_ADDRESS, mock_soother_state

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry


def _entity_id_for(entity_registry: er.EntityRegistry, platform: str, key: str) -> str:
    result = entity_registry.async_get_entity_id(
        platform, DOMAIN, f"{format_mac(TEST_ADDRESS)}_{key}"
    )
    assert result is not None
    return result


@pytest.mark.parametrize(
    "error", [SootherConnectionError("gone"), SootherCommandError("rejected")]
)
async def test_command_error_is_translated(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    error: Exception,
) -> None:
    """A library error from a command surfaces as a translated HomeAssistantError."""
    entity_id = _entity_id_for(entity_registry, "media_player", "sound")
    mock_client.set_volume.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {"entity_id": entity_id, "volume_level": 0.5},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders == {"error": str(error)}
    assert exc_info.value.__cause__ is error


async def test_pushed_state_updates_entities(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A state notification delivered through the registered callback updates entities."""
    entity_id = _entity_id_for(entity_registry, "light", "nightlight")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    (on_state_change,) = mock_client.on_state_change.call_args.args
    mock_client.state = mock_soother_state(nightlight_mode=1)
    on_state_change(mock_client.state)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_disconnect_makes_entities_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """An unexpected disconnect marks every entity unavailable."""
    entity_ids = [
        entry.entity_id
        for entry in entity_registry.entities.get_entries_for_config_entry_id(
            setup_integration.entry_id
        )
    ]
    assert entity_ids
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE

    (on_disconnect,) = mock_client.on_disconnect.call_args.args
    on_disconnect()
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
