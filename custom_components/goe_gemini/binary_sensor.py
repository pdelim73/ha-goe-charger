"""Binary sensor platform for the go-e Charger Gemini (Read-Only) integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, lookup, CAR_STATES
from .coordinator import GoeDataUpdateCoordinator
from .entity import GoeEntity


def _car_connected(data: dict[str, Any]) -> bool | None:
    """Best-effort "is a car plugged in" derived from the `car` state.

    go-e does not expose a dedicated "plugged in" flag over the local API;
    this is inferred from the charge-controller state machine: Charging,
    WaitCar (car connected, session paused/pending) and Complete (finished,
    still plugged in) all imply a car is connected, Idle implies it is not.
    Error/Initializing/unknown are ambiguous, so they report as unknown
    rather than guessing.
    """
    state = lookup(CAR_STATES, data.get("car"))
    if state in ("charging", "wait_car", "complete"):
        return True
    if state == "idle":
        return False
    return None


def _has_problem(data: dict[str, Any]) -> bool | None:
    """`err` is documented as null meaning "no error", not "unknown" - so a
    null value here means no problem (off), not an unavailable reading.
    """
    return data.get("err") not in (None, 0)


@dataclass(frozen=True, kw_only=True)
class GoeBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with a coordinator-data extraction function."""

    value_fn: Callable[[dict[str, Any]], bool | None] = lambda data: None


BINARY_SENSOR_DESCRIPTIONS: tuple[GoeBinarySensorDescription, ...] = (
    GoeBinarySensorDescription(
        key="car_connected",
        translation_key="car_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=_car_connected,
    ),
    GoeBinarySensorDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: lookup(CAR_STATES, d.get("car")) == "charging",
    ),
    GoeBinarySensorDescription(
        key="charging_allowed",
        translation_key="charging_allowed",
        value_fn=lambda d: d.get("alw"),
    ),
    GoeBinarySensorDescription(
        key="pv_surplus_enabled",
        translation_key="pv_surplus_enabled",
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("fup"),
    ),
    GoeBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_has_problem,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up go-e Gemini binary sensors from a config entry."""
    coordinator: GoeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GoeBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class GoeBinarySensor(GoeEntity, BinarySensorEntity):
    """A single read-only binary sensor derived from the charger's status."""

    entity_description: GoeBinarySensorDescription

    def __init__(
        self,
        coordinator: GoeDataUpdateCoordinator,
        description: GoeBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data or {})
