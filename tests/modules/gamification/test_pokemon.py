from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery, SendMessage, SendPhoto
from aiogram.types import CallbackQuery, Chat, Message, PhotoSize, Update
from aiogram.types import User as TelegramUser

from manashelper.core.config import get_settings
from manashelper.modules.gamification.application.catalog import AchievementDisplay
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.infrastructure.models.achievement import UserAchievement
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.gamification.presentation import pokemon
from manashelper.modules.users.application.queries import UsersQuery
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from tests.modules.gamification.factories import build_awards


async def test_pokemon_photo_requires_manual_grant_from_its_admin_message(session, monkeypatch):
    settings = get_settings()
    student = TelegramUser(id=991015, is_bot=False, first_name="Student <name>", username="teststudent")
    admin = TelegramUser(id=991016, is_bot=False, first_name="Admin")
    student_chat = Chat(id=student.id, type="private")
    admin_chat = Chat(id=settings.admin_chat_id, type="private" if settings.admin_chat_id > 0 else "supergroup")
    photo = [PhotoSize(file_id="proof-photo", file_unique_id="proof", width=200, height=200)]
    user = User(id=student.id, full_name=student.full_name)
    session.add(user)
    await session.flush()
    repo = AchievementRepository(session)
    await repo.save_display("pokemon", AchievementDisplay(custom_name="Team <award>"))
    awards = build_awards(session)
    dispatcher = Dispatcher(
        settings=settings,
        gamification=GamificationQuery(repo),
        users=UsersQuery(UserRepository(session)),
        awards=awards,
    )
    dispatcher.message.middleware(PrivateChatOnlyMiddleware())
    for name in ("message", "callback_query"):
        for handler in pokemon.router.observers[name].handlers:
            dispatcher.observers[name].register(
                getattr(handler.callback, "__dishka_orig_func__", handler.callback),
                *(item.callback for item in handler.filters),
                flags=handler.flags.copy(),
            )

    async with Bot("123456:development-placeholder") as bot:
        request = AsyncMock(return_value=True)
        monkeypatch.setattr(bot.session, "make_request", request)

        async def send_message(update_id, *, chat=student_chat, **kwargs):
            message = Message(message_id=update_id, date=0, chat=chat, from_user=student, **kwargs)
            await dispatcher.feed_update(bot, Update(update_id=update_id, message=message))
            return request.await_args.args[1] if request.await_args else None

        async def press_button(update_id, message, data):
            callback = CallbackQuery(
                id=str(update_id), from_user=admin, chat_instance="test-chat", message=message, data=data
            )
            await dispatcher.feed_update(bot, Update(update_id=update_id, callback_query=callback))
            method = request.await_args.args[1]
            assert isinstance(method, AnswerCallbackQuery)
            return method.text

        with i18n.context(), i18n.use_locale("en"):
            assert await send_message(1, photo=photo) is None
            disabled = await send_message(2, text="/pokemon")
            assert disabled.text == i18n.gettext("gamification.unavailable")
            await repo.set_enabled(student.id, True)
            prompt = await send_message(3, text="/pokemon")
            assert "@yunbae" in prompt.text
            text_only = await send_message(4, text="not a photo")
            assert text_only.text == i18n.gettext("gamification.pokemon.photo_required")

            async def fail_photo_once(bot, method, timeout=None):
                if isinstance(method, SendPhoto):
                    raise TelegramBadRequest(method=method, message="simulated failure")
                return True

            request.side_effect = fail_photo_once
            failure = await send_message(5, photo=photo)
            assert failure.text == i18n.gettext("gamification.pokemon.send_failed")
            request.reset_mock(side_effect=True)
            submitted = await send_message(6, photo=photo)
            assert isinstance(submitted, SendMessage)
            assert submitted.text == i18n.gettext("gamification.pokemon.submitted")
            [sent_photo] = [call.args[1] for call in request.await_args_list if isinstance(call.args[1], SendPhoto)]
            assert sent_photo.chat_id == settings.admin_chat_id
            assert sent_photo.photo == "proof-photo" and sent_photo.parse_mode is None
            assert "Student <name> (@teststudent)" in sent_photo.caption
            assert "Team <award>" in sent_photo.caption
            [[button]] = sent_photo.reply_markup.inline_keyboard
            assert not await repo.get_awards(student.id)

            proof = Message(
                message_id=100,
                date=1,
                chat=admin_chat,
                from_user=TelegramUser(id=bot.id, is_bot=True, first_name="Bot"),
                photo=photo,
                reply_markup=sent_photo.reply_markup,
            )
            assert await press_button(7, proof.model_copy(update={"chat": student_chat}), button.callback_data) is None
            assert await press_button(8, proof, pokemon.PokemonGrantCallback(user_id=admin.id).pack()) is None
            assert not await awards.execute(student.id, "pokemon", datetime.now(UTC))
            assert not await repo.get_awards(student.id)

            user.is_blocked = True
            await session.flush()
            unavailable = i18n.gettext("gamification.pokemon.grant_unavailable")
            assert await press_button(9, proof, button.callback_data) == unavailable
            assert not await repo.get_awards(student.id)
            user.is_blocked = False
            await session.flush()
            assert await press_button(10, proof, button.callback_data) == i18n.gettext(
                "gamification.pokemon.granted"
            ).format(name="Team <award>")
            assert await press_button(11, proof, button.callback_data) == unavailable
            stored = await session.get(UserAchievement, (student.id, "pokemon"))
            assert stored is not None and stored.granted_by == admin.id
            after_award = await send_message(12, text="/pokemon")
            assert after_award.text == i18n.gettext("gamification.pokemon.already_earned").format(
                name="Team &lt;award&gt;"
            )
    await dispatcher.storage.close()


async def test_historical_pokemon_award_counts_without_changing_its_grant(session):
    user_id = 991015
    session.add(User(id=user_id, full_name="Award holder"))
    await session.flush()
    repo = AchievementRepository(session)
    await repo.set_enabled(user_id, True)
    earned_at = datetime.now(UTC) - timedelta(days=100)
    session.add(UserAchievement(user_id=user_id, achievement_key="pokemon", earned_at=earned_at, granted_by=17))
    await session.flush()

    query = GamificationQuery(repo)
    profile = await query.profile(user_id)
    card = next(item for item in profile.achievements if item.key == "pokemon")
    assert card.earned_at == earned_at.isoformat() and card.current == card.target == 1
    assert profile.score == 1 and profile.rank is not None
    assert not await repo.award(user_id, "pokemon", datetime.now(UTC), granted_by=18)
    stored = await session.get(UserAchievement, (user_id, "pokemon"))
    assert stored is not None and stored.earned_at == earned_at and stored.granted_by == 17
