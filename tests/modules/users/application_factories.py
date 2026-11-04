from types import SimpleNamespace

from manashelper.modules.users.application.bot_status import BotStatusQuery
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.modules.users.application.use_cases.resolve_user_locale import ResolveUserLocaleUseCase
from manashelper.modules.users.application.use_cases.set_user_locale import SetUserLocaleUseCase
from manashelper.modules.users.application.use_cases.set_user_theme import SetUserThemeUseCase
from manashelper.modules.users.application.use_cases.stop_bot_delivery import StopBotDeliveryUseCase


def build_locale_service(user_repository):
    query = LocaleQuery(user_repository)
    return SimpleNamespace(
        get_locale=query.get_locale,
        resolve=ResolveUserLocaleUseCase(user_repository=user_repository).execute,
        set_locale=SetUserLocaleUseCase(user_repository=user_repository).execute,
    )


def build_theme_service(user_repository):
    query = ThemeQuery(user_repository)
    return SimpleNamespace(
        get_theme=query.get_theme,
        set_theme=SetUserThemeUseCase(user_repository=user_repository).execute,
    )


def build_bot_status_service(users):
    query = BotStatusQuery(users)
    return SimpleNamespace(
        is_stopped=query.is_stopped,
        stop=StopBotDeliveryUseCase(users=users).execute,
    )
