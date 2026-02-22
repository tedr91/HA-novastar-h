from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "novastar_h"
DEFAULT_NAME = "Novastar H Series"
DEFAULT_PORT = 8000  # Novastar OpenAPI default port
DEFAULT_TIMEOUT = 10.0
SCAN_INTERVAL = 5

CONF_DEVICE_ID = "device_id"
CONF_SCREEN_ID = "screen_id"
CONF_PROJECT_ID = "project_id"
CONF_SECRET_KEY = "secret_key"
CONF_ENCRYPTION = "encryption"
CONF_ALLOW_RAW_COMMANDS = "allow_raw_commands"
CONF_ENABLE_DEBUG_LOGGING = "enable_debug_logging"
CONF_LAYER_SELECT_PREPOPULATE_COUNT = "layer_select_prepopulate_count"

DEFAULT_DEVICE_ID = 0
DEFAULT_SCREEN_ID = 0
DEFAULT_ENCRYPTION = False
DEFAULT_ALLOW_RAW_COMMANDS = False
DEFAULT_ENABLE_DEBUG_LOGGING = True
DEFAULT_LAYER_SELECT_PREPOPULATE_COUNT = 3

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
]
