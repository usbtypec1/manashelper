from aiogram import Router, flags
from aiogram.filters import Command
from aiogram.types import LinkPreviewOptions, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.modules.eders.errors import EdersFetchError, EdersParseError, EdersUnsafeUrlError
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError, UserHasNoCredentialsError, UserNotFoundError
from manashelper.modules.obis.presentation.keyboards import build_no_credentials_keyboard
from manashelper.modules.study_week.application import GetStudyWeek
from manashelper.modules.study_week.formatter import format_study_week
from manashelper.platform.telegram.filters.translated_text import TranslatedText

router = Router(name="study_week")


@router.message(TranslatedText("menu.study_week"))
@router.message(Command("week"))
@flags.private_chat_only
async def on_week_command(message: Message, get_study_week: FromDishka[GetStudyWeek]) -> None:
    if message.from_user is None:
        return
    await message.answer(_("eders.loading"))
    try:
        week = await get_study_week.execute(message.from_user.id)
    except UserNotFoundError:
        await message.answer(_("common.start_required"))
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
