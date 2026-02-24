"""Sensor platform for SAJ eSolar BLE."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SAJBLECoordinator
from .ble_modbus import DeviceInfo as SajDeviceInfo, RealtimeData
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS, DOMAIN, MANUFACTURER, RUN_STATUS_MAP


@dataclass(frozen=True, kw_only=True)
class SajBleSensorDescription(SensorEntityDescription):
    """Describes SAJ BLE sensor."""

    value_fn: Callable[[RealtimeData], float | str | None]


SENSOR_DESCRIPTIONS: tuple[SajBleSensorDescription, ...] = (
    SajBleSensorDescription(
        key="run_status",
        translation_key="run_status",
        device_class=SensorDeviceClass.ENUM,
        options=["running", "standby", "fault", "offline"],
        value_fn=lambda data: RUN_STATUS_MAP.get(
            data.run_status, "offline"
        ) if data.run_status is not None else None,
    ),
    SajBleSensorDescription(
        key="current_power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda data: data.current_power_w,
    ),
    SajBleSensorDescription(
        key="pv1_voltage",
        translation_key="pv1_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.pv1_voltage,
    ),
    SajBleSensorDescription(
        key="pv1_current",
        translation_key="pv1_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data.pv1_current,
    ),
    SajBleSensorDescription(
        key="pv2_voltage",
        translation_key="pv2_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.pv2_voltage,
    ),
    SajBleSensorDescription(
        key="pv2_current",
        translation_key="pv2_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data.pv2_current,
    ),
    SajBleSensorDescription(
        key="grid_voltage",
        translation_key="grid_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda data: data.grid_voltage,
    ),
    SajBleSensorDescription(
        key="grid_current",
        translation_key="grid_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: data.grid_current,
    ),
    SajBleSensorDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        value_fn=lambda data: data.grid_frequency,
    ),
    SajBleSensorDescription(
        key="today_energy",
        translation_key="today_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data.today_kwh,
    ),
    SajBleSensorDescription(
        key="month_energy",
        translation_key="month_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data.month_kwh,
    ),
    SajBleSensorDescription(
        key="year_energy",
        translation_key="year_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data.year_kwh,
    ),
    SajBleSensorDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data.total_kwh,
    ),
)


DIAGNOSTIC_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ble_status",
        translation_key="ble_status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="update_interval",
        translation_key="update_interval",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="last_power_reading",
        translation_key="last_power_reading",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SAJ BLE sensors from a config entry."""
    coordinator: SAJBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        SajBleSensor(coordinator, desc) for desc in SENSOR_DESCRIPTIONS
    ]
    entities.extend(
        SajBleDiagnosticSensor(coordinator, desc)
        for desc in DIAGNOSTIC_DESCRIPTIONS
    )
    async_add_entities(entities)


class SajBleSensor(CoordinatorEntity[SAJBLECoordinator], SensorEntity):
    """Representation of an SAJ BLE sensor."""

    _attr_has_entity_name = True
    entity_description: SajBleSensorDescription

    def __init__(
        self,
        coordinator: SAJBLECoordinator,
        description: SajBleSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description

        device_info = coordinator.data["device_info"]
        serial = device_info.serial_number or coordinator.config_entry.entry_id

        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = _as_device_info(device_info)

    @property
    def available(self) -> bool:
        """Return True if coordinator has data."""
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self) -> float | str | None:
        if self.coordinator.data is None:
            return None
        data = self.coordinator.data["realtime"]
        return self.entity_description.value_fn(data)


class SajBleDiagnosticSensor(CoordinatorEntity[SAJBLECoordinator], SensorEntity):
    """Diagnostic sensor for integration metadata."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SAJBLECoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description

        device_info = coordinator.data["device_info"]
        serial = device_info.serial_number or coordinator.config_entry.entry_id

        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = _as_device_info(device_info)

    @property
    def native_value(self) -> float | str | None:
        key = self.entity_description.key
        if key == "ble_status":
            return self.coordinator.ble_status
        if key == "update_interval":
            interval = self.coordinator.config_entry.options.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
            )
            return interval
        if key == "last_power_reading":
            if self.coordinator.data is None:
                return None
            return self.coordinator.data["realtime"].current_power_w
        return None


def _as_device_info(device_info: SajDeviceInfo) -> DeviceInfo:
    serial = device_info.serial_number or "unknown"
    model = f"Type {device_info.device_type_code}"
    sw_version = device_info.comm_version
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        manufacturer=MANUFACTURER,
        name=f"SAJ Inverter {serial}",
        model=model,
        serial_number=serial,
        sw_version=sw_version,
    )
