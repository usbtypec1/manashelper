"""Transactional food notification settings for composed UI scenarios."""

from collections.abc import Mapping

from manashelper.localization.weekdays import weekday_abbr
from manashelper.modules.food_menu.application.food_menu_cleanup_settings import (
    FoodMenuCleanupOption,
    FoodMenuCleanupSettingsService,
)
from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuMeal,
    FoodMenuNotificationSettingsService,
)
from manashelper.modules.food_menu.presentation.keyboards.food_menu_cleanup import _option_label
from ui_flows.application.delegates import DelegateBinding
from ui_flows.domain.contracts import DelegateContext, DelegateDefinition, DelegateParameter, DelegateResult
from ui_flows.domain.schema import DataField, DataValue
from ui_flows.errors import FlowExecutionError

DAY_ROW = DataField(
    type="object",
    properties={
        "weekday": DataField(type="integer"),
        "label": DataField(type="text"),
        "lunch": DataField(type="text"),
        "dinner": DataField(type="text"),
    },
)
DAY_ROWS = DataField(type="list", items=DAY_ROW, max_items=7)
CLEANUP_OPTIONS = DataField(
    type="list",
    items=DataField(type="object", properties={"id": DataField(type="text"), "label": DataField(type="text")}),
    max_items=5,
)


class FoodMenuUiDelegates:
    def __init__(self, settings: FoodMenuNotificationSettingsService, cleanup: FoodMenuCleanupSettingsService) -> None:
        self._settings = settings
        self._cleanup = cleanup

    async def read_cleanup(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        selected = await self._cleanup.get_option(context.chat_id)
        options: list[DataValue] = [
            {"id": option.value, "label": ("✅ " if selected == option else "") + _option_label(option)}
            for option in FoodMenuCleanupOption
        ]
        return DelegateResult("success", {"options": options})

    async def change_cleanup(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        value = arguments.get("option")
        if not isinstance(value, str):
            raise FlowExecutionError("Invalid food menu cleanup option")
        try:
            option = FoodMenuCleanupOption(value)
        except ValueError:
            raise FlowExecutionError("Invalid food menu cleanup option") from None
        await self._cleanup.set_option(context.chat_id, option)
        return DelegateResult("success", {})

    async def read_notifications(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        summary = await self._settings.get_settings(context.user_id)
        rows: list[DataValue] = [
            {
                "weekday": day.weekday,
                "label": weekday_abbr(day.weekday + 1),
                "lunch": "✅" if day.lunch_enabled else "❌",
                "dinner": "✅" if day.dinner_enabled else "❌",
            }
            for day in summary.days
        ]
        return DelegateResult("success", {"days": rows})

    async def change_notifications(
        self, context: DelegateContext, arguments: Mapping[str, DataValue]
    ) -> DelegateResult:
        action = arguments.get("action")
        weekday = arguments.get("weekday")
        meal = arguments.get("meal")
        if type(weekday) is not int or not 0 <= weekday <= 6 or not isinstance(meal, str):
            raise FlowExecutionError("Invalid food notification choice")
        if action == "weekday":
            await self._settings.toggle_weekday(context.user_id, weekday)
        elif action in {"day", "meal"}:
            try:
                selected_meal = FoodMenuMeal(meal)
            except ValueError:
                raise FlowExecutionError("Invalid food notification meal") from None
            if action == "day":
                await self._settings.toggle(context.user_id, weekday, selected_meal)
            else:
                await self._settings.toggle_meal(context.user_id, selected_meal)
        elif action == "enable_all":
            await self._settings.enable_all(context.user_id)
        elif action == "disable_all":
            await self._settings.disable_all(context.user_id)
        else:
            raise FlowExecutionError("Invalid food notification action")
        return DelegateResult("success", {})

    def bindings(self) -> list[DelegateBinding]:
        return [
            DelegateBinding(
                DelegateDefinition(
                    id="food_menu.cleanup.read",
                    effect="read",
                    outputs={"options": CLEANUP_OPTIONS},
                    outcomes=["success"],
                ),
                self.read_cleanup,
            ),
            DelegateBinding(
                DelegateDefinition(
                    id="food_menu.cleanup.change",
                    effect="database_write",
                    inputs={"option": DelegateParameter(type="text")},
                    outcomes=["success"],
                ),
                self.change_cleanup,
            ),
            DelegateBinding(
                DelegateDefinition(
                    id="food_menu.notifications.read", effect="read", outputs={"days": DAY_ROWS}, outcomes=["success"]
                ),
                self.read_notifications,
            ),
            DelegateBinding(
                DelegateDefinition(
                    id="food_menu.notifications.change",
                    effect="database_write",
                    inputs={
                        "action": DelegateParameter(type="text"),
                        "weekday": DelegateParameter(type="integer"),
                        "meal": DelegateParameter(type="text"),
                    },
                    outcomes=["success"],
                ),
                self.change_notifications,
            ),
        ]
