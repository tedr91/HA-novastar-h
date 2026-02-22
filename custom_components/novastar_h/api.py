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
    temp_status: int | None = None  # Temperature status (0=normal, 1=warning, etc.)
    device_status: int | None = None  # Device status (0=busy, 1=ready)
    signal_status: int | None = None  # Signal power status from iSignal
    ftb_active: bool = False  # Fade to black (blackout) active
    freeze_active: bool = False  # Screen freeze active
    current_preset_id: int = -1  # -1 means no preset active
    background_enabled: bool = False
    background_id: int = 0
    screens: list[NovastarScreen] = field(default_factory=list)
    presets: list[NovastarPreset] = field(default_factory=list)
    inputs: list[dict[str, Any]] = field(default_factory=list)
    layers: list[dict[str, Any]] = field(default_factory=list)
    backgrounds: list[dict[str, Any]] = field(default_factory=list)
    audio_inputs: list[dict[str, Any]] = field(default_factory=list)
    audio_outputs: list[dict[str, Any]] = field(default_factory=list)
    audio_input_id: int | None = None
    audio_output_id: int | None = None
    audio_volume: int | None = None
    audio_muted: bool | None = None


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
        self._input_detail_cache: dict[int, dict[str, Any]] = {}
        self._input_signature_cache: dict[int, str] = {}
        self._input_refresh_counter = 0
        self._layer_detail_cache: dict[int, dict[str, Any]] = {}
        self._layer_signature_cache: dict[int, str] = {}
        self._layer_refresh_counter = 0
        self._last_preset_id: int | None = None
        self._force_refresh_input_details = False
        self._force_refresh_layer_details = False
        self._background_list_cache: list[dict[str, Any]] = []
        self._background_refresh_counter = 0
        self._force_refresh_backgrounds = False

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
    ) -> Any | None:
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
                    if isinstance(body_data, (dict, list)):
                        return body_data
                    return {}

        except aiohttp.ClientError as ex:
            _LOGGER.debug("Connection error to %s: %s", url, ex)
            return None
        except Exception as ex:
            _LOGGER.debug("Request to %s failed: %s", endpoint, ex, exc_info=True)
            return None

    async def _async_request_first_success(
        self,
        candidates: list[tuple[str, dict[str, Any]]],
    ) -> Any | None:
        """Try multiple endpoint/payload candidates and return first successful response."""
        for endpoint, payload in candidates:
            result = await self._async_request(endpoint, payload)
            if result is not None:
                return result
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

        # If preset changed, force detail refresh for dependent structures
        if (
            self._last_preset_id is not None
            and state.current_preset_id != self._last_preset_id
        ):
            self._force_refresh_input_details = True
            self._force_refresh_layer_details = True
        self._last_preset_id = state.current_preset_id

        # Get brightness
        state.brightness = await self.async_get_brightness(screen_id, device_id)

        # Get temperature info from device
        temp_data = await self.async_get_device_status_info(device_id)
        state.temp_status = temp_data.get("temp_status")
        state.device_status = temp_data.get("device_status")
        state.signal_status = temp_data.get("signal_status")
        state.inputs = await self.async_get_inputs_with_details(device_id)
        state.layers = await self.async_get_layers_with_details(device_id, screen_id)
        state.backgrounds = await self.async_get_background_list(device_id)
        audio_state = await self.async_get_audio_state(screen_id, device_id)
        state.audio_inputs = audio_state.get("inputs", [])
        state.audio_outputs = audio_state.get("outputs", [])
        state.audio_input_id = audio_state.get("input_id")
        state.audio_output_id = audio_state.get("output_id")
        state.audio_volume = audio_state.get("volume")
        state.audio_muted = audio_state.get("muted")

        return state

    def _audio_option_label(self, option_data: dict[str, Any], fallback_prefix: str) -> str:
        """Build a stable label for audio input/output options."""
        name = option_data.get("name") or option_data.get("defaultName")
        if isinstance(name, str) and name.strip():
            return name.strip()

        option_id = option_data.get("id")
        if isinstance(option_id, int):
            return f"{fallback_prefix} {option_id}"
        return fallback_prefix

    def _normalize_audio_options(
        self,
        raw_items: list[Any],
        id_keys: tuple[str, ...],
        fallback_prefix: str,
    ) -> list[dict[str, Any]]:
        """Normalize raw list payloads into id/name objects."""
        normalized: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue

            option_id: int | None = None
            for key in id_keys:
                value = item.get(key)
                if isinstance(value, int):
                    option_id = value
                    break

            if option_id is None:
                continue

            normalized_item = {
                "id": option_id,
                "name": self._audio_option_label(item, fallback_prefix),
            }
            normalized.append(normalized_item)

        normalized.sort(key=lambda entry: entry["id"])
        return normalized

    def _extract_audio_options_from_container(
        self,
        container: dict[str, Any],
        input_keys: tuple[str, ...],
        output_keys: tuple[str, ...],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract normalized audio input/output options from a container dict."""
        normalized_inputs: list[dict[str, Any]] = []
        normalized_outputs: list[dict[str, Any]] = []

        for key in input_keys:
            raw_inputs = container.get(key)
            if isinstance(raw_inputs, list):
                normalized_inputs = self._normalize_audio_options(
                    raw_inputs,
                    ("audioInputId", "inputId", "inputChannelMode", "id"),
                    "Audio Input",
                )
                if normalized_inputs:
                    break

        for key in output_keys:
            raw_outputs = container.get(key)
            if isinstance(raw_outputs, list):
                normalized_outputs = self._normalize_audio_options(
                    raw_outputs,
                    (
                        "audioOutputId",
                        "outputId",
                        "outputChannelMode",
                        "id",
                    ),
                    "Audio Output",
                )
                if normalized_outputs:
                    break

        return normalized_inputs, normalized_outputs

    def _coerce_audio_id(self, value: Any) -> int | None:
        """Convert supported values to integer audio id."""
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    async def async_get_audio_state(
        self,
        screen_id: int = 0,
        device_id: int = 0,
    ) -> dict[str, Any]:
        """Get audio routes and level with endpoint fallbacks."""
        payload = {"screenId": screen_id, "deviceId": device_id}
        screen_detail_data = await self._async_request("screen/readDetail", payload)
        detail_data = await self._async_request_first_success(
            [
                ("audio/readDetail", payload),
                ("screen/readAudio", payload),
                ("audio/read", payload),
            ]
        )

        list_data = await self._async_request_first_success(
            [
                ("audio/readList", payload),
                ("audio/readAllList", {"deviceId": device_id}),
                ("screen/readAudioList", payload),
            ]
        )

        result: dict[str, Any] = {
            "inputs": [],
            "outputs": [],
            "input_id": None,
            "output_id": None,
            "volume": None,
            "muted": None,
        }

        if isinstance(list_data, dict):
            normalized_inputs, normalized_outputs = self._extract_audio_options_from_container(
                list_data,
                ("inputs", "audioInputs", "inputList"),
                ("outputs", "audioOutputs", "outputList"),
            )
            if normalized_inputs:
                result["inputs"] = normalized_inputs
            if normalized_outputs:
                result["outputs"] = normalized_outputs

        if isinstance(detail_data, dict):
            result["input_id"] = self._coerce_audio_id(
                detail_data.get(
                    "audioInputId",
                    detail_data.get("inputId", detail_data.get("inputChannelMode")),
                )
            )
            result["output_id"] = self._coerce_audio_id(
                detail_data.get(
                    "audioOutputId",
                    detail_data.get("outputId", detail_data.get("outputChannelMode")),
                )
            )

            volume = detail_data.get("volume", detail_data.get("outputVolume"))
            if isinstance(volume, (int, float)):
                result["volume"] = max(0, min(100, int(volume)))

            muted = detail_data.get("mute", detail_data.get("muted"))
            if isinstance(muted, bool):
                result["muted"] = muted
            elif isinstance(muted, (int, float)):
                result["muted"] = bool(int(muted))

            if not result["inputs"] or not result["outputs"]:
                normalized_inputs, normalized_outputs = self._extract_audio_options_from_container(
                    detail_data,
                    ("inputs", "audioInputs", "inputList"),
                    ("outputs", "audioOutputs", "outputList"),
                )
                if normalized_inputs and not result["inputs"]:
                    result["inputs"] = normalized_inputs
                if normalized_outputs and not result["outputs"]:
                    result["outputs"] = normalized_outputs

        if isinstance(screen_detail_data, dict):
            audio_data = screen_detail_data.get("audio")
            if isinstance(audio_data, dict):
                input_channel_mode = self._coerce_audio_id(
                    audio_data.get("inputChannelMode")
                )
                if input_channel_mode is not None:
                    result["input_id"] = input_channel_mode

                output_channel_mode = self._coerce_audio_id(
                    audio_data.get("outputChannelMode")
                )
                if output_channel_mode is not None:
                    result["output_id"] = output_channel_mode

                audio_volume = audio_data.get("volume", audio_data.get("outputVolume"))
                if isinstance(audio_volume, (int, float)):
                    result["volume"] = max(0, min(100, int(audio_volume)))

                audio_muted = audio_data.get("mute", audio_data.get("muted"))
                if isinstance(audio_muted, bool):
                    result["muted"] = audio_muted
                elif isinstance(audio_muted, (int, float)):
                    result["muted"] = bool(int(audio_muted))

                normalized_inputs, normalized_outputs = self._extract_audio_options_from_container(
                    audio_data,
                    ("inputs", "audioInputs", "inputList"),
                    ("outputs", "audioOutputs", "outputList"),
                )
                if normalized_inputs:
                    result["inputs"] = normalized_inputs
                if normalized_outputs:
                    result["outputs"] = normalized_outputs

        return result

    async def async_set_audio_input(
        self,
        input_id: int,
        screen_id: int = 0,
        device_id: int = 0,
    ) -> bool:
        """Set active audio input with endpoint fallbacks."""
        payload_base = {
            "screenId": int(screen_id),
            "deviceId": int(device_id),
        }
        screen_detail_data = await self._async_request("screen/readDetail", payload_base)
        merged_audio_payload: dict[str, Any] | None = None
        if isinstance(screen_detail_data, dict):
            audio_data = screen_detail_data.get("audio")
            if isinstance(audio_data, dict):
                merged_audio_payload = dict(audio_data)
                merged_audio_payload["inputChannelMode"] = int(input_id)

        candidates = [
            (
                "screen/writeDetail",
                {
                    **payload_base,
                    "audio": merged_audio_payload,
                },
            )
            if merged_audio_payload is not None
            else None,
            ("audio/writeInput", {**payload_base, "audioInputId": int(input_id)}),
            ("audio/writeInput", {**payload_base, "inputId": int(input_id)}),
            (
                "audio/writeInput",
                {**payload_base, "inputChannelMode": int(input_id)},
            ),
            ("screen/writeAudioInput", {**payload_base, "inputId": int(input_id)}),
            (
                "screen/writeAudioInput",
                {**payload_base, "inputChannelMode": int(input_id)},
            ),
            (
                "screen/writeDetail",
                {
                    **payload_base,
                    "audio": {
                        "inputChannelMode": int(input_id),
                    },
                },
            ),
            ("audio/write", {**payload_base, "audioInputId": int(input_id)}),
        ]
        valid_candidates = [c for c in candidates if c is not None]
        result = await self._async_request_first_success(valid_candidates)
        return result is not None

    async def async_set_audio_output(
        self,
        output_id: int,
        screen_id: int = 0,
        device_id: int = 0,
    ) -> bool:
        """Set active audio output with endpoint fallbacks."""
        payload_base = {
            "screenId": int(screen_id),
            "deviceId": int(device_id),
        }
        screen_detail_data = await self._async_request("screen/readDetail", payload_base)
        merged_audio_payload: dict[str, Any] | None = None
        if isinstance(screen_detail_data, dict):
            audio_data = screen_detail_data.get("audio")
            if isinstance(audio_data, dict):
                merged_audio_payload = dict(audio_data)
                merged_audio_payload["outputChannelMode"] = int(output_id)

        candidates = [
            (
                "screen/writeDetail",
                {
                    **payload_base,
                    "audio": merged_audio_payload,
                },
            )
            if merged_audio_payload is not None
            else None,
            ("audio/writeOutput", {**payload_base, "audioOutputId": int(output_id)}),
            ("audio/writeOutput", {**payload_base, "outputId": int(output_id)}),
            (
                "audio/writeOutput",
                {**payload_base, "outputChannelMode": int(output_id)},
            ),
            ("screen/writeAudioOutput", {**payload_base, "outputId": int(output_id)}),
            (
                "screen/writeAudioOutput",
                {**payload_base, "outputChannelMode": int(output_id)},
            ),
            (
                "screen/writeDetail",
                {
                    **payload_base,
                    "audio": {
                        "outputChannelMode": int(output_id),
                    },
                },
            ),
            ("audio/write", {**payload_base, "audioOutputId": int(output_id)}),
        ]
        valid_candidates = [c for c in candidates if c is not None]
        result = await self._async_request_first_success(valid_candidates)
        return result is not None

    async def async_set_audio_volume(
        self,
        volume: int,
        screen_id: int = 0,
        device_id: int = 0,
    ) -> bool:
        """Set audio volume with endpoint fallbacks."""
        clamped_volume = max(0, min(100, int(volume)))
        payload_base = {
            "screenId": int(screen_id),
            "deviceId": int(device_id),
        }
        screen_detail_data = await self._async_request("screen/readDetail", payload_base)
        merged_audio_payload: dict[str, Any] | None = None
        if isinstance(screen_detail_data, dict):
            audio_data = screen_detail_data.get("audio")
            if isinstance(audio_data, dict):
                merged_audio_payload = dict(audio_data)
                merged_audio_payload["volume"] = clamped_volume
                merged_audio_payload["outputVolume"] = clamped_volume

        candidates = [
            (
                "screen/writeDetail",
                {
                    **payload_base,
                    "audio": merged_audio_payload,
                },
            )
            if merged_audio_payload is not None
            else None,
            ("audio/writeVolume", {**payload_base, "volume": clamped_volume}),
            ("screen/writeVolume", {**payload_base, "volume": clamped_volume}),
            (
                "screen/writeDetail",
                {
                    **payload_base,
                    "audio": {
                        "volume": clamped_volume,
                        "outputVolume": clamped_volume,
                    },
                },
            ),
            ("audio/write", {**payload_base, "volume": clamped_volume}),
        ]
        valid_candidates = [c for c in candidates if c is not None]
        result = await self._async_request_first_success(valid_candidates)
        return result is not None

    async def async_get_background_list(
        self, device_id: int = 0
    ) -> list[dict[str, Any]]:
        """Get available backgrounds from bkg/readAllList with lightweight caching."""
        self._background_refresh_counter += 1
        periodic_refresh = self._background_refresh_counter % 12 == 0
        should_refresh = periodic_refresh or self._force_refresh_backgrounds

        if not self._background_list_cache or should_refresh:
            self._force_refresh_backgrounds = False
            data = await self._async_request("bkg/readAllList", {"deviceId": device_id})
            if isinstance(data, list):
                parsed: list[dict[str, Any]] = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    bkg_id = item.get("bkgId")
                    if not isinstance(bkg_id, int):
                        continue
                    general = item.get("general")
                    name = item.get("name")
                    if isinstance(general, dict) and isinstance(general.get("name"), str):
                        name = general.get("name")
                    parsed.append(
                        {
                            "bkgId": bkg_id,
                            "name": name if isinstance(name, str) else f"BKG {bkg_id}",
                        }
                    )
                parsed.sort(key=lambda item: item.get("bkgId", 0))
                self._background_list_cache = parsed

        return list(self._background_list_cache)

    async def async_get_input_list(self, device_id: int = 0) -> list[dict[str, Any]]:
        """Read all available inputs from input/readList."""
        data = await self._async_request("input/readList", {"deviceId": device_id})
        if data and isinstance(data, dict):
            inputs = data.get("inputs")
            if isinstance(inputs, list):
                return [item for item in inputs if isinstance(item, dict)]
        return []

    async def async_get_input_detail(
        self, input_id: int, device_id: int = 0
    ) -> dict[str, Any] | None:
        """Read detailed information of one input from input/readDetail."""
        data = await self._async_request(
            "input/readDetail",
            {"deviceId": device_id, "inputId": input_id},
        )
        if data and isinstance(data, dict):
            return data
        return None

    def _input_signature(self, input_data: dict[str, Any]) -> str:
        """Build a signature for change detection on list-level input properties."""
        general = input_data.get("general")
        resolution = input_data.get("resolution")
        timing = input_data.get("timing")
        signature_payload = {
            "online": input_data.get("online"),
            "isUsed": input_data.get("isUsed"),
            "iSignal": input_data.get("iSignal"),
            "interfaceType": input_data.get("interfaceType"),
            "resolution": resolution if isinstance(resolution, dict) else {},
            "timing": timing if isinstance(timing, dict) else {},
            "general": general if isinstance(general, dict) else {},
        }
        return json.dumps(signature_payload, sort_keys=True, default=str)

    async def async_get_inputs_with_details(
        self, device_id: int = 0
    ) -> list[dict[str, Any]]:
        """Get all inputs with selective detail refresh.

        Strategy:
        - Always read input list (cheap, covers all inputs)
        - Read per-input detail only when list-level signature changes
          or on periodic refresh cycles
        """
        inputs = await self.async_get_input_list(device_id)
        if not inputs:
            return []

        self._input_refresh_counter += 1
        periodic_refresh = self._input_refresh_counter % 12 == 0
        force_refresh = self._force_refresh_input_details
        self._force_refresh_input_details = False

        merged_inputs: list[dict[str, Any]] = []
        seen_input_ids: set[int] = set()

        for input_data in inputs:
            input_id_raw = input_data.get("inputId")
            if not isinstance(input_id_raw, int):
                merged_inputs.append(input_data)
                continue

            input_id = input_id_raw
            seen_input_ids.add(input_id)
            signature = self._input_signature(input_data)
            cached_signature = self._input_signature_cache.get(input_id)

            should_refresh_detail = (
                force_refresh or periodic_refresh or cached_signature != signature
            )
            if should_refresh_detail:
                detail = await self.async_get_input_detail(input_id, device_id)
                if detail is not None:
                    self._input_detail_cache[input_id] = detail
                    self._input_signature_cache[input_id] = signature

            cached_detail = self._input_detail_cache.get(input_id)
            if cached_detail and isinstance(cached_detail, dict):
                merged = {**input_data, **cached_detail}
            else:
                merged = dict(input_data)
            merged_inputs.append(merged)

        # Remove cache entries for inputs that no longer exist
        stale_ids = set(self._input_detail_cache) - seen_input_ids
        for stale_id in stale_ids:
            self._input_detail_cache.pop(stale_id, None)
            self._input_signature_cache.pop(stale_id, None)

        merged_inputs.sort(key=lambda item: item.get("inputId", 0))
        return merged_inputs

    async def async_get_layer_list(
        self, device_id: int = 0, screen_id: int = 0
    ) -> list[dict[str, Any]]:
        """Read all layers from layer/detailList."""
        data = await self._async_request(
            "layer/detailList",
            {"deviceId": device_id, "screenId": screen_id},
        )
        if data and isinstance(data, dict):
            layers = data.get("screenLayers") or data.get("layers")
            if isinstance(layers, list):
                return [item for item in layers if isinstance(item, dict)]
        return []

    async def async_get_layer_detail(
        self, layer_id: int, device_id: int = 0, screen_id: int = 0
    ) -> dict[str, Any] | None:
        """Read detailed information of one layer from layer/readDetail."""
        data = await self._async_request(
            "layer/readDetail",
            {"deviceId": device_id, "screenId": screen_id, "layerId": layer_id},
        )
        if data and isinstance(data, dict):
            return data
        return None

    def _layer_signature(self, layer_data: dict[str, Any]) -> str:
        """Build a signature for change detection on list-level layer properties."""
        general = layer_data.get("general")
        window = layer_data.get("window")
        source = layer_data.get("source")
        signature_payload = {
            "layerId": layer_data.get("layerId"),
            "general": general if isinstance(general, dict) else {},
            "window": window if isinstance(window, dict) else {},
            "source": source if isinstance(source, dict) else {},
        }
        return json.dumps(signature_payload, sort_keys=True, default=str)

    async def async_get_layers_with_details(
        self, device_id: int = 0, screen_id: int = 0
    ) -> list[dict[str, Any]]:
        """Get all layers with selective detail refresh."""
        layers = await self.async_get_layer_list(device_id, screen_id)
        if not layers:
            return []

        self._layer_refresh_counter += 1
        periodic_refresh = self._layer_refresh_counter % 12 == 0
        force_refresh = self._force_refresh_layer_details
        self._force_refresh_layer_details = False

        merged_layers: list[dict[str, Any]] = []
        seen_layer_ids: set[int] = set()

        for layer_data in layers:
            layer_id_raw = layer_data.get("layerId")
            if not isinstance(layer_id_raw, int):
                merged_layers.append(layer_data)
                continue

            layer_id = layer_id_raw
            seen_layer_ids.add(layer_id)
            signature = self._layer_signature(layer_data)
            cached_signature = self._layer_signature_cache.get(layer_id)

            should_refresh_detail = (
                force_refresh or periodic_refresh or cached_signature != signature
            )
            if should_refresh_detail:
                detail = await self.async_get_layer_detail(layer_id, device_id, screen_id)
                if detail is not None:
                    self._layer_detail_cache[layer_id] = detail
                    self._layer_signature_cache[layer_id] = signature

            cached_detail = self._layer_detail_cache.get(layer_id)
            if cached_detail and isinstance(cached_detail, dict):
                merged = {**layer_data, **cached_detail}
            else:
                merged = dict(layer_data)
            merged_layers.append(merged)

        stale_ids = set(self._layer_detail_cache) - seen_layer_ids
        for stale_id in stale_ids:
            self._layer_detail_cache.pop(stale_id, None)
            self._layer_signature_cache.pop(stale_id, None)

        merged_layers.sort(key=lambda item: item.get("layerId", 0))
        return merged_layers

    async def async_get_device_status_info(
        self, device_id: int = 0
    ) -> dict[str, Any]:
        """Get device status info from device/readDetail.

        Returns dict with:
        - temp_status: Temperature status code
        - device_status: Device status (0=busy, 1=ready)
        - signal_status: Signal power status from powerList[].iSignal
        """
        data = await self._async_request("device/readDetail", {"deviceId": device_id})
        result: dict[str, Any] = {
            "temp_status": None,
            "device_status": None,
            "signal_status": None,
        }
        if data and isinstance(data, dict):
            temp_status = data.get("temp")
            if temp_status is not None and isinstance(temp_status, (int, float)):
                result["temp_status"] = int(temp_status)
            device_status = data.get("status")
            if device_status is not None and isinstance(device_status, (int, float)):
                result["device_status"] = int(device_status)
            # iSignal is under powerList array
            power_list = data.get("powerList")
            if power_list and isinstance(power_list, list) and len(power_list) > 0:
                first_power = power_list[0]
                if isinstance(first_power, dict):
                    signal_status = first_power.get("iSignal")
                    if signal_status is not None and isinstance(signal_status, (int, float)):
                        result["signal_status"] = int(signal_status)
        return result

    async def async_send_raw_command(
        self, endpoint: str, body: dict[str, Any]
    ) -> Any | None:
        """Send a raw API command.

        Args:
            endpoint: API endpoint path (e.g., "device/readDetail")
            body: Business data for the request body

        Returns:
            Response body dict on success, None on failure
        """
        return await self._async_request(endpoint, body)

    async def async_set_background(
        self,
        background_id: int,
        enabled: bool,
        screen_id: int = 0,
        device_id: int = 0,
    ) -> bool:
        """Set screen background using screen/writeBKG."""
        payload = {
            "screenId": int(screen_id),
            "deviceId": int(device_id),
            "enable": 1 if enabled else 0,
            "bkgId": max(0, int(background_id)),
        }
        data = await self._async_request("screen/writeBKG", payload)
        if data is not None:
            self._force_refresh_backgrounds = True
            return True
        return False

    async def async_set_layer_source(
        self,
        layer_id: int,
        input_id: int | None,
        interface_type: int = 0,
        slot_id: int = 0,
        crop_id: int = 255,
        screen_id: int = 0,
        device_id: int = 0,
    ) -> bool:
        """Set source for a layer via layer/writeSource.

        Args:
            layer_id: Target layer ID
            input_id: Input ID to route, or None to clear source
            interface_type: Input interface type
            slot_id: Input slot/interface ID
            crop_id: Crop ID (255 uses original source)
            screen_id: Screen ID
            device_id: Device ID
        """
        if input_id is None:
            source_type = 0
            payload_input_id = 0
            payload_interface_type = 0
            payload_slot_id = 0
        else:
            source_type = 1
            payload_input_id = max(0, int(input_id))
            payload_interface_type = max(0, int(interface_type))
            payload_slot_id = max(0, int(slot_id))

        payload = {
            "screenId": int(screen_id),
            "deviceId": int(device_id),
            "layerId": int(layer_id),
            "sourceType": source_type,
            "slotId": payload_slot_id,
            "interfaceType": payload_interface_type,
            "inputId": payload_input_id,
            "cropId": int(crop_id),
        }

        data = await self._async_request("layer/writeSource", payload)
        if data is not None:
            self._force_refresh_layer_details = True
            self._force_refresh_input_details = True
            return True
        return False
