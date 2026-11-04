from dishka import Provider, Scope, provide

from manashelper.modules.users.application.bot_status import BotStatusQuery
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.modules.users.application.use_cases.resolve_user_locale import ResolveUserLocaleUseCase
from manashelper.modules.users.application.use_cases.set_user_locale import SetUserLocaleUseCase
from manashelper.modules.users.application.use_cases.set_user_theme import SetUserThemeUseCase
from manashelper.modules.users.application.use_cases.stop_bot_delivery import StopBotDeliveryUseCase
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery


class UsersProvider(Provider):
    scope = Scope.REQUEST

    stop_bot_delivery_use_case = provide(StopBotDeliveryUseCase)

    set_user_theme_use_case = provide(SetUserThemeUseCase)

    set_user_locale_use_case = provide(SetUserLocaleUseCase)

    resolve_user_locale_use_case = provide(ResolveUserLocaleUseCase)

    queries = provide(UsersQuery)
    users = provide(UserRepository)
    locales = provide(LocaleQuery)
    themes = provide(ThemeQuery)
    bot_status = provide(BotStatusQuery)
