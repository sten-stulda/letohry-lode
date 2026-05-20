"""HID-based communication with Concept2 PM3 monitors."""
from __future__ import annotations

import asyncio
import select
import struct
from pathlib import Path
from time import monotonic

from ..config import AppConfig
from ..models import PM3Frame
from ..services.diagnostics import DiagnosticsService
from .csafe import CSAFECommand, build_frame, parse_frame

GET_WORKOUT_DATA = 0xA0

# Concept2 PM3 USB HID identifiers
PM3_VENDOR_ID = 0x0425
PM3_PRODUCT_ID = 0x0000


class PM3HIDMonitor:
    """Communicate with Concept2 PM3 via USB HID (/dev/hidraw*)."""

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
        self._fd: int | None = None
        self._last_frame = PM3Frame()
        self._read_lock = asyncio.Lock()
        self._diagnostics_service = diagnostics_service

    async def connect(self) -> None:
        last_error: Exception | None = None
        for attempt in range(self.connect_retries):
            try:
                self._fd = await asyncio.to_thread(
                    lambda: open(self.device_path, "r+b", buffering=0)
                )
                self._log_diagnostic("connect", self.device_path.encode(), "connected")
                return
            except (OSError, PermissionError) as error:
                last_error = error
                self._log_diagnostic("connect_error", str(error).encode(), "connect failed")
                await asyncio.sleep(0.3)

        perm_hint = ""
        if isinstance(last_error, PermissionError):
            perm_hint = " (zkus: sudo usermod -aG plugdev $USER, pak odhlaš/přihlaš)"
        raise RuntimeError(
            f"Failed to connect to PM3 on {self.device_path}: {last_error}{perm_hint}"
        )

    async def disconnect(self) -> None:
        if self._fd is not None:
            await asyncio.to_thread(self._fd.close)
        self._fd = None

    async def reset(self) -> None:
        self._last_frame = PM3Frame()

    async def read_frame(self) -> PM3Frame:
        if self._fd is None:
            raise RuntimeError("PM3 HID monitor is not connected.")

        async with self._read_lock:
            request = build_frame(CSAFECommand(command_id=GET_WORKOUT_DATA))
            # Some PM3 HID endpoints expect report ID prefix 0x00, some do not.
            # Try both to keep polling resilient across kernels/firmware.
            raw_reply = b""
            last_error: Exception | None = None
            for with_report_id in (True, False):
                try:
                    hid_request = _build_hid_request(request, with_report_id=with_report_id)
                    mode = "with-report-id" if with_report_id else "without-report-id"
                    self._log_diagnostic("tx", hid_request, f"sent HID workout data request ({mode})")
                    await asyncio.to_thread(self._fd.write, hid_request)
                    await asyncio.to_thread(self._fd.flush)
                    # Linux hidraw commonly returns 64-byte reports without explicit report ID.
                    # Wait for readability first to avoid an unbounded blocking read.
                    raw_reply = await asyncio.to_thread(_read_hid_report, self._fd, 64, 0.25)
                    if raw_reply:
                        break
                except (OSError, IOError) as error:
                    last_error = error
                    self._log_diagnostic("rx_error", str(error).encode(), "HID read failed")

            if not raw_reply and last_error is not None:
                raise RuntimeError(
                    f"PM3 HID read failed on {self.device_path}: {last_error}"
                ) from last_error

            if not raw_reply:
                self._log_diagnostic("rx_empty", b"", "no HID response")
                return self._last_frame

            frame_start_idx = raw_reply.find(0xF1)
            if frame_start_idx == -1:
                self._log_diagnostic("rx_empty", raw_reply, "no CSAFE frame start marker")
                return self._last_frame

            # PM3 HID reports are fixed-size with zero padding after FRAME_END (0xF2).
            frame_end_idx = raw_reply.find(0xF2, frame_start_idx)
            if frame_end_idx == -1:
                self._log_diagnostic("rx_empty", raw_reply, "no CSAFE frame end marker")
                return self._last_frame

            reply_payload = raw_reply[frame_start_idx : frame_end_idx + 1]

            try:
                self._log_diagnostic("rx", raw_reply, "raw HID reply")
                message = parse_frame(reply_payload)
                self._log_diagnostic("rx_parsed", message, "parsed CSAFE payload")
                self._last_frame = self._decode_workout_data(message)
            except (ValueError, IndexError):
                self._log_diagnostic("rx_invalid", raw_reply, "failed to parse HID reply")
                return self._last_frame
            return self._last_frame

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
    def _decode_workout_data(message: bytes) -> PM3Frame:
        if len(message) < 8:
            raise ValueError("PM3 reply is too short for workout telemetry.")

        values = list(_chunk_bytes(message, 2))
        elapsed_s = int.from_bytes(values[0], byteorder="big") / 10
        distance_m = int.from_bytes(values[1], byteorder="big") / 10
        pace_per_500_s = float(int.from_bytes(values[2], byteorder="big"))
        stroke_rate = int.from_bytes(values[3], byteorder="big")
        watts = int.from_bytes(values[4], byteorder="big") if len(values) > 4 else None
        return PM3Frame(
            elapsed_s=elapsed_s,
            distance_m=distance_m,
            pace_per_500_s=pace_per_500_s,
            stroke_rate=stroke_rate,
            watts=watts,
        )


def _chunk_bytes(payload: bytes, size: int):
    for index in range(0, len(payload), size):
        yield payload[index : index + size]


def _read_hid_report(fd, size: int = 64, timeout_s: float = 0.25) -> bytes:
    ready, _, _ = select.select([fd.fileno()], [], [], timeout_s)
    if not ready:
        return b""
    return fd.read(size)


def _build_hid_request(payload: bytes, with_report_id: bool = True) -> bytes:
    if with_report_id:
        return (bytes([0x00]) + payload).ljust(64, b"\x00")
    return payload.ljust(64, b"\x00")


def discover_pm3_hid_devices() -> list[str]:
    """Discover PM3 monitors connected via USB HID (/dev/hidraw*)."""
    discovered: list[str] = []

    for hidraw_path in sorted(Path("/dev").glob("hidraw*")):
        dev_path = str(hidraw_path)
        is_pm3 = False

        # Check uevent for HID name
        info_path = Path(f"/sys/class/hidraw/{hidraw_path.name}/device/uevent")
        if info_path.exists():
            try:
                content = info_path.read_text(encoding="utf-8", errors="ignore")
                if "Concept2" in content or "0425:0000" in content:
                    is_pm3 = True
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
            discovered.append(dev_path)

    return discovered
