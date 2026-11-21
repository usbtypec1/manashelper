from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TelegramUser
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.aiogram import setup_dishka

from manashelper.modules.users.application.queries import UsersQuery
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.platform.telegram.middlewares.user_blocking import UserBlockingMiddleware


async def test_blocked_actor_cannot_use_messages_groups_or_callbacks(session):
    user_id = 980001
    session.add(User(id=user_id, full_name="Target", is_blocked=True))
    await session.flush()
    repository = UserRepository(session)

    class TestUsersProvider(Provider):
        @provide(scope=Scope.REQUEST)
        def users(self) -> UsersQuery:
            return UsersQuery(repository)

    dispatcher = Dispatcher()
    calls = []

    @dispatcher.message()
    async def message_handler(message: Message):
        calls.append(message.text)

    @dispatcher.callback_query()
    async def callback_handler(callback: CallbackQuery):
        calls.append(callback.data)

    actor = TelegramUser(id=user_id, is_bot=False, first_name="Target")
    group = Chat(id=-100001, type="supergroup")
    private = Chat(id=user_id, type="private")
    start = Message(message_id=1, date=0, chat=private, from_user=actor, text="/start")
    command = Message(message_id=2, date=0, chat=group, from_user=actor, text="/food")
    anonymous = Message(message_id=3, date=0, chat=group, from_user=actor, sender_chat=group, text="/food")
    callback = CallbackQuery(id="test", chat_instance="group", from_user=actor, data="action", message=command)
    updates = [
        Update(update_id=1, message=start),
        Update(update_id=2, message=command),
        Update(update_id=3, message=anonymous),
        Update(update_id=4, callback_query=callback),
    ]

    async with make_async_container(TestUsersProvider()) as container, Bot("123456:development-placeholder") as bot:
        setup_dishka(container, dispatcher)
        dispatcher.update.middleware(UserBlockingMiddleware())
        try:
            for update in updates:
                await dispatcher.feed_update(bot, update)
            assert not calls
            assert await repository.set_blocked(user_id, False)
            for update in updates:
                await dispatcher.feed_update(bot, update)
            assert calls == ["/start", "/food", "action"]
        finally:
            await dispatcher.storage.close()
