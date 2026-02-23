from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE
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
    """Set up Novastar number entities."""
    coordinator: NovastarCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_info: NovastarDeviceInfo = hass.data[DOMAIN][entry.entry_id]["device_info"]

    async_add_entities(
        [
            NovastarBrightnessNumber(entry, coordinator, device_info),
            NovastarAudioVolumeNumber(entry, coordinator, device_info),
            NovastarAudioOutputModeNumber(entry, coordinator, device_info),
        ]
    )


class NovastarBrightnessNumber(CoordinatorEntity[NovastarCoordinator], NumberEntity):
    """Number entity for brightness control.

    Note: Brightness control is only supported on certain sending cards:
    - H_16xRJ45+2xfiber
    - H_20xRJ45
    - H_4xfiber
    - H_4xfiber (enhanced)
    """

    _attr_has_entity_name = True
    _attr_name = "Brightness"
    _attr_translation_key = "brightness"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_brightness"

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
    def native_value(self) -> float | None:
        """Return current brightness."""
        if self.coordinator.data:
            return float(self.coordinator.data.brightness)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set brightness value."""
        await self.coordinator.client.async_set_brightness(
            brightness=int(value),
            screen_id=self.coordinator.screen_id,
            device_id=self.coordinator.device_id,
        )
        await self.coordinator.async_request_refresh()


class NovastarAudioVolumeNumber(CoordinatorEntity[NovastarCoordinator], NumberEntity):
    """Number entity for audio volume control."""

    _attr_has_entity_name = True
    _attr_name = "Audio Volume"
    _attr_translation_key = "audio_volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_audio_volume"

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
    def native_value(self) -> float | None:
        """Return current audio volume."""
        if self.coordinator.data and self.coordinator.data.audio_volume is not None:
            return float(self.coordinator.data.audio_volume)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set audio volume value."""
        await self.coordinator.async_set_audio_volume(int(value))


class NovastarAudioOutputModeNumber(CoordinatorEntity[NovastarCoordinator], NumberEntity):
    """Number entity for audio output mode (audioOutputMode/outputChannelMode)."""

    _attr_has_entity_name = True
    _attr_name = "Audio Output Mode"
    _attr_translation_key = "audio_output_mode"
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_audio_output_mode"

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
    def native_value(self) -> float | None:
        """Return current audio output mode."""
        if self.coordinator.data and self.coordinator.data.audio_output_id is not None:
            return float(self.coordinator.data.audio_output_id)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set audio output mode value."""
        await self.coordinator.async_set_audio_output(int(value))
