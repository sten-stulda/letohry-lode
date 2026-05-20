#!/usr/bin/env python3
"""Debug: Compare STATUS (working) vs TELEMETRY (failing) commands"""

import asyncio
from pathlib import Path
import usb.core
import usb.util
from backend.pm3.device import discover_pm3_usb_devices
from backend.pm3.hid_device import PM3HIDMonitor, _build_csafe_frame, _build_report
from backend.services.diagnostics import DiagnosticsService

# CSAFE commands
GET_STATUS = 0x80
GET_WORKTIME = 0xA0
GO_IN_USE = 0x85

def _build_status_frame():
    """Build status request (known to work)"""
    payload = bytes([GET_STATUS])
    return _build_csafe_frame(payload)

def _build_telemetry_frame():
    """Build telemetry request (known to fail)"""
    payload = bytes([0x1A, 0x02, GET_WORKTIME, 0xA3, 0xA7, 0xB4])  # PM_WRAPPER + fields
    return _build_csafe_frame(payload)

async def debug_commands():
    """Compare status vs telemetry"""
    
    print("=" * 80)
    print("PM3 COMMAND COMPARISON: STATUS vs TELEMETRY")
    print("=" * 80)
    
    devices = discover_pm3_usb_devices()
    if not devices:
        print("❌ No PM3 devices found!")
        return
    
    device_path = devices[0]
    print(f"\n→ Using device: {device_path}")
    
    diag = DiagnosticsService(
        enabled=True,
        log_path=Path("data/pm3-debug-compare.log"),
        max_events=1000
    )
    
    monitor = PM3HIDMonitor(
        lane_id=1,
        name="Debug",
        device_path=device_path,
        diagnostics_service=diag
    )
    
    try:
        await monitor.connect()
        print("✓ Connected to PM3\n")
        
        # Test 1: STATUS command
        print("=" * 80)
        print("TEST 1: STATUS COMMAND (expected to work)")
        print("=" * 80)
        
        status_frame = _build_status_frame()
        status_request = _build_report(status_frame, 0x02)
        
        print(f"Request (121 bytes report_id=0x02):")
        print(f"  Frame hex: {status_frame.hex()}")
        print(f"  Request[0:10]: {status_request[0:10].hex()}")
        
        try:
            monitor._usb_dev.write(monitor._out_ep, status_request, timeout=1500)
            status_response = bytes(monitor._usb_dev.read(monitor._in_ep, 121, timeout=1500))
            print(f"✓ Got {len(status_response)} bytes back")
            print(f"  Response[0:20]: {status_response[0:20].hex()}")
        except Exception as e:
            print(f"❌ Status read failed: {e}")
        
        print()
        
        # Test 2: TELEMETRY command  
        print("=" * 80)
        print("TEST 2: TELEMETRY COMMAND (expected to fail)")
        print("=" * 80)
        
        telemetry_frame = _build_telemetry_frame()
        telemetry_request = _build_report(telemetry_frame, 0x02)
        
        print(f"Request (121 bytes report_id=0x02):")
        print(f"  Frame hex: {telemetry_frame.hex()}")
        print(f"  Request[0:10]: {telemetry_request[0:10].hex()}")
        
        try:
            monitor._usb_dev.write(monitor._out_ep, telemetry_request, timeout=1500)
            telemetry_response = bytes(monitor._usb_dev.read(monitor._in_ep, 121, timeout=1500))
            print(f"✓ Got {len(telemetry_response)} bytes back")
            print(f"  Response[0:20]: {telemetry_response[0:20].hex()}")
        except Exception as e:
            print(f"❌ Telemetry read failed: {e}")
        
        print()
        
        # Test 3: Try GO_IN_USE first, then telemetry
        print("=" * 80)
        print("TEST 3: GO_IN_USE + TELEMETRY (maybe state matters?)")
        print("=" * 80)
        
        go_in_use_frame = _build_csafe_frame(bytes([GO_IN_USE]))
        go_in_use_request = _build_report(go_in_use_frame, 0x02)
        
        print(f"Sending GO_IN_USE...")
        try:
            monitor._usb_dev.write(monitor._out_ep, go_in_use_request, timeout=1500)
            print("✓ Wrote GO_IN_USE")
        except Exception as e:
            print(f"❌ GO_IN_USE write failed: {e}")
        
        await asyncio.sleep(0.5)
        
        print(f"Now sending TELEMETRY...")
        try:
            monitor._usb_dev.write(monitor._out_ep, telemetry_request, timeout=1500)
            telemetry_response = bytes(monitor._usb_dev.read(monitor._in_ep, 121, timeout=1500))
            print(f"✓ Got {len(telemetry_response)} bytes back!")
            print(f"  Response[0:20]: {telemetry_response[0:20].hex()}")
        except Exception as e:
            print(f"❌ Telemetry still failed: {e}")
        
        await monitor.disconnect()
        print("\n✓ Disconnected")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_commands())
