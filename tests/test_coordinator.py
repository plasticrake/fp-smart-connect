"""Tests for the coordinator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fp_soother_lib import SootherCommandError, SootherConnectionError

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


@pytest.mark.parametrize(
    ("method", "error"),
    [
        ("open", SootherConnectionError("boom")),
        ("refresh_state", SootherConnectionError("boom")),
        ("refresh_state", SootherCommandError("boom")),
    ],
)
async def test_failed_poll_keeps_needing_reconnect(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    method: str,
    error: Exception,
) -> None:
    """A failed reconnect re-raises and leaves the coordinator wanting another poll."""
    coordinator = setup_integration.runtime_data
    mock_client.is_connected = False
    getattr(mock_client, method).side_effect = error

    with pytest.raises(type(error)):
        await coordinator._async_poll_soother(None)

    assert coordinator.available is False
    assert coordinator._needs_poll(None, None) is True


async def test_poll_while_connected_only_refreshes(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """A poll with a still-live link refreshes state without reopening."""
    coordinator = setup_integration.runtime_data
    mock_client.reset_mock()
    mock_client.is_connected = True

    await coordinator._async_poll_soother(None)

    mock_client.open.assert_not_awaited()
    mock_client.refresh_state.assert_awaited_once()
    assert coordinator.available is True
