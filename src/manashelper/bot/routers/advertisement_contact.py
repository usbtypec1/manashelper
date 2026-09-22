import uuid

from aiogram import Router, flags
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.routers.start import send_welcome
from manashelper.services.advertisement import AdvertisementNotFoundError
from manashelper.services.advertisement_contact import AdvertisementContactService
from manashelper.services.advertisement_formatter import format_contact_reveal

router = Router(name="advertisement_contact")

AD_DEEPLINK_PAYLOAD_PREFIX = "ad_"


@router.message(CommandStart(deep_link=True))
@flags.private_chat_only
async def on_advertisement_deep_link(
    message: Message,
    command: CommandObject,
    advertisement_contact_service: FromDishka[AdvertisementContactService],
) -> None:
    payload = command.args or ""
    if message.from_user is None or not payload.startswith(AD_DEEPLINK_PAYLOAD_PREFIX):
        await send_welcome(message)
        return

    try:
        advertisement_id = uuid.UUID(payload[len(AD_DEEPLINK_PAYLOAD_PREFIX) :])
    except ValueError:
        await send_welcome(message)
        return

    try:
        reveal = await advertisement_contact_service.reveal_contact(advertisement_id, message.from_user.id)
    except AdvertisementNotFoundError:
        await message.answer(_("This ad no longer exists"))
        return

    await message.answer(format_contact_reveal(reveal))
