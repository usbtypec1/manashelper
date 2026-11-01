from dataclasses import replace
from datetime import UTC, datetime

from aiogram.fsm.context import FSMContext
from aiogram.types import LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _

from manashelper.modules.eders.application.eders import EdersService, filter_activities
from manashelper.modules.eders.application.models import DeadlineFilter
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.errors import (
    EdersFetchError,
    EdersParseError,
    EdersSnapshotNotReadyError,
    EdersUnsafeUrlError,
)
from manashelper.modules.eders.presentation.formatter import format_activity_page
from manashelper.modules.eders.presentation.keyboards import build_eders_keyboard
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError, UserHasNoCredentialsError, UserNotFoundError
from manashelper.modules.obis.presentation.keyboards import build_no_credentials_keyboard

SNAPSHOT_KEY = "eders_snapshot"
SNAPSHOT_OPENED_AT_KEY = "eders_snapshot_opened_at"


async def show_eders(
    message: Message,
    user_id: int,
    state: FSMContext,
    eders_service: EdersService,
    tracking: EdersTrackingService,
    selected: DeadlineFilter = DeadlineFilter.ALL,
    query: str = "",
) -> None:
    await state.update_data({SNAPSHOT_KEY: None})
    try:
        snapshot = await eders_service.get_snapshot(user_id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
        return
    except EdersSnapshotNotReadyError:
        await message.answer(_("data.preparing"))
        return
    except UserHasNoCredentialsError:
        await message.answer(_("obis.credentials_missing"), reply_markup=build_no_credentials_keyboard())
        return
    except ObisLoginError:
        await message.answer(_("obis.credentials_invalid"), reply_markup=build_no_credentials_keyboard())
        return
    except (EdersFetchError, EdersParseError, EdersUnsafeUrlError, ObisParseError):
        await message.answer(_("eders.fetch_failed"))
        return
    if query.strip():
        search = query.strip().casefold()
        snapshot = replace(
            snapshot,
            activities=tuple(
                item
                for item in snapshot.activities
                if search in f"{item.course.name} {item.section} {item.name} {item.description}".casefold()
            ),
        )
    await state.update_data({SNAPSHOT_KEY: snapshot, SNAPSHOT_OPENED_AT_KEY: datetime.now(UTC)})
    settings = await tracking.get_settings(user_id)
    activities = filter_activities(snapshot.activities, selected, datetime.now(UTC), settings.hide_archived)
    await message.answer(
        format_activity_page(activities, 0),
        reply_markup=build_eders_keyboard(selected, 0, len(activities)),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
