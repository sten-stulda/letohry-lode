"""HID-based communication with Concept2 PM3 monitors."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

try:
    import usb.core
    import usb.util
except ImportError:  # optional at import-time; hard fail only when HID monitor is used
    usb = None  # type: ignore[assignment]

from ..models import PM3Frame
from ..services.diagnostics import DiagnosticsService

GET_CADENCE = 0xA7
GET_POWER = 0xB4
GO_IN_USE = 0x85
PM_GET_WORKTIME = 0xA0
PM_GET_WORKDISTANCE = 0xA3
PM_WRAPPER = 0x1A

# Concept2 PM3 USB HID identifiers
PM3_VENDOR_ID = 0x0425
PM3_PRODUCT_ID = 0x0000

FRAME_START = 0xF1
FRAME_END = 0xF2
FRAME_ESCAPE = 0xF3

REPORT_SIZES = {
    0x01: 21,
    0x04: 63,
    0x02: 121,
}


class PM3HIDMonitor:
    """Communicate with Concept2 PM3 via USB endpoints (pyusb/libusb)."""

    def __init__(
        self,
        lane_id: int,
        name: str,
        device_path: str,
        connect_retries: int = 3,
        diagnostics_service: DiagnosticsService | None = None,
    ) -> None:
        self.lane_id = lane_id
        self.name = name
        self.device_path = device_path
        self.connect_retries = max(connect_retries, 1)
        self._usb_dev: Any | None = None
        self._in_ep: int | None = None
        self._out_ep: int | None = None
        self._report_id: int = 0x02
        self._hid_uniq: str = ""
        self._last_frame = PM3Frame()
        self._read_lock = asyncio.Lock()
        self._diagnostics_service = diagnostics_service
        self._consecutive_telemetry_failures = 0

    async def connect(self) -> None:
        if usb is None:
            raise RuntimeError("pyusb is required for PM3 HID monitor. Install with: pip install pyusb")

        self._hid_uniq = _read_hid_uniq(self.device_path)
        last_error: Exception | None = None
        for _ in range(self.connect_retries):
            try:
                self._usb_dev, self._in_ep, self._out_ep = await asyncio.to_thread(
                    _open_pm3_usb_device,
                    self._hid_uniq,
                )
                self._log_diagnostic(
                    "connect",
                    self.device_path.encode(),
                    f"connected via usb serial={self._hid_uniq or '-'} in=0x{self._in_ep:02x} out=0x{self._out_ep:02x}",
                )
                await self._prime_monitor()
                return
            except Exception as error:
                last_error = error
                self._log_diagnostic("connect_error", str(error).encode(), "connect failed")
                await asyncio.sleep(0.3)

        perm_hint = _build_connect_hint()
        raise RuntimeError(
            f"Failed to connect to PM3 on {self.device_path} (uniq={self._hid_uniq or '-'})"
            f": {last_error}{perm_hint}"
        )

    async def disconnect(self) -> None:
        if self._usb_dev is not None:
            await asyncio.to_thread(usb.util.dispose_resources, self._usb_dev)
        self._usb_dev = None
        self._in_ep = None
        self._out_ep = None

    async def reset(self) -> None:
        self._last_frame = PM3Frame()
        self._consecutive_telemetry_failures = 0

    async def read_frame(self) -> PM3Frame:
        if self._usb_dev is None or self._in_ep is None or self._out_ep is None:
            raise RuntimeError("PM3 HID monitor is not connected.")

        async with self._read_lock:
            # Request exactly the fields needed for live race telemetry.
            command_payload = _build_monitor_command_payload()
            raw_reply = b""
            last_error: Exception | None = None
            for report_id in _report_fallback_order(self._report_id):
                try:
                    request = _build_report(_build_csafe_frame(command_payload), report_id)
                    self._log_diagnostic(
                        "tx",
                        request,
                        f"sent PM3 telemetry request (report_id=0x{report_id:02x})",
                    )
                    raw = await asyncio.to_thread(self._write_then_read, request)
                    raw_reply = bytes(raw)
                    if raw_reply:
                        self._report_id = report_id
                        break
                except Exception as error:
                    last_error = error
                    self._log_diagnostic(
                        "rx_error",
                        str(error).encode(),
                        f"USB read failed (report_id=0x{report_id:02x})",
                    )
                    if "resource busy" in str(error).lower():
                        # Back off immediately instead of blasting more report-id retries.
                        break

            if not raw_reply and last_error is not None:
                self._log_diagnostic("rx_empty", str(last_error).encode(), "no telemetry response; keeping last frame")
                self._consecutive_telemetry_failures += 1
                # After 10 consecutive timeouts, mark as disconnected to signal UI that telemetry is unavailable.
                if self._consecutive_telemetry_failures >= 10:
                    self._last_frame.connected = False
                return self._last_frame

            if not raw_reply:
                self._log_diagnostic("rx_empty", b"", "no HID response")
                self._consecutive_telemetry_failures += 1
                if self._consecutive_telemetry_failures >= 10:
                    self._last_frame.connected = False
                return self._last_frame

            try:
                self._log_diagnostic("rx", raw_reply, "raw HID reply")
                message = _extract_csafe_payload(raw_reply)
                if message is None:
                    self._log_diagnostic("rx_invalid", raw_reply, "failed to parse CSAFE frame")
                    return self._last_frame
                self._log_diagnostic("rx_parsed", message, "parsed CSAFE payload")
                new_frame = self._decode_monitor_payload(message)
                # Preserve connected flag from previous frame to track telemetry availability
                new_frame.connected = self._last_frame.connected
                self._last_frame = new_frame
                self._consecutive_telemetry_failures = 0  # Reset on successful parse
            except (ValueError, IndexError, KeyError):
                self._log_diagnostic("rx_invalid", raw_reply, "failed to parse HID reply")
                self._consecutive_telemetry_failures += 1
                if self._consecutive_telemetry_failures >= 10:
                    self._last_frame.connected = False
                return self._last_frame
            return self._last_frame

    async def _prime_monitor(self) -> None:
        # PM3 may ignore workout telemetry until it has entered the in-use state.
        await asyncio.to_thread(self._send_command_no_reply, bytes([GO_IN_USE]))

    def _send_command_no_reply(self, command_payload: bytes) -> None:
        if self._usb_dev is None:
            return
        frame = _build_csafe_frame(command_payload)
        last_error: Exception | None = None
        for report_id in _report_fallback_order(self._report_id):
            try:
                request = _build_report(frame, report_id)
                self._log_diagnostic(
                    "tx",
                    request,
                    f"sent PM3 init command (report_id=0x{report_id:02x})",
                )
                self._usb_dev.write(self._out_ep, request, timeout=1500)
                try:
                    raw = bytes(self._usb_dev.read(self._in_ep, len(request), timeout=250))
                    if raw:
                        self._log_diagnostic("rx", raw, "raw reply to PM3 init command")
                except Exception:
                    pass
                self._report_id = report_id
                return
            except Exception as error:
                last_error = error
        if last_error is not None:
            self._log_diagnostic("rx_error", str(last_error).encode(), "PM3 init command failed")

    def _write_then_read(self, request: bytes) -> bytes:
        self._usb_dev.write(self._out_ep, request, timeout=1500)
        return bytes(self._usb_dev.read(self._in_ep, len(request), timeout=1500))

    def _log_diagnostic(self, direction: str, payload: bytes, note: str | None = None) -> None:
        if not self._diagnostics_service:
            return
        self._diagnostics_service.log_event(
            lane_id=self.lane_id,
            port=self.device_path,
            direction=direction,
            payload=payload,
            note=note,
        )

    @staticmethod
    def _decode_monitor_payload(message: bytes) -> PM3Frame:
        parsed = _parse_response_payload(message)

        elapsed_s = 0.0
        distance_m = 0.0
        stroke_rate = 0
        watts: float | None = None

        work_time_raw = parsed.get("pm_work_time")
        if work_time_raw and len(work_time_raw) >= 5:
            elapsed_s = (_le_int(work_time_raw[:4]) + work_time_raw[4]) / 100.0

        work_distance_raw = parsed.get("pm_work_distance")
        if work_distance_raw and len(work_distance_raw) >= 5:
            distance_m = (_le_int(work_distance_raw[:4]) + work_distance_raw[4]) / 10.0

        cadence_raw = parsed.get("cadence")
        if cadence_raw and len(cadence_raw) >= 2:
            stroke_rate = _le_int(cadence_raw[:2])

        power_raw = parsed.get("power")
        if power_raw and len(power_raw) >= 2:
            watts = float(_le_int(power_raw[:2]))

        pace_per_500_s = ((2.8 / watts) ** (1.0 / 3.0)) * 500.0 if watts and watts > 0 else 0.0

        return PM3Frame(
            elapsed_s=elapsed_s,
            distance_m=distance_m,
            pace_per_500_s=pace_per_500_s,
            stroke_rate=stroke_rate,
            watts=watts,
        )


def _le_int(raw: bytes) -> int:
    return int.from_bytes(raw, byteorder="little", signed=False)


def _xor_checksum(payload: bytes) -> int:
    value = 0
    for b in payload:
        value ^= b
    return value


def _stuff(payload: bytes) -> bytes:
    out = bytearray()
    for b in payload:
        if 0xF0 <= b <= 0xF3:
            out.append(FRAME_ESCAPE)
            out.append(b & 0x03)
        else:
            out.append(b)
    return bytes(out)


def _unstuff(payload: bytes) -> bytes:
    out = bytearray()
    idx = 0
    while idx < len(payload):
        b = payload[idx]
        if b == FRAME_ESCAPE and idx + 1 < len(payload):
            out.append(0xF0 | payload[idx + 1])
            idx += 2
            continue
        out.append(b)
        idx += 1
    return bytes(out)


def _build_csafe_frame(command_payload: bytes) -> bytes:
    message = command_payload + bytes([_xor_checksum(command_payload)])
    stuffed = _stuff(message)
    return bytes([FRAME_START]) + stuffed + bytes([FRAME_END])


def _build_monitor_command_payload() -> bytes:
    # Match PyRow ordering: PM-specific wrapped commands first, then generic commands.
    # Every response already contains the status byte, so GET_STATUS is not needed here.
    wrapped = bytes([PM_GET_WORKTIME, PM_GET_WORKDISTANCE])
    return bytes([
        PM_WRAPPER,
        len(wrapped),
    ]) + wrapped + bytes([
        GET_CADENCE,
        GET_POWER,
    ])


def _report_fallback_order(preferred: int) -> tuple[int, ...]:
    ordered = [preferred, 0x02, 0x04, 0x01]
    deduped: list[int] = []
    for report_id in ordered:
        if report_id not in deduped:
            deduped.append(report_id)
    return tuple(deduped)


def _build_report(frame: bytes, report_id: int) -> bytes:
    size = REPORT_SIZES.get(report_id)
    if not size:
        raise ValueError(f"Unsupported report id: 0x{report_id:02x}")
    report = bytes([report_id]) + frame
    if len(report) > size:
        raise ValueError(f"CSAFE report too long for report id 0x{report_id:02x}")
    return report.ljust(size, b"\x00")


def _extract_csafe_payload(raw_report: bytes) -> bytes | None:
    try:
        start_idx = raw_report.index(FRAME_START)
        end_idx = raw_report.index(FRAME_END, start_idx + 1)
    except ValueError:
        return None

    inner = _unstuff(raw_report[start_idx + 1 : end_idx])
    if len(inner) < 2:
        return None

    payload = inner[:-1]
    checksum = inner[-1]
    if _xor_checksum(payload) != checksum:
        return None
    return payload


def _parse_response_payload(payload: bytes) -> dict[str, bytes]:
    if not payload:
        return {}

    idx = 1  # payload[0] is PM status byte
    parsed: dict[str, bytes] = {}

    while idx + 1 < len(payload):
        cmd = payload[idx]
        idx += 1
        bytecount = payload[idx]
        idx += 1

        if cmd == PM_WRAPPER:
            wrap_end = idx + bytecount
            while idx + 1 < min(wrap_end, len(payload)):
                sub_cmd = payload[idx]
                idx += 1
                sub_len = payload[idx]
                idx += 1
                sub_data = payload[idx : idx + sub_len]
                idx += sub_len
                if sub_cmd == PM_GET_WORKTIME:
                    parsed["pm_work_time"] = sub_data
                elif sub_cmd == PM_GET_WORKDISTANCE:
                    parsed["pm_work_distance"] = sub_data
            idx = max(idx, wrap_end)
            continue

        data = payload[idx : idx + bytecount]
        idx += bytecount

        if cmd == GET_CADENCE:
            parsed["cadence"] = data
        elif cmd == GET_POWER:
            parsed["power"] = data

    return parsed


def _safe_usb_string(device: Any, index: int | None) -> str:
    if not index:
        return ""
    try:
        text = usb.util.get_string(device, index)
        return text or ""
    except Exception:
        return ""


def _read_hid_uniq(device_path: str) -> str:
    if device_path.startswith("usb:"):
        return device_path.split(":", 1)[1].strip()

    dev_name = Path(device_path).name
    uevent_path = Path(f"/sys/class/hidraw/{dev_name}/device/uevent")
    if not uevent_path.exists():
        return ""
    try:
        for line in uevent_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("HID_UNIQ="):
                return line.split("=", 1)[1].strip()
    except OSError:
        return ""
    return ""


def _open_pm3_usb_device(hid_uniq: str) -> tuple[Any, int, int]:
    devices = list(
        usb.core.find(
            find_all=True,
            idVendor=PM3_VENDOR_ID,
            idProduct=PM3_PRODUCT_ID,
        )
        or []
    )
    if not devices:
        raise RuntimeError("No PM3 USB device found via libusb")

    selected = None
    if hid_uniq:
        for dev in devices:
            serial = _safe_usb_string(dev, getattr(dev, "iSerialNumber", None))
            if serial == hid_uniq:
                selected = dev
                break

    if selected is None:
        selected = devices[0]

    try:
        if selected.is_kernel_driver_active(0):
            selected.detach_kernel_driver(0)
    except Exception:
        pass

    try:
        selected.set_configuration()
    except Exception:
        pass

    cfg = selected.get_active_configuration()
    iface = cfg[(0, 0)]

    in_ep = None
    out_ep = None
    for endpoint in iface:
        direction = usb.util.endpoint_direction(endpoint.bEndpointAddress)
        if direction == usb.util.ENDPOINT_IN:
            in_ep = endpoint.bEndpointAddress
        elif direction == usb.util.ENDPOINT_OUT:
            out_ep = endpoint.bEndpointAddress

    if in_ep is None or out_ep is None:
        raise RuntimeError("Could not resolve PM3 USB endpoints")

    return selected, in_ep, out_ep


def discover_pm3_usb_devices() -> list[str]:
    """Discover PM3 monitors directly via libusb and return usb:<serial> identifiers."""
    if usb is None:
        return []

    discovered: list[str] = []
    seen_serials: set[str] = set()

    try:
        devices = list(
            usb.core.find(
                find_all=True,
                idVendor=PM3_VENDOR_ID,
                idProduct=PM3_PRODUCT_ID,
            )
            or []
        )
    except Exception:
        return []

    for dev in devices:
        serial = _safe_usb_string(dev, getattr(dev, "iSerialNumber", None)).strip()
        if not serial:
            serial = f"bus{getattr(dev, 'bus', 0)}-addr{getattr(dev, 'address', 0)}"
        if serial in seen_serials:
            continue
        seen_serials.add(serial)
        discovered.append(f"usb:{serial}")

    return discovered


def discover_pm3_hid_devices() -> list[str]:
    """Discover PM3 monitors connected via USB HID (/dev/hidraw*)."""
    discovered: list[str] = []
    seen_units: set[str] = set()

    for hidraw_path in sorted(Path("/dev").glob("hidraw*")):
        dev_path = str(hidraw_path)
        is_pm3 = False
        hid_uniq = ""

        # Check uevent for HID name
        info_path = Path(f"/sys/class/hidraw/{hidraw_path.name}/device/uevent")
        if info_path.exists():
            try:
                content = info_path.read_text(encoding="utf-8", errors="ignore")
                if "Concept2" in content or "0425:0000" in content:
                    is_pm3 = True
                for line in content.splitlines():
                    if line.startswith("HID_UNIQ="):
                        hid_uniq = line.split("=", 1)[1].strip()
                        break
            except (OSError, PermissionError):
                pass

        # Also check device name via sysfs
        if not is_pm3:
            name_path = Path(f"/sys/class/hidraw/{hidraw_path.name}/device/name")
            if name_path.exists():
                try:
                    name = name_path.read_text(encoding="utf-8", errors="ignore").strip()
                    if "Concept2" in name or "PM3" in name:
                        is_pm3 = True
                except (OSError, PermissionError):
                    pass

        if is_pm3:
            unit_key = hid_uniq or dev_path
            if unit_key in seen_units:
                continue
            seen_units.add(unit_key)
            discovered.append(dev_path)

    return discovered


def _running_in_wsl() -> bool:
    if os.getenv("WSL_DISTRO_NAME"):
        return True

    try:
        kernel_release = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    lowered = kernel_release.lower()
    return "microsoft" in lowered or "wsl" in lowered


def _build_connect_hint() -> str:
    if _running_in_wsl():
        return (
            " (WSL hint: attach PM3 from Windows first: usbipd list, usbipd bind --busid X-Y, "
            "usbipd attach --wsl --busid X-Y. If libusb access still fails, use WinUSB driver on Windows "
            "for the PM3 USB interface.)"
        )

    return (
        " (zkus: sudo cp deploy/raspi/99-pm3-hid.rules /etc/udev/rules.d/ && "
        "sudo udevadm control --reload-rules && sudo udevadm trigger)"
    )
