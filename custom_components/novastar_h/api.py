"""Novastar H Series API client implementation.

Based on official Novastar OpenAPI documentation:
https://openapi.novastar.tech/en/h/doc-7540897
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


@dataclass
class NovastarDeviceInfo:
    """Device information from Novastar H series processor."""

    device_id: int = 0
    model_id: int = 0
    name: str = ""
    serial: str = ""
    firmware: str = ""
    mac: str = ""
    status: int = 0  # 0: busy, 1: ready


@dataclass
class NovastarScreen:
    """Screen information."""

    screen_id: int = 0
    name: str = ""


@dataclass
class NovastarPreset:
    """Preset information."""

    preset_id: int = 0
    name: str = ""


@dataclass
class NovastarState:
    """State of Novastar H series processor."""

    device_id: int = 0
    screen_id: int = 0
    brightness: int = 100
    temperature: float | None = None  # Backboard temperature in Celsius
    temp_status: int | None = None  # Temperature status (0=normal, 1=warning, etc.)
    ftb_active: bool = False  # Fade to black (blackout) active
    freeze_active: bool = False  # Screen freeze active
    current_preset_id: int = -1  # -1 means no preset active
    screens: list[NovastarScreen] = field(default_factory=list)
    presets: list[NovastarPreset] = field(default_factory=list)


class NovastarClient:
    """HTTP API client for Novastar H series processor.

    Implements the Novastar OpenAPI specification using HTTP POST requests
    with signed JSON payloads.
    """

    def __init__(
        self,
        host: str,
        port: int = 8000,
        project_id: str = "",
        secret_key: str = "",
        encryption: bool = False,
        timeout: float = 10.0,
    ) -> None:
        """Initialize the client.

        Args:
            host: IP address of the Novastar processor
            port: HTTP port (default 8000 per Novastar spec)
            project_id: pId from device OpenAPI settings
            secret_key: secretKey from device OpenAPI settings
            encryption: Enable DES encryption for payloads
            timeout: Request timeout in seconds
        """
        self._host = host
        self._port = port
        self._project_id = project_id
        self._secret_key = secret_key
        self._encryption = encryption
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._base_url = f"http://{host}:{port}/open/api"

    @property
    def host(self) -> str:
        """Return the host."""
        return self._host

    def _get_timestamp(self) -> str:
        """Get current timestamp in milliseconds."""
        return str(int(time.time() * 1000))

    def _generate_signature(self, body_str: str, timestamp: str) -> str:
        """Generate request signature.

        Signing rules per Novastar spec:
        - Encryption enabled: Base64(md5(body_ciphertext + timestamp + pId + secretKey))
        - Encryption disabled: Base64(md5(timestamp + pId))

        MD5 is output in hexadecimal format.
        """
        if self._encryption:
            message = f"{body_str}{timestamp}{self._project_id}{self._secret_key}"
        else:
            message = f"{timestamp}{self._project_id}"

        md5_hash = hashlib.md5(message.encode("utf-8")).hexdigest()
        return base64.b64encode(md5_hash.encode("utf-8")).decode("utf-8")

    def _encrypt_body(self, body: dict[str, Any]) -> str | dict[str, Any]:
        """Encrypt body using DES ECB mode with PKCS5 padding.

        Returns Base64 encoded ciphertext when encryption is enabled,
        otherwise returns the body dict unchanged.
        """
        if not self._encryption:
            return body

        try:
            from pyDes import PAD_PKCS5, ECB, des

            key = self._secret_key[:8].encode("utf-8").ljust(8, b"\0")
            cipher = des(key, ECB, padmode=PAD_PKCS5)
            json_data = json.dumps(body).encode("utf-8")
            encrypted = cipher.encrypt(json_data)
            return base64.b64encode(encrypted).decode("utf-8")
        except ImportError:
            _LOGGER.warning("pyDes not installed, sending unencrypted")
            return body
        except Exception as ex:
            _LOGGER.error("Encryption failed: %s", ex)
            return body

    def _decrypt_body(self, encrypted_body: str) -> dict[str, Any]:
        """Decrypt body from Base64 DES ciphertext."""
        if not self._encryption or isinstance(encrypted_body, dict):
            return encrypted_body if isinstance(encrypted_body, dict) else {}

        try:
            from pyDes import PAD_PKCS5, ECB, des

            key = self._secret_key[:8].encode("utf-8").ljust(8, b"\0")
            cipher = des(key, ECB, padmode=PAD_PKCS5)
            encrypted = base64.b64decode(encrypted_body)
            decrypted = cipher.decrypt(encrypted)
            return json.loads(decrypted.decode("utf-8"))
        except ImportError:
            _LOGGER.warning("pyDes not installed, cannot decrypt")
            return {}
        except Exception as ex:
            _LOGGER.error("Decryption failed: %s", ex)
            return {}

    def _build_request(self, body: dict[str, Any]) -> dict[str, Any]:
        """Build a signed API request payload."""
        timestamp = self._get_timestamp()
        body_payload = self._encrypt_body(body)
        body_str = body_payload if isinstance(body_payload, str) else json.dumps(body)
        signature = self._generate_signature(body_str, timestamp)

        return {
            "body": body_payload,
            "sign": signature,
            "pId": self._project_id,
            "timeStamp": timestamp,
        }

    async def _async_request(
        self, endpoint: str, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Send POST request to Novastar API.

        Args:
            endpoint: API endpoint path (e.g., "device/readDetail")
            body: Business data for the request body

        Returns:
            Response body dict on success, None on failure
        """
        url = f"{self._base_url}/{endpoint}"
        request_data = self._build_request(body)

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(url, json=request_data) as response:
                    if response.status != 200:
                        _LOGGER.debug(
                            "Request to %s failed with status %s",
                            endpoint,
                            response.status,
                        )
                        return None

                    data = await response.json()

                    # Check API status
                    if data.get("status") != 0:
                        _LOGGER.debug(
                            "API error from %s: %s",
                            endpoint,
                            data.get("msg", "Unknown error"),
                        )
                        return None

                    # Handle response - might be in "body" or "data" depending on endpoint
                    body_data = data.get("body") or data.get("data") or {}
                    if self._encryption and isinstance(body_data, str):
                        return self._decrypt_body(body_data)
                    return body_data if isinstance(body_data, dict) else {}

        except aiohttp.ClientError as ex:
            _LOGGER.debug("Connection error to %s: %s", url, ex)
            return None
        except Exception as ex:
            _LOGGER.debug("Request to %s failed: %s", endpoint, ex, exc_info=True)
            return None

    async def async_can_connect(self) -> bool:
        """Test if we can connect to the device."""
        result = await self._async_request("device/readDetail", {"deviceId": 0})
        return result is not None

    async def async_get_device_info(self) -> NovastarDeviceInfo:
        """Get device information."""
        info = NovastarDeviceInfo()
        data = await self._async_request("device/readDetail", {"deviceId": 0})

        if data:
            info.device_id = data.get("deviceId", 0)
            info.model_id = data.get("modelId", 0)
            info.name = data.get("name", "")
            info.serial = data.get("sn", "")
            info.firmware = data.get("protoVersion", "")
            info.mac = data.get("MAC", "")
            info.status = data.get("status", 0)

        return info

    async def async_get_screens(self, device_id: int = 0) -> list[NovastarScreen]:
        """Get list of screens."""
        data = await self._async_request("screen/readList", {"deviceId": device_id})

        screens = []
        if data and "screens" in data:
            for screen in data["screens"]:
                screens.append(
                    NovastarScreen(
                        screen_id=screen.get("screenId", 0),
                        name=screen.get("name", ""),
                    )
                )
        return screens

    async def async_get_presets(
        self, screen_id: int = 0, device_id: int = 0
    ) -> list[NovastarPreset]:
        """Get list of presets for a screen."""
        data = await self._async_request(
            "preset/readList",
            {"screenId": screen_id, "deviceId": device_id},
        )

        presets = []
        if data and "presets" in data:
            for preset in data["presets"]:
                presets.append(
                    NovastarPreset(
                        preset_id=preset.get("presetId", 0),
                        name=preset.get("name", ""),
                    )
                )
        return presets

    async def async_get_current_preset(
        self, screen_id: int = 0, device_id: int = 0
    ) -> int:
        """Get currently active preset ID. Returns -1 if no preset active."""
        data = await self._async_request(
            "preset/readPlay",
            {"screenId": screen_id, "deviceId": device_id},
        )

        if data:
            return data.get("presetId", -1)
        return -1

    async def async_load_preset(
        self, preset_id: int, screen_id: int = 0, device_id: int = 0
    ) -> bool:
        """Load/activate a preset."""
        data = await self._async_request(
            "preset/play",
            {"presetId": preset_id, "screenId": screen_id, "deviceId": device_id},
        )
        return data is not None

    async def async_set_brightness(
        self, brightness: int, screen_id: int = 0, device_id: int = 0
    ) -> bool:
        """Set screen brightness (0-100)."""
        brightness = max(0, min(100, brightness))
        data = await self._async_request(
            "screen/writeBrightness",
            {"brightness": brightness, "screenId": screen_id, "deviceId": device_id},
        )
        return data is not None

    async def async_get_brightness(
        self, screen_id: int = 0, device_id: int = 0
    ) -> int:
        """Get current screen brightness (0-100)."""
        data = await self._async_request(
            "screen/readDetail",
            {"screenId": screen_id, "deviceId": device_id},
        )
        if data and isinstance(data, dict):
            return data.get("brightness", 100)
        return 100

    async def async_set_ftb(
        self,
        blackout: bool,
        transition_time: int = 0,
        screen_id: int = 0,
        device_id: int = 0,
    ) -> bool:
        """Set Fade to Black (FTB) state.

        Args:
            blackout: True for blackout, False for screen on
            transition_time: Transition duration in seconds
            screen_id: Screen ID
            device_id: Device ID
        """
        data = await self._async_request(
            "screen/ftb",
            {
                "type": 0 if blackout else 1,  # 0: Blackout, 1: Screen on
                "time": transition_time,
                "screenId": screen_id,
                "deviceId": device_id,
            },
        )
        return data is not None

    async def async_set_freeze(
        self,
        freeze: bool,
        screen_id: int = 0,
        device_id: int = 0,
    ) -> bool:
        """Set screen freeze state.

        Args:
            freeze: True to freeze screen, False to unfreeze
            screen_id: Screen ID
            device_id: Device ID
        """
        data = await self._async_request(
            "screen/writeFreeze",
            {
                "enable": 1 if freeze else 0,  # 1: Freeze, 0: Unfreeze
                "screenId": screen_id,
                "deviceId": device_id,
            },
        )
        return data is not None

    async def async_get_state(
        self, screen_id: int = 0, device_id: int = 0
    ) -> NovastarState:
        """Get comprehensive device state."""
        state = NovastarState(device_id=device_id, screen_id=screen_id)

        # Get screens
        state.screens = await self.async_get_screens(device_id)

        # Get presets for the specified screen
        state.presets = await self.async_get_presets(screen_id, device_id)

        # Get current preset
        state.current_preset_id = await self.async_get_current_preset(
            screen_id, device_id
        )

        # Get brightness
        state.brightness = await self.async_get_brightness(screen_id, device_id)

        # Get temperature info from device
        temp_data = await self.async_get_temperature_info(device_id)
        state.temperature = temp_data.get("temperature")
        state.temp_status = temp_data.get("temp_status")

        return state

    async def async_get_temperature_info(
        self, device_id: int = 0
    ) -> dict[str, float | int | None]:
        """Get device temperature info.

        Returns dict with:
        - temperature: Backboard temperature in Celsius
        - temp_status: Temperature status code
        """
        data = await self._async_request("device/readDetail", {"deviceId": device_id})
        result: dict[str, float | int | None] = {
            "temperature": None,
            "temp_status": None,
        }
        if data and isinstance(data, dict):
            temp = data.get("backboardTemperature")
            if temp is not None:
                result["temperature"] = float(temp)
            temp_status = data.get("temp")
            if temp_status is not None:
                result["temp_status"] = int(temp_status)
        return result

    async def async_get_temperature(self, device_id: int = 0) -> float | None:
        """Get device backboard temperature in Celsius."""
        info = await self.async_get_temperature_info(device_id)
        return info.get("temperature")
