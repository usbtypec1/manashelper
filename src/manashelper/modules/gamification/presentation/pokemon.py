import logging
from datetime import UTC, datetime

from aiogram import Bot, F, Router, flags
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.core.config import Settings
from manashelper.localization.locale import DEFAULT_LOCALE
from manashelper.localization.theme import Theme
from manashelper.modules.gamification.application.catalog import POKEMON_KEY
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.application.use_cases.award_achievement import AwardAchievementUseCase
from manashelper.modules.gamification.presentation.catalog import achievement_strings
from manashelper.modules.users.application.queries import UsersQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html

logger = logging.getLogger(__name__)
router = Router(name="pokemon")


class PokemonForm(StatesGroup):
    photo = State()


class PokemonGrantCallback(CallbackData, prefix="pokemon_grant"):
    user_id: int


def _pokemon_name(custom_name: str | None) -> str:
    return custom_name or achievement_strings()[POKEMON_KEY][0]


async def _can_submit(message: Message, state: FSMContext, query: GamificationQuery) -> bool:
    if message.from_user is None:
        return False
    if not await query.is_enabled(message.from_user.id):
        await state.clear()
        await message.answer(_("gamification.unavailable"))
        return False
    if await query.has_award(message.from_user.id, POKEMON_KEY):
        await state.clear()
        display = await query.display_for(POKEMON_KEY)
        name = escape_html(_pokemon_name(display.custom_name))
        await message.answer(_("gamification.pokemon.already_earned").format(name=name))
        return False
    return True


@router.message(Command("pokemon"))
@flags.private_chat_only
async def request_pokemon_photo(
    message: Message, state: FSMContext, gamification: FromDishka[GamificationQuery]
) -> None:
    await state.clear()
    if await _can_submit(message, state, gamification):
        await state.set_state(PokemonForm.photo)
        await message.answer(_("gamification.pokemon.photo_prompt"), parse_mode=None)


@router.message(PokemonForm.photo, F.photo)
@flags.private_chat_only
@flags.mask_logged_message
async def submit_pokemon_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    settings: FromDishka[Settings],
    gamification: FromDishka[GamificationQuery],
) -> None:
    user = message.from_user
    if user is None or not message.photo or not await _can_submit(message, state, gamification):
        return
    sender = f"{user.full_name} (@{user.username})" if user.username else user.full_name
    display = await gamification.display_for(POKEMON_KEY)
    with i18n.use_locale(DEFAULT_LOCALE.value), i18n.use_theme(Theme.BASIC):
        caption = _("gamification.pokemon.admin_photo").format(sender=sender, name=_pokemon_name(display.custom_name))
        button = InlineKeyboardButton(
            text=_("gamification.pokemon.grant"), callback_data=PokemonGrantCallback(user_id=user.id).pack()
        )
    try:
        await bot.send_photo(
            chat_id=settings.admin_chat_id,
            photo=message.photo[-1].file_id,
            caption=caption,
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]),
        )
    except TelegramAPIError:
        logger.warning("Failed to send Pokemon photo to the admin chat", exc_info=True)
        await message.answer(_("gamification.pokemon.send_failed"))
        return
    await state.clear()
    await message.answer(_("gamification.pokemon.submitted"))


@router.message(PokemonForm.photo, F.text.is_(None) | ~F.text.startswith("/"))
@flags.private_chat_only
@flags.mask_logged_message
async def expect_pokemon_photo(message: Message) -> None:
    await message.answer(_("gamification.pokemon.photo_required"))


@router.callback_query(PokemonGrantCallback.filter())
async def grant_pokemon(
    callback_query: CallbackQuery,
    callback_data: PokemonGrantCallback,
    bot: Bot,
    settings: FromDishka[Settings],
    users: FromDishka[UsersQuery],
    awards: FromDishka[AwardAchievementUseCase],
    gamification: FromDishka[GamificationQuery],
) -> None:
    message = callback_query.message
    # Telegram clients can submit arbitrary callback data. Take the recipient from a button on our proof message.
    if (
        not isinstance(message, Message)
        or message.chat.id != settings.admin_chat_id
        or message.from_user is None
        or message.from_user.id != bot.id
        or not message.photo
        or message.reply_markup is None
        or not any(
            button.callback_data == callback_query.data
            for row in message.reply_markup.inline_keyboard
            for button in row
        )
    ):
        await callback_query.answer()
        return

    user_id = callback_data.user_id
    granted = await users.can_use_bot(user_id) and await awards.execute(
        user_id, POKEMON_KEY, datetime.now(UTC), granted_by=callback_query.from_user.id
    )
    if granted:
        display = await gamification.display_for(POKEMON_KEY)
        text = _("gamification.pokemon.granted").format(name=_pokemon_name(display.custom_name))
    else:
        text = _("gamification.pokemon.grant_unavailable")
    await callback_query.answer(text, show_alert=True)
