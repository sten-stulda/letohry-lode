# Test PM3 HID device detection
from backend.pm3.hid_device import discover_pm3_hid_devices

if __name__ == "__main__":
    devices = discover_pm3_hid_devices()
    print("Nalezená PM3 HID zařízení:", devices)
