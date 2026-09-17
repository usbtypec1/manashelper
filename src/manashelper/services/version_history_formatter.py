from aiogram.utils.i18n import gettext as _

from manashelper.services.version_history import VersionDetail


def format_versions_list_header(page: int, total_pages: int) -> str:
    if total_pages > 1:
        return _("📦 Version history (page {page}/{total_pages})").format(page=page + 1, total_pages=total_pages)
    return _("📦 Version history")


def format_version_detail(entry: VersionDetail) -> str:
    return "\n".join(
        [
            _("📦 <b>Version {version}</b>").format(version=entry.version),
            _("📅 Released: {date}").format(date=entry.released_at.strftime("%d.%m.%Y")),
            "",
            entry.description,
        ]
    )
