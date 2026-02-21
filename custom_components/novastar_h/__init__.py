from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .api import NovastarClient
from .const import (
    CONF_ALLOW_RAW_COMMANDS,
    CONF_DEVICE_ID,
    CONF_ENCRYPTION,
    CONF_PROJECT_ID,
    CONF_SCREEN_ID,
    CONF_SECRET_KEY,
    DEFAULT_ALLOW_RAW_COMMANDS,
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

SERVICE_SEND_RAW_COMMAND = "send_raw_command"
ATTR_ENDPOINT = "endpoint"
ATTR_BODY = "body"

SERVICE_SEND_RAW_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(ATTR_ENDPOINT): cv.string,
        vol.Required(ATTR_BODY): dict,
    }
)


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

    # Register send_raw_command service if not already registered
    # Check is done at call time via options/data
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_RAW_COMMAND):
        async def async_send_raw_command(call: ServiceCall) -> None:
            """Handle send_raw_command service call."""
            host = call.data[CONF_HOST]
            endpoint = call.data[ATTR_ENDPOINT]
            body = call.data[ATTR_BODY]

            # Find the client for the specified host
            client_found = None
            for eid, data in hass.data[DOMAIN].items():
                if isinstance(data, dict) and "client" in data:
                    if data["client"].host == host:
                        # Check if this entry allows raw commands (options first, then data)
                        config_entry = hass.config_entries.async_get_entry(eid)
                        if config_entry:
                            allow_raw = config_entry.options.get(
                                CONF_ALLOW_RAW_COMMANDS,
                                config_entry.data.get(
                                    CONF_ALLOW_RAW_COMMANDS, DEFAULT_ALLOW_RAW_COMMANDS
                                ),
                            )
                            if allow_raw:
                                client_found = data["client"]
                                break

            if not client_found:
                _LOGGER.error(
                    "No Novastar device found at %s with raw commands enabled", host
                )
                return

            result = await client_found.async_send_raw_command(endpoint, body)
            if result is None:
                _LOGGER.warning("Raw command to %s failed", endpoint)
            else:
                _LOGGER.debug("Raw command result: %s", result)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_RAW_COMMAND,
            async_send_raw_command,
            schema=SERVICE_SEND_RAW_COMMAND_SCHEMA,
        )

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
