from aiogram import Bot, Router, flags
from aiogram.filters import CommandObject, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Update
from dishka import FromDishka

from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.router import FlowLaunchChat
from manashelper.platform.telegram.filters.translated_text import TranslatedText
from manashelper.platform.telegram.middlewares.after_request import AfterRequestActions

router = Router(name="ui_flow_menus")


class NoStartPayload(Filter):
    async def __call__(self, message: Message, command: CommandObject) -> bool:
        return command.args is None


@router.message(FlowLaunchChat(), CommandStart(), NoStartPayload())
@router.message(FlowLaunchChat(), TranslatedText("common.back_to_menu"))
@flags.private_chat_only
@flags.ui_flow
async def main_menu(
    message: Message,
    state: FSMContext,
    bot: Bot,
    event_update: Update,
    after_request: AfterRequestActions,
    coordinator: FromDishka[FlowTelegramCoordinator],
) -> None:
    await state.clear()
    after_request.add(lambda: coordinator.menu(bot, message.chat.id, event_update.update_id))


@router.message(FlowLaunchChat(), TranslatedText("menu.study"))
@flags.private_chat_only
@flags.ui_flow
async def study_menu(
    message: Message,
    state: FSMContext,
    bot: Bot,
    event_update: Update,
    after_request: AfterRequestActions,
    coordinator: FromDishka[FlowTelegramCoordinator],
) -> None:
    await state.clear()
    after_request.add(lambda: coordinator.menu(bot, message.chat.id, event_update.update_id, "study"))
