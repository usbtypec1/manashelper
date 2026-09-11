from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka

from manashelper.bot.callback_data import LessonSearchPageCallback, TimetableMenuAction, TimetableMenuCallback
from manashelper.bot.keyboards.lesson_search import build_lesson_search_keyboard
from manashelper.services.lesson_search import LessonSearchResult, LessonSearchService
from manashelper.services.lesson_search_formatter import format_lesson_search_page, total_page_count

router = Router(name="lesson_search")

MIN_QUERY_LENGTH = 2
RESULTS_KEY = "lesson_search_results"

PROMPT_TEXT = (
    "Введите название предмета. Турецкие буквы можно набирать обычными латинскими "
    "(например, s вместо ş или i вместо ı)."
)
QUERY_TOO_SHORT_TEXT = "Слишком короткий запрос. Откройте «🔎 Поиск предмета» ещё раз и попробуйте снова."
NO_RESULTS_TEXT = "Ничего не найдено."
RESULTS_EXPIRED_TEXT = "Результаты поиска устарели. Повторите поиск ещё раз."


class LessonSearchForm(StatesGroup):
    query = State()


@router.callback_query(TimetableMenuCallback.filter(F.action == TimetableMenuAction.OPEN_LESSON_SEARCH))
async def on_search_selected(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LessonSearchForm.query)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(PROMPT_TEXT)
    await callback_query.answer()


@router.message(StateFilter(LessonSearchForm.query))
async def on_search_query_entered(
    message: Message,
    state: FSMContext,
    lesson_search_service: FromDishka[LessonSearchService],
) -> None:
    await state.clear()

    query = message.text.strip() if message.text else ""
    if len(query) < MIN_QUERY_LENGTH:
        await message.answer(QUERY_TOO_SHORT_TEXT)
        return

    results = await lesson_search_service.search(query)
    if not results:
        await message.answer(NO_RESULTS_TEXT)
        return

    await state.update_data({RESULTS_KEY: results})
    await message.answer(
        format_lesson_search_page(results, 0),
        reply_markup=build_lesson_search_keyboard(0, total_page_count(results)),
    )


@router.callback_query(LessonSearchPageCallback.filter())
async def on_search_page_selected(
    callback_query: CallbackQuery,
    callback_data: LessonSearchPageCallback,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    results: list[LessonSearchResult] | None = data.get(RESULTS_KEY)
    if not results:
        await callback_query.answer(RESULTS_EXPIRED_TEXT, show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            format_lesson_search_page(results, callback_data.page),
            reply_markup=build_lesson_search_keyboard(callback_data.page, total_page_count(results)),
        )
    await callback_query.answer()
