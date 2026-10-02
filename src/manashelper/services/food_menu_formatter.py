from aiogram.enums import ParseMode
from aiogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaLivePhoto,
    InputMediaPhoto,
    InputMediaVideo,
    InputRichBlockButtons,
    InputRichBlockCollage,
    InputRichBlockParagraph,
    InputRichBlockPhoto,
    InputRichBlockSectionHeading,
    InputRichBlockUnion,
    InputRichMessage,
    RichBlockButtons,
    RichBlockCollage,
    RichBlockPhoto,
    RichBlockUnion,
    RichMessage,
    RichMessageButton,
)
from aiogram.utils.i18n import gettext as _

from manashelper.services.daily_menu import DailyMenuModel
from manashelper.services.html_sanitization import escape_html
from manashelper.services.timetable_formatter import weekday_full

MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaLivePhoto | InputMediaPhoto | InputMediaVideo


def format_daily_menu(daily_menu: DailyMenuModel) -> str:
    weekday_name = weekday_full(daily_menu.date.isoweekday())
    lines = [
        _("food.menu_header").format(weekday=weekday_name, date=daily_menu.date.strftime("%d.%m.%Y")),
        "",
    ]

    total_calories = 0
    for index, dish in enumerate(daily_menu.dishes, start=1):
        lines.append(_("food.dish").format(index=index, name=escape_html(dish.name), calories=dish.calories))
        total_calories += dish.calories

    lines.append("")
    lines.append(_("food.total_calories").format(calories=total_calories))
    if daily_menu.ratings_count:
        lines.append(
            _("food.rating").format(average=f"{daily_menu.average_rating:.1f}", count=daily_menu.ratings_count)
        )
    else:
        lines.append(_("food.no_ratings"))
    lines.append(_("food.views").format(count=daily_menu.views_count))
    return "\n".join(lines)


def format_not_found(skip_days: int) -> str:
    if skip_days == 0:
        return _("food.today_unpublished")
    return _("food.menu_unpublished")


def build_photos(caption: str, daily_menu: DailyMenuModel) -> list[MediaGroupItem]:
    photos: list[MediaGroupItem] = [
        InputMediaPhoto(
            media=dish.photo_url,
            caption=caption if index == 0 else None,
            parse_mode=ParseMode.HTML if index == 0 else None,
        )
        for index, dish in enumerate(daily_menu.dishes)
    ]
    return photos


def _format_menu_rating(daily_menu: DailyMenuModel) -> str:
    if daily_menu.ratings_count:
        return _("food.rich_rating").format(average=f"{daily_menu.average_rating:.1f}", count=daily_menu.ratings_count)
    return _("food.no_ratings")


def format_menu_day_selection(has_dates: bool, *, show_usage: bool = False) -> str:
    lines = [_("food.day_selection_title")]
    if show_usage:
        lines.append(_("food.rich_command_usage"))
    lines.append(_("food.choose_day") if has_dates else _("food.no_available_menus"))
    return "\n\n".join(lines)


def build_daily_menu_rich_message(
    daily_menu: DailyMenuModel,
    rating_buttons: InputRichBlockButtons,
    settings_buttons: list[RichMessageButton],
) -> InputRichMessage:
    blocks: list[InputRichBlockUnion] = [
        InputRichBlockSectionHeading(
            size=2,
            text=_("food.rich_menu_header").format(
                weekday=weekday_full(daily_menu.date.isoweekday()), date=daily_menu.date.strftime("%d.%m.%Y")
            ),
        ),
    ]
    photos: list[InputRichBlockUnion] = [
        InputRichBlockPhoto(photo=InputMediaPhoto(media=dish.photo_url)) for dish in daily_menu.dishes
    ]
    if len(photos) > 1:
        blocks.append(InputRichBlockCollage(blocks=photos))
    elif photos:
        blocks.append(photos[0])
    dish_lines = []
    for index, dish in enumerate(daily_menu.dishes, start=1):
        dish_lines.append(_("food.rich_dish").format(index=index, name=dish.name, calories=dish.calories))
    blocks.append(InputRichBlockParagraph(text="\n".join(dish_lines)))
    blocks.extend(
        [
            InputRichBlockParagraph(
                text=_("food.rich_total_calories").format(calories=sum(dish.calories for dish in daily_menu.dishes))
            ),
            InputRichBlockParagraph(text=_format_menu_rating(daily_menu)),
            InputRichBlockParagraph(text=_("food.rate_prompt")),
            rating_buttons,
            InputRichBlockParagraph(text=_("food.views").format(count=daily_menu.views_count)),
            InputRichBlockParagraph(text=_("food.enjoy_meal")),
        ]
    )
    blocks.extend(InputRichBlockButtons(buttons=[button]) for button in settings_buttons)
    # Block text is plain RichText, so dish names cannot inject HTML or links.
    return InputRichMessage(blocks=blocks, skip_entity_detection=True)


def refresh_daily_menu_rating(
    rich_message: RichMessage, daily_menu: DailyMenuModel, rating_buttons: InputRichBlockButtons
) -> InputRichMessage:
    blocks: list[dict[str, object]] = []
    for block in rich_message.blocks:
        data = _rich_block_to_input(block)
        if (
            isinstance(block, RichBlockButtons)
            and block.buttons
            and block.buttons[0].callback_data == rating_buttons.buttons[0].callback_data
            and len(blocks) >= 2
        ):
            blocks[-2] = InputRichBlockParagraph(text=_format_menu_rating(daily_menu)).model_dump()
            data = rating_buttons.model_dump()
        blocks.append(data)
    return InputRichMessage.model_validate({"blocks": blocks, "skip_entity_detection": True})


def _rich_block_to_input(block: RichBlockUnion) -> dict[str, object]:
    data = block.model_dump()
    if isinstance(block, RichBlockPhoto):
        data["photo"] = InputMediaPhoto(media=block.photo[-1].file_id).model_dump()
    elif isinstance(block, RichBlockCollage):
        data["blocks"] = [_rich_block_to_input(child) for child in block.blocks]
    return data
