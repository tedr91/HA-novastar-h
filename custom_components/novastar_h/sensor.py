from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
)
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
    """Set up Novastar sensor entities."""
    coordinator: NovastarCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_info: NovastarDeviceInfo = hass.data[DOMAIN][entry.entry_id]["device_info"]

    async_add_entities([
        NovastarTempStatusSensor(entry, coordinator, device_info),
        NovastarDeviceStatusSensor(entry, coordinator, device_info),
        NovastarSignalStatusSensor(entry, coordinator, device_info),
        NovastarInputsSensor(entry, coordinator, device_info),
    ])


class NovastarTempStatusSensor(CoordinatorEntity[NovastarCoordinator], SensorEntity):
    """Sensor entity for device temperature status."""

    _attr_has_entity_name = True
    _attr_name = "Temperature Status"
    _attr_translation_key = "temp_status"

    # Map status codes to human-readable values
    STATUS_MAP = {
        0: "Normal",
        1: "Warning",
        2: "Critical",
    }

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_temp_status"

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
    def native_value(self) -> str | None:
        """Return current temperature status."""
        if self.coordinator.data and self.coordinator.data.temp_status is not None:
            return self.STATUS_MAP.get(
                self.coordinator.data.temp_status,
                f"Unknown ({self.coordinator.data.temp_status})",
            )
        return None


class NovastarDeviceStatusSensor(CoordinatorEntity[NovastarCoordinator], SensorEntity):
    """Sensor entity for device status."""

    _attr_has_entity_name = True
    _attr_name = "Device Status"
    _attr_translation_key = "device_status"

    # Map status codes to human-readable values
    STATUS_MAP = {
        0: "Busy",
        1: "Ready",
    }

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_device_status"

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
    def native_value(self) -> str | None:
        """Return current device status."""
        if self.coordinator.data and self.coordinator.data.device_status is not None:
            return self.STATUS_MAP.get(
                self.coordinator.data.device_status,
                f"Unknown ({self.coordinator.data.device_status})",
            )
        return None


class NovastarSignalStatusSensor(CoordinatorEntity[NovastarCoordinator], SensorEntity):
    """Sensor entity for signal status."""

    _attr_has_entity_name = True
    _attr_name = "Signal Status"
    _attr_translation_key = "signal_status"

    # Map status codes to human-readable values
    STATUS_MAP = {
        0: "No Signal",
        1: "Signal Present",
    }

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_signal_status"

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
    def native_value(self) -> str | None:
        """Return current signal power status."""
        if self.coordinator.data and self.coordinator.data.signal_status is not None:
            return self.STATUS_MAP.get(
                self.coordinator.data.signal_status,
                f"Unknown ({self.coordinator.data.signal_status})",
            )
        return None


class NovastarInputsSensor(CoordinatorEntity[NovastarCoordinator], SensorEntity):
    """Sensor entity summarizing discovered inputs."""

    _attr_has_entity_name = True
    _attr_name = "Inputs"
    _attr_translation_key = "inputs"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the inputs sensor entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_inputs"

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
    def native_value(self) -> str:
        """Return summary as '<online>/<total> Online'."""
        if not self.coordinator.data:
            return "0/0 Online"

        inputs = self.coordinator.data.inputs
        total = len(inputs)
        online = sum(1 for item in inputs if item.get("online") == 1)
        return f"{online}/{total} Online"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full input properties from readList/readDetail merge."""
        if not self.coordinator.data:
            return {"inputs": []}

        return {
            "input_count": len(self.coordinator.data.inputs),
            "inputs": self.coordinator.data.inputs,
        }


