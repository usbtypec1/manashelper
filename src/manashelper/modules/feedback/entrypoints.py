from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.modules.feedback.keyboards import build_feedback_cancel_keyboard
from manashelper.modules.feedback.states import FeedbackForm


async def start_feedback(message: Message, state: FSMContext) -> None:
    await state.set_state(FeedbackForm.message)
    await message.answer(_("feedback.message_prompt"), reply_markup=build_feedback_cancel_keyboard())
