from dataclasses import dataclass
from datetime import datetime, timedelta

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.food_menu.application.daily_menu import DailyMenuModel
from manashelper.modules.food_menu.application.use_cases.get_daily_menu import GetDailyMenuUseCase


@dataclass(frozen=True, slots=True)
class GetDailyMenuByOffsetUseCase:
    get_daily_menu: GetDailyMenuUseCase

    async def execute(self, skip_days: int, user_id: int | None = None) -> DailyMenuModel:
        target_date = datetime.now(BISHKEK_TZ).date() + timedelta(days=skip_days)
        return await self.get_daily_menu.execute(target_date, user_id=user_id)
