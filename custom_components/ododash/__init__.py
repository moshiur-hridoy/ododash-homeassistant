"""The OdoDash integration: vehicles, costs and alerts from OdoDash."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.typing import ConfigType

from .api import OdoDashApiClient
from .const import DOMAIN
from .coordinator import OdoDashConfigEntry, OdoDashCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OdoDashConfigEntry) -> bool:
    """Set up OdoDash from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = OdoDashApiClient(session, entry.data[CONF_URL], entry.data[CONF_API_KEY])
    coordinator = OdoDashCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # The account device must exist before vehicle devices point at it.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="OdoDash",
        manufacturer="OdoDash",
        entry_type=DeviceEntryType.SERVICE,
        sw_version=coordinator.data.overview.get("version"),
        configuration_url=client.url,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: OdoDashConfigEntry) -> None:
    """Reload so a new scan interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OdoDashConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
