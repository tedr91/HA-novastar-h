from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import NovastarDeviceInfo
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import NovastarCoordinator


def _supported_features() -> MediaPlayerEntityFeature:
    """Return supported features."""
    features = MediaPlayerEntityFeature(0)
    for feature_name in ("TURN_ON", "TURN_OFF", "SELECT_SOURCE"):
        feature_value = getattr(MediaPlayerEntityFeature, feature_name, None)
        if feature_value is not None:
            features |= feature_value
    return features


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Novastar media player entity."""
    coordinator: NovastarCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_info: NovastarDeviceInfo = hass.data[DOMAIN][entry.entry_id]["device_info"]

    async_add_entities([NovastarMediaPlayer(entry, coordinator, device_info)])


class NovastarMediaPlayer(CoordinatorEntity[NovastarCoordinator], MediaPlayerEntity):
    """Media player entity for Novastar H series.

    Provides unified control with:
    - Turn on/off: Controls FTB (Fade to Black)
    - Source selection: Select presets
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = _supported_features()

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_media_player"

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
    def state(self) -> MediaPlayerState:
        """Return current state.

        OFF = FTB active (screen blacked out)
        ON = Screen displaying content
        """
        if not self.coordinator.data:
            return MediaPlayerState.OFF
        if self.coordinator.data.ftb_active:
            return MediaPlayerState.OFF
        return MediaPlayerState.ON

    @property
    def source(self) -> str | None:
        """Return current source/preset."""
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

    @property
    def source_list(self) -> list[str]:
        """Return list of available sources (presets)."""
        presets = self.coordinator.presets
        if presets:
            return [p.name or f"Preset {p.preset_id}" for p in presets]
        return []

    async def async_turn_on(self) -> None:
        """Turn on the display (disable FTB/blackout)."""
        await self.coordinator.client.async_set_ftb(
            blackout=False,
            screen_id=self.coordinator.screen_id,
            device_id=self.coordinator.device_id,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the display (enable FTB/blackout)."""
        await self.coordinator.client.async_set_ftb(
            blackout=True,
            screen_id=self.coordinator.screen_id,
            device_id=self.coordinator.device_id,
        )
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Select a source (preset)."""
        presets = self.coordinator.presets
        for preset in presets:
            preset_name = preset.name or f"Preset {preset.preset_id}"
            if preset_name == source:
                await self.coordinator.client.async_load_preset(
                    preset_id=preset.preset_id,
                    screen_id=self.coordinator.screen_id,
                    device_id=self.coordinator.device_id,
                )
                await self.coordinator.async_request_refresh()
                return

        # Fallback: try parsing preset number from source name
        if source.startswith("Preset "):
            try:
                preset_num = int(source.replace("Preset ", ""))
                await self.coordinator.client.async_load_preset(
                    preset_id=preset_num,
                    screen_id=self.coordinator.screen_id,
                    device_id=self.coordinator.device_id,
                )
                await self.coordinator.async_request_refresh()
            except ValueError:
                pass
