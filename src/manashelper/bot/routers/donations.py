from aiogram import Bot, F, Router, flags
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import DonationBankCallback, SettingsAction, SettingsCallback
from manashelper.bot.keyboards.donations import build_donations_keyboard
from manashelper.services.donations import DonationQrService, DonationService, list_donation_banks

router = Router(name="donations")


async def _donation_text(donation_service: DonationService, has_banks: bool) -> str:
    others = await donation_service.other_users_count()
    text = _(
        "❤️ <b>Help keep Manashelper running</b>\n\n"
        "On September 28, the bot stopped working after restrictions on its free AWS account. "
        "I moved it to a paid server so you can keep checking your schedule, cafeteria menu, grades and attendance.\n\n"
        "Your contribution helps cover the server for you and {others} other bot users. "
        "Any amount helps, and every donation goes toward server rent. Thank you for supporting the bot!"
    ).format(others=others)
    if has_banks:
        return text + "\n\n" + _("Choose a bank below to see its payment QR code:")
    return text + "\n\n" + _("Payment QR codes will appear here soon.")


@router.message(Command("donate"))
@flags.private_chat_only
async def cmd_donate(message: Message, donation_service: FromDishka[DonationService]) -> None:
    banks = list_donation_banks()
    await message.answer(
        await _donation_text(donation_service, bool(banks)), reply_markup=build_donations_keyboard(banks)
    )


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_DONATIONS))
@flags.private_chat_only
async def on_open_donations(callback_query: CallbackQuery, donation_service: FromDishka[DonationService]) -> None:
    banks = list_donation_banks()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            await _donation_text(donation_service, bool(banks)), reply_markup=build_donations_keyboard(banks)
        )
    await callback_query.answer()


@router.callback_query(DonationBankCallback.filter())
@flags.private_chat_only
async def on_donation_bank(
    callback_query: CallbackQuery,
    callback_data: DonationBankCallback,
    bot: Bot,
    donation_qr_service: FromDishka[DonationQrService],
) -> None:
    bank = next((bank for bank in list_donation_banks() if bank.id == callback_data.bank_id), None)
    if bank is None:
        await callback_query.answer(_("This bank's QR code is no longer available."), show_alert=True)
        return
    if isinstance(callback_query.message, Message):
        try:
            await donation_qr_service.send_bank_qr(bot, callback_query.message.chat.id, bank)
        except FileNotFoundError:
            await callback_query.answer(_("This bank's QR code is no longer available."), show_alert=True)
            return
    await callback_query.answer()
