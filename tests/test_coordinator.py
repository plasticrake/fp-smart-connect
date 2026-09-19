"""Tests for the coordinator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fp_soother_lib import SootherConnectionError
from homeassistant.config_entries import ConfigEntryState

from custom_components.fp_smart_connect.const import LOGGER
from custom_components.fp_smart_connect.coordinator import FpSootherCoordinator

from .conftest import TEST_ADDRESS

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_async_setup_registers_callbacks_once(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_client: MagicMock,
) -> None:
    """async_setup opens, refreshes, and registers callbacks exactly once."""
    coordinator = FpSootherCoordinator(
        hass, LOGGER, address=TEST_ADDRESS, client=mock_client
    )

    await coordinator.async_setup()

    mock_client.open.assert_awaited_once()
    mock_client.refresh_state.assert_awaited_once()
    mock_client.on_state_change.assert_called_once()
    mock_client.on_disconnect.assert_called_once()
    assert coordinator._connection_ready is True


async def test_setup_failure_propagates_as_config_entry_not_ready(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A connection failure during setup leaves the entry in SETUP_RETRY."""
    mock_client.open.side_effect = SootherConnectionError("boom")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_disconnect_flips_available(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """An unexpected disconnect makes the coordinator unavailable."""
    coordinator = setup_integration.runtime_data
    assert coordinator.available is True

    coordinator._handle_disconnect()

    assert coordinator.available is False
    assert coordinator._connection_ready is False


async def test_poll_restores_available_after_disconnect(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A successful poll after a disconnect restores availability."""
    coordinator = setup_integration.runtime_data
    coordinator._handle_disconnect()
    assert coordinator.available is False

    mock_client.is_connected = False
    await coordinator._async_poll_soother(None)

    mock_client.open.assert_awaited()
    assert coordinator.available is True


async def test_needs_poll_reflects_connection_state(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """_needs_poll is a pure reflection of whether we hold a live connection."""
    coordinator = setup_integration.runtime_data
    assert coordinator._needs_poll(None, None) is False

    coordinator._connection_ready = False
    assert coordinator._needs_poll(None, None) is True
