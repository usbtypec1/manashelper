from aiogram import Router, flags
from aiogram.filters import Command, CommandObject, or_f
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.core.config import Settings
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.application.use_cases.set_gamification_enabled import (
    SetGamificationEnabledUseCase,
)
from manashelper.modules.gamification.presentation.keyboard import build_achievements_keyboard
from manashelper.platform.telegram.filters.translated_text import TranslatedText

router = Router(name="gamification")


@router.message(or_f(TranslatedText("menu.achievements_button"), TranslatedText("menu.achievements")))
@flags.private_chat_only
async def on_achievements(
    message: Message, state: FSMContext, settings: FromDishka[Settings], query: FromDishka[GamificationQuery]
) -> None:
    await state.clear()
    if settings.public_url is None or message.from_user is None or not await query.is_enabled(message.from_user.id):
        await message.answer(_("gamification.unavailable"))
        return
    profile = await query.profile(message.from_user.id)
    await message.answer(
        _("gamification.open_prompt").format(
            score=profile.score,
            total=profile.total,
            rank=profile.rank if profile.rank is not None else _("gamification.rank_unassigned"),
        ),
        reply_markup=build_achievements_keyboard(settings.public_url),
    )


@router.message(Command("gamification"))
async def set_gamification(
    message: Message,
    command: CommandObject,
    access: FromDishka[SetGamificationEnabledUseCase],
    settings: FromDishka[Settings],
) -> None:
    if message.chat.id != settings.admin_chat_id or message.from_user is None:
        return
    args = (command.args or "").split()
    if len(args) != 2 or not args[0].isdecimal() or not 0 < int(args[0]) < 2**63 or args[1] not in {"on", "off"}:
        await message.answer(_("gamification.access_usage"), parse_mode=None)
        return
    try:
        await access.execute(int(args[0]), args[1] == "on", admin_chat_id=message.chat.id)
    except LookupError:
        await message.answer(_("common.start_required"))
        return
    await message.answer(_("gamification.access_enabled") if args[1] == "on" else _("gamification.access_disabled"))
