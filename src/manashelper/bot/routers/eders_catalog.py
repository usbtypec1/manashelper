import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aiogram import Router, flags
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import EdersCatalogCallback
from manashelper.bot.keyboards.eders_catalog import COURSES_PER_PAGE, build_catalog_keyboard
from manashelper.bot.keyboards.obis import build_no_credentials_keyboard
from manashelper.scraping.eders_client import EdersFetchError
from manashelper.scraping.eders_parser import EdersParseError
from manashelper.scraping.eders_urls import EdersUnsafeUrlError
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.eders import EdersService
from manashelper.services.eders_catalog import catalog_courses, find_grades, find_materials
from manashelper.services.eders_catalog_formatter import FEEDBACK_PAGE_SIZE, format_catalog_page, format_feedback_page
from manashelper.services.eders_models import EdersCatalogView, EdersGrade, EdersSnapshot
from manashelper.services.html_sanitization import escape_html
from manashelper.services.obis import UserHasNoCredentialsError, UserNotFoundError

router = Router(name="eders_catalog")
CATALOG_KEY = "eders_catalog_results"
CATALOG_TTL = timedelta(minutes=15)
MAX_CATALOGS = 5


@dataclass(frozen=True, slots=True)
class CatalogSession:
    snapshot: EdersSnapshot
    query: str


def _page(
    session_id: str,
    data: CatalogSession,
    view: EdersCatalogView,
    course_id: int = 0,
    page: int = 0,
    grade_id: int = 0,
) -> tuple[str, InlineKeyboardMarkup]:
    courses = catalog_courses(data.snapshot)
    is_grades = view in {EdersCatalogView.GRADE_COURSES, EdersCatalogView.GRADES, EdersCatalogView.FEEDBACK}
    grade_index, show_feedback = 0, False
    if view in {EdersCatalogView.MATERIAL_COURSES, EdersCatalogView.GRADE_COURSES}:
        count = max(1, math.ceil(len(courses) / COURSES_PER_PAGE))
        page = min(max(0, page), count - 1)
        header = _("eders.grades_header") if is_grades else _("eders.materials_header")
        text = header + "\n\n" + (_("eders.choose_course") if courses else _("eders.catalog_empty"))
        if data.query:
            text += "\n\n" + _("eders.search_query").format(value=escape_html(data.query))
    else:
        items = (
            find_grades(data.snapshot, course_id) if is_grades else find_materials(data.snapshot, course_id, data.query)
        )
        if view == EdersCatalogView.FEEDBACK and (
            grade := next((item for item in data.snapshot.grades if item.id == grade_id and item in items), None)
        ):
            grade_index = next(index for index, item in enumerate(items) if item == grade)
            count = max(1, math.ceil(len(grade.feedback or "") / FEEDBACK_PAGE_SIZE))
            page = min(max(0, page), count - 1)
            text = format_feedback_page(grade, page, count)
        else:
            count = len(items)
            page = min(max(0, page), max(0, count - 1))
            selected = items[page] if count else None
            if is_grades and selected:
                grade_id = selected.id
                show_feedback = isinstance(selected, EdersGrade) and len(selected.feedback or "") > 200
            text = format_catalog_page(
                selected, grades=is_grades, page=page, count=count, updated=data.snapshot.fetched_at
            )
    if is_grades and any(
        not course_id or course_id == identifier for identifier in data.snapshot.unavailable_grade_courses
    ):
        text += "\n\n" + _("eders.grades_unavailable")
    return text, build_catalog_keyboard(
        session_id,
        view,
        course_id,
        page,
        count,
        courses,
        grade_id=grade_id,
        grade_index=grade_index,
        show_feedback=show_feedback,
    )


@router.message(Command("materials", "eders_grades"))
@flags.private_chat_only
async def on_eders_catalog_command(
    message: Message, command: CommandObject, state: FSMContext, eders_service: FromDishka[EdersService]
) -> None:
    if message.from_user is None:
        return
    query = (command.args or "").strip() if command.command == "materials" else ""
    if len(query) > 100:
        await message.answer(_("eders.search_too_long"))
        return
    loading = await message.answer(_("eders.loading"))
    try:
        snapshot = await eders_service.get_snapshot(message.from_user.id)
    except UserNotFoundError:
        await loading.edit_text(_("common.start_required"))
        return
    except UserHasNoCredentialsError:
        await loading.edit_text(_("obis.credentials_missing"), reply_markup=build_no_credentials_keyboard())
        return
    except ObisLoginError:
        await loading.edit_text(_("obis.credentials_invalid"), reply_markup=build_no_credentials_keyboard())
        return
    except (EdersFetchError, EdersParseError, EdersUnsafeUrlError, ObisParseError):
        await loading.edit_text(_("eders.fetch_failed"))
        return
    session_id = uuid.uuid4().hex[:16]
    session = CatalogSession(snapshot, query)
    data = await state.get_data()
    catalogs = dict(data.get(CATALOG_KEY, {}))
    catalogs[session_id] = session
    while len(catalogs) > MAX_CATALOGS:
        del catalogs[next(iter(catalogs))]
    await state.update_data({CATALOG_KEY: catalogs})
    view = (
        EdersCatalogView.GRADE_COURSES
        if command.command == "eders_grades"
        else (EdersCatalogView.MATERIALS if query else EdersCatalogView.MATERIAL_COURSES)
    )
    text, keyboard = _page(session_id, session, view)
    await loading.edit_text(text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True))


@router.callback_query(EdersCatalogCallback.filter())
@flags.private_chat_only
async def on_eders_catalog_page(
    callback: CallbackQuery, callback_data: EdersCatalogCallback, state: FSMContext
) -> None:
    session = (await state.get_data()).get(CATALOG_KEY, {}).get(callback_data.session_id)
    if not isinstance(session, CatalogSession) or datetime.now(UTC) - session.snapshot.fetched_at > CATALOG_TTL:
        await callback.answer(_("eders.expired"), show_alert=True)
        return
    text, keyboard = _page(
        callback_data.session_id,
        session,
        callback_data.view,
        callback_data.course_id,
        callback_data.page,
        callback_data.grade_id,
    )
    if isinstance(callback.message, Message) and (
        callback.message.html_text != text or callback.message.reply_markup != keyboard
    ):
        await callback.message.edit_text(
            text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    await callback.answer()
