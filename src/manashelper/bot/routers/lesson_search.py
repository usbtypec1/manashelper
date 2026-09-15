from aiogram import F, Router, flags
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import LessonSearchPageCallback, TimetableMenuAction, TimetableMenuCallback
from manashelper.bot.keyboards.lesson_search import build_lesson_search_keyboard
from manashelper.services.lesson_search import LessonSearchResult, LessonSearchService
from manashelper.services.lesson_search_formatter import format_lesson_search_page, total_page_count

router = Router(name="lesson_search")

MIN_QUERY_LENGTH = 2
RESULTS_KEY = "lesson_search_results"


class LessonSearchForm(StatesGroup):
    query = State()


@router.callback_query(TimetableMenuCallback.filter(F.action == TimetableMenuAction.OPEN_LESSON_SEARCH))
@flags.private_chat_only
async def on_search_selected(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LessonSearchForm.query)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _(
                "Enter the subject name. You can type Turkish letters using regular Latin ones "
                "(e.g. s instead of ş, or i instead of ı)."
            )
        )
    await callback_query.answer()


@router.message(StateFilter(LessonSearchForm.query))
@flags.private_chat_only
async def on_search_query_entered(
    message: Message,
    state: FSMContext,
    lesson_search_service: FromDishka[LessonSearchService],
) -> None:
    await state.clear()

    query = message.text.strip() if message.text else ""
    if len(query) < MIN_QUERY_LENGTH:
        await message.answer(_("The query is too short. Open «🔎 Search for a subject» again and try once more."))
        return

    results = await lesson_search_service.search(query)
    if not results:
        await message.answer(_("Nothing found."))
        return

    await state.update_data({RESULTS_KEY: results})
    await message.answer(
        format_lesson_search_page(results, 0),
        reply_markup=build_lesson_search_keyboard(0, total_page_count(results)),
    )


@router.callback_query(LessonSearchPageCallback.filter())
@flags.private_chat_only
async def on_search_page_selected(
    callback_query: CallbackQuery,
    callback_data: LessonSearchPageCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    results: list[LessonSearchResult] | None = data.get(RESULTS_KEY)
    if not results:
        await callback_query.answer(_("The search results have expired. Please search again."), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            format_lesson_search_page(results, callback_data.page),
            reply_markup=build_lesson_search_keyboard(callback_data.page, total_page_count(results)),
        )
    await callback_query.answer()
