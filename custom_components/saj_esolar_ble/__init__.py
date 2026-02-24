"""The SAJ eSolar BLE integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .ble_modbus import DeviceInfo, RealtimeData, SAJBLEClient
from .const import (
    CONF_BLE_ADDRESS,
    CONF_BLE_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


class SAJBLEResponse(TypedDict):
    """Coordinator data payload."""

    device_info: DeviceInfo
    realtime: RealtimeData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SAJ eSolar BLE from a config entry."""
    coordinator = SAJBLECoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update - adjust coordinator interval."""
    coordinator: SAJBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    new_interval = entry.options.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
    )
    coordinator.update_interval = timedelta(seconds=new_interval)
    _LOGGER.debug("Update interval changed to %ds", new_interval)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class SAJBLECoordinator(DataUpdateCoordinator[SAJBLEResponse]):
    """Data update coordinator for BLE devices."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
            config_entry=entry,
        )
        self._entry = entry
        self._device_info: DeviceInfo | None = None
        self.last_update_success_time: datetime | None = None
        self.ble_status: str = "Unknown"

    async def _async_update_data(self) -> SAJBLEResponse:
        """Fetch the latest data from the inverter via BLE."""
        address = self._entry.data[CONF_BLE_ADDRESS]
        password = self._entry.data[CONF_BLE_PASSWORD]

        try:
            client = SAJBLEClient(address, password=password)
            self.ble_status = "Connecting"

            if self._device_info is None:
                self._device_info = await client.read_device_info()

            realtime = await client.read_realtime_data()

        except Exception as err:
            self.ble_status = "Error"
            raise UpdateFailed(f"BLE update failed: {err}") from err

        self.ble_status = "Connected"
        self.last_update_success_time = datetime.now()
        _LOGGER.debug("Update OK: %sW", realtime.current_power_w)
        return {
            "device_info": self._device_info,
            "realtime": realtime,
        }
