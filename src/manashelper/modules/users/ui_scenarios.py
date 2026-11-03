"""Initial reusable preference dialogs; published database documents stay authoritative."""

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from ui_flows.domain.schema import (
    ActionNode,
    Button,
    CatalogText,
    DataField,
    FlowDocument,
    InlineText,
    LiteralValue,
    MenuNode,
    ReferenceValue,
    ReturnNode,
    TransitionButton,
)

_LANGUAGES = {
    Locale.KY: ("🇰🇬 Кыргызча", "Кыргызча"),
    Locale.RU: ("🇷🇺 Русский", "Русский"),
    Locale.EN: ("🇬🇧 English", "English"),
    Locale.TR: ("🇹🇷 Türkçe", "Türkçe"),
    Locale.ZH: ("🇨🇳 中文", "中文"),
}


def _cancel_button() -> list[Button]:
    return [
        TransitionButton(
            kind="transition",
            id="cancel",
            label=CatalogText(kind="catalog", key="common.cancel"),
            target="cancelled",
        )
    ]


def _cancelled() -> ReturnNode:
    return ReturnNode(
        kind="return",
        id="cancelled",
        outcome="cancelled",
        text=[CatalogText(kind="catalog", key="common.cancelled")],
    )


def _select_locale() -> FlowDocument:
    buttons: list[list[Button]] = [
        [
            TransitionButton(
                kind="transition",
                id=locale.value,
                label=InlineText(kind="inline", translations={"en": label}),
                target="save",
                assignments={
                    "selected": LiteralValue(kind="literal", value=locale.value),
                    "selected_name": LiteralValue(kind="literal", value=name),
                },
            )
        ]
        for locale, (label, name) in _LANGUAGES.items()
    ]
    buttons.append(_cancel_button())
    return FlowDocument(
        schema_version=2,
        id="select_locale",
        entry="choose",
        fields={"selected": DataField(type="text"), "selected_name": DataField(type="text")},
        outcomes=["completed", "cancelled"],
        nodes=[
            MenuNode(
                kind="menu",
                id="choose",
                keyboard="inline",
                text=[CatalogText(kind="catalog", key="language.prompt")],
                buttons=buttons,
            ),
            ActionNode(
                kind="action",
                id="save",
                delegate="users.set_locale",
                arguments={"locale": ReferenceValue(kind="ref", scope="data", field="selected")},
                outcomes={"success": "completed"},
            ),
            ReturnNode(
                kind="return",
                id="completed",
                outcome="completed",
                text=[
                    CatalogText(
                        kind="catalog",
                        key="language.selected",
                        parameters={"language": ReferenceValue(kind="ref", scope="data", field="selected_name")},
                    )
                ],
            ),
            _cancelled(),
        ],
    )


def _select_theme() -> FlowDocument:
    buttons: list[list[Button]] = [
        [
            TransitionButton(
                kind="transition",
                id=theme.value,
                label=CatalogText(kind="catalog", key=f"theme.{theme.value}"),
                target="save",
                assignments={"selected": LiteralValue(kind="literal", value=theme.value)},
            )
        ]
        for theme in Theme
    ]
    buttons.append(_cancel_button())
    return FlowDocument(
        schema_version=2,
        id="select_theme",
        entry="choose",
        fields={"selected": DataField(type="text"), "selected_name": DataField(type="text")},
        outcomes=["completed", "cancelled"],
        nodes=[
            MenuNode(
                kind="menu",
                id="choose",
                keyboard="inline",
                text=[CatalogText(kind="catalog", key="theme.prompt")],
                buttons=buttons,
            ),
            ActionNode(
                kind="action",
                id="save",
                delegate="users.set_theme",
                arguments={"theme": ReferenceValue(kind="ref", scope="data", field="selected")},
                results={"selected_name": "selected_name"},
                outcomes={"success": "completed"},
            ),
            ReturnNode(
                kind="return",
                id="completed",
                outcome="completed",
                text=[
                    CatalogText(
                        kind="catalog",
                        key="theme.selected",
                        parameters={"theme": ReferenceValue(kind="ref", scope="data", field="selected_name")},
                    )
                ],
            ),
            _cancelled(),
        ],
    )


def user_scenarios() -> list[FlowDocument]:
    return [_select_locale(), _select_theme()]
