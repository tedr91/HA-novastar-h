from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
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
SERVICE_GET_SCREEN_DETAILS = "get_screen_details"
SERVICE_GET_INPUT_DETAILS = "get_input_details"
SERVICE_GET_OUTPUT_DETAILS = "get_output_details"
SERVICE_GET_LAYER_DETAILS = "get_layer_details"
SERVICE_GET_PRESET_DETAILS = "get_preset_details"
SERVICE_GET_SCREENS = "get_screens"
SERVICE_GET_INPUTS = "get_inputs"
SERVICE_GET_OUTPUTS = "get_outputs"
SERVICE_GET_LAYERS = "get_layers"
SERVICE_GET_PRESETS = "get_presets"
ATTR_ENDPOINT = "endpoint"
ATTR_BODY = "body"
ATTR_LAYER_ID = "layer_id"
ATTR_INPUT_ID = "input_id"
ATTR_OUTPUT_ID = "output_id"
ATTR_INTERFACE_TYPE = "interface_type"
ATTR_SLOT_ID = "slot_id"
ATTR_CROP_ID = "crop_id"
ATTR_PRESET_ID = "preset_id"

SERVICE_SEND_RAW_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(ATTR_ENDPOINT): cv.string,
        vol.Optional(ATTR_BODY, default=dict): dict,
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

SERVICE_GET_SCREEN_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
        vol.Optional(CONF_SCREEN_ID, default=DEFAULT_SCREEN_ID): vol.Coerce(int),
    }
)

SERVICE_GET_INPUT_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(ATTR_INPUT_ID): vol.Coerce(int),
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
    }
)

SERVICE_GET_OUTPUT_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(ATTR_OUTPUT_ID): vol.Coerce(int),
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
    }
)

SERVICE_GET_LAYER_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Required(ATTR_LAYER_ID): vol.Coerce(int),
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
        vol.Optional(CONF_SCREEN_ID, default=DEFAULT_SCREEN_ID): vol.Coerce(int),
    }
)

SERVICE_GET_PRESET_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(ATTR_PRESET_ID): vol.Coerce(int),
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
        vol.Optional(CONF_SCREEN_ID, default=DEFAULT_SCREEN_ID): vol.Coerce(int),
    }
)

SERVICE_GET_SCREENS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
    }
)

SERVICE_GET_INPUTS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
    }
)

SERVICE_GET_OUTPUTS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
    }
)

SERVICE_GET_LAYERS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
        vol.Optional(CONF_SCREEN_ID, default=DEFAULT_SCREEN_ID): vol.Coerce(int),
    }
)

SERVICE_GET_PRESETS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.Coerce(int),
        vol.Optional(CONF_SCREEN_ID, default=DEFAULT_SCREEN_ID): vol.Coerce(int),
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

    # Always refresh send_raw_command registration so schema changes apply.
    if hass.services.has_service(DOMAIN, SERVICE_SEND_RAW_COMMAND):
        hass.services.async_remove(DOMAIN, SERVICE_SEND_RAW_COMMAND)

    async def async_send_raw_command(call: ServiceCall) -> dict[str, Any]:
        """Handle send_raw_command service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None

        endpoint = call.data[ATTR_ENDPOINT]
        body = call.data.get(ATTR_BODY, {})
        effective_body = dict(body)
        effective_body.setdefault("deviceId", 0)
        effective_body.setdefault("screenId", 0)

        coordinator_found, resolved_host, error_message = resolve_coordinator_by_host(
            host
        )

        if coordinator_found is None:
            _LOGGER.error(error_message)
            return {"ok": False, "error": error_message}

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
            return {"ok": False, "error": f"No Novastar device found at {resolved_host}"}

        if not raw_enabled:
            _LOGGER.error(
                "Raw commands are not enabled for Novastar device at %s",
                resolved_host,
            )
            return {
                "ok": False,
                "error": f"Raw commands are not enabled for Novastar device at {resolved_host}",
            }

# TEMPORARY DEBUG LOGGING - can be removed in future releases
        _LOGGER.warning(
            "Sending POST request to Novastar API url=%s body=%s",
            endpoint,
            effective_body
        )

        result = await client_found.async_send_raw_command(endpoint, effective_body)
        if result is None:
            _LOGGER.warning("Raw command to %s failed", endpoint)
            return {
                "ok": False,
                "host": resolved_host,
                "endpoint": endpoint,
                "request_body": effective_body,
                "response": None,
            }
        else:
            _LOGGER.debug("Raw command result: %s", result)
            return {
                "ok": True,
                "host": resolved_host,
                "endpoint": endpoint,
                "request_body": effective_body,
                "response": result,
            }

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_RAW_COMMAND,
        async_send_raw_command,
        schema=SERVICE_SEND_RAW_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_SET_LAYER_SOURCE):
        hass.services.async_remove(DOMAIN, SERVICE_SET_LAYER_SOURCE)

    async def async_set_layer_source(call: ServiceCall) -> dict[str, Any]:
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
            return {"ok": False, "error": error_message}

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

        return {
            "ok": bool(result),
            "host": resolved_host,
            "layer_id": layer_id,
            "input_id": input_id,
            "interface_type": interface_type,
            "slot_id": slot_id,
            "crop_id": crop_id,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LAYER_SOURCE,
        async_set_layer_source,
        schema=SERVICE_SET_LAYER_SOURCE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_SET_ACTIVE_PRESET):
        hass.services.async_remove(DOMAIN, SERVICE_SET_ACTIVE_PRESET)

    async def async_set_active_preset(call: ServiceCall) -> dict[str, Any]:
        """Handle set_active_preset service call."""
        host = call.data.get(CONF_HOST)
        preset_id = call.data[ATTR_PRESET_ID]

        coordinator_found, resolved_host, error_message = resolve_coordinator_by_host(
            host
        )

        if coordinator_found is None:
            _LOGGER.error(error_message)
            return {"ok": False, "error": error_message}

        result = await coordinator_found.async_set_active_preset(preset_id)
        if not result:
            _LOGGER.warning(
                "Failed to set active preset for host=%s preset_id=%s",
                resolved_host,
                preset_id,
            )

        return {
            "ok": bool(result),
            "host": resolved_host,
            "preset_id": preset_id,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_PRESET,
        async_set_active_preset,
        schema=SERVICE_SET_ACTIVE_PRESET_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def async_read_detail(
        host: str | None,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Read detail from one endpoint and return structured service response."""
        coordinator_found, resolved_host, error_message = resolve_coordinator_by_host(
            host
        )
        if coordinator_found is None:
            _LOGGER.error(error_message)
            return {"ok": False, "error": error_message}

        result = await coordinator_found.client.async_send_raw_command(endpoint, payload)
        if result is None:
            _LOGGER.warning("Read detail failed host=%s endpoint=%s", resolved_host, endpoint)
            return {
                "ok": False,
                "host": resolved_host,
                "endpoint": endpoint,
                "request_body": payload,
                "response": None,
            }

        return {
            "ok": True,
            "host": resolved_host,
            "endpoint": endpoint,
            "request_body": payload,
            "response": result,
        }

    if hass.services.has_service(DOMAIN, SERVICE_GET_SCREEN_DETAILS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_SCREEN_DETAILS)

    async def async_get_screen_details(call: ServiceCall) -> dict[str, Any]:
        """Handle get_screen_details service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None
        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
            "screenId": call.data[CONF_SCREEN_ID],
        }
        return await async_read_detail(host, "screen/readDetail", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SCREEN_DETAILS,
        async_get_screen_details,
        schema=SERVICE_GET_SCREEN_DETAILS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_INPUT_DETAILS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_INPUT_DETAILS)

    async def async_get_input_details(call: ServiceCall) -> dict[str, Any]:
        """Handle get_input_details service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None
        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
            "inputId": call.data[ATTR_INPUT_ID],
        }
        return await async_read_detail(host, "input/readDetail", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_INPUT_DETAILS,
        async_get_input_details,
        schema=SERVICE_GET_INPUT_DETAILS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_OUTPUT_DETAILS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_OUTPUT_DETAILS)

    async def async_get_output_details(call: ServiceCall) -> dict[str, Any]:
        """Handle get_output_details service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None

        coordinator_found, _resolved_host, error_message = resolve_coordinator_by_host(
            host
        )
        if coordinator_found is None:
            _LOGGER.error(error_message)
            return {"ok": False, "error": error_message}

        output_id = call.data.get(ATTR_OUTPUT_ID)
        if output_id is None:
            active_output_id: int | None = None
            if coordinator_found.data and coordinator_found.data.audio_output_id is not None:
                active_output_id = int(coordinator_found.data.audio_output_id)
            else:
                screen_detail = await coordinator_found.client.async_send_raw_command(
                    "screen/readDetail",
                    {
                        "deviceId": int(call.data[CONF_DEVICE_ID]),
                        "screenId": int(coordinator_found.screen_id),
                    },
                )
                if isinstance(screen_detail, dict):
                    audio_data = screen_detail.get("audio")
                    if isinstance(audio_data, dict):
                        for key in ("outputChannelMode", "outputId", "audioOutputId"):
                            candidate = audio_data.get(key)
                            if isinstance(candidate, int):
                                active_output_id = int(candidate)
                                break

            if active_output_id is None:
                return {
                    "ok": False,
                    "error": "output_id not provided and no active output is currently available",
                }
            output_id = active_output_id

        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
            "outputId": int(output_id),
        }
        return await async_read_detail(host, "output/readDetail", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_OUTPUT_DETAILS,
        async_get_output_details,
        schema=SERVICE_GET_OUTPUT_DETAILS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_LAYER_DETAILS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_LAYER_DETAILS)

    async def async_get_layer_details(call: ServiceCall) -> dict[str, Any]:
        """Handle get_layer_details service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None
        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
            "screenId": call.data[CONF_SCREEN_ID],
            "layerId": call.data[ATTR_LAYER_ID],
        }
        return await async_read_detail(host, "layer/readDetail", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LAYER_DETAILS,
        async_get_layer_details,
        schema=SERVICE_GET_LAYER_DETAILS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_PRESET_DETAILS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_PRESET_DETAILS)

    async def async_get_preset_details(call: ServiceCall) -> dict[str, Any]:
        """Handle get_preset_details service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None

        coordinator_found, _resolved_host, error_message = resolve_coordinator_by_host(
            host
        )
        if coordinator_found is None:
            _LOGGER.error(error_message)
            return {"ok": False, "error": error_message}

        preset_id = call.data.get(ATTR_PRESET_ID)
        if preset_id is None:
            active_preset_id: int | None = None
            if coordinator_found.data and coordinator_found.data.current_preset_id >= 0:
                active_preset_id = int(coordinator_found.data.current_preset_id)
            else:
                active_candidate = await coordinator_found.client.async_get_current_preset(
                    screen_id=int(call.data[CONF_SCREEN_ID]),
                    device_id=int(call.data[CONF_DEVICE_ID]),
                )
                if isinstance(active_candidate, int) and active_candidate >= 0:
                    active_preset_id = int(active_candidate)

            if active_preset_id is None:
                return {
                    "ok": False,
                    "error": "preset_id not provided and no active preset is currently available",
                }
            preset_id = active_preset_id

        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
            "screenId": call.data[CONF_SCREEN_ID],
            "presetId": int(preset_id),
        }
        return await async_read_detail(host, "preset/readDetail", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRESET_DETAILS,
        async_get_preset_details,
        schema=SERVICE_GET_PRESET_DETAILS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_SCREENS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_SCREENS)

    async def async_get_screens(call: ServiceCall) -> dict[str, Any]:
        """Handle get_screens service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None
        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
        }
        return await async_read_detail(host, "screen/readList", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SCREENS,
        async_get_screens,
        schema=SERVICE_GET_SCREENS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_INPUTS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_INPUTS)

    async def async_get_inputs(call: ServiceCall) -> dict[str, Any]:
        """Handle get_inputs service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None
        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
        }
        return await async_read_detail(host, "input/readList", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_INPUTS,
        async_get_inputs,
        schema=SERVICE_GET_INPUTS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_OUTPUTS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_OUTPUTS)

    async def async_get_outputs(call: ServiceCall) -> dict[str, Any]:
        """Handle get_outputs service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None
        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
        }
        return await async_read_detail(host, "output/readList", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_OUTPUTS,
        async_get_outputs,
        schema=SERVICE_GET_OUTPUTS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_LAYERS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_LAYERS)

    async def async_get_layers(call: ServiceCall) -> dict[str, Any]:
        """Handle get_layers service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None
        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
            "screenId": call.data[CONF_SCREEN_ID],
        }
        return await async_read_detail(host, "layer/detailList", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LAYERS,
        async_get_layers,
        schema=SERVICE_GET_LAYERS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    if hass.services.has_service(DOMAIN, SERVICE_GET_PRESETS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_PRESETS)

    async def async_get_presets(call: ServiceCall) -> dict[str, Any]:
        """Handle get_presets service call."""
        host = call.data.get(CONF_HOST)
        if isinstance(host, str):
            host = host.strip() or None
        payload = {
            "deviceId": call.data[CONF_DEVICE_ID],
            "screenId": call.data[CONF_SCREEN_ID],
        }
        return await async_read_detail(host, "preset/readList", payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRESETS,
        async_get_presets,
        schema=SERVICE_GET_PRESETS_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
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

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_SCREEN_DETAILS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_SCREEN_DETAILS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_INPUT_DETAILS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_INPUT_DETAILS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_OUTPUT_DETAILS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_OUTPUT_DETAILS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_LAYER_DETAILS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_LAYER_DETAILS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_PRESET_DETAILS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_PRESET_DETAILS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_SCREENS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_SCREENS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_INPUTS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_INPUTS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_OUTPUTS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_OUTPUTS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_LAYERS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_LAYERS)

        if not hass.data.get(DOMAIN) and hass.services.has_service(
            DOMAIN, SERVICE_GET_PRESETS
        ):
            hass.services.async_remove(DOMAIN, SERVICE_GET_PRESETS)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
