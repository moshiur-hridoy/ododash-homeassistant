"""Constants for the OdoDash integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "ododash"
LOGGER = logging.getLogger(__package__)

CONF_SCAN_INTERVAL: Final = "scan_interval"

# Minutes. OdoDash data only changes when someone logs a fill or an expense,
# so there is no point polling faster than this.
DEFAULT_SCAN_INTERVAL: Final = 15
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 1440

REQUEST_TIMEOUT: Final = 10

SERVICE_ADD_FUEL: Final = "add_fuel"

ATTR_DEVICE_ID: Final = "device_id"
ATTR_ODOMETER: Final = "odometer"
ATTR_VOLUME: Final = "volume"
ATTR_PRICE_PER_UNIT: Final = "price_per_unit"
ATTR_TOTAL_COST: Final = "total_cost"
ATTR_DATE: Final = "date"
ATTR_IS_FULL_TANK: Final = "is_full_tank"
ATTR_NOTES: Final = "notes"
