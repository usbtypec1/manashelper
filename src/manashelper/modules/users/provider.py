from dishka import Provider, Scope, provide

from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery


class UsersProvider(Provider):
    scope = Scope.REQUEST

    queries = provide(UsersQuery)
    users = provide(UserRepository)
    locales = provide(LocaleService)
    themes = provide(ThemeService)
    bot_status = provide(BotStatusService)
