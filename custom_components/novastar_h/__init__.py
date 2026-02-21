from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .api import NovastarClient
from .const import (
    CONF_DEVICE_ID,
    CONF_ENCRYPTION,
    CONF_PROJECT_ID,
    CONF_SCREEN_ID,
    CONF_SECRET_KEY,
    DEFAULT_DEVICE_ID,
    DEFAULT_ENCRYPTION,
    DEFAULT_PORT,
    DEFAULT_SCREEN_ID,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import NovastarCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Novastar H Series from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = NovastarClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        project_id=entry.data[CONF_PROJECT_ID],
        secret_key=entry.data[CONF_SECRET_KEY],
        encryption=entry.data.get(CONF_ENCRYPTION, DEFAULT_ENCRYPTION),
        timeout=DEFAULT_TIMEOUT,
    )

    device_id = entry.data.get(CONF_DEVICE_ID, DEFAULT_DEVICE_ID)
    screen_id = entry.data.get(CONF_SCREEN_ID, DEFAULT_SCREEN_ID)

    device_info = await client.async_get_device_info()

    coordinator = NovastarCoordinator(
        hass, entry, client, device_id=device_id, screen_id=screen_id
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "device_info": device_info,
    }

    loaded_platforms: list[Any] = []
    for platform in PLATFORMS:
        try:
            await hass.config_entries.async_forward_entry_setups(entry, [platform])
            loaded_platforms.append(platform)
        except Exception:
            _LOGGER.exception(
                "Failed to set up Novastar platform '%s' for entry %s",
                platform,
                entry.entry_id,
            )

    if not loaded_platforms:
        _LOGGER.error("No Novastar platforms could be set up for entry %s", entry.entry_id)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return False

    hass.data[DOMAIN][entry.entry_id]["loaded_platforms"] = loaded_platforms
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    loaded_platforms = entry_data.get("loaded_platforms", PLATFORMS)
    unloaded = await hass.config_entries.async_unload_platforms(entry, loaded_platforms)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
