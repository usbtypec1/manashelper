from aiogram import Bot
from aiogram.utils.i18n import gettext as _
from dishka import AsyncContainer

from manashelper.core.config import Settings
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html
from manashelper.platform.web.auth import AdminAuthService, web_origin


class AdminLoginCoordinator:
    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    async def open(self, bot: Bot, user_id: int) -> None:
        async with self._container() as request:
            settings = await request.get(Settings)
            locale = await (await request.get(LocaleService)).get_locale(user_id)
            theme = await (await request.get(ThemeService)).get_theme(user_id)
            if settings.admin_web_origin is None or settings.admin_web_signing_key is None:
                link = None
            else:
                ticket = await (await request.get(AdminAuthService)).issue(user_id)
                link = web_origin(settings) + "/admin/#ticket=" + ticket
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            text = (
                _("ui_flows.editor_unavailable")
                if link is None
                else _("ui_flows.editor_link").format(link=escape_html(link))
            )
        await bot.send_message(user_id, text, parse_mode="HTML", disable_web_page_preview=True)
