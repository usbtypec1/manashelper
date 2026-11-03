import json
import secrets

from aiogram.utils.i18n import gettext as _
from aiohttp import web

from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html


async def login_page(request: web.Request) -> web.Response:
    with i18n.context(), i18n.use_locale("en"):
        title = _("ui_flows.web.title")
        messages = {
            "waiting": _("ui_flows.web.waiting"),
            "ready": _("ui_flows.web.ready"),
            "failed": _("ui_flows.web.failed"),
            "login": _("ui_flows.web.login"),
        }
    nonce = secrets.token_urlsafe(16)
    payload = json.dumps(messages, ensure_ascii=False).replace("<", "\\u003c")
    # The ticket is removed before fetch; neither storage nor query parameters contain it.
    content = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape_html(title)}</title>
<style nonce="{nonce}">body{{font:18px system-ui;max-width:640px;margin:15vh auto;padding:24px;line-height:1.5}}</style>
</head><body><h1>{escape_html(title)}</h1><p id="status">{escape_html(messages["waiting"])}</p>
<script nonce="{nonce}">
const copy={payload};
const ticket=new URLSearchParams(location.hash.slice(1)).get('ticket');
history.replaceState(null,'',location.pathname);
(async()=>{{
try{{
const response=await fetch('/admin/api/v1/auth/'+(ticket?'exchange':'session'),ticket?{{
method:'POST',credentials:'same-origin',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticket}})
}}:{{credentials:'same-origin'}});
document.getElementById('status').textContent=response.ok?copy.ready:(ticket?copy.failed:copy.login);
}}catch{{document.getElementById('status').textContent=copy.failed;}}
}})();
</script></body></html>'''
    return web.Response(
        text=content,
        content_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
            "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
        },
    )
