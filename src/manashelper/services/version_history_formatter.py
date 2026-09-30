from aiogram.utils.i18n import gettext as _

from manashelper.services.version_history import VersionDetail


def format_versions_list_header(page: int, total_pages: int) -> str:
    if total_pages > 1:
        return _("versions.title_page").format(page=page + 1, total_pages=total_pages)
    return _("versions.title")


def format_version_detail(entry: VersionDetail) -> str:
    return "\n".join(
        [
            _("versions.version_header").format(version=entry.version),
            _("versions.release_date").format(date=entry.released_at.strftime("%d.%m.%Y")),
            "",
            entry.description,
        ]
    )
