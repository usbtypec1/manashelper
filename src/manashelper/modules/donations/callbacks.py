from aiogram.filters.callback_data import CallbackData


class DonationBankCallback(CallbackData, prefix="donate"):
    bank_id: str
