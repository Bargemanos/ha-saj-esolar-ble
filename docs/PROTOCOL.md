# SAJ R5 DTU - MC20 (2G) BLE Protocol Reference

Reverse-engineered from the SAJ eSolar O&M Android app (v5.1.7) and
verified against a live SAJ R5-3K-S1 inverter with DTU BLE dongle.

## BLE Service

| Item | Value |
|---|---|
| Service UUID | `00001834-0000-1000-8000-00805f9b34fb` |
| Characteristic | Same UUID, single char with [read, write, notify, indicate] |
| Descriptor | `00002913` (non-standard, replaces CCCD `0x2902`) |

The MC20 module exposes a single service with a single characteristic.
All communication happens through writes and notifications on this characteristic.

## Packet Format

**TX (host -> DTU):** Raw ModBus frame + CRC16 (no prefix, no framing).

```
[ModBus payload bytes] [CRC16-lo] [CRC16-hi]
```

- No `0x32` prefix (unlike some older SAJ protocols)
- No `BSAJ` framing
- No AES encryption
- No password authentication required

**RX (DTU -> host):** Same format, may arrive in multiple BLE notification chunks.
Response may have optional `0x32` prefix byte - strip it before parsing.

## CRC16-ModBus

Standard ModBus CRC16 with polynomial `0xA001`, init `0xFFFF`, LSB first.

## ModBus Commands (function 0x03 - Read Holding Registers)

| Command | Hex | Registers | Description |
|---|---|---|---|
| Device Info | `01 03 8F00 000D` | 13 @ 0x8F00 | Serial number, type, firmware |
| Realtime Gen2 | `01 03 0100 003B` | 59 @ 0x0100 | Power, energy (newer inverters) |
| Realtime R6 | `01 03 6004 005F` | 95 @ 0x6004 | Power, energy (older R6 protocol) |

## Device Info Response (0x8F00, 13 registers)

After stripping optional `0x32` prefix and ModBus header (3 bytes: addr + func + byte_count):

| Offset (hex chars) | Length | Field |
|---|---|---|
| 6-10 | 4 | Device type code |
| 10-14 | 4 | Sub type |
| 14-18 | 4 | Comm version (raw / 1000 = version) |
| 18-58 | 40 | Serial number (ASCII, null-padded) |
| 98-102 | 4 | Display version (optional) |
| 102-106 | 4 | Main controller version (optional) |
| 106-110 | 4 | Slave controller version (optional) |

## Realtime Gen2 Response (0x0100, 59 registers)

Minimum 210 hex chars after prefix strip.

| Offset (hex chars) | Length | Field | Scale |
|---|---|---|---|
| 82-86 | 4 | Current power (W) | raw = watts |
| 182-186 | 4 | Today energy | raw / 100 = kWh |
| 186-194 | 8 | Month energy | raw / 100 = kWh |
| 194-202 | 8 | Year energy | raw / 100 = kWh |
| 202-210 | 8 | Total energy | raw / 100 = kWh |

## Realtime R6 Response (0x6004, 95 registers)

Minimum 114 hex chars after prefix strip. Fallback when Gen2 returns no data.

| Offset (hex chars) | Length | Field | Scale |
|---|---|---|---|
| 6-14 | 8 | Total energy | raw / 100 = kWh |
| 14-22 | 8 | Year energy | raw / 100 = kWh |
| 22-30 | 8 | Month energy | raw / 100 = kWh |
| 30-38 | 8 | Today energy | raw / 100 = kWh |
| 106-114 | 8 | Current power (W) | raw = watts |

## Communication Flow

1. Connect to BLE device
2. Wait ~800ms after connection (matches SAJ app behavior)
3. Find characteristic with UUID containing `00001834`
4. Reset descriptor `0x2913` -> `0x0000` (clears stale BlueZ bond state)
5. Enable descriptor `0x2913` -> `0x0100`
6. Start notifications on characteristic
7. Write command bytes to characteristic (write without response)
8. Collect notification chunks until expected byte count reached
9. Parse response, strip optional `0x32` prefix
