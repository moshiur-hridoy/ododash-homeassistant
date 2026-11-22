"""Base entities for OdoDash."""

from __future__ import annotations

import inspect
from typing import Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OdoDashCoordinator, vehicle_identifier


# HA 2026.11+ wants `via_device_id` (the registry id); older cores only know `via_device`.
_SUPPORTS_VIA_DEVICE_ID = (
    "via_device_id" in inspect.signature(dr.DeviceRegistry.async_get_or_create).parameters
)


class OdoDashAccountEntity(CoordinatorEntity[OdoDashCoordinator]):
    """An entity on the account-level "OdoDash" device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OdoDashCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="OdoDash",
            manufacturer="OdoDash",
            entry_type=DeviceEntryType.SERVICE,
            sw_version=coordinator.data.overview.get("version"),
            configuration_url=coordinator.client.url,
        )


class OdoDashVehicleEntity(CoordinatorEntity[OdoDashCoordinator]):
    """An entity on one vehicle's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OdoDashCoordinator, vehicle_id: int, key: str) -> None:
        super().__init__(coordinator)
        self.vehicle_id = vehicle_id
        entry = coordinator.config_entry
        vehicle = coordinator.data.vehicles[vehicle_id]
        # The account device is created in async_setup_entry before the platforms load.
        account = dr.async_get(coordinator.hass).async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )
        self._attr_unique_id = f"{entry.entry_id}_{vehicle_id}_{key}"
        self._attr_translation_key = key
        info = DeviceInfo(
            identifiers={vehicle_identifier(entry.entry_id, vehicle_id)},
            name=vehicle.get("name") or f"Vehicle {vehicle_id}",
            manufacturer=vehicle.get("make") or None,
            model=vehicle.get("model") or None,
            configuration_url=f"{coordinator.client.url}/vehicles/{vehicle_id}",
        )
        if _SUPPORTS_VIA_DEVICE_ID:
            info["via_device_id"] = account.id if account else None
        else:
            info["via_device"] = (DOMAIN, entry.entry_id)
        self._attr_device_info = info

    @property
    def vehicle(self) -> dict[str, Any]:
        """This vehicle's latest data."""
        return self.coordinator.data.vehicles.get(self.vehicle_id, {})

    @property
    def available(self) -> bool:
        return super().available and self.vehicle_id in self.coordinator.data.vehicles
