from dishka import Provider, Scope, provide

from manashelper.modules.ui_flows.application.admin_queries import AdminQueries
from manashelper.modules.ui_flows.infrastructure.admin_queries import AdminQueriesRepository


class AdminUiFlowsProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(AdminQueriesRepository)
    queries = provide(AdminQueries)
