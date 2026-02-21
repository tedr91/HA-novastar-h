from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant.components import ssdp, zeroconf
from homeassistant.config_entries import ConfigFlow, FlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .api import NovastarClient
from .const import (
    CONF_ENCRYPTION,
    CONF_PROJECT_ID,
    CONF_SECRET_KEY,
    DEFAULT_ENCRYPTION,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class NovastarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Novastar H Series."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_port: int = DEFAULT_PORT
        self._discovered_name: str = DEFAULT_NAME

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - redirect to discovery."""
        return self.async_abort(reason="discovery_only")

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> FlowResult:
        """Handle SSDP discovery."""
        _LOGGER.debug("SSDP discovery: %s", discovery_info)

        # Extract host from SSDP location URL
        location = discovery_info.ssdp_location
        if location:
            parsed = urlparse(location)
            self._discovered_host = parsed.hostname
            self._discovered_port = DEFAULT_PORT  # Novastar API uses port 8000
        else:
            return self.async_abort(reason="no_host")

        # Try to get friendly name from SSDP data
        self._discovered_name = (
            discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME)
            or DEFAULT_NAME
        )

        # Set unique ID based on host (serial requires authentication)
        unique_id = f"novastar_h_{self._discovered_host}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._discovered_host}
        )

        # Show discovery in UI - credentials will be validated in confirm step
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_discovery_confirm()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle Zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)

        self._discovered_host = str(discovery_info.host)
        self._discovered_port = DEFAULT_PORT  # Novastar API uses port 8000
        self._discovered_name = discovery_info.name.removesuffix("._novastar._tcp.local.")

        # Set unique ID based on host (serial requires authentication)
        unique_id = f"novastar_h_{self._discovered_host}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._discovered_host}
        )

        # Show discovery in UI - credentials will be validated in confirm step
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user confirmation of discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME, self._discovered_name)
            project_id = user_input[CONF_PROJECT_ID]
            secret_key = user_input[CONF_SECRET_KEY]
            encryption = user_input.get(CONF_ENCRYPTION, DEFAULT_ENCRYPTION)

            # Validate credentials by testing connection
            client = NovastarClient(
                host=self._discovered_host,
                port=self._discovered_port,
                project_id=project_id,
                secret_key=secret_key,
                encryption=encryption,
            )
            if await client.async_can_connect():
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: self._discovered_host,
                        CONF_PORT: self._discovered_port,
                        CONF_NAME: name,
                        CONF_PROJECT_ID: project_id,
                        CONF_SECRET_KEY: secret_key,
                        CONF_ENCRYPTION: encryption,
                    },
                )
            errors["base"] = "cannot_connect"

        placeholders = {
            "name": self._discovered_name,
            "host": self._discovered_host,
        }

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=placeholders,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROJECT_ID): str,
                    vol.Required(CONF_SECRET_KEY): str,
                    vol.Optional(CONF_ENCRYPTION, default=DEFAULT_ENCRYPTION): bool,
                    vol.Optional(CONF_NAME, default=self._discovered_name): str,
                }
            ),
            errors=errors,
        )
