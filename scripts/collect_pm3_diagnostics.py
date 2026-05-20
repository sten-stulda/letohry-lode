#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def _fetch(url: str) -> bytes:
    with urlopen(url, timeout=10) as response:  # nosec B310 - local diagnostics endpoint
        return response.read()


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect PM3 diagnostics from local API.")
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    parser.add_argument("output_dir", nargs="?", default="./data/pm3-capture")
    args = parser.parse_args()

    base_url = _normalize_base_url(args.base_url)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir = Path(args.output_dir) / stamp
    target_dir.mkdir(parents=True, exist_ok=True)

    endpoints = {
        "status.json": f"{base_url}/api/status",
        "diagnostics-status.json": f"{base_url}/api/diagnostics/status",
        "diagnostics-events.json": f"{base_url}/api/diagnostics/events?limit=200",
        "pm3-diagnostics.log": f"{base_url}/api/diagnostics/export",
    }

    print(f"Collecting PM3 diagnostics into {target_dir}")

    try:
        for file_name, endpoint in endpoints.items():
            payload = _fetch(endpoint)
            _write_bytes(target_dir / file_name, payload)
    except (HTTPError, URLError, OSError) as error:
        print(f"Diagnostics collection failed: {error}")
        return 1

    print("Saved files:")
    for file_name in endpoints:
        print(f"  {target_dir / file_name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
