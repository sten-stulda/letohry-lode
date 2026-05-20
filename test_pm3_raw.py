"""Raw HID diagnostic – prints exactly what PM3 sends back."""
from __future__ import annotations

from pathlib import Path
import select
import sys

DEVICE = sys.argv[1] if len(sys.argv) > 1 else "/dev/hidraw0"

# CSAFE frame pro command 0xA0 (GET_WORKOUT_DATA) s length byte
# [0xF1, 0xA0, 0x00, 0xA0, 0xF2]  - formát s length byte (aktuální kód)
CSAFE_WITH_LEN  = bytes([0xF1, 0xA0, 0x00, 0xA0, 0xF2])

# [0xF1, 0xA0, 0xA0, 0xF2]  - formát bez length byte (krátký CSAFE příkaz)
CSAFE_SHORT     = bytes([0xF1, 0xA0, 0xA0, 0xF2])

# Více příkazů najednou: elapsed, distance, pace, cadence, power
# 0xA0 GETTWORK, 0xA1 GETHORIZONTAL, 0xA5 GETSPEED, 0xA7 GETCADENCE, 0xB4 GETPOWER
def build_multi():
    cmds = bytes([0xA0, 0xA1, 0xA5, 0xA7, 0xB4])
    chk = 0
    for b in cmds:
        chk ^= b
    return bytes([0xF1]) + cmds + bytes([chk, 0xF2])

CSAFE_MULTI = build_multi()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def list_pm3_candidates() -> list[str]:
    candidates: list[str] = []
    for hidraw in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        uevent = _read_text(hidraw / "device" / "uevent")
        name = _read_text(hidraw / "device" / "name")
        if any(token in f"{uevent} {name}" for token in ("Concept2", "PM3", "0425", "17A4", "17a4")):
            candidates.append(f"/dev/{hidraw.name}")
    return candidates


def print_device_identity(device_path: str) -> None:
    dev_name = Path(device_path).name
    sysfs = Path("/sys/class/hidraw") / dev_name / "device"
    print("\n--- Identita HID zarizeni ---")
    if not sysfs.exists():
        print(f"Sysfs path nenalezen: {sysfs}")
        return

    uevent = _read_text(sysfs / "uevent")
    name = _read_text(sysfs / "name")
    parent_uevent = _read_text(sysfs.parent / "uevent")

    if name:
        print(f"name: {name}")
    if uevent:
        print("uevent:")
        for line in uevent.splitlines():
            if any(line.startswith(prefix) for prefix in ("HID_ID=", "HID_NAME=", "HID_UNIQ=", "MODALIAS=")):
                print(f"  {line}")
    if parent_uevent:
        for line in parent_uevent.splitlines():
            if line.startswith("PRODUCT="):
                print(f"parent PRODUCT: {line}")

    candidates = list_pm3_candidates()
    print(f"PM3 kandidati v systemu: {candidates or 'zadni'}")


def _send_request(fd, payload: bytes, with_report_id: bool) -> bytes:
    if with_report_id:
        request = (bytes([0x00]) + payload).ljust(64, b"\x00")
    else:
        request = payload.ljust(64, b"\x00")
    fd.write(request)
    return request


def send_and_receive(device_path: str, payload: bytes, label: str) -> None:
    print(f"\n=== {label} ===")
    for with_report_id in (True, False):
        mode = "s report ID 0x00" if with_report_id else "bez report ID"
        try:
            with open(device_path, "r+b", buffering=0) as fd:
                request = _send_request(fd, payload, with_report_id=with_report_id)
                print(f"TX [{mode}] ({len(request)} B): {request[:16].hex(' ')} ...")
                ready, _, _ = select.select([fd.fileno()], [], [], 0.8)
                if not ready:
                    print(f"RX [{mode}]: timeout (zadna data do 800 ms)")
                    continue
                raw = fd.read(64)

            print(f"RX [{mode}] ({len(raw)} B): {raw.hex(' ')}")
            if 0xF1 in raw and 0xF2 in raw:
                start = raw.index(0xF1)
                end = raw.index(0xF2, start)
                frame = raw[start : end + 1]
                print(f"  CSAFE frame: {frame.hex(' ')}")
                inner = frame[1:-1]
                print(f"  Inner bytes: {inner.hex(' ')}")
            else:
                print("  Zadny CSAFE ramec nenalezen (0xF1/0xF2 chybi)")
        except Exception as e:
            print(f"  CHYBA [{mode}]: {e}")


print(f"Testování PM3 na {DEVICE}")
print_device_identity(DEVICE)
send_and_receive(DEVICE, CSAFE_WITH_LEN, "0xA0 s length byte (aktuální kód)")
send_and_receive(DEVICE, CSAFE_SHORT,    "0xA0 bez length byte (short CSAFE)")
send_and_receive(DEVICE, CSAFE_MULTI,    "Více příkazů: 0xA0 0xA1 0xA5 0xA7 0xB4")
