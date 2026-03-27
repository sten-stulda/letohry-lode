from __future__ import annotations

import uvicorn

from backend.config import get_config


if __name__ == "__main__":
    config = get_config()
    uvicorn.run("backend.main:app", host=config.host, port=config.port, reload=False)