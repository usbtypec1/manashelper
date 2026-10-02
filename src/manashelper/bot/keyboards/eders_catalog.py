from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import EdersCatalogCallback
from manashelper.services.eders_models import EdersCatalogView, EdersCourse

COURSES_PER_PAGE = 5


def build_catalog_keyboard(
    session_id: str,
    view: EdersCatalogView,
    course_id: int,
    page: int,
    count: int,
    courses: list[EdersCourse],
    *,
    grade_id: int = 0,
    grade_index: int = 0,
    show_feedback: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    is_courses = view in {EdersCatalogView.MATERIAL_COURSES, EdersCatalogView.GRADE_COURSES}
    target = (
        EdersCatalogView.GRADES
        if view in {EdersCatalogView.GRADES, EdersCatalogView.GRADE_COURSES, EdersCatalogView.FEEDBACK}
        else EdersCatalogView.MATERIALS
    )
    if is_courses:
        for course in courses[page * COURSES_PER_PAGE : (page + 1) * COURSES_PER_PAGE]:
            builder.button(
                text=course.name[:60],
                callback_data=EdersCatalogCallback(session_id=session_id, view=target, course_id=course.id),
            )
        builder.button(
            text=_("eders.all_courses"), callback_data=EdersCatalogCallback(session_id=session_id, view=target)
        )
    else:
        if view == EdersCatalogView.FEEDBACK:
            builder.button(
                text=_("eders.back_to_grade"),
                callback_data=EdersCatalogCallback(
                    session_id=session_id, view=EdersCatalogView.GRADES, course_id=course_id, page=grade_index
                ),
            )
        elif show_feedback:
            builder.button(
                text=_("eders.full_feedback"),
                callback_data=EdersCatalogCallback(
                    session_id=session_id, view=EdersCatalogView.FEEDBACK, course_id=course_id, grade_id=grade_id
                ),
            )
        builder.button(
            text=_("eders.choose_course"),
            callback_data=EdersCatalogCallback(
                session_id=session_id,
                view=EdersCatalogView.GRADE_COURSES
                if target == EdersCatalogView.GRADES
                else EdersCatalogView.MATERIAL_COURSES,
            ),
        )
    builder.adjust(1)
    navigation = InlineKeyboardBuilder()
    if page > 0:
        navigation.button(
            text="◀",
            callback_data=EdersCatalogCallback(
                session_id=session_id, view=view, course_id=course_id, page=page - 1, grade_id=grade_id
            ),
        )
    if page + 1 < count:
        navigation.button(
            text="▶",
            callback_data=EdersCatalogCallback(
                session_id=session_id, view=view, course_id=course_id, page=page + 1, grade_id=grade_id
            ),
        )
    builder.attach(navigation)
    return builder.as_markup()
