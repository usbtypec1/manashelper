from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.modules.users.application.user_contact import UserContactService
from manashelper.modules.users.presentation.keyboards.phone_numbers import build_phone_numbers_keyboard


async def show_phone_numbers(message: Message, user_id: int, contacts: UserContactService) -> None:
    await message.answer(
        _("phone.list"), reply_markup=build_phone_numbers_keyboard(await contacts.get_phone_numbers(user_id))
    )
