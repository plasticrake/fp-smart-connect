"""Tests for config entry setup and unload."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from bleak.backends.device import BLEDevice
from fp_soother_lib import SootherCommandError, SootherConnectionError
from homeassistant.config_entries import ConfigEntryState

from .conftest import TEST_ADDRESS, TEST_SESSION_KEY_HEX

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

INIT_MODULE = "custom_components.fp_smart_connect"


@pytest.mark.parametrize(
    ("method", "error"),
    [
        ("open", SootherConnectionError("boom")),
        ("open", SootherCommandError("boom")),
        ("refresh_state", SootherConnectionError("boom")),
        ("refresh_state", SootherCommandError("boom")),
    ],
)
async def test_setup_failure_retries(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    error: Exception,
) -> None:
    """Any library error during the initial connection leaves the entry in SETUP_RETRY."""
    getattr(mock_client, method).side_effect = error
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_passes_stored_credentials(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The client is built from the entry's address and decoded session key."""
    mock_config_entry.add_to_hass(hass)
    with patch(f"{INIT_MODULE}.SootherClient", return_value=mock_client) as client_cls:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    client_cls.assert_called_once()
    assert client_cls.call_args.args == (TEST_ADDRESS,)
    assert client_cls.call_args.kwargs["session_key"] == bytes.fromhex(
        TEST_SESSION_KEY_HEX
    )


async def test_ble_device_callback(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The reconnect callback resolves a fresh BLE route, or raises if there is none."""
    mock_config_entry.add_to_hass(hass)
    with patch(f"{INIT_MODULE}.SootherClient", return_value=mock_client) as client_cls:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    resolve = client_cls.call_args.kwargs["ble_device_callback"]

    device = BLEDevice(TEST_ADDRESS, "Deluxe Soother", {})
    with patch(
        f"{INIT_MODULE}.bluetooth.async_ble_device_from_address", return_value=device
    ) as from_address:
        assert resolve() is device
    from_address.assert_called_once_with(hass, TEST_ADDRESS, connectable=True)

    with (
        patch(
            f"{INIT_MODULE}.bluetooth.async_ble_device_from_address", return_value=None
        ),
        pytest.raises(SootherConnectionError),
    ):
        resolve()


async def test_unload_closes_connection(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Unloading the entry closes the BLE connection."""
    mock_client.close.assert_not_awaited()

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    mock_client.close.assert_awaited_once()
