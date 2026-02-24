# SAJ eSolar BLE

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/Bargemanos/ha-saj-esolar-ble)](https://github.com/Bargemanos/ha-saj-esolar-ble/releases)

Home Assistant custom integration for **SAJ solar inverters** (R5 series) via **Bluetooth Low Energy (BLE)**. Communicates directly with the inverter's DTU (MC20 2G module) using Modbus over BLE — no cloud, no Wi-Fi required.

---
**This integration is provided as-is. No support or maintenance is guaranteed.**
---

## Features

- Auto-discovery of SAJ inverters via Bluetooth
- Real-time solar production monitoring
- Configurable polling interval (10–300 seconds)

### Sensors

| Sensor | Unit | Description |
|---|---|---|
| Current Power | W | Live power output |
| PV1/PV2 Voltage | V | String voltages |
| PV1/PV2 Current | A | String currents |
| Grid Voltage | V | AC grid voltage |
| Grid Current | A | AC grid current |
| Grid Frequency | Hz | AC frequency |
| Today Energy | kWh | Generation today |
| Month Energy | kWh | Generation this month |
| Year Energy | kWh | Generation this year |
| Total Energy | kWh | Lifetime generation |
| Run Status | — | Offline / Standby / Running / Fault |

Diagnostic sensors: BLE connection status, update interval, last power reading.

## Requirements

- Home Assistant 2025.2+
- Bluetooth adapter accessible to HA (built-in or USB)
- SAJ R5 series inverter with MC20 (2G) DTU module

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu (top right) → **Custom repositories**
3. Add `https://github.com/Bargemanos/ha-saj-esolar-ble` as **Integration**
4. Search for "SAJ eSolar BLE" and install
5. Restart Home Assistant

### Manual

1. Copy `custom_components/saj_esolar_ble/` to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **SAJ eSolar BLE**
3. Select your inverter from discovered devices
4. Enter the BLE password

The polling interval can be changed in the integration's options (default: 30 seconds).

## Supported Devices

- SAJ R5 series inverters with MC20 (2G) BLE DTU module
- Communication via BLE Modbus (service UUID `00001834-0000-1000-8000-00805f9b34fb`)

## Troubleshooting

See [docs/BLE_WORKAROUNDS.md](docs/BLE_WORKAROUNDS.md) for known BLE connection issues and workarounds.

## License

MIT
