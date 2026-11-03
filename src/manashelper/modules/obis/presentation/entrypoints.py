import logging
from collections.abc import Awaitable, Callable

import httpx
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisParseError,
    ObisSnapshotNotReadyError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)
from manashelper.modules.obis.presentation.formatter import format_attendance_pages, format_exam_grades_pages
from manashelper.modules.obis.presentation.keyboards import (
    build_no_credentials_keyboard,
    build_obis_results_keyboard,
    build_obis_settings_keyboard,
)

logger = logging.getLogger(__name__)
RESULTS_KEY = "obis_result_pages"
MAX_SAVED_RESULTS = 5


async def show_obis_settings(message: Message, user_id: int, obis: ObisService) -> None:
    await message.answer(
        _("obis.settings"), reply_markup=build_obis_settings_keyboard(await obis.has_credentials(user_id))
    )


async def _show_obis_results[T](
    message: Message,
    state: FSMContext,
    user_id: int,
    fetch: Callable[[int], Awaitable[list[T]]],
    format_results: Callable[[list[T]], list[str]],
    loading_text: str,
) -> None:
    sent = await message.answer(loading_text, parse_mode=None)
    try:
        lessons = await fetch(user_id)
    except UserNotFoundError:
        await sent.edit_text(_("common.start_required"))
        return
    except ObisSnapshotNotReadyError:
        await sent.edit_text(_("data.preparing"))
        return
    except UserHasNoCredentialsError:
        await sent.edit_text(
            _("obis.credentials_missing"),
            reply_markup=build_no_credentials_keyboard(),
        )
        return
    except ObisLoginError:
        await sent.edit_text(
            _("obis.credentials_invalid"),
            reply_markup=build_no_credentials_keyboard(),
        )
        return
    except (ObisParseError, httpx.HTTPError):
        logger.warning("Failed to load requested OBIS data", exc_info=True)
        await sent.edit_text(_("obis.fetch_failed"))
        return
    except Exception:
        await sent.edit_text(_("obis.fetch_failed"))
        raise
    pages = format_results(lessons)
    if len(pages) > 1:
        data = await state.get_data()
        snapshots: dict[str, list[str]] = dict(data.get(RESULTS_KEY, {}))
        snapshots[str(sent.message_id)] = pages
        while len(snapshots) > MAX_SAVED_RESULTS:
            snapshots.pop(next(iter(snapshots)))
        await state.update_data({RESULTS_KEY: snapshots})
    await sent.edit_text(pages[0], parse_mode=None, reply_markup=build_obis_results_keyboard(0, len(pages)))


async def show_attendance(message: Message, user_id: int, state: FSMContext, service: ObisService) -> None:
    await _show_obis_results(
        message, state, user_id, service.get_attendance, format_attendance_pages, _("obis.loading_attendance")
    )


async def show_grades(message: Message, user_id: int, state: FSMContext, service: ObisService) -> None:
    await _show_obis_results(
        message, state, user_id, service.get_exam_grades, format_exam_grades_pages, _("obis.loading_grades")
    )
