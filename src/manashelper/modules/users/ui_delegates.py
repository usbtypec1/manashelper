"""Transactional user preferences for explicitly authored UI scenarios."""

from collections.abc import Mapping

from aiogram.utils.i18n import gettext as _

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.platform.i18n.catalog import i18n
from ui_flows.application.delegates import DelegateBinding
from ui_flows.domain.contracts import DelegateContext, DelegateDefinition, DelegateParameter, DelegateResult
from ui_flows.domain.schema import DataField, DataValue
from ui_flows.errors import FlowExecutionError


class UserUiDelegates:
    def __init__(self, locale_service: LocaleService, theme_service: ThemeService) -> None:
        self._locales = locale_service
        self._themes = theme_service

    async def set_locale(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        candidate = arguments.get("locale")
        if not isinstance(candidate, str):
            raise FlowExecutionError("A supported locale is required")
        try:
            locale = Locale(candidate)
        except ValueError:
            raise FlowExecutionError("A supported locale is required") from None
        await self._locales.set_locale(context.user_id, locale)
        return DelegateResult("success", {})

    async def set_theme(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        candidate = arguments.get("theme")
        if not isinstance(candidate, str):
            raise FlowExecutionError("A supported theme is required")
        try:
            theme = Theme(candidate)
        except ValueError:
            raise FlowExecutionError("A supported theme is required") from None
        await self._themes.set_theme(context.user_id, theme)
        locale = await self._locales.get_locale(context.user_id)
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            name = _("theme.halloween") if theme == Theme.HALLOWEEN else _("theme.basic")
        return DelegateResult("success", {"selected_name": name})

    def bindings(self) -> list[DelegateBinding]:
        return [
            DelegateBinding(
                DelegateDefinition(
                    id="users.set_locale",
                    effect="database_write",
                    inputs={"locale": DelegateParameter(type="text")},
                    outcomes=["success"],
                ),
                self.set_locale,
            ),
            DelegateBinding(
                DelegateDefinition(
                    id="users.set_theme",
                    effect="database_write",
                    inputs={"theme": DelegateParameter(type="text")},
                    outputs={"selected_name": DataField(type="text")},
                    outcomes=["success"],
                ),
                self.set_theme,
            ),
        ]
