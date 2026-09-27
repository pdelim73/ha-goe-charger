"""Constants for the go-e Charger Gemini (Read-Only) integration."""

from __future__ import annotations

DOMAIN = "goe_gemini"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 300

DEFAULT_TIMEOUT = 10

MANUFACTURER = "go-e"

# Keys requested from GET /api/status?filter=<...>. go-e's own API docs warn
# that the unfiltered endpoint causes "higher system load, lots of traffic,
# shouldn't be used for productive setups" - so this list is kept to exactly
# what the sensor/binary_sensor platforms below render, nothing more.
STATUS_KEYS: list[str] = [
    # identity (mostly constant, used for device_info)
    "fna", "sse", "fwv", "typ", "var",
    # charging state
    "car", "err", "modelStatus", "alw",
    # energy / power (nrg is the legacy combined array, see sensor.py)
    "wh", "eto", "nrg", "pnp",
    # current limits (read-only display only, never written)
    "acu", "ama",
    # PV / energy management
    "fup", "lmo", "pgrid", "ppv", "pakku", "dsrc",
    # cable lock / RFID
    "cus", "lck", "ffb", "trx",
    # diagnostics
    "rssi", "fhz",
]

# Minimal probe used once during config_flow validation.
VALIDATION_FILTER_KEYS: list[str] = ["alw", "fwv", "sse", "typ", "var"]

# --- Enum lookup tables -------------------------------------------------
# Sourced from goecharger/go-eCharger-API-v2, API_KEYS_FIRMWARE/
# apikeys_Firmware_60.4_sorted.md (closest published firmware reference to
# this integration's target FW 60.5). go-e evolves these numeric codes
# between firmware generations and explicitly reserves the right to add new
# ones without notice, so unmapped codes render as "unknown_code_<n>"
# instead of raising - see lookup() below.

CAR_STATES: dict[int, str] = {
    0: "unknown",
    1: "idle",
    2: "charging",
    3: "wait_car",
    4: "complete",
    5: "error",
    6: "initializing",
}

ERROR_CODES: dict[int, str] = {
    0: "none",
    1: "fi_ac",
    2: "fi_dc",
    3: "phase",
    4: "overvolt",
    5: "overamp",
    6: "diode",
    7: "pp_invalid",
    8: "gnd_invalid",
    9: "contactor_stuck",
    10: "contactor_miss",
    12: "status_lock_stuck_open",
    13: "status_lock_stuck_locked",
    14: "fi_unknown",
    15: "unknown",
    16: "overtemp",
    17: "no_comm",
    18: "cp_invalid",
    23: "rdc_self_test_failed",
}

MODEL_STATUS: dict[int, str] = {
    0: "charging_because_no_chargectrl_data",
    1: "not_charging_because_overtemperature",
    2: "not_charging_because_access_control",
    3: "charging_because_force_state_on",
    4: "not_charging_because_force_state_off",
    5: "not_charging_because_scheduler",
    6: "not_charging_because_energy_limit",
    7: "charging_because_awattar_price_low",
    8: "charging_because_automatic_stop_test_charge",
    9: "charging_because_automatic_stop_not_enough_time",
    10: "charging_because_automatic_stop",
    11: "charging_because_automatic_stop_no_clock",
    12: "charging_because_pv_surplus",
    13: "charging_because_fallback_v2_default",
    14: "charging_because_fallback_v2_scheduler",
    15: "charging_because_fallback_default",
    16: "not_charging_because_fallback_v2_awattar",
    17: "not_charging_because_fallback_awattar",
    18: "not_charging_because_fallback_automatic_stop",
    19: "charging_because_car_compatibility_keep_alive",
    20: "charging_because_charge_pause_not_allowed",
    22: "not_charging_because_simulate_unplugging",
    23: "not_charging_because_phase_switch",
    24: "not_charging_because_min_pause_duration",
    26: "not_charging_because_error",
    27: "not_charging_because_load_management_doesnt_want",
    28: "not_charging_because_ocpp_doesnt_want",
    29: "not_charging_because_reconnect_delay",
    30: "not_charging_because_adapter_blocking",
    31: "not_charging_because_underfrequency_control",
    32: "not_charging_because_unbalanced_load",
    33: "charging_because_discharging_pv_battery",
    34: "not_charging_because_grid_monitoring",
    35: "not_charging_because_ocpp_fallback",
    36: "not_charging_because_floor_detected",
    37: "not_charging_because_ocpp_inoperable",
    38: "not_charging_because_undervoltage_control",
    39: "not_charging_because_zero_setpoint",
    40: "not_charging_because_initializing",
    41: "not_charging_because_failsafe_limit",
}

CABLE_LOCK_STATUS: dict[int, str] = {
    0: "unknown",
    1: "unlocked",
    2: "unlock_failed",
    3: "locked",
    4: "lock_failed",
    5: "lock_unlock_power_out",
}

LOCK_MODE: dict[int, str] = {
    0: "normal",
    1: "auto_unlock",
    2: "always_lock",
    3: "force_unlock",
}

LOCK_FEEDBACK: dict[int, str] = {
    0: "no_problem",
    1: "problem_lock",
    2: "problem_unlock",
}

LOGIC_MODE: dict[int, str] = {
    3: "default",
    4: "awattar",
    5: "next_trip",
}

VARIANT_NAMES: dict[int, str] = {
    11: "11 kW / 16 A",
    22: "22 kW / 32 A",
}


def lookup(table: dict[int, str], code: int | None) -> str | None:
    """Map a numeric enum code to its name, defensively.

    Returns None if code itself is None (field absent/null on this
    firmware), or "unknown_code_<n>" for a code this table doesn't
    recognize yet, rather than raising - firmware updates add new codes
    without notice.
    """
    if code is None:
        return None
    return table.get(code, f"unknown_code_{code}")
