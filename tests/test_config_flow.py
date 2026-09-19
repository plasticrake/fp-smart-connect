"""Tests for the config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from fp_soother_lib import SootherCommandError, SootherConnectionError
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType

from custom_components.fp_smart_connect.const import CONF_SESSION_KEY, DOMAIN

from .conftest import TEST_ADDRESS, TEST_SESSION_KEY_HEX, make_discovery_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

CONFIG_FLOW_MODULE = "custom_components.fp_smart_connect.config_flow"


def _mock_pairing_client(*, pair_error: Exception | None = None) -> AsyncMock:
    client = AsyncMock()
    client.session_key = bytes.fromhex(TEST_SESSION_KEY_HEX)
    if pair_error is not None:
        client.pair.side_effect = pair_error
    return client


async def test_bluetooth_discovery_happy_path(hass: HomeAssistant) -> None:
    """A discovered device can be confirmed and paired, creating an entry."""
    client = _mock_pairing_client()
    with patch(f"{CONFIG_FLOW_MODULE}.SootherClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=make_discovery_info(),
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"
        progress = hass.config_entries.flow.async_get(result["flow_id"])
        assert progress["context"]["title_placeholders"] == {
            "name": f"Deluxe Soother ({TEST_ADDRESS.lower()})"
        }

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS
    assert result["data"][CONF_SESSION_KEY] == TEST_SESSION_KEY_HEX
    client.pair.assert_awaited_once()
    client.close.assert_awaited_once()


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A device that is already configured aborts discovery."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=make_discovery_info(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """A connection failure during pairing is shown as a retryable form error."""
    client = _mock_pairing_client()
    client.open.side_effect = SootherConnectionError("boom")
    with patch(f"{CONFIG_FLOW_MODULE}.SootherClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=make_discovery_info(),
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_confirm_pairing_failed(hass: HomeAssistant) -> None:
    """A pairing failure (e.g. device not in pairing mode) shows a distinct error."""
    client = _mock_pairing_client(pair_error=SootherCommandError("nope"))
    with patch(f"{CONFIG_FLOW_MODULE}.SootherClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=make_discovery_info(),
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"] == {"base": "pairing_failed"}


async def test_bluetooth_confirm_pairing_timeout(hass: HomeAssistant) -> None:
    """A pairing timeout (device never replied) also shows pairing_failed."""
    client = _mock_pairing_client(pair_error=TimeoutError())
    with patch(f"{CONFIG_FLOW_MODULE}.SootherClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=make_discovery_info(),
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["errors"] == {"base": "pairing_failed"}


async def test_user_flow_happy_path(hass: HomeAssistant) -> None:
    """A user-initiated flow lists discovered devices and pairs the chosen one."""
    client = _mock_pairing_client()
    discovery_info = make_discovery_info()
    with (
        patch(f"{CONFIG_FLOW_MODULE}.SootherClient", return_value=client),
        patch(
            f"{CONFIG_FLOW_MODULE}.async_discovered_service_info",
            return_value=[discovery_info],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: TEST_ADDRESS}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS


async def test_user_flow_no_devices_found(hass: HomeAssistant) -> None:
    """A user-initiated flow with nothing discovered re-shows the form to retry."""
    with patch(f"{CONFIG_FLOW_MODULE}.async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_devices_found"}


async def test_user_flow_retry_after_no_devices_found(hass: HomeAssistant) -> None:
    """Resubmitting the no-devices form re-scans instead of restarting the flow."""
    client = _mock_pairing_client()
    discovery_info = make_discovery_info()
    with patch(f"{CONFIG_FLOW_MODULE}.async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices_found"}

    with (
        patch(f"{CONFIG_FLOW_MODULE}.SootherClient", return_value=client),
        patch(
            f"{CONFIG_FLOW_MODULE}.async_discovered_service_info",
            return_value=[discovery_info],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: TEST_ADDRESS}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS
