"""BLE ModBus client for SAJ eSolar inverters (MC20 2G protocol)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from bleak import BleakClient, BleakError

from .const import (
    BLE_FRAME_PREFIX,
    CMD_DEVICE_INFO,
    CMD_REALTIME_GEN2,
    CMD_REALTIME_R6,
    DEFAULT_PASSWORD,
    DESCRIPTOR_UUID,
    SERVICE_UUID,
)

_LOGGER = logging.getLogger(__name__)

try:
    from bleak_retry_connector import establish_connection
    HAS_RETRY = True
except ImportError:
    HAS_RETRY = False


@dataclass(frozen=True)
class DeviceInfo:
    serial_number: str
    device_type_code: int
    sub_type: int
    comm_version: str
    display_version: str | None
    main_ctrl_version: str | None
    slave_ctrl_version: str | None


@dataclass(frozen=True)
class RealtimeData:
    current_power_w: float | None
    today_kwh: float | None
    month_kwh: float | None
    year_kwh: float | None
    total_kwh: float | None
    protocol: str
    run_status: int | None = None
    pv1_voltage: float | None = None
    pv1_current: float | None = None
    pv2_voltage: float | None = None
    pv2_current: float | None = None
    grid_voltage: float | None = None
    grid_current: float | None = None
    grid_frequency: float | None = None


class SAJBLEClient:
    """MC20 (2G) BLE client for SAJ R5 DTU."""

    def __init__(
        self,
        address: str,
        password: str | None = None,
        timeout: int = 15,
        ble_device: Any | None = None,
    ) -> None:
        self._address = address
        self._password = password or DEFAULT_PASSWORD
        self._timeout = timeout
        self._ble_device = ble_device

    async def _get_client(self) -> BleakClient:
        target = self._ble_device or self._address
        _LOGGER.debug("Connecting to %s", self._address)
        client = BleakClient(target, timeout=self._timeout)
        await client.connect()
        _LOGGER.debug("Connected, MTU=%s", getattr(client, "mtu_size", "?"))
        return client

    def _find_char_uuid(self, client: BleakClient) -> str:
        """Find the MC20 application characteristic (UUID 00001834)."""
        for service in client.services:
            for char in service.characteristics:
                if SERVICE_UUID.lower() in char.uuid.lower():
                    _LOGGER.debug(
                        "Found char %s [%s]",
                        char.uuid,
                        ",".join(char.properties),
                    )
                    return char.uuid
        raise BleakError("MC20 characteristic not found")

    def _find_descriptor_handle(
        self, client: BleakClient, char_uuid: str
    ) -> int | None:
        """Find the 0x2913 descriptor handle on the MC20 characteristic."""
        for service in client.services:
            for char in service.characteristics:
                if char.uuid.lower() == char_uuid.lower():
                    for desc in char.descriptors:
                        if DESCRIPTOR_UUID.lower() in desc.uuid.lower():
                            return desc.handle
        return None

    async def _setup_notifications(
        self, client: BleakClient, char_uuid: str, callback
    ) -> bool:
        """Enable notifications on the MC20 characteristic.

        Strategy: try start_notify directly first. The MC20 DTU uses
        descriptor 0x2913 instead of standard CCCD 0x2902, but BlueZ
        handles this via bonded GATT cache. Manipulating the descriptor
        manually can cause BlueZ to drop the connection (ATT error 0x0e),
        so we only touch it as a last resort.

        Also works around bleak 2.0.0 AcquireNotify regression by forcing
        StartNotify via the bluez kwarg (bleak >= 2.1.0).
        """
        # Strategy 1: start_notify with use_start_notify (bleak >= 2.1)
        try:
            await client.start_notify(
                char_uuid, callback,
                bluez={"use_start_notify": True},
            )
            _LOGGER.debug("start_notify(use_start_notify) succeeded")
            return True
        except TypeError:
            _LOGGER.debug("bluez kwarg not supported, trying without")
        except Exception as err:
            _LOGGER.debug("start_notify(use_start_notify) failed: %s", err)

        # Strategy 2: standard start_notify
        try:
            await client.start_notify(char_uuid, callback)
            _LOGGER.debug("start_notify succeeded")
            return True
        except Exception as err:
            _LOGGER.debug("start_notify failed: %s", err)

        # Strategy 3: reset descriptor then retry start_notify
        if client.is_connected:
            desc_handle = self._find_descriptor_handle(client, char_uuid)
            if desc_handle is not None:
                try:
                    _LOGGER.debug("Trying descriptor reset as last resort")
                    await client.write_gatt_descriptor(
                        desc_handle, b"\x00\x00"
                    )
                    await asyncio.sleep(0.1)
                    await client.write_gatt_descriptor(
                        desc_handle, b"\x01\x00"
                    )
                    await client.start_notify(char_uuid, callback)
                    _LOGGER.debug("start_notify after descriptor reset OK")
                    return True
                except Exception as err:
                    _LOGGER.debug(
                        "Descriptor reset strategy failed: %s", err
                    )

        _LOGGER.warning("All notify strategies failed")
        return False

    async def _send_and_notify(
        self, client: BleakClient, modbus_hex: str, char_uuid: str
    ) -> str:
        """Send ModBus command and collect response via notifications."""
        payload = build_ble_packet(modbus_hex)

        if not client.is_connected:
            raise BleakError("Client disconnected before send")

        _LOGGER.debug("TX (%db): %s", len(payload), payload.hex())

        response_event = asyncio.Event()
        response_buf = bytearray()
        expected_len: int | None = None

        def on_notify(_handle: int, data: bytearray) -> None:
            nonlocal expected_len
            _LOGGER.debug("RX chunk (%db)", len(data))
            response_buf.extend(data)

            # Check "Authenticated" response
            if response_buf.hex().startswith("41757468656e74696361746564"):
                response_event.set()
                return

            # Parse expected length from ModBus header
            if expected_len is None and len(response_buf) >= 4:
                offset = 1 if response_buf[0] == BLE_FRAME_PREFIX else 0
                byte_count = response_buf[offset + 2]
                expected_len = offset + 3 + byte_count + 2

            if expected_len and len(response_buf) >= expected_len:
                _LOGGER.debug("Response complete: %db", len(response_buf))
                response_event.set()

        use_notify = await self._setup_notifications(client, char_uuid, on_notify)

        try:
            await client.write_gatt_char(char_uuid, payload, response=False)

            if use_notify:
                await asyncio.wait_for(
                    response_event.wait(), timeout=self._timeout
                )
            else:
                # Poll-read fallback when notifications couldn't be set up
                _LOGGER.debug("Using poll-read fallback")
                deadline = asyncio.get_event_loop().time() + self._timeout
                while asyncio.get_event_loop().time() < deadline:
                    await asyncio.sleep(0.3)
                    try:
                        data = await client.read_gatt_char(char_uuid)
                        if data and len(data) > 0:
                            on_notify(0, bytearray(data))
                            if response_event.is_set():
                                break
                    except Exception as err:
                        _LOGGER.debug("Poll-read error: %s", err)
                if not response_event.is_set():
                    raise asyncio.TimeoutError("No response via poll-read")
        finally:
            try:
                if use_notify:
                    await client.stop_notify(char_uuid)
            except Exception:
                pass

        _LOGGER.debug(
            "Full response (%db): %s...",
            len(response_buf),
            response_buf.hex()[:60],
        )
        return response_buf.hex()

    async def read_device_info(self) -> DeviceInfo:
        """Read device info registers from inverter."""
        client = await self._get_client()
        try:
            char_uuid = self._find_char_uuid(client)
            # Wait 800ms after connection (matches SAJ app behavior)
            await asyncio.sleep(0.8)

            response = await self._send_and_notify(
                client, CMD_DEVICE_INFO, char_uuid
            )
            info = _parse_device_info(response)
            _LOGGER.debug(
                "DeviceInfo: sn=%s type=%s",
                info.serial_number,
                info.device_type_code,
            )
            return info
        finally:
            await client.disconnect()

    async def read_realtime_data(self) -> RealtimeData:
        """Read realtime data registers from inverter."""
        client = await self._get_client()
        try:
            char_uuid = self._find_char_uuid(client)
            await asyncio.sleep(0.8)

            response = await self._send_and_notify(
                client, CMD_REALTIME_GEN2, char_uuid
            )
            data = _parse_realtime_gen2(response)
            if data is None:
                _LOGGER.debug("Gen2 parse returned None, trying R6")
                response = await self._send_and_notify(
                    client, CMD_REALTIME_R6, char_uuid
                )
                data = _parse_realtime_r6(response)
            if data is None:
                raise ValueError("Failed to parse realtime data")
            _LOGGER.debug(
                "Realtime: %sW today=%skWh",
                data.current_power_w,
                data.today_kwh,
            )
            return data
        finally:
            await client.disconnect()


def build_ble_packet(modbus_hex: str) -> bytes:
    """Build BLE packet: raw ModBus + CRC16 (no prefix for MC20 path)."""
    modbus_bytes = bytes.fromhex(modbus_hex)
    crc = crc16_modbus(modbus_bytes)
    return modbus_bytes + crc


def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte & 0xFF
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def _strip_prefix(hex_str: str) -> str:
    if hex_str.startswith("32"):
        return hex_str[2:]
    return hex_str


def _parse_uint16(hex_str: str, start: int, end: int) -> int | None:
    if len(hex_str) < end:
        return None
    return int(hex_str[start:end], 16)


def _parse_uint32(hex_str: str, start: int, end: int) -> int | None:
    if len(hex_str) < end:
        return None
    return int(hex_str[start:end], 16)


def _parse_device_info(hex_str: str) -> DeviceInfo:
    hex_str = _strip_prefix(hex_str)
    _LOGGER.debug("device_info hex (%d chars)", len(hex_str))
    if len(hex_str) < 58:
        raise ValueError(
            f"Device info response too short ({len(hex_str)} hex chars)"
        )

    device_type_hex = hex_str[6:10]
    sub_type_hex = hex_str[10:14]
    comm_ver_hex = hex_str[14:18]
    sn_hex = hex_str[18:58]

    serial_number = (
        bytes.fromhex(sn_hex)
        .decode("ascii", errors="ignore")
        .strip("\x00")
        .strip()
    )
    device_type_code = int(device_type_hex, 16)
    sub_type = int(sub_type_hex, 16)
    comm_version = f"STV{int(comm_ver_hex, 16) / 1000:.3f}"

    display_ver = _parse_uint16(hex_str, 98, 102)
    main_ver = _parse_uint16(hex_str, 102, 106)
    slave_ver = _parse_uint16(hex_str, 106, 110)

    return DeviceInfo(
        serial_number=serial_number,
        device_type_code=device_type_code,
        sub_type=sub_type,
        comm_version=comm_version,
        display_version=_format_version(display_ver),
        main_ctrl_version=_format_version(main_ver),
        slave_ctrl_version=_format_version(slave_ver),
    )


def _parse_realtime_gen2(hex_str: str) -> RealtimeData | None:
    """Parse Gen2 response (0x0100, 59 registers)."""
    hex_str = _strip_prefix(hex_str)
    if len(hex_str) < 210:
        return None

    run_status = _parse_uint16(hex_str, 6, 10)
    pv1_voltage_raw = _parse_uint16(hex_str, 34, 38)
    pv1_current_raw = _parse_uint16(hex_str, 38, 42)
    pv2_voltage_raw = _parse_uint16(hex_str, 46, 50)
    pv2_current_raw = _parse_uint16(hex_str, 50, 54)
    current_power = _parse_uint16(hex_str, 82, 86)
    grid_voltage_raw = _parse_uint16(hex_str, 94, 98)
    grid_current_raw = _parse_uint16(hex_str, 98, 102)
    grid_freq_raw = _parse_uint16(hex_str, 102, 106)
    today_energy = _parse_uint16(hex_str, 182, 186)
    month_energy = _parse_uint32(hex_str, 186, 194)
    year_energy = _parse_uint32(hex_str, 194, 202)
    total_energy = _parse_uint32(hex_str, 202, 210)

    if current_power is None:
        return None

    return RealtimeData(
        current_power_w=float(current_power),
        today_kwh=_scale_energy(today_energy),
        month_kwh=_scale_energy(month_energy),
        year_kwh=_scale_energy(year_energy),
        total_kwh=_scale_energy(total_energy),
        protocol="gen2",
        run_status=run_status,
        pv1_voltage=_scale(pv1_voltage_raw, 10),
        pv1_current=_scale(pv1_current_raw, 100),
        pv2_voltage=_scale(pv2_voltage_raw, 10),
        pv2_current=_scale(pv2_current_raw, 100),
        grid_voltage=_scale(grid_voltage_raw, 10),
        grid_current=_scale(grid_current_raw, 100),
        grid_frequency=_scale(grid_freq_raw, 100),
    )


def _parse_realtime_r6(hex_str: str) -> RealtimeData | None:
    """Parse R6 response (0x6004, 95 registers)."""
    hex_str = _strip_prefix(hex_str)
    if len(hex_str) < 114:
        return None

    total_energy = _parse_uint32(hex_str, 6, 14)
    year_energy = _parse_uint32(hex_str, 14, 22)
    month_energy = _parse_uint32(hex_str, 22, 30)
    today_energy = _parse_uint32(hex_str, 30, 38)
    current_power = _parse_uint32(hex_str, 106, 114)

    if current_power is None:
        return None

    return RealtimeData(
        current_power_w=float(current_power),
        today_kwh=_scale_energy(today_energy),
        month_kwh=_scale_energy(month_energy),
        year_kwh=_scale_energy(year_energy),
        total_kwh=_scale_energy(total_energy),
        protocol="r6",
    )


def _format_version(raw: int | None) -> str | None:
    if raw is None:
        return None
    return f"V{raw / 1000:.3f}"


def _scale(value: int | None, divisor: int) -> float | None:
    """Scale a raw register value by a divisor.

    Treats 0xFFFF as absent (inverter returns this for unused inputs).
    """
    if value is None or value == 0xFFFF:
        return None
    return float(value) / divisor


def _scale_energy(value: int | None) -> float | None:
    if value is None:
        return None
    return float(value) / 100.0
