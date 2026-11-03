from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dishka import AsyncContainer

from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.service import TextCatalogService


@asynccontextmanager
async def catalog_request(container: AsyncContainer) -> AsyncIterator[AsyncContainer]:
    """Select one DB release per business request; no file fallback or HTTP calls."""
    async with container() as request:
        snapshot = await (await request.get(TextCatalogService)).current()
        with i18n.use_catalog(snapshot):
            yield request
