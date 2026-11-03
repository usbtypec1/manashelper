from dataclasses import replace

from aiogram import Bot
from aiogram.types import CallbackQuery, Message, TelegramObject

from manashelper.modules.ui_flows.presentation.ingress_codecs import CODECS
from ui_flows.domain.ingress import IncomingEvent


def event_identity(event: TelegramObject, bot: Bot, update_id: int) -> IncomingEvent | None:
    callback = event if isinstance(event, CallbackQuery) else None
    message = callback.message if callback else event
    actor = callback.from_user if callback else message.from_user if isinstance(message, Message) else None
    if actor is None or not isinstance(message, Message):
        return None
    return IncomingEvent(
        bot.id,
        update_id,
        actor.id,
        message.chat.id,
        message.chat.type,
        "unsupported",
        message.message_id,
        message.message_thread_id,
    )


async def normalize(
    event: TelegramObject, bot: Bot, update_id: int, *, known_commands: frozenset[str] | None = None
) -> IncomingEvent | None:
    common = event_identity(event, bot, update_id)
    if common is None:
        return None
    callback = event if isinstance(event, CallbackQuery) else None
    message = callback.message if callback else event
    assert isinstance(message, Message)
    if callback:
        data = callback.data or ""
        codec = data.partition(":")[0]
        try:
            if len(data.encode()) > 64:
                raise ValueError
            parsed = CODECS[codec].unpack(data)
        except (KeyError, ValueError, TypeError):
            return replace(common, kind="callback", callback=data, codec=codec, valid=False)
        return replace(
            common, kind="callback", callback=data, codec=codec, action=str(getattr(parsed, "action", "")) or None
        )
    text = message.text or ""
    if text.startswith("/"):
        command, _, arguments = text.partition(" ")
        name, _, mention = command[1:].partition("@")
        # The legacy password field accepts arbitrary secrets, including slash/@ prefixes.
        if known_commands is not None and name.casefold() not in known_commands:
            return replace(common, kind="text", text=text, valid=len(text) <= 4096)
        valid = not mention or mention.casefold() == ((await bot.me()).username or "").casefold()
        if not valid:
            return replace(common, valid=False)
        arguments = arguments.strip()
        if name.casefold() == "start" and arguments:
            return replace(common, kind="deep_link", key=arguments, valid=valid and len(arguments) <= 64)
        return replace(common, kind="command", key=name.casefold(), arguments=arguments, valid=valid)
    if message.reply_to_message is not None:
        return replace(
            common,
            kind="reply",
            text=text,
            caption=message.caption,
            reply_to_message_id=message.reply_to_message.message_id,
        )
    if message.contact is not None:
        return replace(
            common, kind="contact", contact_owner=message.contact.user_id, phone=message.contact.phone_number
        )
    if message.photo:
        return replace(
            common,
            kind="media",
            media_type="photo",
            file_ids=(message.photo[-1].file_id,),
            caption=message.caption,
            media_group_id=message.media_group_id,
        )
    if message.video:
        return replace(
            common,
            kind="media",
            media_type="video",
            file_ids=(message.video.file_id,),
            caption=message.caption,
            media_group_id=message.media_group_id,
        )
    if message.text is not None:
        return replace(common, kind="text", text=text, valid=len(text) <= 4096)
    return common
