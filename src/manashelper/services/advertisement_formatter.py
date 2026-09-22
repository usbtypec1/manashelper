from aiogram.enums import ParseMode
from aiogram.types import InputMediaAudio, InputMediaDocument, InputMediaLivePhoto, InputMediaPhoto, InputMediaVideo
from aiogram.utils.i18n import gettext as _

from manashelper.db.models.advertisement_media import AdvertisementMediaType
from manashelper.services.advertisement import AdvertisementMediaItem, AdvertisementSummary
from manashelper.services.user_contact import ContactStatus

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
        "pending": _("Awaiting review"),
        "published": _("Published"),
        "rejected": _("Rejected"),
    }
    return labels.get(status_value, status_value)


def format_advertisement(
    advertisement: AdvertisementSummary, *, contact: ContactStatus | None = None, show_status: bool = False
) -> str:
    lines = [f"<b>{advertisement.title}</b>", "", advertisement.description]

    if advertisement.price is not None:
        lines.append("")
        lines.append(_("💵 Price: <b>{price}</b> som").format(price=advertisement.price))

    if advertisement.expires_at is not None:
        lines.append(_("⏰ Valid until: {date}").format(date=advertisement.expires_at.strftime("%d.%m.%Y")))

    if contact is not None:
        contact_lines = []
        if contact.username:
            contact_lines.append(f"@{contact.username}")
        contact_lines.extend(contact.phone_numbers)
        if contact_lines:
            lines.append("")
            lines.append(_("📞 Contacts:"))
            lines.extend(contact_lines)

    if show_status:
        lines.append("")
        lines.append(f"{status_emoji(advertisement.status.value)} {_status_label(advertisement.status.value)}")
        if advertisement.status.value == "rejected" and advertisement.rejection_comment:
            lines.append(_("💬 Reason: {comment}").format(comment=advertisement.rejection_comment))

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
