"""Fixtures for the Fisher-Price Smart Connect integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from bleak.backends.device import BLEDevice
from fp_soother_lib import SootherClient, SootherState
from fp_soother_lib.constants import SERVICE_UUID
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fp_smart_connect.const import CONF_SESSION_KEY, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

TEST_ADDRESS = "AA:BB:CC:DD:EE:FF"
TEST_SESSION_KEY_HEX = "00" * 16


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for every test in this suite."""


def mock_soother_state(**overrides: Any) -> SootherState:
    """Build a SootherState with library defaults, overridable per test."""
    return SootherState(**overrides)


def make_discovery_info(
    address: str = TEST_ADDRESS, service_uuids: list[str] | None = None
) -> BluetoothServiceInfoBleak:
    """Build a fake bluetooth discovery info for a Deluxe Soother."""
    device = BLEDevice(address, "Deluxe Soother", {})
    return BluetoothServiceInfoBleak(
        name="Deluxe Soother",
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_UUID.lower()]
        if service_uuids is None
        else service_uuids,
        source="local",
        device=device,
        advertisement=None,
        connectable=True,
        time=0.0,
        tx_power=None,
    )


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """A fully autospecced, mocked SootherClient."""
    client = create_autospec(SootherClient, instance=True)
    client.address = TEST_ADDRESS
    client.is_connected = True
    client.is_paired = True
    client.session_key = bytes.fromhex(TEST_SESSION_KEY_HEX)
    client.state = mock_soother_state()
    with patch("custom_components.fp_smart_connect.SootherClient", return_value=client):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry for an already-paired Deluxe Soother."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_ADDRESS),
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_SESSION_KEY: TEST_SESSION_KEY_HEX},
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the integration with a mocked SootherClient."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    # No real advertisement is ever seen in tests, so the base coordinator's
    # own advertisement-presence flag (_available) never flips true on its
    # own. Poking it directly is the pragmatic choice here: these tests cover
    # entity state-mapping/command-delegation, not the bluetooth manager's
    # own advertisement tracking (which is HA core's responsibility and is
    # exercised directly, without this shortcut, in test_coordinator.py).
    mock_config_entry.runtime_data._available = True
    mock_config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()
    yield mock_config_entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
