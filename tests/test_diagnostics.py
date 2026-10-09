"""Tests for config entry diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_ADDRESS
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.fp_smart_connect.const import CONF_SESSION_KEY

from .conftest import TEST_ADDRESS, make_discovery_info, mock_soother_state

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

DIAGNOSTICS_MODULE = "custom_components.fp_smart_connect.diagnostics"


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Diagnostics report the decoded state and redact secrets."""
    mock_client.state = mock_soother_state(
        volume_level=7, firmware_version=11, raw_state=b"\x01" * 16
    )

    with patch(
        f"{DIAGNOSTICS_MODULE}.bluetooth.async_last_service_info",
        return_value=make_discovery_info(),
    ):
        result = await get_diagnostics_for_config_entry(
            hass, hass_client, setup_integration
        )

    assert result["entry_data"] == {
        CONF_ADDRESS: TEST_ADDRESS,
        CONF_SESSION_KEY: REDACTED,
    }
    assert result["coordinator"] == {"available": True}
    assert result["client"] == {
        "is_connected": True,
        "uses_shared_key": False,
        "peripheral_type": 1,
    }
    assert result["advertisement"] == {
        "source": "local",
        "rssi": -60,
        "connectable": True,
    }
    state = result["state"]
    assert isinstance(state, dict)
    assert state["volume_level"] == 7
    assert state["firmware_version"] == 11
    assert "raw_state" not in state


async def test_diagnostics_without_advertisement(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: MockConfigEntry,
) -> None:
    """With no advertisement on record, that section is null."""
    with patch(
        f"{DIAGNOSTICS_MODULE}.bluetooth.async_last_service_info", return_value=None
    ):
        result = await get_diagnostics_for_config_entry(
            hass, hass_client, setup_integration
        )

    assert result["advertisement"] is None
