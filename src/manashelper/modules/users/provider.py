from dishka import Provider, Scope, provide

from manashelper.modules.users.queries import UsersQuery


class UsersProvider(Provider):
    scope = Scope.REQUEST

    queries = provide(UsersQuery)
