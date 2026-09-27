"""Minimal read-only HTTP client for a go-e Charger's local API v2.

This client only ever issues GET requests against /api/status. It never
calls /api/set (or any other write endpoint), which is what makes it safe
to run alongside another controller such as evcc: reads and writes are
separate endpoints on the charger's stateless local web server, so there
is nothing here for a write from another client to collide with.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class GoeApiError(Exception):
    """Raised when the charger cannot be reached or returns a bad response."""


class GoeApiClient:
    """Thin async wrapper around go-e's local `GET /api/status` endpoint."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self._host = host

    async def async_get_status(self, filter_keys: list[str]) -> dict[str, Any]:
        """Fetch a filtered status payload from the charger.

        Always uses `filter=` - go-e's own API docs warn that requesting
        every key on a schedule causes "higher system load, lots of
        traffic" on the charger's embedded web server.
        """
        url = f"http://{self._host}/api/status"
        params = {"filter": ",".join(filter_keys)}

        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                async with self._session.get(url, params=params) as resp:
                    if resp.status != 200:
                        raise GoeApiError(
                            f"Unexpected HTTP status {resp.status} from {url}"
                        )
                    data = await resp.json(content_type=None)
        except TimeoutError as err:
            raise GoeApiError(f"Timed out talking to {self._host}") from err
        except aiohttp.ClientError as err:
            raise GoeApiError(f"Error talking to {self._host}: {err}") from err

        if not isinstance(data, dict):
            raise GoeApiError(
                f"Unexpected response payload from {self._host}: {data!r}"
            )

        return data
