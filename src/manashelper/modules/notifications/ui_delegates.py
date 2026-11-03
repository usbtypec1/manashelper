"""Transactional notification preferences for authored UI scenarios."""

from collections.abc import Mapping

from manashelper.modules.notifications.settings import (
    NotificationSetting,
    NotificationSettingsService,
    NotificationSettingsSummary,
    UserNotFoundError,
)
from ui_flows.application.delegates import DelegateBinding
from ui_flows.domain.contracts import DelegateContext, DelegateDefinition, DelegateParameter, DelegateResult
from ui_flows.domain.schema import DataField, DataValue
from ui_flows.errors import FlowExecutionError


def _values(settings: NotificationSettingsSummary) -> dict[str, DataValue]:
    return {
        "schedule_changes": settings.schedule_changes_enabled,
        "exam_grades": settings.exam_grades_enabled,
        "lesson_skips": settings.lesson_skips_enabled,
    }


class NotificationUiDelegates:
    def __init__(self, settings: NotificationSettingsService) -> None:
        self._settings = settings

    async def get_settings(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        try:
            settings = await self._settings.get_settings(context.user_id)
        except UserNotFoundError:
            return DelegateResult("not_found", dict.fromkeys(setting.value for setting in NotificationSetting))
        return DelegateResult("success", _values(settings))

    async def toggle_setting(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        value = arguments.get("setting")
        if not isinstance(value, str):
            raise FlowExecutionError("Invalid notification setting")
        try:
            setting = NotificationSetting(value)
        except ValueError:
            raise FlowExecutionError("Invalid notification setting") from None
        try:
            settings = await self._settings.toggle_setting(context.user_id, setting)
        except UserNotFoundError:
            return DelegateResult("not_found", dict.fromkeys(setting.value for setting in NotificationSetting))
        return DelegateResult("success", _values(settings))

    def bindings(self) -> list[DelegateBinding]:
        outputs = {name.value: DataField(type="boolean", nullable=True) for name in NotificationSetting}
        return [
            DelegateBinding(
                DelegateDefinition(
                    id="notifications.get_settings",
                    effect="database_write",
                    outputs=outputs,
                    outcomes=["success", "not_found"],
                ),
                self.get_settings,
            ),
            DelegateBinding(
                DelegateDefinition(
                    id="notifications.toggle_setting",
                    effect="database_write",
                    inputs={"setting": DelegateParameter(type="text")},
                    outputs=outputs,
                    outcomes=["success", "not_found"],
                ),
                self.toggle_setting,
            ),
        ]
