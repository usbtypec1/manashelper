from aiogram import Bot, F, Router, flags
from aiogram.filters import CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Update
from dishka import AsyncContainer, FromDishka

from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.router import FlowLaunchChat, private_user
from manashelper.platform.telegram.middlewares.after_request import AfterRequestActions
from ui_flows.application.dialogs import DialogService
from ui_flows.domain.state import RuntimeUser

router = Router(name="ui_flow_survey")


class NoLegacySurvey(Filter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        return not (await state.get_state() or "").startswith("StudentQuestionsForm:")


class SurveyEntryChat(FlowLaunchChat):
    async def __call__(self, message: Message, dishka_container: AsyncContainer) -> bool:
        if not private_user(message):
            return False
        active = await (await dishka_container.get(DialogService)).active(RuntimeUser(message.chat.id, message.chat.id))
        return (active is not None and active.flow_id == "student_questions") or await super().__call__(
            message, dishka_container
        )


@router.message(SurveyEntryChat(), CommandStart(deep_link=True, magic=F.args == "student_questions"), NoLegacySurvey())
@flags.private_chat_only
@flags.ui_flow
async def survey_start(
    message: Message,
    state: FSMContext,
    bot: Bot,
    event_update: Update,
    after_request: AfterRequestActions,
    coordinator: FromDishka[FlowTelegramCoordinator],
) -> None:
    await state.clear()
    after_request.add(lambda: coordinator.survey(bot, message.chat.id, event_update.update_id))
