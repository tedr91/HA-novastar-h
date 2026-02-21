from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Novastar switch entities."""
    coordinator: NovastarCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_info: NovastarDeviceInfo = hass.data[DOMAIN][entry.entry_id]["device_info"]

    entities = [
        NovastarFTBSwitch(entry, coordinator, device_info),
        NovastarFreezeSwitch(entry, coordinator, device_info),
    ]
    async_add_entities(entities)


class NovastarSwitchBase(CoordinatorEntity[NovastarCoordinator], SwitchEntity):
    """Base class for Novastar switches."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize the switch."""
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


class NovastarFTBSwitch(NovastarSwitchBase):
    """Switch for Fade to Black (FTB) control.

    When ON: Screen is displaying content (not blacked out)
    When OFF: Screen is blacked out (FTB active)
    """

    _attr_name = "Power (Screen Output)"
    _attr_translation_key = "screen_output"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize FTB switch."""
        super().__init__(entry, coordinator, device_info)
        self._attr_unique_id = f"{entry.entry_id}_ftb"

    @property
    def is_on(self) -> bool:
        """Return True if screen output is active (not blacked out)."""
        if self.coordinator.data:
            # FTB active means screen is OFF, so we invert
            return not self.coordinator.data.ftb_active
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on screen output (disable FTB/blackout)."""
        await self.coordinator.async_set_ftb(blackout=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off screen output (enable FTB/blackout)."""
        await self.coordinator.async_set_ftb(blackout=True)


class NovastarFreezeSwitch(NovastarSwitchBase):
    """Switch for screen freeze control.

    When ON: Screen is frozen (displaying last frame)
    When OFF: Screen is live
    """

    _attr_name = "Freeze Screen"
    _attr_translation_key = "freeze"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: NovastarCoordinator,
        device_info: NovastarDeviceInfo,
    ) -> None:
        """Initialize freeze switch."""
        super().__init__(entry, coordinator, device_info)
        self._attr_unique_id = f"{entry.entry_id}_freeze"

    @property
    def is_on(self) -> bool:
        """Return True if screen is frozen."""
        if self.coordinator.data:
            return self.coordinator.data.freeze_active
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Freeze screen."""
        await self.coordinator.async_set_freeze(freeze=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unfreeze screen."""
        await self.coordinator.async_set_freeze(freeze=False)
