"""Serve only built editor assets; the official Mini App SDK has a narrow CSP source."""

from pathlib import Path

from aiohttp import web

EDITOR_CSP = (
    "default-src 'none'; script-src 'self' https://telegram.org/js/telegram-web-app.js; "
    "style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; "
    "frame-ancestors https://web.telegram.org; form-action 'none'"
)


def install_editor(app: web.Application, directory: Path) -> bool:
    index, assets = directory / "index.html", directory / "assets"
    if directory.is_symlink() or index.is_symlink() or assets.is_symlink():
        return False
    if not index.is_file() or not assets.is_dir():
        return False

    async def page(request: web.Request) -> web.FileResponse:
        return web.FileResponse(index, headers={"Content-Security-Policy": EDITOR_CSP})

    app.router.add_get("/admin/", page)
    app.router.add_static("/admin/assets/", assets, show_index=False, follow_symlinks=False)
    return True
