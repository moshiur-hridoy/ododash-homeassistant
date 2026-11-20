"""Binary sensors for OdoDash alerts and server connectivity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import OdoDashConfigEntry, OdoDashCoordinator
from .entity import OdoDashAccountEntity, OdoDashVehicleEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OdoDashAlertDescription(BinarySensorEntityDescription):
    """A problem sensor that is on while the vehicle has alerts of one type."""

    alert_type: str


ALERT_SENSORS: tuple[OdoDashAlertDescription, ...] = (
    OdoDashAlertDescription(
        key="maintenance_due",
        translation_key="maintenance_due",
        device_class=BinarySensorDeviceClass.PROBLEM,
        alert_type="maintenance",
    ),
    OdoDashAlertDescription(
        key="document_expiring",
        translation_key="document_expiring",
        device_class=BinarySensorDeviceClass.PROBLEM,
        alert_type="document",
    ),
    OdoDashAlertDescription(
        key="reminder_due",
        translation_key="reminder_due",
        device_class=BinarySensorDeviceClass.PROBLEM,
        alert_type="reminder",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OdoDashConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OdoDash binary sensors."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new_vehicles() -> None:
        entities: list[BinarySensorEntity] = []
        for vehicle_id in coordinator.data.vehicles:
            if vehicle_id in known:
                continue
            known.add(vehicle_id)
            entities.extend(
                OdoDashAlertSensor(coordinator, vehicle_id, description)
                for description in ALERT_SENSORS
            )
        if entities:
            async_add_entities(entities)

    async_add_entities([OdoDashOnlineSensor(coordinator)])
    _add_new_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_vehicles))


class OdoDashAlertSensor(OdoDashVehicleEntity, BinarySensorEntity):
    """On while the vehicle has at least one alert of this type."""

    entity_description: OdoDashAlertDescription

    def __init__(
        self,
        coordinator: OdoDashCoordinator,
        vehicle_id: int,
        description: OdoDashAlertDescription,
    ) -> None:
        super().__init__(coordinator, vehicle_id, description.key)
        self.entity_description = description

    def _alerts(self) -> list[dict[str, Any]]:
        return [
            alert
            for alert in self.vehicle.get("alerts") or []
            if alert.get("type") == self.entity_description.alert_type
        ]

    @property
    def is_on(self) -> bool:
        return bool(self._alerts())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"alerts": self._alerts()}


class OdoDashOnlineSensor(OdoDashAccountEntity, BinarySensorEntity):
    """On while the last poll of OdoDash succeeded."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: OdoDashCoordinator) -> None:
        super().__init__(coordinator, "online")

    @property
    def available(self) -> bool:
        # Stays available so it can report "disconnected" while polls fail.
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
