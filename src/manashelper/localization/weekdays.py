from aiogram.utils.i18n import gettext as _


def weekday_abbr(weekday: int) -> str:
    match weekday:
        case 1:
            return _("weekday.mon")
        case 2:
            return _("weekday.tue")
        case 3:
            return _("weekday.wed")
        case 4:
            return _("weekday.thu")
        case 5:
            return _("weekday.fri")
        case 6:
            return _("weekday.sat")
        case _:
            return _("weekday.sun")


def weekday_full(weekday: int) -> str:
    match weekday:
        case 1:
            return _("weekday.monday")
        case 2:
            return _("weekday.tuesday")
        case 3:
            return _("weekday.wednesday")
        case 4:
            return _("weekday.thursday")
        case 5:
            return _("weekday.friday")
        case 6:
            return _("weekday.saturday")
        case _:
            return _("weekday.sunday")
