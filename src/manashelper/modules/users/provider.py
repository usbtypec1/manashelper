from dishka import Provider, Scope, provide

from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.user_contact import UserContactService
from manashelper.modules.users.infrastructure.user_phone_number_repository import UserPhoneNumberRepository
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.queries import UsersQuery


class UsersProvider(Provider):
    scope = Scope.REQUEST

    queries = provide(UsersQuery)
    users = provide(UserRepository)
    phone_numbers = provide(UserPhoneNumberRepository)
    locales = provide(LocaleService)
    contacts = provide(UserContactService)
