import logging
from typing import Protocol

from manashelper.modules.food_menu.application.daily_menu import (
    DailyMenuModel,
)

logger = logging.getLogger(__name__)


class FoodMenuSender(Protocol):
    async def send(self, daily_menu: DailyMenuModel, user_id: int) -> None: ...
