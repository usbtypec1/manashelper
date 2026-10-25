from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class ObisAction(StrEnum):
    START_CREDENTIALS = "start_credentials"
    ACCEPT_TERMS = "accept_terms"
    CANCEL_CREDENTIALS = "cancel_credentials"
    CLEAR_CREDENTIALS = "clear_credentials"
    CONFIRM_CLEAR_CREDENTIALS = "confirm_clear_credentials"


class ObisCallback(CallbackData, prefix="obis"):
    action: ObisAction


class ObisResultsPageCallback(CallbackData, prefix="obis_results_page"):
    page: int
