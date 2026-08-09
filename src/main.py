"""Valet server entrypoint."""
from __future__ import annotations

import uvicorn

from . import config
from .api import app


def main() -> None:
    uvicorn.run(
        "src.api:app",
        host=str(config.VALET_HOST),
        port=config.VALET_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
