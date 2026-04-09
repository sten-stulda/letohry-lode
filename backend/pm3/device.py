from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import serial
from serial.tools import list_ports

from ..config import AppConfig
from ..models import PM3Frame
from ..services.diagnostics import DiagnosticsService
from .csafe import CSAFECommand, build_frame, parse_frame
from .hid_device import PM3HIDMonitor, discover_pm3_hid_devices


GET_WORKOUT_DATA = 0xA0


@dataclass(slots=True)
class DeviceInfo:
    lane_id: int
    port: str
    connected: bool = False


class RowingMonitor:
    def __init__(self, lane_id: int, name: str) -> None:
        self.lane_id = lane_id
        self.name = name

    async def connect(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def reset(self) -> None:
        raise NotImplementedError

    async def read_frame(self) -> PM3Frame:
        raise NotImplementedError


class MockRowingMonitor(RowingMonitor):
    def __init__(self, lane_id: int, name: str, speed_multiplier: float = 1.0) -> None:
        super().__init__(lane_id=lane_id, name=name)
        self._start = monotonic()
        self._distance_m = 0.0
        self._elapsed_s = 0.0
        self._speed_multiplier = max(speed_multiplier, 0.1)

    async def connect(self) -> None:
        self._start = monotonic()

    async def disconnect(self) -> None:
        return None

    async def reset(self) -> None:
        self._start = monotonic()
        self._distance_m = 0.0
        self._elapsed_s = 0.0

    async def read_frame(self) -> PM3Frame:
        self._elapsed_s = monotonic() - self._start
        tick_seconds = 0.25
        base_speed = (4.2 + (self.lane_id * 0.25)) * self._speed_multiplier
        surge = (1.1 * self._speed_multiplier) if int(self._elapsed_s) % 20 > 15 else 0.0
        self._distance_m += (base_speed + surge) * tick_seconds
        pace_seconds = max(95.0 / self._speed_multiplier, 500.0 / max(base_speed + surge, 0.1))
        stroke_rate = 24 + ((int(self._elapsed_s) + self.lane_id) % 8)
        watts = round(2.8 / ((pace_seconds / 500.0) ** 3), 1)
        return PM3Frame(
            elapsed_s=self._elapsed_s,
            distance_m=self._distance_m,
            pace_per_500_s=pace_seconds,
            stroke_rate=stroke_rate,
            watts=watts,
        )


class PM3SerialMonitor(RowingMonitor):
    def __init__(
        self,
        lane_id: int,
        name: str,
        port: str,
        baudrate: int = 115200,
        connect_retries: int = 3,
        diagnostics_service: DiagnosticsService | None = None,
    ) -> None:
        super().__init__(lane_id=lane_id, name=name)
        self.port = port
        self.baudrate = baudrate
        self.connect_retries = max(connect_retries, 1)
        self._serial: serial.Serial | None = None
        self._last_frame = PM3Frame()
        self._read_lock = asyncio.Lock()
        self._diagnostics_service = diagnostics_service

    async def connect(self) -> None:
        last_error: Exception | None = None
        for _ in range(self.connect_retries):
            try:
                self._serial = await asyncio.to_thread(
                    serial.Serial,
                    self.port,
                    self.baudrate,
                    timeout=0.2,
                )
                await asyncio.to_thread(self._serial.reset_input_buffer)
                await asyncio.to_thread(self._serial.reset_output_buffer)
                self._log_diagnostic("connect", self.port.encode("utf-8"), "connected")
                return
            except serial.SerialException as error:
                last_error = error
                self._log_diagnostic("connect_error", str(error).encode("utf-8"), "connect failed")
                await asyncio.sleep(0.2)
        raise RuntimeError(f"Failed to connect to PM3 on {self.port}: {last_error}")

    async def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            await asyncio.to_thread(self._serial.close)
        self._serial = None

    async def reset(self) -> None:
        self._last_frame = PM3Frame()

    async def read_frame(self) -> PM3Frame:
        if not self._serial:
            raise RuntimeError("PM3 serial monitor is not connected.")

        async with self._read_lock:
            request = build_frame(CSAFECommand(command_id=GET_WORKOUT_DATA))
            self._log_diagnostic("tx", request, "sent workout data request")
            try:
                await asyncio.to_thread(self._serial.write, request)
                raw_reply = await asyncio.to_thread(self._serial.read_until, bytes((0xF2,)))
            except serial.SerialException as error:
                self._log_diagnostic("rx_error", str(error).encode("utf-8"), "serial read failed")
                raise RuntimeError(f"PM3 serial read failed on {self.port}: {error}") from error

            if not raw_reply:
                self._log_diagnostic("rx_empty", b"", "no response")
                return self._last_frame

            try:
                self._log_diagnostic("rx", raw_reply, "raw reply")
                message = parse_frame(raw_reply)
                self._log_diagnostic("rx_parsed", message, "parsed CSAFE payload")
                self._last_frame = self._decode_workout_data(message)
            except ValueError:
                self._log_diagnostic("rx_invalid", raw_reply, "failed to parse reply")
                return self._last_frame
            return self._last_frame

    def _log_diagnostic(self, direction: str, payload: bytes, note: str | None = None) -> None:
        if not self._diagnostics_service:
            return
        self._diagnostics_service.log_event(
            lane_id=self.lane_id,
            port=self.port,
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


def _chunk_bytes(payload: bytes, size: int) -> Iterable[bytes]:
    for index in range(0, len(payload), size):
        yield payload[index : index + size]


def discover_pm3_ports(config: AppConfig) -> list[str]:
    discovered: list[str] = []

    for preferred_port in config.default_serial_ports:
        if Path(preferred_port).exists():
            discovered.append(preferred_port)

    for port_info in list_ports.comports():
        haystack = " ".join(
            filter(
                None,
                [
                    port_info.device,
                    getattr(port_info, "description", ""),
                    getattr(port_info, "manufacturer", ""),
                    getattr(port_info, "product", ""),
                    getattr(port_info, "hwid", ""),
                ],
            )
        ).lower()
        if any(keyword in haystack for keyword in config.pm3_discovery_keywords):
            if port_info.device not in discovered:
                discovered.append(port_info.device)

    return discovered


def resolve_pm3_ports(config: AppConfig, expected_count: int = 2) -> list[str]:
    """Resolve PM3 device paths, trying serial ports first, then HID devices."""
    # Try serial ports first
    discovered = discover_pm3_ports(config)

    # If not enough serial ports, also try HID devices
    if len(discovered) < expected_count:
        hid_devices = discover_pm3_hid_devices()
        for hid_dev in hid_devices:
            if hid_dev not in discovered:
                discovered.append(hid_dev)
            if len(discovered) >= expected_count:
                break

    if len(discovered) < expected_count:
        # Check if we have any HID devices at all for a better error message
        hid_devices = discover_pm3_hid_devices()
        if hid_devices:
            hint = (
                f"Found {len(hid_devices)} PM3 as HID device(s) ({', '.join(hid_devices)}), "
                f"but need {expected_count}. "
                "Check USB connections or use Mock PM3."
            )
        else:
            hint = (
                "Set ROWING_PORT_1 and ROWING_PORT_2 explicitly or connect both monitors over USB."
            )
        raise RuntimeError(
            f"Not enough PM3 devices detected. "
            f"Expected {expected_count}, found {len(discovered)}. {hint}"
        )
    return discovered[:expected_count]