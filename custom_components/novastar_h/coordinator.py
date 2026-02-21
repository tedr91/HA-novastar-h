from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import NovastarClient, NovastarPreset, NovastarState
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class NovastarCoordinator(DataUpdateCoordinator[NovastarState]):
    """Coordinator for Novastar H series device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NovastarClient,
        device_id: int = 0,
        screen_id: int = 0,
    ) -> None:
        """Initialize the coordinator."""
        self._client = client
        self._device_id = device_id
        self._screen_id = screen_id
        self._ftb_active = False  # Track FTB state locally (API doesn't expose read)
        self._freeze_active = False  # Track freeze state locally
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    @property
    def client(self) -> NovastarClient:
        """Return the API client."""
        return self._client

    @property
    def device_id(self) -> int:
        """Return the device ID."""
        return self._device_id

    @property
    def screen_id(self) -> int:
        """Return the screen ID."""
        return self._screen_id

    @property
    def presets(self) -> list[NovastarPreset]:
        """Return cached presets."""
        if self.data:
            return self.data.presets
        return []

    async def async_set_ftb(self, blackout: bool) -> bool:
        """Set FTB state and track it locally."""
        result = await self._client.async_set_ftb(
            blackout=blackout,
            screen_id=self._screen_id,
            device_id=self._device_id,
        )
        if result:
            self._ftb_active = blackout
            # Update coordinator data immediately
            if self.data:
                self.data.ftb_active = blackout
            self.async_set_updated_data(self.data)
        return result

    async def async_set_freeze(self, freeze: bool) -> bool:
        """Set freeze state and track it locally."""
        result = await self._client.async_set_freeze(
            freeze=freeze,
            screen_id=self._screen_id,
            device_id=self._device_id,
        )
        if result:
            self._freeze_active = freeze
            # Update coordinator data immediately
            if self.data:
                self.data.freeze_active = freeze
            self.async_set_updated_data(self.data)
        return result

    async def _async_update_data(self) -> NovastarState:
        """Fetch data from the device."""
        state = await self._client.async_get_state(self._screen_id, self._device_id)
        # Preserve locally tracked states
        state.ftb_active = self._ftb_active
        state.freeze_active = self._freeze_active
        return state
