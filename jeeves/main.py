"""Jeeves server entrypoint."""
from __future__ import annotations

import uvicorn

from . import config
from .api import app


def main() -> None:
    uvicorn.run(
        "jeeves.api:app",
        host=str(config.JEEVES_HOST),
        port=config.JEEVES_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
