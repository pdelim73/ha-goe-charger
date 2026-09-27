"""Config flow for the go-e Charger Gemini (Read-Only) integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoeApiClient, GoeApiError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    VALIDATION_FILTER_KEYS,
)

_LOGGER = logging.getLogger(__name__)


async def _async_validate_host(hass, host: str) -> dict[str, Any]:
    """Probe the charger once with a minimal filter to confirm it's reachable.

    This performs exactly one read-only GET request - the same kind of
    request evcc itself issues - and nothing else. No credentials, no
    pairing, no write.
    """
    session = async_get_clientsession(hass)
    client = GoeApiClient(session, host)
    return await client.async_get_status(VALIDATION_FILTER_KEYS)


class GoeGeminiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for go-e Charger Gemini (Read-Only)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                status = await _async_validate_host(self.hass, host)
            except GoeApiError:
                errors["base"] = "cannot_connect"
            else:
                serial = status.get("sse")
                if serial:
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                name = user_input.get(CONF_NAME) or status.get("fna") or "go-e Charger Gemini"
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return GoeGeminiOptionsFlow()


class GoeGeminiOptionsFlow(OptionsFlow):
    """Options flow: lets the user tune the poll interval, nothing else."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
