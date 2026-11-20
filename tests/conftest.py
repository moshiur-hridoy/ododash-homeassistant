"""Fixtures for OdoDash tests."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ododash.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL

URL = "http://ododash.local:5050"
KEY = "odoha_testkey"

STATUS = {"status": "online", "user": "admin", "version": "0.51.0"}

PETROL = {
    "id": 1,
    "name": "Family Car",
    "make": "Toyota",
    "model": "Corolla",
    "year": 2020,
    "registration": "AB12 CDE",
    "fuel_type": "petrol",
    "is_electric": False,
    "current_odometer": 12345.0,
    "distance_unit": "km",
    "volume_unit": "L",
    "currency_symbol": "£",
    "avg_consumption": 6.1,
    "consumption_unit": "L/100km",
    "total_cost": 1234.5,
    "total_fuel_cost": 900.0,
    "total_expenses": 334.5,
    "cost_last_30_days": 120.0,
    "last_fill_date": "2026-11-01",
    "last_fill_volume": 40.2,
    "last_fill_cost": 60.3,
    "last_charge": None,
    "alerts": [
        {
            "type": "maintenance",
            "vehicle": "Family Car",
            "vehicle_id": 1,
            "title": "Oil change",
            "status": "due",
            "due_date": "2026-11-10",
            "due_odometer": None,
        }
    ],
}

EV = {
    "id": 2,
    "name": "EV",
    "make": "Tesla",
    "model": "Model 3",
    "year": 2023,
    "registration": None,
    "fuel_type": "electric",
    "is_electric": True,
    "current_odometer": 8000.0,
    "distance_unit": "mi",
    "volume_unit": "L",
    "currency_symbol": "£",
    "avg_consumption": 0,
    "consumption_unit": "mpg",
    "total_cost": 300.0,
    "total_fuel_cost": 0,
    "total_expenses": 300.0,
    "cost_last_30_days": 0,
    "last_fill_date": None,
    "last_fill_volume": None,
    "last_fill_cost": None,
    "last_charge": {
        "date": "2026-11-15",
        "kwh_added": 30.0,
        "start_soc": 20,
        "end_soc": 80,
        "total_cost": 9.0,
    },
    "alerts": [],
}

OVERVIEW = {
    "version": "0.51.0",
    "user": "admin",
    "currency": "GBP",
    "vehicles": [PETROL, EV],
    "alerts_count": 1,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    return


@pytest.fixture
def overview() -> dict[str, Any]:
    return copy.deepcopy(OVERVIEW)


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="OdoDash (admin)",
        unique_id=f"{URL}|admin",
        data={CONF_URL: URL, CONF_API_KEY: KEY, CONF_VERIFY_SSL: True},
    )


@pytest.fixture
def mock_api(aioclient_mock, overview):
    aioclient_mock.get(f"{URL}/api/ha/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/ha/overview", json=overview)
    return aioclient_mock


@pytest.fixture
async def setup_integration(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
