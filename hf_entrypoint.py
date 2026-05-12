"""
Hugging Face Spaces entrypoint.

- Default: in-memory mock FastAPI (no Postgres/Redis) — reliable on free Spaces.
- Full stack: set USE_FULL_BACKEND=true and DATABASE_URL to a reachable Postgres
  (plus secrets in the Space). Runs uvicorn from backend/ with src.app:app.
"""

from __future__ import annotations

import os
import sys


def _use_full_backend() -> bool:
    """Use full FastAPI app when USE_FULL_BACKEND is set or DATABASE_URL is remote."""
    if os.environ.get("USE_FULL_BACKEND", "").lower() in ("1", "true", "yes"):
        return True
    database_url = (
        os.environ.get("DATABASE_URL", "")
        or os.environ.get("database_url", "")
    ).strip()
    if not database_url:
        return False
    lowered = database_url.lower()
    if "localhost" in lowered or "127.0.0.1" in lowered:
        return False
    return True


def main() -> None:
    repo_root = os.path.dirname(os.path.abspath(__file__))
    port = int(os.environ.get("PORT", "7860"))
    host = "0.0.0.0"

    if _use_full_backend():
        backend_dir = os.path.join(repo_root, "backend")
        os.chdir(backend_dir)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        import uvicorn

        uvicorn.run("src.app:app", host=host, port=port)
    else:
        os.chdir(repo_root)
        import uvicorn

        uvicorn.run("mock_backend:app", host=host, port=port)


if __name__ == "__main__":
    main()
