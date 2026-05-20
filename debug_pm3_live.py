#!/usr/bin/env python3
"""Live PM3 communication debugger - shows exactly what's being sent/received"""

import asyncio
from pathlib import Path
import usb.core
import usb.util
from backend.pm3.device import discover_pm3_usb_devices
from backend.pm3.hid_device import PM3HIDMonitor
from backend.services.diagnostics import DiagnosticsService

async def debug_pm3_communication():
    """Connect to PM3 and show detailed communication logs"""
    
    print("=" * 80)
    print("PM3 LIVE COMMUNICATION DEBUGGER")
    print("=" * 80)
    
    # Find PM3 devices
    devices = discover_pm3_usb_devices()
    if not devices:
        print("❌ No PM3 devices found!")
        return
    
    print(f"✓ Found {len(devices)} PM3 device(s):")
    for i, device in enumerate(devices):
        print(f"  {i+1}. USB {device}")
    
    # Create diagnostics service to capture logs
    diag = DiagnosticsService(
        enabled=True,
        log_path=Path("data/pm3-diagnostics-debug.log"),
        max_events=1000
    )
    
    # Connect to first device
    device_path = devices[0]
    print(f"\n→ Connecting to {device_path}...")
    
    try:
        monitor = PM3HIDMonitor(
            lane_id=1,
            name="Debug PM3 Lane 1",
            device_path=device_path,
            diagnostics_service=diag
        )
        
        await monitor.connect()
        print("✓ Connected!")
        
        # Now read frames and show diagnostics
        print("\n" + "=" * 80)
        print("READING TELEMETRY (showing first 15 reads with diagnostics)")
        print("=" * 80)
        
        for read_num in range(15):
            print(f"\n[Read {read_num + 1}]")
            frame = await monitor.read_frame()
            
            print(f"  connected={frame.connected}, "
                  f"distance={frame.distance_m}m, "
                  f"elapsed={frame.elapsed_s}s, "
                  f"stroke_rate={frame.stroke_rate}")
            
            # Show diagnostics for this read
            recent = diag.recent_events(limit=10)
            if recent:
                print("  Recent diagnostics:")
                for event in recent[-3:]:
                    direction = event.direction
                    note = event.note or ''
                    note_short = (note[:50] + '...') if len(note) > 50 else note
                    payload_len = len(event.payload_hex.split()) if event.payload_hex else 0
                    print(f"    [{direction:5}] {note_short:50} ({payload_len} bytes)")
            
            await asyncio.sleep(0.5)
        
        await monitor.disconnect()
        print("\n✓ Disconnected")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_pm3_communication())
