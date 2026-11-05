import uuid

from aiogram import Router, flags
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.core.config import Settings
from manashelper.modules.advertisements.application.advertisement import AdvertisementNotFoundError
from manashelper.modules.advertisements.application.use_cases.reveal_advertisement_contact import (
    RevealAdvertisementContactUseCase,
)
from manashelper.modules.advertisements.presentation.advertisement import send_marketplace_menu
from manashelper.modules.advertisements.presentation.advertisement_formatter import format_contact_reveal
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.platform.telegram.navigation import send_welcome

router = Router(name="advertisement_contact")

AD_DEEPLINK_PAYLOAD_PREFIX = "ad_"
MARKET_DEEPLINK_PAYLOAD = "market"


@router.message(CommandStart(deep_link=True))
@flags.private_chat_only
async def on_advertisement_deep_link(
    message: Message,
    command: CommandObject,
    settings: FromDishka[Settings],
    reveal_advertisement_contact: FromDishka[RevealAdvertisementContactUseCase],
    gamification: FromDishka[GamificationQuery],
) -> None:
    payload = command.args or ""
    if message.from_user is None:
        return

    if payload == MARKET_DEEPLINK_PAYLOAD:
        await send_marketplace_menu(message, settings)
        return

    if not payload.startswith(AD_DEEPLINK_PAYLOAD_PREFIX):
        await send_welcome(message, achievements_enabled=await gamification.is_enabled(message.from_user.id))
        return

    try:
        advertisement_id = uuid.UUID(payload[len(AD_DEEPLINK_PAYLOAD_PREFIX) :])
    except ValueError:
        await send_welcome(message, achievements_enabled=await gamification.is_enabled(message.from_user.id))
        return

    try:
        reveal = await reveal_advertisement_contact.execute(advertisement_id, message.from_user.id)
    except AdvertisementNotFoundError:
        await message.answer(_("ads.not_found"))
        return

    await message.answer(format_contact_reveal(reveal))
