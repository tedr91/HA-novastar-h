from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import NovastarDeviceInfo
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import NovastarCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Novastar select entities."""
    coordinator: NovastarCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_info: NovastarDeviceInfo = hass.data[DOMAIN][entry.entry_id]["device_info"]

    async_add_entities([NovastarPresetSelect(entry, coordinator, device_info)])


class NovastarPresetSelect(CoordinatorEntity[NovastarCoordinator], SelectEntity):
    """Select entity for preset selection."""

    _attr_has_entity_name = True
    _attr_name = "Preset"
    _attr_translation_key = "preset"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_preset"

    @property
    def device_info(self):
        """Return device info."""
        model = "H Series"
        if self._device_info.model_id:
            model = f"H Series (Model {self._device_info.model_id})"
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "manufacturer": "Novastar",
            "model": model,
            "name": self._entry.data.get(CONF_NAME, DEFAULT_NAME),
            "sw_version": self._device_info.firmware,
            "serial_number": self._device_info.serial,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def options(self) -> list[str]:
        """Return list of preset options."""
        presets = self.coordinator.presets
        if presets:
            return [p.name or f"Preset {p.preset_id}" for p in presets]
        return ["No presets"]

    @property
    def current_option(self) -> str | None:
        """Return current preset."""
        if not self.coordinator.data:
            return None

        current_id = self.coordinator.data.current_preset_id
        if current_id < 0:
            return None

        presets = self.coordinator.presets
        for preset in presets:
            if preset.preset_id == current_id:
                return preset.name or f"Preset {preset.preset_id}"

        return f"Preset {current_id}"

    async def async_select_option(self, option: str) -> None:
        """Select a preset."""
        presets = self.coordinator.presets
        for preset in presets:
            preset_name = preset.name or f"Preset {preset.preset_id}"
            if preset_name == option:
                await self.coordinator.client.async_load_preset(
                    preset_id=preset.preset_id,
                    screen_id=self.coordinator.screen_id,
                    device_id=self.coordinator.device_id,
                )
                await self.coordinator.async_request_refresh()
                return

        # Fallback: try parsing preset number from option
        if option.startswith("Preset "):
            try:
                preset_num = int(option.replace("Preset ", ""))
                await self.coordinator.client.async_load_preset(
                    preset_id=preset_num,
                    screen_id=self.coordinator.screen_id,
                    device_id=self.coordinator.device_id,
                )
                await self.coordinator.async_request_refresh()
            except ValueError:
                pass
