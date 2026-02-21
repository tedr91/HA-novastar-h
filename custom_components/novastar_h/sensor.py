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


def _layer_is_active(layer: dict[str, Any]) -> bool:
    """Return whether a layer should be treated as active."""
    source = layer.get("source")
    source_type = source.get("sourceType") if isinstance(source, dict) else None
    if isinstance(source_type, int) and source_type != 0:
        return True

    window = layer.get("window")
    if isinstance(window, dict):
        width = window.get("width")
        height = window.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return True

    return False


def _layer_z_order(layer: dict[str, Any]) -> int:
    """Return layer z-order with safe fallback."""
    z_order = layer.get("zOrder")
    if z_order is None:
        general = layer.get("general")
        if isinstance(general, dict):
            z_order = general.get("zorder")
    if isinstance(z_order, int):
        return z_order
    if isinstance(z_order, float):
        return int(z_order)
    return -1


def _layer_source_name(layer: dict[str, Any]) -> str:
    """Return human-friendly source name for a layer."""
    source = layer.get("source")
    if isinstance(source, dict):
        source_name = source.get("name") or source.get("sourceName")
        if isinstance(source_name, str) and source_name:
            return source_name

    input_id = source.get("inputId") if isinstance(source, dict) else layer.get("inputId")
    if isinstance(input_id, int):
        return f"Input {input_id}"

    source_id = source.get("sourceId") if isinstance(source, dict) else layer.get("sourceId")
    if isinstance(source_id, int):
        return f"Source {source_id}"

    layer_id = layer.get("layerId")
    if isinstance(layer_id, int):
        return f"Layer {layer_id}"

    return "Unknown"


def _input_summary(input_data: dict[str, Any]) -> dict[str, Any]:
    """Return concise useful fields for an input."""
    resolution = input_data.get("resolution")
    if isinstance(resolution, dict):
        width = resolution.get("width")
        height = resolution.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            resolution_value: str | None = f"{width}x{height}"
        else:
            resolution_value = None
    else:
        resolution_value = None

    return {
        "name": input_data.get("name") or input_data.get("defaultName"),
        "inputId": input_data.get("inputId"),
        "interfaceId": input_data.get("interfaceId"),
        "interfaceType": input_data.get("interfaceType"),
        "online": input_data.get("online"),
        "resolution": resolution_value,
    }


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
        NovastarLayersSensor(entry, coordinator, device_info),
        NovastarActiveLayerCountSensor(entry, coordinator, device_info),
        NovastarTopLayerSourceSensor(entry, coordinator, device_info),
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
            return {"inputs": [], "inputs_summary": []}

        return {
            "input_count": len(self.coordinator.data.inputs),
            "inputs_summary": [
                _input_summary(input_data) for input_data in self.coordinator.data.inputs
            ],
            "inputs": self.coordinator.data.inputs,
        }


class NovastarLayersSensor(CoordinatorEntity[NovastarCoordinator], SensorEntity):
    """Sensor entity summarizing discovered layers."""

    _attr_has_entity_name = True
    _attr_name = "Layers"
    _attr_translation_key = "layers"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the layers sensor entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_layers"

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
        """Return summary as '<active>/<total> Active'."""
        if not self.coordinator.data:
            return "0/0 Active"

        layers = self.coordinator.data.layers
        total = len(layers)
        active = sum(1 for item in layers if _layer_is_active(item))
        return f"{active}/{total} Active"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full layer properties from readList/readDetail merge."""
        if not self.coordinator.data:
            return {"layers": []}

        return {
            "layer_count": len(self.coordinator.data.layers),
            "layers": self.coordinator.data.layers,
        }


class NovastarActiveLayerCountSensor(
    CoordinatorEntity[NovastarCoordinator], SensorEntity
):
    """Sensor entity for active layer count."""

    _attr_has_entity_name = True
    _attr_name = "Active Layer Count"
    _attr_translation_key = "active_layer_count"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize active layer count sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_active_layer_count"

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
    def native_value(self) -> int:
        """Return count of active layers."""
        if not self.coordinator.data:
            return 0
        return sum(1 for layer in self.coordinator.data.layers if _layer_is_active(layer))


class NovastarTopLayerSourceSensor(CoordinatorEntity[NovastarCoordinator], SensorEntity):
    """Sensor entity for source used by top-most active layer."""

    _attr_has_entity_name = True
    _attr_name = "Top Layer Source"
    _attr_translation_key = "top_layer_source"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize top layer source sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_top_layer_source"

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
        """Return source of top-most active layer."""
        if not self.coordinator.data:
            return None

        active_layers = [
            layer for layer in self.coordinator.data.layers if _layer_is_active(layer)
        ]
        if not active_layers:
            return None

        top_layer = max(active_layers, key=_layer_z_order)
        return _layer_source_name(top_layer)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return metadata for the top-most active layer."""
        if not self.coordinator.data:
            return None

        active_layers = [
            layer for layer in self.coordinator.data.layers if _layer_is_active(layer)
        ]
        if not active_layers:
            return None

        top_layer = max(active_layers, key=_layer_z_order)
        source = top_layer.get("source")
        return {
            "layer_id": top_layer.get("layerId"),
            "z_order": _layer_z_order(top_layer),
            "source_type": source.get("sourceType") if isinstance(source, dict) else top_layer.get("sourceType"),
            "input_id": source.get("inputId") if isinstance(source, dict) else top_layer.get("inputId"),
            "source_id": source.get("sourceId") if isinstance(source, dict) else top_layer.get("sourceId"),
        }


