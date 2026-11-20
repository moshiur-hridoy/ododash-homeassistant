"""Diagnostics for OdoDash, with the key and server address redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from .coordinator import OdoDashConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_URL, "unique_id", "registration", "user", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OdoDashConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "overview": async_redact_data(coordinator.data.overview, TO_REDACT),
    }
