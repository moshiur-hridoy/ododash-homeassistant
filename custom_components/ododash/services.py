"""The ododash.add_fuel service."""

from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .api import OdoDashError
from .const import (
    ATTR_DATE,
    ATTR_DEVICE_ID,
    ATTR_IS_FULL_TANK,
    ATTR_NOTES,
    ATTR_ODOMETER,
    ATTR_PRICE_PER_UNIT,
    ATTR_TOTAL_COST,
    ATTR_VOLUME,
    DOMAIN,
    SERVICE_ADD_FUEL,
)
from .coordinator import OdoDashConfigEntry

ADD_FUEL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_ODOMETER): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Required(ATTR_VOLUME): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Required(ATTR_PRICE_PER_UNIT): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(ATTR_TOTAL_COST): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(ATTR_DATE): cv.date,
        vol.Optional(ATTR_IS_FULL_TANK, default=True): cv.boolean,
        vol.Optional(ATTR_NOTES, default=""): cv.string,
    }
)


def _resolve_vehicle(hass: HomeAssistant, device_id: str) -> tuple[OdoDashConfigEntry, int]:
    """Map a vehicle device to its loaded config entry and OdoDash vehicle id."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="unknown_device"
        )
    for domain, identifier in device.identifiers:
        if domain != DOMAIN or "_" not in identifier:
            continue
        entry_id, _, vehicle_id = identifier.rpartition("_")
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="not_loaded"
            )
        return entry, int(vehicle_id)
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="not_a_vehicle"
    )


async def _async_add_fuel(call: ServiceCall) -> None:
    hass = call.hass
    entry, vehicle_id = _resolve_vehicle(hass, call.data[ATTR_DEVICE_ID])
    coordinator = entry.runtime_data

    volume = call.data[ATTR_VOLUME]
    price = call.data[ATTR_PRICE_PER_UNIT]
    total_cost = call.data.get(ATTR_TOTAL_COST)
    if total_cost is None:
        total_cost = round(volume * price, 2)
    fill_date: date = call.data.get(ATTR_DATE) or dt_util.now().date()

    payload = {
        "vehicle_id": vehicle_id,
        "date": fill_date.isoformat(),
        "odometer": call.data[ATTR_ODOMETER],
        "volume": volume,
        "price_per_unit": price,
        "total_cost": total_cost,
        "is_full_tank": call.data[ATTR_IS_FULL_TANK],
        "notes": call.data[ATTR_NOTES],
    }
    try:
        await coordinator.client.async_add_fuel(payload)
    except OdoDashError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="add_fuel_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    await coordinator.async_request_refresh()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register ododash services."""
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_FUEL, _async_add_fuel, schema=ADD_FUEL_SCHEMA
    )
