"""Explicit baseline catalog dependency for isolated middleware/job unit tests."""

from unittest.mock import AsyncMock

from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.service import TextCatalogService


def text_dependencies(dependencies):
    return {
        TextCatalogService: AsyncMock(
            spec=TextCatalogService,
            current=AsyncMock(return_value=i18n.current_catalog),
            historical_labels=AsyncMock(return_value={}),
        ),
        **dependencies,
    }
