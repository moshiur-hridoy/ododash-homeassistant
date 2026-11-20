"""Setup, entities, auth failure, stale devices, diagnostics and the add_fuel service."""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.ododash.const import DOMAIN
from custom_components.ododash.diagnostics import async_get_config_entry_diagnostics
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .conftest import KEY, URL


def _entity_id(hass: HomeAssistant, entry_id: str, suffix: str, platform: str = "sensor") -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry_id}_{suffix}")
    assert entity_id, f"no {platform} entity for {suffix}"
    return entity_id


async def test_petrol_car_entities(hass: HomeAssistant, setup_integration) -> None:
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_1")})
    assert device.name == "Family Car"
    assert device.manufacturer == "Toyota"
    assert device.model == "Corolla"
    assert device.configuration_url == f"{URL}/vehicles/1"

    odometer = hass.states.get(_entity_id(hass, entry.entry_id, "1_odometer"))
    assert odometer.state == "12345.0"
    assert odometer.attributes["unit_of_measurement"] == "km"
    assert odometer.attributes["device_class"] == "distance"
    assert odometer.attributes["state_class"] == "total_increasing"

    consumption = hass.states.get(_entity_id(hass, entry.entry_id, "1_avg_consumption"))
    assert consumption.state == "6.1"
    assert consumption.attributes["unit_of_measurement"] == "L/100km"

    total = hass.states.get(_entity_id(hass, entry.entry_id, "1_total_cost"))
    assert total.state == "1234.5"
    assert total.attributes["unit_of_measurement"] == "GBP"
    assert total.attributes["device_class"] == "monetary"

    assert hass.states.get(_entity_id(hass, entry.entry_id, "1_last_fill")).state == "2026-11-01"
    volume = hass.states.get(_entity_id(hass, entry.entry_id, "1_last_fill_volume"))
    assert volume.state == "40.2"
    assert volume.attributes["unit_of_measurement"] == "L"
    assert hass.states.get(_entity_id(hass, entry.entry_id, "1_cost_30d")).state == "120.0"
    assert hass.states.get(_entity_id(hass, entry.entry_id, "1_alerts")).state == "1"

    # no EV sensors on a petrol car
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_1_last_charge_energy") is None

    maintenance = hass.states.get(
        _entity_id(hass, entry.entry_id, "1_maintenance_due", "binary_sensor")
    )
    assert maintenance.state == "on"
    assert maintenance.attributes["alerts"][0]["title"] == "Oil change"
    reminder = hass.states.get(_entity_id(hass, entry.entry_id, "1_reminder_due", "binary_sensor"))
    assert reminder.state == "off"

    # account device
    assert hass.states.get(_entity_id(hass, entry.entry_id, "total_alerts")).state == "1"
    assert hass.states.get(_entity_id(hass, entry.entry_id, "online", "binary_sensor")).state == "on"


async def test_ev_entities(hass: HomeAssistant, setup_integration) -> None:
    entry = setup_integration
    energy = hass.states.get(_entity_id(hass, entry.entry_id, "2_last_charge_energy"))
    assert energy.state == "30.0"
    assert energy.attributes["unit_of_measurement"] == "kWh"
    soc = hass.states.get(_entity_id(hass, entry.entry_id, "2_last_charge_soc"))
    assert soc.state == "80"
    assert soc.attributes["device_class"] == "battery"
    # miles with a distance device class: Home Assistant shows it in the
    # install's unit system (metric in tests)
    odometer = hass.states.get(_entity_id(hass, entry.entry_id, "2_odometer"))
    assert odometer.attributes["unit_of_measurement"] == "km"
    assert float(odometer.state) == pytest.approx(8000 * 1.609344, abs=0.1)
    # null values are skipped
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_2_last_fill") is None


async def test_hours_and_gallon_units(hass, config_entry, aioclient_mock, overview) -> None:
    tractor = overview["vehicles"][0]
    tractor.update(distance_unit="h", avg_consumption=None, consumption_unit=None, volume_unit="gal")
    overview["vehicles"] = [tractor]
    aioclient_mock.get(f"{URL}/api/ha/overview", json=overview)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    odometer = hass.states.get(_entity_id(hass, config_entry.entry_id, "1_odometer"))
    assert odometer.attributes["unit_of_measurement"] == "h"
    assert "device_class" not in odometer.attributes
    volume = hass.states.get(_entity_id(hass, config_entry.entry_id, "1_last_fill_volume"))
    assert volume.attributes["unit_of_measurement"] == "imp gal"
    assert "device_class" not in volume.attributes
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{config_entry.entry_id}_1_avg_consumption") is None


async def test_auth_failure_at_setup_starts_reauth(hass, config_entry, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ha/overview", status=401, json={"error": "Invalid API token"})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_auth_failure_during_poll_starts_reauth(
    hass, setup_integration, aioclient_mock, freezer: FrozenDateTimeFactory
) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/ha/overview", status=401, json={})
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in flows)


async def test_connection_failure_marks_offline(
    hass, setup_integration, aioclient_mock, freezer: FrozenDateTimeFactory
) -> None:
    entry = setup_integration
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/ha/overview", status=502, text="bad gateway")
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, entry.entry_id, "online", "binary_sensor")).state == "off"
    assert hass.states.get(_entity_id(hass, entry.entry_id, "1_odometer")).state == "unavailable"


async def test_removed_vehicle_device_is_removed(
    hass, setup_integration, aioclient_mock, overview, freezer: FrozenDateTimeFactory
) -> None:
    entry = setup_integration
    registry = dr.async_get(hass)
    assert registry.async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_2")})

    overview["vehicles"] = overview["vehicles"][:1]
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/ha/overview", json=overview)
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert registry.async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_2")}) is None
    assert registry.async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_1")})


async def test_new_vehicle_gets_entities(
    hass, setup_integration, aioclient_mock, overview, freezer: FrozenDateTimeFactory
) -> None:
    entry = setup_integration
    bike = {**overview["vehicles"][0], "id": 3, "name": "Bike", "alerts": []}
    overview["vehicles"].append(bike)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/ha/overview", json=overview)
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, entry.entry_id, "3_odometer")).state == "12345.0"


async def test_unload(hass: HomeAssistant, setup_integration) -> None:
    entry = setup_integration
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_diagnostics_redacts(hass: HomeAssistant, setup_integration) -> None:
    diag = await async_get_config_entry_diagnostics(hass, setup_integration)
    text = str(diag)
    assert KEY not in text
    assert URL not in text
    assert "AB12 CDE" not in text
    assert diag["overview"]["vehicles"][0]["current_odometer"] == 12345.0


async def test_add_fuel_service(hass: HomeAssistant, setup_integration, aioclient_mock) -> None:
    entry = setup_integration
    aioclient_mock.post(f"{URL}/api/ha/fuel/add", status=201, json={"success": True, "id": 9})
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_1")})
    calls_before = len(aioclient_mock.mock_calls)

    await hass.services.async_call(
        DOMAIN,
        "add_fuel",
        {
            "device_id": device.id,
            "odometer": 12500,
            "volume": 40,
            "price_per_unit": 1.555,
            "date": "2026-11-20",
            "notes": "from HA",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    posts = [c for c in aioclient_mock.mock_calls[calls_before:] if c[0] == "POST"]
    assert len(posts) == 1
    method, url, payload, headers = posts[0]
    assert str(url) == f"{URL}/api/ha/fuel/add"
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert payload == {
        "vehicle_id": 1,
        "date": "2026-11-20",
        "odometer": 12500.0,
        "volume": 40.0,
        "price_per_unit": 1.555,
        "total_cost": 62.2,
        "is_full_tank": True,
        "notes": "from HA",
    }
    # refreshed after the post
    gets = [c for c in aioclient_mock.mock_calls[calls_before:] if str(c[1]).endswith("/overview")]
    assert gets


async def test_add_fuel_explicit_total_and_default_date(
    hass: HomeAssistant, setup_integration, aioclient_mock
) -> None:
    entry = setup_integration
    aioclient_mock.post(f"{URL}/api/ha/fuel/add", status=201, json={"success": True})
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_1")})
    await hass.services.async_call(
        DOMAIN,
        "add_fuel",
        {"device_id": device.id, "odometer": 1, "volume": 2, "price_per_unit": 3, "total_cost": 5, "is_full_tank": False},
        blocking=True,
    )
    payload = [c for c in aioclient_mock.mock_calls if c[0] == "POST"][-1][2]
    assert payload["total_cost"] == 5.0
    assert payload["is_full_tank"] is False
    assert len(payload["date"]) == 10


async def test_add_fuel_rejects_account_device(hass: HomeAssistant, setup_integration) -> None:
    entry = setup_integration
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "add_fuel",
            {"device_id": device.id, "odometer": 1, "volume": 2, "price_per_unit": 3},
            blocking=True,
        )
