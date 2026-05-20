"""PyUSB diagnostic for Concept2 PM3 using CSAFE framing similar to PyRow.

This script does not depend on legacy Python 2 PyRow code.
It probes PM3 devices via USB interrupt endpoints and tries multiple report IDs.
"""
from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Iterable

try:
    import usb.core
    import usb.util
except ImportError as exc:
    print("Missing dependency: pyusb. Install with: pip install pyusb")
    raise SystemExit(3) from exc


VENDOR_IDS = (0x0425, 0x17A4)
INTERFACE = 0
TIMEOUT_MS = 1500

FRAME_START = 0xF1
FRAME_END = 0xF2
FRAME_ESCAPE = 0xF3


@dataclass(slots=True)
class PM3UsbDevice:
    device: usb.core.Device
    in_ep: int
    out_ep: int
    serial_hint: str


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
    i = 0
    while i < len(payload):
        b = payload[i]
        if b == FRAME_ESCAPE and i + 1 < len(payload):
            out.append(0xF0 | payload[i + 1])
            i += 2
            continue
        out.append(b)
        i += 1
    return bytes(out)


def build_csafe_frame(commands: bytes) -> bytes:
    checksum = _xor_checksum(commands)
    stuffed = _stuff(commands + bytes([checksum]))
    return bytes([FRAME_START]) + stuffed + bytes([FRAME_END])


def build_report(frame: bytes, report_id: int) -> bytes:
    if report_id == 0x01:
        total = 21
    elif report_id == 0x04:
        total = 63
    elif report_id == 0x02:
        total = 121
    else:
        raise ValueError(f"Unsupported report id: {report_id}")

    report = bytes([report_id]) + frame
    if len(report) > total:
        raise ValueError(f"Report too long for report id 0x{report_id:02x}: {len(report)} > {total}")
    return report.ljust(total, b"\x00")


def _device_id(dev: usb.core.Device) -> str:
    return f"bus={dev.bus} addr={dev.address} vid=0x{dev.idVendor:04x} pid=0x{dev.idProduct:04x}"


def _safe_get_string(dev: usb.core.Device, index: int | None) -> str:
    if not index:
        return ""
    try:
        return usb.util.get_string(dev, index) or ""
    except usb.core.USBError:
        return ""


def _iter_pm3_devices() -> Iterable[usb.core.Device]:
    for vid in VENDOR_IDS:
        found = usb.core.find(find_all=True, idVendor=vid)
        if not found:
            continue
        for dev in found:
            if dev.idProduct == 0x0000:
                yield dev


def _open_pm3_device(dev: usb.core.Device) -> PM3UsbDevice:
    if sys.platform != "win32":
        try:
            if dev.is_kernel_driver_active(INTERFACE):
                dev.detach_kernel_driver(INTERFACE)
        except (NotImplementedError, usb.core.USBError):
            pass

    try:
        dev.set_configuration()
    except usb.core.USBError:
        # Often already configured/busy on Linux; keep going like PyRow does.
        pass

    cfg = dev.get_active_configuration()
    iface = cfg[(INTERFACE, 0)]

    in_ep = None
    out_ep = None
    for ep in iface:
        direction = usb.util.endpoint_direction(ep.bEndpointAddress)
        if direction == usb.util.ENDPOINT_IN:
            in_ep = ep.bEndpointAddress
        elif direction == usb.util.ENDPOINT_OUT:
            out_ep = ep.bEndpointAddress

    if in_ep is None or out_ep is None:
        raise RuntimeError(f"Could not resolve IN/OUT endpoints for {_device_id(dev)}")

    serial_hint = _safe_get_string(dev, getattr(dev, "iSerialNumber", None))
    return PM3UsbDevice(device=dev, in_ep=in_ep, out_ep=out_ep, serial_hint=serial_hint)


def decode_response(raw: bytes) -> bytes | None:
    if not raw:
        return None

    # Report ID is first byte. CSAFE frame starts at raw[1].
    try:
        start_idx = raw.index(FRAME_START)
        end_idx = raw.index(FRAME_END, start_idx + 1)
    except ValueError:
        return None

    body = _unstuff(raw[start_idx + 1 : end_idx])
    if len(body) < 2:
        return None

    payload = body[:-1]
    checksum = body[-1]
    if _xor_checksum(payload) != checksum:
        return None
    return payload


def probe_device(pm3: PM3UsbDevice) -> bool:
    dev = pm3.device
    print("\n" + "=" * 72)
    print(f"USB device: {_device_id(dev)} serial={pm3.serial_hint or '-'}")
    print(f"Endpoints: IN=0x{pm3.in_ep:02x} OUT=0x{pm3.out_ep:02x}")

    # Start with simple command: CSAFE_GETSTATUS_CMD (0x80).
    frame = build_csafe_frame(bytes([0x80]))

    got_valid = False
    for report_id in (0x01, 0x04, 0x02):
        try:
            tx = build_report(frame, report_id)
            written = dev.write(pm3.out_ep, tx, timeout=TIMEOUT_MS)
            rx = bytes(dev.read(pm3.in_ep, len(tx), timeout=TIMEOUT_MS))
            payload = decode_response(rx)

            print(f"TX report 0x{report_id:02x}: wrote={written} bytes, first={tx[:12].hex(' ')}")
            print(f"RX report 0x{report_id:02x}: len={len(rx)}, first={rx[:16].hex(' ')}")
            if payload is None:
                print("  parse: invalid/no CSAFE frame")
                continue

            print(f"  parse: ok payload={payload.hex(' ')}")
            got_valid = True
        except usb.core.USBError as exc:
            print(f"TX/RX report 0x{report_id:02x}: USBError: {exc}")
        except Exception as exc:  # diagnostic script; keep probing
            print(f"TX/RX report 0x{report_id:02x}: ERROR: {exc}")

    usb.util.dispose_resources(dev)
    return got_valid


def main() -> int:
    devices = list(_iter_pm3_devices())
    if not devices:
        print("No PM3 USB device found (VID 0x0425 or 0x17a4, PID 0x0000).")
        return 1

    print(f"Found PM3 USB devices: {len(devices)}")

    ok_count = 0
    for dev in devices:
        try:
            pm3 = _open_pm3_device(dev)
        except Exception as exc:
            print("\n" + "=" * 72)
            print(f"USB device: {_device_id(dev)}")
            print(f"Open failed: {exc}")
            continue

        if probe_device(pm3):
            ok_count += 1

    print("\n" + "-" * 72)
    print(f"Devices with valid CSAFE response: {ok_count}/{len(devices)}")
    return 0 if ok_count else 2


if __name__ == "__main__":
    raise SystemExit(main())
