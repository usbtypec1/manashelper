import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import DailyMenu
from manashelper.localization.i18n import i18n
from manashelper.repositories.daily_menu_rating_repository import DailyMenuRatingRepository
from manashelper.repositories.daily_menu_repository import DailyMenuRepository
from manashelper.services import daily_menu as daily_menu_module
from manashelper.services.daily_menu import BISHKEK_TZ, DailyMenuService


class _Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        # 22:30 UTC is already the next date in Bishkek.
        return datetime(2097, 12, 28, 22, 30, tzinfo=UTC).astimezone(tz or BISHKEK_TZ)


async def test_availability_includes_only_published_dates_in_seven_day_window_and_keeps_views(
    session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(daily_menu_module, "datetime", _Clock)
    today = _Clock.now().date()
    menus = [
        DailyMenu(id=uuid.uuid4(), date=today + timedelta(days=offset), dishes=[], views_count=23)
        for offset in (7, 2, -1, 6, 0, 9, 4)
    ]
    session.add_all(menus)
    await session.flush()
    service = DailyMenuService(DailyMenuRepository(session), DailyMenuRatingRepository(session))
    available = await service.get_available_dates()
    assert available.today == today
    assert available.dates == [today + timedelta(days=offset) for offset in (0, 2, 4, 6)]
    for menu in menus:
        await session.refresh(menu)
        assert menu.views_count == 23


async def test_availability_is_empty_when_no_menu_is_published(session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(daily_menu_module, "datetime", _Clock)
    service = DailyMenuService(DailyMenuRepository(session), DailyMenuRatingRepository(session))
    assert (await service.get_available_dates()).dates == []


def test_all_seven_day_buttons_contain_fixed_dates_and_fit_callback_limit() -> None:
    from manashelper.bot.callback_data import FoodMenuDateCallback
    from manashelper.bot.keyboards.food_menu import build_menu_day_buttons

    today = _Clock.now().date()
    dates = [today + timedelta(days=offset) for offset in range(7)]
    for locale in ("en", "ru", "ky", "tr", "zh"):
        with i18n.context(), i18n.use_locale(locale):
            rows = build_menu_day_buttons(dates, today)
            for menu_date, row in zip(dates, rows, strict=True):
                assert len(row.buttons) == 1
                button = row.buttons[0]
                assert menu_date.strftime("%d.%m") in button.text
                assert FoodMenuDateCallback.unpack(button.callback_data).menu_date == menu_date.isoformat()
                assert len(button.callback_data.encode()) <= 64
                assert "food." not in button.text
