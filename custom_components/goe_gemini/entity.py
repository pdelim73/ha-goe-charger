"""Base entity for the go-e Charger Gemini (Read-Only) integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, VARIANT_NAMES
from .coordinator import GoeDataUpdateCoordinator


class GoeEntity(CoordinatorEntity[GoeDataUpdateCoordinator]):
    """Common device_info handling for all go-e Gemini entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GoeDataUpdateCoordinator, unique_id_suffix: str) -> None:
        super().__init__(coordinator)
        serial = (coordinator.data or {}).get("sse") or coordinator.entry.entry_id
        self._device_serial = serial
        self._attr_unique_id = f"{serial}_{unique_id_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data or {}
        variant = data.get("var")
        variant_name = VARIANT_NAMES.get(variant) if variant is not None else None
        model = f"Gemini ({variant_name})" if variant_name else "Gemini"
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_serial)},
            manufacturer=MANUFACTURER,
            name=data.get("fna") or "go-e Charger",
            model=model,
            sw_version=data.get("fwv"),
        )
