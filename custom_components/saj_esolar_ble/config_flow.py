"""Config flow for SAJ eSolar BLE."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_PASSWORD

from .ble_modbus import SAJBLEClient
from .const import (
    CONF_BLE_ADDRESS,
    CONF_BLE_PASSWORD,
    CONF_DEVICE_SN,
    CONF_DEVICE_TYPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_PASSWORD,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    SERVICE_UUID,
)

_LOGGER = logging.getLogger(__name__)


class SajEsBLeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SAJ eSolar BLE."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SajEsBleOptionsFlow:
        """Get the options flow handler."""
        return SajEsBleOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._selected_address: str | None = None
        self._ble_device: Any | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        devices = _discovered_devices(self.hass)

        if user_input is not None:
            address = user_input.get(CONF_BLE_ADDRESS)
            if not address:
                errors["base"] = "no_devices"
            else:
                self._selected_address = address
                for service_info in bluetooth.async_discovered_service_info(self.hass):
                    if service_info.address == address:
                        self._ble_device = service_info.device
                        break
                self._async_abort_entries_match({CONF_BLE_ADDRESS: address})
                return await self.async_step_confirm()

        if devices:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_BLE_ADDRESS): vol.In(
                        {addr: label for addr, label in devices.items()}
                    )
                }
            )
        else:
            errors["base"] = "no_devices"
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_BLE_ADDRESS): str,
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None):
        """Confirm connection details and authenticate."""
        errors: dict[str, str] = {}
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            address = self._selected_address
            if not address:
                return self.async_abort(reason="unknown")

            try:
                client = SAJBLEClient(
                    address,
                    password=password,
                    ble_device=self._ble_device,
                )
                device_info = await client.read_device_info()
            except Exception as err:
                _LOGGER.error("BLE connection failed: %s", err, exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(device_info.serial_number or address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_info.serial_number or address,
                    data={
                        CONF_BLE_ADDRESS: address,
                        CONF_BLE_PASSWORD: password,
                        CONF_DEVICE_SN: device_info.serial_number,
                        CONF_DEVICE_TYPE: device_info.device_type_code,
                    },
                )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str}
            ),
            errors=errors,
        )


class SajEsBleOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for SAJ eSolar BLE."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=current_interval,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                        ),
                    ),
                }
            ),
        )


def _discovered_devices(hass) -> dict[str, str]:
    devices: dict[str, str] = {}
    for service_info in bluetooth.async_discovered_service_info(hass):
        if SERVICE_UUID not in service_info.service_uuids:
            continue
        name = service_info.name or "SAJ Inverter"
        devices[service_info.address] = f"{name} ({service_info.address})"
    return devices
