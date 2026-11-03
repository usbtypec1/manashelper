from dishka import Provider, Scope, provide

from manashelper.platform.i18n.repository import TextCatalogRepository
from manashelper.platform.i18n.service import TextCatalogService
from ui_flows.ports.texts import TextCatalog


class TextCatalogProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(TextCatalogRepository)
    service = provide(TextCatalogService)

    @provide
    async def snapshot(self, service: TextCatalogService) -> TextCatalog:
        return await service.current()
