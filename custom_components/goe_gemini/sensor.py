"""Sensor platform for the go-e Charger Gemini (Read-Only) integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CABLE_LOCK_STATUS,
    DOMAIN,
    ERROR_CODES,
    CAR_STATES,
    LOCK_FEEDBACK,
    LOCK_MODE,
    LOGIC_MODE,
    MODEL_STATUS,
    VARIANT_NAMES,
    lookup,
)
from .coordinator import GoeDataUpdateCoordinator
from .entity import GoeEntity


def _nrg(data: dict[str, Any], index: int) -> float | None:
    """Read one raw value out of the legacy `nrg` array, if present.

    Array layout: 0-2 U L1-L3 (V), 3 U N (V), 4-6 I L1-L3 (A, documented as
    0.1 A steps but see below), 7-9 P L1-L3 (W), 10 P N (W), 11 P total (W),
    12-15 power factor L1-L3-N (%).

    The go-e API v1 spec (written for older HOME/HOME+ hardware) documents
    the power sub-fields as scaled integers (0.1 kW / 0.01 kW steps). On a
    real Gemini V4 (firmware 60.5), that scaling does not apply: the power
    values come back already in plain Watts - confirmed by a user report
    where the old ×10/×100 scaling produced power readings 10x/100x too
    high. Voltage was always documented as direct volts, so it's unaffected.
    Current (4-6) is left at the documented 0.1 A scaling since it hasn't
    been contradicted by a real reading yet, but given the power fields
    were wrong, it's a reasonable suspect if current readings ever look 10x
    off too.
    """
    nrg = data.get("nrg")
    if not isinstance(nrg, list) or index >= len(nrg):
        return None
    return nrg[index]


def _nrg_scaled(index: int, factor: float) -> Callable[[dict[str, Any]], float | None]:
    def _value(data: dict[str, Any]) -> float | None:
        raw = _nrg(data, index)
        return None if raw is None else round(raw * factor, 3)

    return _value


def _error_state(data: dict[str, Any]) -> str | None:
    """Translate `err`: the API documents null as "no error", not "unknown" -
    treat it as code 0 ("none") rather than surfacing it as unavailable.
    """
    err = data.get("err")
    return lookup(ERROR_CODES, 0 if err is None else err)


def _trx_state(data: dict[str, Any]) -> str | None:
    """Translate `trx`: null=no transaction, 0=no card, N=card index N-1."""
    trx = data.get("trx")
    if trx is None:
        return "no_transaction"
    if trx == 0:
        return "no_card"
    return f"card_{trx - 1}"


@dataclass(frozen=True, kw_only=True)
class GoeSensorDescription(SensorEntityDescription):
    """Sensor description with a coordinator-data extraction function."""

    value_fn: Callable[[dict[str, Any]], Any] = lambda data: None


SENSOR_DESCRIPTIONS: tuple[GoeSensorDescription, ...] = (
    # --- charging state -------------------------------------------------
    GoeSensorDescription(
        key="car_state",
        translation_key="car_state",
        icon="mdi:car-electric",
        value_fn=lambda d: lookup(CAR_STATES, d.get("car")),
    ),
    GoeSensorDescription(
        key="charging_status_reason",
        translation_key="charging_status_reason",
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: lookup(MODEL_STATUS, d.get("modelStatus")),
    ),
    GoeSensorDescription(
        key="error",
        translation_key="error",
        icon="mdi:alert-circle-outline",
        value_fn=_error_state,
    ),
    # --- energy ----------------------------------------------------------
    GoeSensorDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda d: None if d.get("wh") is None else round(d["wh"] / 1000, 3),
    ),
    GoeSensorDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda d: None if d.get("eto") is None else round(d["eto"] / 1000, 3),
    ),
    # --- live power / current / voltage (from the legacy `nrg` array) ----
    GoeSensorDescription(
        key="charging_power",
        translation_key="charging_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_nrg_scaled(11, 1),  # already in W on Gemini V4/FW 60.5
    ),
    *(
        GoeSensorDescription(
            key=f"power_l{phase}",
            translation_key=f"power_l{phase}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            entity_registry_enabled_default=False,
            value_fn=_nrg_scaled(6 + phase, 1),  # already in W on Gemini V4/FW 60.5
        )
        for phase in (1, 2, 3)
    ),
    *(
        GoeSensorDescription(
            key=f"voltage_l{phase}",
            translation_key=f"voltage_l{phase}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            entity_registry_enabled_default=False,
            value_fn=_nrg_scaled(phase - 1, 1),
        )
        for phase in (1, 2, 3)
    ),
    *(
        GoeSensorDescription(
            key=f"current_l{phase}",
            translation_key=f"current_l{phase}",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            entity_registry_enabled_default=False,
            value_fn=_nrg_scaled(3 + phase, 0.1),
        )
        for phase in (1, 2, 3)
    ),
    GoeSensorDescription(
        key="active_phases",
        translation_key="active_phases",
        icon="mdi:sine-wave",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("pnp"),
    ),
    # --- current limits (informational only - never written) ------------
    GoeSensorDescription(
        key="allowed_current",
        translation_key="allowed_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda d: d.get("acu"),
    ),
    GoeSensorDescription(
        key="max_current_limit",
        translation_key="max_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("ama"),
    ),
    # --- PV / energy management ------------------------------------------
    GoeSensorDescription(
        key="logic_mode",
        translation_key="logic_mode",
        icon="mdi:transmission-tower",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: lookup(LOGIC_MODE, d.get("lmo")),
    ),
    GoeSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("pgrid"),
    ),
    GoeSensorDescription(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("ppv"),
    ),
    GoeSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.get("pakku"),
    ),
    GoeSensorDescription(
        key="energy_data_source",
        translation_key="energy_data_source",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("dsrc"),
    ),
    # --- cable lock / RFID -------------------------------------------------
    GoeSensorDescription(
        key="cable_lock_status",
        translation_key="cable_lock_status",
        icon="mdi:lock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: lookup(CABLE_LOCK_STATUS, d.get("cus")),
    ),
    GoeSensorDescription(
        key="lock_mode",
        translation_key="lock_mode",
        icon="mdi:lock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: lookup(LOCK_MODE, d.get("lck")),
    ),
    GoeSensorDescription(
        key="lock_feedback",
        translation_key="lock_feedback",
        icon="mdi:lock-alert-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: lookup(LOCK_FEEDBACK, d.get("ffb")),
    ),
    GoeSensorDescription(
        key="rfid_transaction",
        translation_key="rfid_transaction",
        icon="mdi:card-account-details-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_trx_state,
    ),
    # --- diagnostics -------------------------------------------------------
    GoeSensorDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("fhz") or None,
    ),
    GoeSensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("rssi"),
    ),
    GoeSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("fwv"),
    ),
    GoeSensorDescription(
        key="serial_number",
        translation_key="serial_number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("sse"),
    ),
    GoeSensorDescription(
        key="device_variant",
        translation_key="device_variant",
        icon="mdi:ev-station",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: VARIANT_NAMES.get(d.get("var"), d.get("var")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up go-e Gemini sensors from a config entry."""
    coordinator: GoeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GoeSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class GoeSensor(GoeEntity, SensorEntity):
    """A single read-only sensor derived from the charger's status payload."""

    entity_description: GoeSensorDescription

    def __init__(
        self,
        coordinator: GoeDataUpdateCoordinator,
        description: GoeSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})
