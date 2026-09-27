"""Diagnostics support for the go-e Charger Gemini (Read-Only) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import GoeDataUpdateCoordinator

# The serial number is the only value here that could identify the specific
# physical device; everything else in the status payload is charging/power
# telemetry, not personal data.
TO_REDACT = {"sse"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return the last known status payload for support/debugging."""
    coordinator: GoeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry": {
            "options": dict(entry.options),
        },
        "last_status_payload": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
