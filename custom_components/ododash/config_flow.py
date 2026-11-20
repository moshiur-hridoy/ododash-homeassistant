"""Config flow for OdoDash: server URL + Home Assistant key, set up from the UI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import OdoDashApiClient, OdoDashAuthError, OdoDashConnectionError, OdoDashError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def normalise_url(url: str) -> str:
    """http(s)://host[:port][/path] with no trailing slash, scheme and host lower-cased."""
    url = url.strip()
    if "://" not in url:
        url = f"http://{url}"
    parsed = URL(url)
    normalised = parsed.with_scheme(parsed.scheme.lower()).with_query(None).with_fragment(None)
    return str(normalised).rstrip("/")


async def _async_status(
    hass: HomeAssistant, url: str, api_key: str, verify_ssl: bool
) -> dict[str, Any]:
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    return await OdoDashApiClient(session, url, api_key).async_get_status()


def _error_for(err: Exception) -> str:
    if isinstance(err, OdoDashAuthError):
        return "invalid_auth"
    if isinstance(err, OdoDashConnectionError):
        return "cannot_connect"
    LOGGER.exception("Unexpected error talking to OdoDash")
    return "unknown"


class OdoDashConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OdoDash."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
            try:
                url = normalise_url(user_input[CONF_URL])
                status = await _async_status(
                    self.hass, url, user_input[CONF_API_KEY], verify_ssl
                )
            except ValueError:
                errors[CONF_URL] = "invalid_url"
            except OdoDashError as err:
                errors["base"] = _error_for(err)
            else:
                user = status.get("user", "")
                await self.async_set_unique_id(f"{url}|{user}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"OdoDash ({user})" if user else "OdoDash",
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The key stopped working: ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                status = await _async_status(
                    self.hass,
                    entry.data[CONF_URL],
                    user_input[CONF_API_KEY],
                    entry.data.get(CONF_VERIFY_SSL, True),
                )
            except OdoDashError as err:
                errors["base"] = _error_for(err)
            else:
                await self.async_set_unique_id(f"{entry.data[CONF_URL]}|{status.get('user', '')}")
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OdoDashOptionsFlow:
        return OdoDashOptionsFlow()


class OdoDashOptionsFlow(OptionsFlow):
    """How often to poll OdoDash."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )
