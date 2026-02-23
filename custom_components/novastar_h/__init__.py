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
    CONF_ENABLE_DEBUG_LOGGING,
    CONF_PROJECT_ID,
    CONF_SCREEN_ID,
    CONF_SECRET_KEY,
    DEFAULT_ALLOW_RAW_COMMANDS,
    DEFAULT_DEVICE_ID,
    DEFAULT_ENCRYPTION,
    DEFAULT_ENABLE_DEBUG_LOGGING,
    DEFAULT_PORT,
    DEFAULT_SCREEN_ID,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import NovastarCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_RAW_COMMAND = "send_raw_command"
SERVICE_SET_LAYER_SOURCE = "set_layer_source"
SERVICE_SET_ACTIVE_PRESET = "set_active_preset"
ATTR_ENDPOINT = "endpoint"
ATTR_BODY = "body"
ATTR_LAYER_ID = "layer_id"
ATTR_INPUT_ID = "input_id"
ATTR_INTERFACE_TYPE = "interface_type"
ATTR_SLOT_ID = "slot_id"
ATTR_CROP_ID = "crop_id"
ATTR_PRESET_ID = "preset_id"

SERVICE_SEND_RAW_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(ATTR_ENDPOINT): cv.string,
        vol.Required(ATTR_BODY): dict,
    }
)

SERVICE_SET_LAYER_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(ATTR_LAYER_ID): vol.Coerce(int),
        vol.Optional(ATTR_INPUT_ID): vol.Any(None, vol.Coerce(int)),
        vol.Optional(ATTR_INTERFACE_TYPE, default=0): vol.Coerce(int),
        vol.Optional(ATTR_SLOT_ID, default=0): vol.Coerce(int),
        vol.Optional(ATTR_CROP_ID, default=255): vol.Coerce(int),
    }
)

SERVICE_SET_ACTIVE_PRESET_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(ATTR_PRESET_ID): vol.Coerce(int),
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
        enable_debug_logging=entry.options.get(
            CONF_ENABLE_DEBUG_LOGGING,
            entry.data.get(
                CONF_ENABLE_DEBUG_LOGGING,
                DEFAULT_ENABLE_DEBUG_LOGGING,
            ),
        ),
        timeout=DEFAULT_TIMEOUT,
    )

    device_id = entry.data.get(CONF_DEVICE_ID, DEFAULT_DEVICE_ID)
    screen_id = entry.data.get(CONF_SCREEN_ID, DEFAULT_SCREEN_ID)

    device_info = await client.async_get_device_info()

    coordinator = NovastarCoordinator(
        hass, entry, client, device_id=device_id, screen_id=screen_id
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        _LOGGER.warning(
            "Initial refresh failed for entry %s; continuing setup with unavailable entities",
            entry.entry_id,
            exc_info=True,
        )

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "device_info": device_info,
    }

    def resolve_coordinator_by_host(
        host: str | None,
    ) -> tuple[NovastarCoordinator | None, str | None, str | None]:
        """Resolve a coordinator from optional host input."""
        coordinators: list[tuple[str, NovastarCoordinator]] = []
        for data in hass.data[DOMAIN].values():
            if isinstance(data, dict) and "client" in data and "coordinator" in data:
                coordinators.append((data["client"].host, data["coordinator"]))

        if host:
            for known_host, coordinator in coordinators:
                if known_host == host:
                    return coordinator, known_host, None
            return None, host, f"No Novastar device found at {host}"

        if len(coordinators) == 1:
            known_host, coordinator = coordinators[0]
            return coordinator, known_host, None

        if not coordinators:
            return None, None, "No Novastar devices are currently available"

        return (
            None,
            None,
            "Multiple Novastar devices configured; specify host for this service call",
        )

    # Register send_raw_command service if not already registered
    # Check is done at call time via options/data
    if not hass.services.has_service(DOMAIN, SERVICE_SEND_RAW_COMMAND):
        async def async_send_raw_command(call: ServiceCall) -> None:
            """Handle send_raw_command service call."""
            host = call.data.get(CONF_HOST)
            endpoint = call.data[ATTR_ENDPOINT]
            body = call.data[ATTR_BODY]

            coordinator_found, resolved_host, error_message = resolve_coordinator_by_host(
                host
            )

            if coordinator_found is None:
                _LOGGER.error(error_message)
                return

            client_found = None
            raw_enabled = False
            for eid, data in hass.data[DOMAIN].items():
                if not isinstance(data, dict) or "client" not in data:
                    continue
                client = data["client"]
                if client.host != resolved_host:
                    continue
                client_found = client

                config_entry = hass.config_entries.async_get_entry(eid)
                if config_entry:
                    raw_enabled = config_entry.options.get(
                        CONF_ALLOW_RAW_COMMANDS,
                        config_entry.data.get(
                            CONF_ALLOW_RAW_COMMANDS, DEFAULT_ALLOW_RAW_COMMANDS
                        ),
                    )
                break

            if not client_found:
                _LOGGER.error(
                    "No Novastar device found at %s", resolved_host
                )
                return

            if not raw_enabled:
                _LOGGER.error(
                    "Raw commands are not enabled for Novastar device at %s",
                    resolved_host,
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

    if not hass.services.has_service(DOMAIN, SERVICE_SET_LAYER_SOURCE):
        async def async_set_layer_source(call: ServiceCall) -> None:
            """Handle set_layer_source service call."""
            host = call.data.get(CONF_HOST)
            layer_id = call.data[ATTR_LAYER_ID]
            input_id = call.data.get(ATTR_INPUT_ID)
            interface_type = call.data[ATTR_INTERFACE_TYPE]
            slot_id = call.data[ATTR_SLOT_ID]
            crop_id = call.data[ATTR_CROP_ID]

            coordinator_found, resolved_host, error_message = resolve_coordinator_by_host(
                host
            )

            if coordinator_found is None:
                _LOGGER.error(error_message)
                return

            result = await coordinator_found.async_set_layer_source(
                layer_id=layer_id,
                input_id=input_id,
                interface_type=interface_type,
                slot_id=slot_id,
                crop_id=crop_id,
            )
            if not result:
                _LOGGER.warning(
                    "Failed to set layer source for host=%s layer_id=%s",
                    resolved_host,
                    layer_id,
                )

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_LAYER_SOURCE,
            async_set_layer_source,
            schema=SERVICE_SET_LAYER_SOURCE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_ACTIVE_PRESET):
        async def async_set_active_preset(call: ServiceCall) -> None:
            """Handle set_active_preset service call."""
            host = call.data.get(CONF_HOST)
            preset_id = call.data[ATTR_PRESET_ID]

            coordinator_found, resolved_host, error_message = resolve_coordinator_by_host(
                host
            )

            if coordinator_found is None:
                _LOGGER.error(error_message)
                return

            result = await coordinator_found.async_set_active_preset(preset_id)
            if not result:
                _LOGGER.warning(
                    "Failed to set active preset for host=%s preset_id=%s",
                    resolved_host,
                    preset_id,
                )

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_ACTIVE_PRESET,
            async_set_active_preset,
            schema=SERVICE_SET_ACTIVE_PRESET_SCHEMA,
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

        # Remove raw command service if no remaining entries allow it.
        has_raw_enabled_entry = False
        for eid in hass.data.get(DOMAIN, {}):
            config_entry = hass.config_entries.async_get_entry(eid)
            if not config_entry:
                continue
            allow_raw = config_entry.options.get(
                CONF_ALLOW_RAW_COMMANDS,
                config_entry.data.get(
                    CONF_ALLOW_RAW_COMMANDS, DEFAULT_ALLOW_RAW_COMMANDS
                ),
            )
            if allow_raw:
                has_raw_enabled_entry = True
                break

        if (
            not has_raw_enabled_entry
            and hass.services.has_service(DOMAIN, SERVICE_SEND_RAW_COMMAND)
        ):
            hass.services.async_remove(DOMAIN, SERVICE_SEND_RAW_COMMAND)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_SET_LAYER_SOURCE
        ):
            hass.services.async_remove(DOMAIN, SERVICE_SET_LAYER_SOURCE)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_SET_ACTIVE_PRESET
        ):
            hass.services.async_remove(DOMAIN, SERVICE_SET_ACTIVE_PRESET)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
