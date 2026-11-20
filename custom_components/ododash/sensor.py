"""Sensors for OdoDash vehicles and the account."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import OdoDashConfigEntry, OdoDashCoordinator
from .entity import OdoDashAccountEntity, OdoDashVehicleEntity

PARALLEL_UPDATES = 0

# OdoDash distance_unit: "km", "mi", or "h" for a vehicle metered in engine hours.
DISTANCE_UNITS = {
    "km": UnitOfLength.KILOMETERS,
    "mi": UnitOfLength.MILES,
}

# OdoDash volume_unit: "L", "gal" (imperial / UK gallons) or "us_gal".
# Home Assistant has no imperial gallon, so "gal" keeps OdoDash's figure with
# its own label and no device class rather than being silently relabelled as
# US gallons (which are 17% smaller).
IMPERIAL_GALLON = "imp gal"
VOLUME_UNITS = {
    "L": UnitOfVolume.LITERS,
    "us_gal": UnitOfVolume.GALLONS,
    "gal": IMPERIAL_GALLON,
}


def _currency(coordinator: OdoDashCoordinator, _vehicle: dict[str, Any]) -> str | None:
    return coordinator.data.overview.get("currency")


def _distance_unit(_coordinator: OdoDashCoordinator, vehicle: dict[str, Any]) -> str | None:
    unit = vehicle.get("distance_unit")
    if unit == "h":
        return UnitOfTime.HOURS
    return DISTANCE_UNITS.get(unit, unit)


def _distance_device_class(vehicle: dict[str, Any]) -> SensorDeviceClass | None:
    return SensorDeviceClass.DISTANCE if vehicle.get("distance_unit") in DISTANCE_UNITS else None


def _volume_unit(_coordinator: OdoDashCoordinator, vehicle: dict[str, Any]) -> str | None:
    unit = vehicle.get("volume_unit")
    return VOLUME_UNITS.get(unit, unit)


def _volume_device_class(vehicle: dict[str, Any]) -> SensorDeviceClass | None:
    if vehicle.get("volume_unit") in ("L", "us_gal"):
        return SensorDeviceClass.VOLUME_STORAGE
    return None


def _date(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def _last_charge(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda v: (v.get("last_charge") or {}).get(key)


@dataclass(frozen=True, kw_only=True)
class OdoDashVehicleSensorDescription(SensorEntityDescription):
    """Describes one per-vehicle sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    unit_fn: Callable[[OdoDashCoordinator, dict[str, Any]], str | None] | None = None
    device_class_fn: Callable[[dict[str, Any]], SensorDeviceClass | None] | None = None
    ev_only: bool = False


VEHICLE_SENSORS: tuple[OdoDashVehicleSensorDescription, ...] = (
    OdoDashVehicleSensorDescription(
        key="odometer",
        translation_key="odometer",
        value_fn=lambda v: v.get("current_odometer"),
        unit_fn=_distance_unit,
        device_class_fn=_distance_device_class,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    OdoDashVehicleSensorDescription(
        key="avg_consumption",
        translation_key="avg_consumption",
        value_fn=lambda v: v.get("avg_consumption"),
        unit_fn=lambda _c, v: v.get("consumption_unit"),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    OdoDashVehicleSensorDescription(
        key="total_cost",
        translation_key="total_cost",
        value_fn=lambda v: v.get("total_cost"),
        unit_fn=_currency,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    OdoDashVehicleSensorDescription(
        key="fuel_cost",
        translation_key="fuel_cost",
        value_fn=lambda v: v.get("total_fuel_cost"),
        unit_fn=_currency,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    OdoDashVehicleSensorDescription(
        key="expenses",
        translation_key="expenses",
        value_fn=lambda v: v.get("total_expenses"),
        unit_fn=_currency,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    OdoDashVehicleSensorDescription(
        key="cost_30d",
        translation_key="cost_30d",
        value_fn=lambda v: v.get("cost_last_30_days"),
        unit_fn=_currency,
        device_class=SensorDeviceClass.MONETARY,
    ),
    OdoDashVehicleSensorDescription(
        key="last_fill",
        translation_key="last_fill",
        value_fn=lambda v: _date(v.get("last_fill_date")),
        device_class=SensorDeviceClass.DATE,
    ),
    OdoDashVehicleSensorDescription(
        key="last_fill_volume",
        translation_key="last_fill_volume",
        value_fn=lambda v: v.get("last_fill_volume"),
        unit_fn=_volume_unit,
        device_class_fn=_volume_device_class,
    ),
    OdoDashVehicleSensorDescription(
        key="last_charge_energy",
        translation_key="last_charge_energy",
        value_fn=_last_charge("kwh_added"),
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        ev_only=True,
    ),
    OdoDashVehicleSensorDescription(
        key="last_charge_soc",
        translation_key="last_charge_soc",
        value_fn=_last_charge("end_soc"),
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        ev_only=True,
    ),
    OdoDashVehicleSensorDescription(
        key="alerts",
        translation_key="alerts",
        value_fn=lambda v: len(v.get("alerts") or []),
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OdoDashConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OdoDash sensors."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new_vehicles() -> None:
        entities: list[SensorEntity] = []
        for vehicle_id, vehicle in coordinator.data.vehicles.items():
            if vehicle_id in known:
                continue
            known.add(vehicle_id)
            entities.extend(
                OdoDashVehicleSensor(coordinator, vehicle_id, description)
                for description in VEHICLE_SENSORS
                if (not description.ev_only or vehicle.get("is_electric"))
                and description.value_fn(vehicle) is not None
            )
        if entities:
            async_add_entities(entities)

    async_add_entities([OdoDashTotalAlertsSensor(coordinator)])
    _add_new_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_vehicles))


class OdoDashVehicleSensor(OdoDashVehicleEntity, SensorEntity):
    """One figure for one vehicle."""

    entity_description: OdoDashVehicleSensorDescription

    def __init__(
        self,
        coordinator: OdoDashCoordinator,
        vehicle_id: int,
        description: OdoDashVehicleSensorDescription,
    ) -> None:
        super().__init__(coordinator, vehicle_id, description.key)
        self.entity_description = description
        vehicle = coordinator.data.vehicles[vehicle_id]
        if description.unit_fn:
            self._attr_native_unit_of_measurement = description.unit_fn(coordinator, vehicle)
        if description.device_class_fn:
            self._attr_device_class = description.device_class_fn(vehicle)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.vehicle)


class OdoDashTotalAlertsSensor(OdoDashAccountEntity, SensorEntity):
    """Alerts across every vehicle on the account."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: OdoDashCoordinator) -> None:
        super().__init__(coordinator, "total_alerts")

    @property
    def native_value(self) -> int:
        return int(self.coordinator.data.overview.get("alerts_count") or 0)
