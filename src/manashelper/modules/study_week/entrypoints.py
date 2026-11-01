from aiogram.types import LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _

from manashelper.modules.eders.errors import (
    EdersFetchError,
    EdersParseError,
    EdersSnapshotNotReadyError,
    EdersUnsafeUrlError,
)
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError, UserHasNoCredentialsError, UserNotFoundError
from manashelper.modules.obis.presentation.keyboards import build_no_credentials_keyboard
from manashelper.modules.study_week.application import GetStudyWeek
from manashelper.modules.study_week.formatter import format_study_week


async def show_study_week(message: Message, user_id: int, get_study_week: GetStudyWeek) -> None:
    try:
        week = await get_study_week.execute(user_id)
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
    for text in format_study_week(week):
        await message.answer(text, link_preview_options=LinkPreviewOptions(is_disabled=True))
