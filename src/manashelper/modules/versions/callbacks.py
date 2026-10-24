from aiogram.filters.callback_data import CallbackData


class VersionsPageCallback(CallbackData, prefix="versions_page"):
    page: int


class VersionCallback(CallbackData, prefix="version"):
    version: str
    page: int
