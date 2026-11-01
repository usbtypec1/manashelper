"""Serve the locally built Vue editor without exposing the source tree."""

from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

EDITOR_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
)


def install_editor(app: FastAPI, directory: Path) -> bool:
    index = directory / "index.html"
    assets = directory / "assets"
    if not index.is_file() or not assets.is_dir():
        return False

    async def page() -> FileResponse:
        # Vue Flow positions nodes through style attributes; scripts remain external and same-origin.
        return FileResponse(index, headers={"Content-Security-Policy": EDITOR_CSP})

    app.add_api_route("/admin/", page, methods=["GET"], include_in_schema=False)
    app.mount("/admin/assets", StaticFiles(directory=assets), name="admin-assets")
    return True
