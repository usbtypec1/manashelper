"""Bind the actor's explicit preferences around application UI adapters."""

from collections.abc import Mapping

from manashelper.localization.theme import Theme
from manashelper.platform.i18n.catalog import i18n
from ui_flows.domain.contracts import Delegate, DelegateContext, DelegateResult
from ui_flows.domain.schema import DataValue


class LocalizedDelegate:
    def __init__(self, handler: Delegate) -> None:
        self._handler = handler

    async def __call__(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        with i18n.context(), i18n.use_locale(context.locale), i18n.use_theme(Theme(context.theme)):
            return await self._handler(context, arguments)
