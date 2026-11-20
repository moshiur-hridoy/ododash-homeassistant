"""Config, reauth and options flows."""

from __future__ import annotations

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ododash.const import CONF_SCAN_INTERVAL, DOMAIN
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import KEY, STATUS, URL

USER_INPUT = {CONF_URL: f"{URL}/", CONF_API_KEY: KEY, CONF_VERIFY_SSL: True}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ha/status", json=STATUS)
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OdoDash (admin)"
    # trailing slash stripped
    assert result["data"] == {CONF_URL: URL, CONF_API_KEY: KEY, CONF_VERIFY_SSL: True}
    assert result["result"].unique_id == f"{URL}|admin"
    _, _, _, headers = aioclient_mock.mock_calls[0]
    assert headers["Authorization"] == f"Bearer {KEY}"


async def test_user_flow_invalid_auth(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ha/status", status=401, json={"error": "Invalid API token"})
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ha/status", exc=aiohttp.ClientConnectionError())
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_timeout(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ha/status", exc=TimeoutError())
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_not_ododash(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ha/status", text="<html>hello</html>")
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_recovers_after_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ha/status", status=401, json={})
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "invalid_auth"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/ha/status", json=STATUS)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_aborts(
    hass: HomeAssistant, aioclient_mock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    aioclient_mock.get(f"{URL}/api/ha/status", json=STATUS)
    result = await _start(hass)
    # Same server typed differently: upper-case scheme and a trailing slash.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_URL: "HTTP://ododash.local:5050/"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, aioclient_mock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    aioclient_mock.get(f"{URL}/api/ha/status", json=STATUS)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "odoha_newkey"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_KEY] == "odoha_newkey"


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant, aioclient_mock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    aioclient_mock.get(f"{URL}/api/ha/status", json={**STATUS, "user": "someone_else"})
    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "odoha_otherkey"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert config_entry.data[CONF_API_KEY] == KEY


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, aioclient_mock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    aioclient_mock.get(f"{URL}/api/ha/status", status=401, json={})
    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "odoha_bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow(hass: HomeAssistant, setup_integration) -> None:
    entry = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert entry.runtime_data.update_interval.total_seconds() == 30 * 60
