"""Polls /api/ha/overview for one OdoDash account."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OdoDashApiClient, OdoDashAuthError, OdoDashError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER


@dataclass
class OdoDashData:
    """One poll's worth of data."""

    overview: dict[str, Any]
    vehicles: dict[int, dict[str, Any]] = field(default_factory=dict)


type OdoDashConfigEntry = ConfigEntry[OdoDashCoordinator]


def vehicle_identifier(entry_id: str, vehicle_id: int) -> tuple[str, str]:
    """Device registry identifier for one vehicle."""
    return (DOMAIN, f"{entry_id}_{vehicle_id}")


class OdoDashCoordinator(DataUpdateCoordinator[OdoDashData]):
    """Fetches the overview and keeps the device registry in step with it."""

    config_entry: OdoDashConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OdoDashConfigEntry, client: OdoDashApiClient
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> OdoDashData:
        try:
            overview = await self.client.async_get_overview()
        except OdoDashAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except OdoDashError as err:
            raise UpdateFailed(str(err)) from err

        vehicles = {int(v["id"]): v for v in overview.get("vehicles", [])}
        self._remove_stale_devices(set(vehicles))
        return OdoDashData(overview=overview, vehicles=vehicles)

    def _remove_stale_devices(self, current_ids: set[int]) -> None:
        """Drop devices for vehicles OdoDash no longer returns."""
        entry_id = self.config_entry.entry_id
        current = {vehicle_identifier(entry_id, vid) for vid in current_ids}
        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(registry, entry_id):
            ours = {
                ident
                for ident in device.identifiers
                if ident[0] == DOMAIN and ident[1].startswith(f"{entry_id}_")
            }
            if ours and not ours & current:
                LOGGER.debug("Removing device %s: vehicle no longer in OdoDash", device.name)
                registry.async_update_device(
                    device.id, remove_config_entry_id=entry_id
                )
