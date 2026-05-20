"""Raw HID diagnostic – prints exactly what PM3 sends back."""
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


def send_and_receive(device_path: str, payload: bytes, label: str) -> None:
    print(f"\n=== {label} ===")
    request = (bytes([0x00]) + payload).ljust(64, b"\x00")
    print(f"TX ({len(request)} B): {request[:16].hex(' ')} ...")
    try:
        with open(device_path, "r+b", buffering=0) as fd:
            fd.write(request)
            ready, _, _ = select.select([fd.fileno()], [], [], 0.5)
            if not ready:
                print("RX: timeout (zadna data do 500 ms)")
                return
            raw = fd.read(64)
        print(f"RX ({len(raw)} B): {raw.hex(' ')}")
        # Najdi CSAFE rámec
        if 0xF1 in raw and 0xF2 in raw:
            start = raw.index(0xF1)
            end = raw.index(0xF2, start)
            frame = raw[start:end+1]
            print(f"  CSAFE frame: {frame.hex(' ')}")
            inner = frame[1:-1]
            print(f"  Inner bytes: {inner.hex(' ')}")
        else:
            print("  Žádný CSAFE rámec nenalezen (0xF1/0xF2 chybí)")
    except Exception as e:
        print(f"  CHYBA: {e}")


print(f"Testování PM3 na {DEVICE}")
send_and_receive(DEVICE, CSAFE_WITH_LEN, "0xA0 s length byte (aktuální kód)")
send_and_receive(DEVICE, CSAFE_SHORT,    "0xA0 bez length byte (short CSAFE)")
send_and_receive(DEVICE, CSAFE_MULTI,    "Více příkazů: 0xA0 0xA1 0xA5 0xA7 0xB4")
