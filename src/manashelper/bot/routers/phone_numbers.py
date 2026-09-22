from aiogram import F, Router, flags
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import (
    PhoneNumberAction,
    PhoneNumberActionCallback,
    PhoneNumberDeleteCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.bot.keyboards.phone_numbers import build_contact_request_keyboard, build_phone_numbers_keyboard
from manashelper.services.user_contact import (
    InvalidPhoneNumberError,
    PhoneNumberForbiddenError,
    PhoneNumberNotFoundError,
    UserContactService,
    UserNotFoundError,
)

router = Router(name="phone_numbers")


class PhoneNumberForm(StatesGroup):
    phone_number = State()


def _phone_numbers_text() -> str:
    return _("📱 <b>My phone numbers</b>\n\nThese are shown to buyers on the ads you post.")


async def _render_phone_numbers(callback_query: CallbackQuery, user_contact_service: UserContactService) -> None:
    phone_numbers = await user_contact_service.get_phone_numbers(callback_query.from_user.id)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _phone_numbers_text(), reply_markup=build_phone_numbers_keyboard(phone_numbers)
        )
    await callback_query.answer()


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_PHONE_NUMBERS))
@flags.private_chat_only
async def on_open_phone_numbers(
    callback_query: CallbackQuery, user_contact_service: FromDishka[UserContactService]
) -> None:
    await _render_phone_numbers(callback_query, user_contact_service)


@router.callback_query(PhoneNumberActionCallback.filter(F.action == PhoneNumberAction.ADD))
@flags.private_chat_only
async def on_add_phone_number_requested(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PhoneNumberForm.phone_number)
    if isinstance(callback_query.message, Message):
        await callback_query.message.answer(
            _("Share a phone number using the button below, or type one in manually (e.g. +996700123456):"),
            reply_markup=build_contact_request_keyboard(),
        )
    await callback_query.answer()


@router.message(F.contact, StateFilter(PhoneNumberForm.phone_number))
@flags.private_chat_only
async def on_phone_number_shared(
    message: Message, state: FSMContext, user_contact_service: FromDishka[UserContactService]
) -> None:
    if message.contact is None or message.from_user is None:
        return
    await _save_phone_number(message, state, user_contact_service, message.from_user.id, message.contact.phone_number)


@router.message(StateFilter(PhoneNumberForm.phone_number))
@flags.private_chat_only
async def on_phone_number_entered(
    message: Message, state: FSMContext, user_contact_service: FromDishka[UserContactService]
) -> None:
    if message.from_user is None:
        return
    phone_number = message.text.strip() if message.text else ""
    await _save_phone_number(message, state, user_contact_service, message.from_user.id, phone_number)


async def _save_phone_number(
    message: Message, state: FSMContext, user_contact_service: UserContactService, user_id: int, phone_number: str
) -> None:
    try:
        await user_contact_service.add_phone_number(user_id, phone_number)
    except UserNotFoundError:
        await state.clear()
        await message.answer(_("Please start with the /start command"), reply_markup=ReplyKeyboardRemove())
        return
    except InvalidPhoneNumberError:
        await message.answer(
            _("That doesn't look like a valid phone number (e.g. +996700123456). Please try again:"),
            reply_markup=build_contact_request_keyboard(),
        )
        return

    await state.clear()
    await message.answer(_("✅ Phone number saved."), reply_markup=ReplyKeyboardRemove())
    phone_numbers = await user_contact_service.get_phone_numbers(user_id)
    await message.answer(_phone_numbers_text(), reply_markup=build_phone_numbers_keyboard(phone_numbers))


@router.callback_query(PhoneNumberDeleteCallback.filter())
@flags.private_chat_only
async def on_delete_phone_number(
    callback_query: CallbackQuery,
    callback_data: PhoneNumberDeleteCallback,
    user_contact_service: FromDishka[UserContactService],
) -> None:
    try:
        await user_contact_service.delete_phone_number(callback_query.from_user.id, callback_data.id)
    except (PhoneNumberNotFoundError, PhoneNumberForbiddenError):
        await callback_query.answer(_("This phone number is no longer saved"), show_alert=True)
        return

    await _render_phone_numbers(callback_query, user_contact_service)
