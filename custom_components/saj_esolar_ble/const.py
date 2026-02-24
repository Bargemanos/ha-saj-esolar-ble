"""Constants for the SAJ eSolar BLE integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "saj_esolar_ble"
MANUFACTURER: Final = "SAJ"

# MC20 (2G) BLE UUID - single service+characteristic
SERVICE_UUID: Final = "00001834-0000-1000-8000-00805f9b34fb"
# Non-standard descriptor on MC20 DTU (instead of CCCD 0x2902)
DESCRIPTOR_UUID: Final = "00002913-0000-1000-8000-00805f9b34fb"

# ModBus read commands (function 0x03)
CMD_DEVICE_INFO: Final = "01038F00000D"  # 13 registers at 0x8F00 (matches SAJ app)
CMD_REALTIME_GEN2: Final = "01030100003B"  # 59 registers at 0x0100
CMD_REALTIME_R6: Final = "01036004005F"  # 95 registers at 0x6004
CMD_PROTECT_PARAM: Final = "010333240011"  # 17 registers at 0x3324
CMD_CHARACTER_PARAM: Final = "010333090016"  # 22 registers at 0x3309

DEFAULT_PASSWORD: Final = "123456"
DEFAULT_UPDATE_INTERVAL_SECONDS: Final = 30
BLE_FRAME_PREFIX: Final = 0x32

CONF_BLE_ADDRESS: Final = "ble_address"
CONF_BLE_PASSWORD: Final = "ble_password"
CONF_DEVICE_SN: Final = "device_sn"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_ENABLE_PROTECTION: Final = "enable_protection"
CONF_ENABLE_CHARACTER: Final = "enable_character"

MIN_UPDATE_INTERVAL: Final = 10
MAX_UPDATE_INTERVAL: Final = 300

RUN_STATUS_MAP: Final[dict[int, str]] = {
    0: "Offline",
    1: "Standby",
    2: "Running",
    3: "Running",
    4: "Running",
    5: "Fault",
    6: "Offline",
}
