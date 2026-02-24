# BLE Workarounds for Home Assistant

Issues encountered running on HA OS with BlueZ, and their solutions.

## 1. bleak 2.0.0 AcquireNotify Regression

**Problem:** HA Core 2026.1+ pins `bleak==2.0.0` which switched from D-Bus
`StartNotify` to `AcquireNotify`. The MC20 DTU doesn't support AcquireNotify,
causing `[org.bluez.Error.NotPermitted] Notify acquired` errors.

**Fix:** Pass `bluez={"use_start_notify": True}` to `client.start_notify()`.
This forces the older StartNotify path. Available in bleak >= 2.1.0, but works
as a kwarg passthrough in 2.0.0 too.

```python
await client.start_notify(
    char_uuid, callback,
    bluez={"use_start_notify": True},
)
```

**Fallback:** If the kwarg raises `TypeError` (older bleak), fall back to
plain `client.start_notify(char_uuid, callback)`.

## 2. BlueZ Auto-Bonding Stale State

**Problem:** BlueZ automatically bonds with BLE devices after first connection.
On reconnect, it restores prior GATT state including notification subscriptions.
This causes "Notify acquired" errors because BlueZ thinks notifications are
already active from the previous session.

**Fix:** Before enabling notifications, reset descriptor `0x2913` to `0x0000`,
wait 100ms, then write `0x0100` to enable fresh.

```python
# Reset stale notification state
await client.write_gatt_descriptor(desc_handle, b"\x00\x00")
await asyncio.sleep(0.1)
# Enable fresh
await client.write_gatt_descriptor(desc_handle, b"\x01\x00")
```

**Note:** The MC20 uses non-standard descriptor `0x2913` instead of the
standard CCCD `0x2902`. The reset/enable sequence works the same way.

## 3. Poll-Read Fallback

**Problem:** If both notification strategies fail, the integration has no way
to receive responses.

**Fix:** Fall back to polling `read_gatt_char()` every 300ms until the
expected response length is received or timeout is reached. Less efficient
but functional.

## 4. Python 3.13 Dataclass Inheritance

**Problem:** HA Core 2026.x runs Python 3.13 which is strict about dataclass
field ordering. Subclassing `SensorEntityDescription` (which has fields with
defaults) and adding a field without a default raises `TypeError`.

**Fix:** Use `kw_only=True` on the subclass dataclass decorator.

```python
@dataclass(frozen=True, kw_only=True)
class SajBleSensorDescription(SensorEntityDescription):
    value_fn: Callable[[RealtimeData], float | None]
```
