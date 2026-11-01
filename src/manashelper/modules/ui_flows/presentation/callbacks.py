from aiogram.filters.callback_data import CallbackData


class UiFlowCallback(CallbackData, prefix="uf"):
    token: str
    index: int
