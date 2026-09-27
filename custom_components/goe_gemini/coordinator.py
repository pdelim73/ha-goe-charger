"""DataUpdateCoordinator for the go-e Charger Gemini (Read-Only) integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GoeApiClient, GoeApiError
from .const import DOMAIN, STATUS_KEYS

_LOGGER = logging.getLogger(__name__)


class GoeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the charger's read-only status endpoint on a fixed interval.

    This is the single code path in the integration that talks to the
    charger: one filtered GET per cycle, never concurrent, never a write.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: GoeApiClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry = entry
        self._client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self._client.async_get_status(STATUS_KEYS)
        except GoeApiError as err:
            raise UpdateFailed(str(err)) from err
