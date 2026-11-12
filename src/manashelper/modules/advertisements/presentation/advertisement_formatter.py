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
    InputRichBlockVideo,
    InputRichMessage,
    RichMessageButton,
)
from aiogram.utils.i18n import gettext as _

from manashelper.modules.advertisements.application.advertisement import AdvertisementMediaItem, AdvertisementSummary
from manashelper.modules.advertisements.application.advertisement_contact import ContactReveal
from manashelper.modules.advertisements.domain.contact import ContactStatus
from manashelper.modules.advertisements.domain.enums import AdvertisementMediaType
from manashelper.platform.telegram.html import escape_html

MediaGroupItem = InputMediaAudio | InputMediaDocument | InputMediaLivePhoto | InputMediaPhoto | InputMediaVideo

_STATUS_EMOJI = {
    "pending": "⏳",
    "published": "✅",
    "rejected": "❌",
}


def status_emoji(status_value: str) -> str:
    return _STATUS_EMOJI.get(status_value, "❓")


def _status_label(status_value: str) -> str:
    labels = {
        "pending": _("ads.status_pending"),
        "published": _("ads.status_published"),
        "rejected": _("ads.status_rejected"),
    }
    return labels.get(status_value, status_value)


def format_advertisement(
    advertisement: AdvertisementSummary,
    *,
    contact: ContactStatus | None = None,
    show_status: bool = False,
) -> str:
    """Render an ad as HTML, optionally with contacts for its owner or moderator.

    All user-supplied fields (title, description, rejection comment, contact details) are HTML-escaped
    here, since a bare `&`/`<`/`>` would otherwise make Telegram reject the whole message."""
    lines = [f"<b>{escape_html(advertisement.title)}</b>", "", escape_html(advertisement.description)]

    if advertisement.price is not None:
        lines.append("")
        lines.append(_("ads.price").format(price=advertisement.price))

    if advertisement.expires_at is not None:
        lines.append(_("ads.valid_until").format(date=advertisement.expires_at.strftime("%d.%m.%Y %H:%M")))

    if contact is not None:
        contact_lines = []
        if contact.username:
            contact_lines.append(f"@{escape_html(contact.username)}")
        contact_lines.extend(escape_html(phone) for phone in contact.phone_numbers)
        if contact_lines:
            lines.append("")
            lines.append(_("ads.contacts"))
            lines.extend(contact_lines)

    if show_status:
        lines.append("")
        lines.append(f"{status_emoji(advertisement.status.value)} {_status_label(advertisement.status.value)}")
        if advertisement.status.value == "rejected" and advertisement.rejection_comment:
            lines.append(_("ads.reason").format(comment=escape_html(advertisement.rejection_comment)))

    return "\n".join(lines)


def build_advertisement_rich_message(advertisement: AdvertisementSummary, contact_deep_link: str) -> InputRichMessage:
    """Build a public post with plain source data and contacts gated by the bot deep link."""
    blocks: list[InputRichBlockUnion] = [InputRichBlockSectionHeading(size=2, text=advertisement.title)]
    media: list[InputRichBlockUnion] = []
    for item in advertisement.media:
        if item.media_type == AdvertisementMediaType.VIDEO:
            media.append(InputRichBlockVideo(video=InputMediaVideo(media=item.file_id)))
        else:
            media.append(InputRichBlockPhoto(photo=InputMediaPhoto(media=item.file_id)))
    if len(media) > 1:
        blocks.append(InputRichBlockCollage(blocks=media))
    elif media:
        blocks.append(media[0])
    blocks.append(InputRichBlockParagraph(text=advertisement.description))
    if advertisement.price is not None:
        blocks.append(InputRichBlockParagraph(text=_("ads.rich_price").format(price=advertisement.price)))
    if advertisement.expires_at is not None:
        blocks.append(
            InputRichBlockParagraph(
                text=_("ads.valid_until").format(date=advertisement.expires_at.strftime("%d.%m.%Y %H:%M"))
            )
        )
    blocks.append(
        InputRichBlockButtons(buttons=[RichMessageButton(text=_("ads.contacts_button"), url=contact_deep_link)])
    )
    return InputRichMessage(blocks=blocks, skip_entity_detection=True)


def format_contact_reveal(reveal: ContactReveal) -> str:
    lines = [_("ads.contact_title").format(title=escape_html(reveal.advertisement_title))]
    if reveal.contact.username:
        lines.append(f"@{escape_html(reveal.contact.username)}")
    lines.extend(escape_html(phone) for phone in reveal.contact.phone_numbers)
    if len(lines) == 1:
        lines.append(_("ads.no_contacts"))
    return "\n".join(lines)


def build_media_group(caption: str, media: list[AdvertisementMediaItem]) -> list[MediaGroupItem]:
    items: list[MediaGroupItem] = []
    for index, item in enumerate(media):
        item_caption = caption if index == 0 else None
        parse_mode = ParseMode.HTML if index == 0 else None
        if item.media_type == AdvertisementMediaType.VIDEO:
            items.append(InputMediaVideo(media=item.file_id, caption=item_caption, parse_mode=parse_mode))
        else:
            items.append(InputMediaPhoto(media=item.file_id, caption=item_caption, parse_mode=parse_mode))
    return items
