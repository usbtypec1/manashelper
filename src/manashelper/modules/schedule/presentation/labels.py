from aiogram.utils.i18n import gettext as _

from manashelper.modules.schedule.application.course_level import CourseLevel


def course_label(number: int, level: CourseLevel) -> str:
    """Undergraduates see their year ("3 курс"); graduate programmes are named instead of numbered 5/6."""
    match level:
        case CourseLevel.MASTER:
            return _("schedule.course_master")
        case CourseLevel.DOCTORATE:
            return _("schedule.course_doctorate")
        case _:
            return _("schedule.course_year").format(number=number)
