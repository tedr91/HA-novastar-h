from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import NovastarDeviceInfo
from .const import (
    CONF_LAYER_SELECT_PREPOPULATE_COUNT,
    DEFAULT_LAYER_SELECT_PREPOPULATE_COUNT,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import NovastarCoordinator


def _coerce_int(value: Any) -> int | None:
    """Safely coerce a value to int."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _input_label(input_data: dict[str, Any]) -> str:
    """Build a stable option label for one input."""
    input_id = _coerce_int(input_data.get("inputId"))
    base_name = input_data.get("name") or input_data.get("defaultName")
    if isinstance(base_name, str) and base_name.strip():
        return base_name.strip()
    elif input_id is not None:
        return f"Input {input_id}"
    return "Input"


def _layer_source_type(layer: dict[str, Any]) -> int:
    """Return source type for a layer."""
    source = layer.get("source")
    source_type = source.get("sourceType") if isinstance(source, dict) else None
    source_type_int = _coerce_int(source_type)
    return source_type_int if source_type_int is not None else 0


def _layer_input_id(layer: dict[str, Any]) -> int | None:
    """Return current input id for a layer source."""
    source = layer.get("source")
    input_id = source.get("inputId") if isinstance(source, dict) else layer.get("inputId")
    return _coerce_int(input_id)


def _background_label(background: dict[str, Any]) -> str:
    """Build stable display label for one background item."""
    bkg_id = _coerce_int(background.get("bkgId"))
    name = background.get("name")
    if isinstance(name, str) and name.strip():
        clean_name = name.strip()
    elif bkg_id is not None:
        clean_name = f"BKG {bkg_id}"
    else:
        clean_name = "Background"

    if bkg_id is not None:
        return f"{clean_name} ({bkg_id})"
    return clean_name


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Novastar select entities."""
    coordinator: NovastarCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_info: NovastarDeviceInfo = hass.data[DOMAIN][entry.entry_id]["device_info"]
    layer_count = entry.options.get(
        CONF_LAYER_SELECT_PREPOPULATE_COUNT,
        entry.data.get(
            CONF_LAYER_SELECT_PREPOPULATE_COUNT,
            DEFAULT_LAYER_SELECT_PREPOPULATE_COUNT,
        ),
    )
    layer_count = _coerce_int(layer_count) or DEFAULT_LAYER_SELECT_PREPOPULATE_COUNT

    entities: list[SelectEntity] = [NovastarPresetSelect(entry, coordinator, device_info)]
    entities.append(NovastarBackgroundSelect(entry, coordinator, device_info))
    entities.append(NovastarAudioInputSelect(entry, coordinator, device_info))
    entities.append(NovastarAudioOutputSelect(entry, coordinator, device_info))
    entities.extend(
        [
            NovastarLayerSourceSelect(entry, coordinator, device_info, layer_id)
            for layer_id in range(max(1, layer_count))
        ]
    )
    async_add_entities(entities)


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
                await self.coordinator.async_set_active_preset(preset.preset_id)
                return

        # Fallback: try parsing preset number from option
        if option.startswith("Preset "):
            try:
                preset_num = int(option.replace("Preset ", ""))
                await self.coordinator.async_set_active_preset(preset_num)
            except ValueError:
                pass


class NovastarLayerSourceSelect(CoordinatorEntity[NovastarCoordinator], SelectEntity):
    """Select entity for setting source on one layer."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
        layer_id: int,
    ) -> None:
        """Initialize layer source select."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._layer_id = layer_id
        self._attr_name = f"Layer {layer_id} Source"
        self._attr_unique_id = f"{entry.entry_id}_layer_{layer_id}_source"

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
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return any(
            _coerce_int(layer.get("layerId")) == self._layer_id
            for layer in self.coordinator.data.layers
        )

    def _get_layer(self) -> dict[str, Any] | None:
        """Return layer payload for this select."""
        if not self.coordinator.data:
            return None
        for layer in self.coordinator.data.layers:
            if _coerce_int(layer.get("layerId")) == self._layer_id:
                return layer
        return None

    def _input_map(self) -> dict[str, dict[str, Any]]:
        """Return option label -> input mapping."""
        if not self.coordinator.data:
            return {}

        mapped: dict[str, dict[str, Any]] = {}
        for input_data in self.coordinator.data.inputs:
            input_id = _coerce_int(input_data.get("inputId"))
            if input_id is None:
                continue
            mapped[_input_label(input_data)] = input_data
        return dict(sorted(mapped.items(), key=lambda item: item[0]))

    @property
    def options(self) -> list[str]:
        """Return available source options for this layer."""
        options = ["None"]
        input_options = list(self._input_map().keys())
        options.extend(input_options)

        current = self.current_option
        if current and current not in options:
            options.append(current)
        return options

    @property
    def current_option(self) -> str | None:
        """Return currently selected source option."""
        layer = self._get_layer()
        if layer is None:
            return None

        if _layer_source_type(layer) == 0:
            return "None"

        current_input_id = _layer_input_id(layer)
        if current_input_id is None:
            return "None"

        for label, input_data in self._input_map().items():
            if _coerce_int(input_data.get("inputId")) == current_input_id:
                return label

        return f"Input {current_input_id}"

    async def async_select_option(self, option: str) -> None:
        """Set source for this layer."""
        if option == "None":
            await self.coordinator.async_set_layer_source(
                layer_id=self._layer_id,
                input_id=None,
            )
            return

        input_data = self._input_map().get(option)
        if input_data is None:
            if option.startswith("Input "):
                try:
                    parsed_id = int(option.replace("Input ", "").strip())
                except ValueError:
                    return
                await self.coordinator.async_set_layer_source(
                    layer_id=self._layer_id,
                    input_id=parsed_id,
                )
            return

        input_id = _coerce_int(input_data.get("inputId"))
        if input_id is None:
            return

        interface_type = _coerce_int(input_data.get("interfaceType"))
        slot_id = _coerce_int(input_data.get("interfaceId"))

        await self.coordinator.async_set_layer_source(
            layer_id=self._layer_id,
            input_id=input_id,
            interface_type=interface_type or 0,
            slot_id=slot_id or 0,
            crop_id=255,
        )


class NovastarBackgroundSelect(CoordinatorEntity[NovastarCoordinator], SelectEntity):
    """Select entity for active background."""

    _attr_has_entity_name = True
    _attr_name = "Background"
    _attr_translation_key = "background"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize background select."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_background"

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

    def _background_map(self) -> dict[str, int]:
        """Return label->background_id map."""
        if not self.coordinator.data:
            return {}

        mapped: dict[str, int] = {}
        for background in self.coordinator.data.backgrounds:
            bkg_id = _coerce_int(background.get("bkgId"))
            if bkg_id is None:
                continue
            mapped[_background_label(background)] = bkg_id
        return dict(sorted(mapped.items(), key=lambda item: item[0]))

    @property
    def options(self) -> list[str]:
        """Return available background options."""
        options = list(self._background_map().keys())
        current = self.current_option
        if current and current not in options:
            options.append(current)
        if not options:
            options.append("Background 0")
        return options

    @property
    def current_option(self) -> str | None:
        """Return currently selected background option."""
        if not self.coordinator.data:
            return None

        current_id = _coerce_int(self.coordinator.data.background_id)
        if current_id is None:
            return None

        for label, bkg_id in self._background_map().items():
            if bkg_id == current_id:
                return label

        return f"Background {current_id}"

    async def async_select_option(self, option: str) -> None:
        """Set active background and enable it."""
        bkg_id = self._background_map().get(option)
        if bkg_id is None:
            text = option.strip()
            try:
                if text.startswith("Background "):
                    bkg_id = int(text.replace("Background ", "").strip())
                elif text.startswith("BKG "):
                    bkg_id = int(text.replace("BKG ", "").strip())
            except ValueError:
                return

        if bkg_id is None:
            return

        await self.coordinator.async_set_background(background_id=bkg_id, enabled=True)


class _NovastarBaseAudioSelect(CoordinatorEntity[NovastarCoordinator], SelectEntity):
    """Base select for audio route entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize audio select base."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info

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


class NovastarAudioInputSelect(_NovastarBaseAudioSelect):
    """Select entity for active audio input."""

    _attr_name = "Audio Input"
    _attr_translation_key = "audio_input"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize audio input select."""
        super().__init__(entry, coordinator, device_info)
        self._attr_unique_id = f"{entry.entry_id}_audio_input"

    def _audio_input_map(self) -> dict[str, int]:
        """Map audio input option label to id."""
        if not self.coordinator.data:
            return {}

        mapped: dict[str, int] = {}
        for input_data in self.coordinator.data.audio_inputs:
            input_id = _coerce_int(input_data.get("id"))
            if input_id is None:
                continue
            base_label = _input_label(input_data)
            label = base_label
            if label in mapped and mapped[label] != input_id:
                label = f"{base_label} ({input_id})"
            mapped[label] = input_id
        return dict(sorted(mapped.items(), key=lambda item: item[0]))

    @property
    def options(self) -> list[str]:
        """Return available audio input options."""
        options = list(self._audio_input_map().keys())
        current = self.current_option
        if current and current not in options:
            options.append(current)
        return options or ["Audio Input 0"]

    @property
    def current_option(self) -> str | None:
        """Return selected audio input option."""
        if not self.coordinator.data:
            return None
        current_id = _coerce_int(self.coordinator.data.audio_input_id)
        if current_id is None:
            return None

        for label, option_id in self._audio_input_map().items():
            if option_id == current_id:
                return label
        return f"Audio Input {current_id}"

    async def async_select_option(self, option: str) -> None:
        """Set active audio input."""
        input_id = self._audio_input_map().get(option)
        if input_id is None:
            text = option.strip()
            if text.startswith("Audio Input "):
                try:
                    input_id = int(text.replace("Audio Input ", "").strip())
                except ValueError:
                    return
        if input_id is None:
            return
        await self.coordinator.async_set_audio_input(input_id)


class NovastarAudioOutputSelect(_NovastarBaseAudioSelect):
    """Select entity for active audio output."""

    _attr_name = "Audio Output"
    _attr_translation_key = "audio_output"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize audio output select."""
        super().__init__(entry, coordinator, device_info)
        self._attr_unique_id = f"{entry.entry_id}_audio_output"

    def _audio_output_map(self) -> dict[str, int]:
        """Map audio output option label to id."""
        if not self.coordinator.data:
            return {}

        mapped: dict[str, int] = {}
        for output_data in self.coordinator.data.audio_outputs:
            output_id = _coerce_int(output_data.get("id"))
            if output_id is None:
                continue
            label = output_data.get("name") or f"Audio Output {output_id}"
            if isinstance(label, str):
                base_label = label.strip() or f"Audio Output {output_id}"
                unique_label = base_label
                if unique_label in mapped and mapped[unique_label] != output_id:
                    unique_label = f"{base_label} ({output_id})"
                mapped[unique_label] = output_id
        return dict(sorted(mapped.items(), key=lambda item: item[0]))

    @property
    def options(self) -> list[str]:
        """Return available audio output options."""
        options = list(self._audio_output_map().keys())
        current = self.current_option
        if current and current not in options:
            options.append(current)
        return options or ["Audio Output 0"]

    @property
    def current_option(self) -> str | None:
        """Return selected audio output option."""
        if not self.coordinator.data:
            return None
        current_id = _coerce_int(self.coordinator.data.audio_output_id)
        if current_id is None:
            return None

        for label, option_id in self._audio_output_map().items():
            if option_id == current_id:
                return label
        return f"Audio Output {current_id}"

    async def async_select_option(self, option: str) -> None:
        """Set active audio output."""
        output_id = self._audio_output_map().get(option)
        if output_id is None:
            text = option.strip()
            if text.startswith("Audio Output "):
                try:
                    output_id = int(text.replace("Audio Output ", "").strip())
                except ValueError:
                    return
        if output_id is None:
            return
        await self.coordinator.async_set_audio_output(output_id)
