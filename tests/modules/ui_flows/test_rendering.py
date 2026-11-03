from dataclasses import replace
from uuid import uuid4

import pytest

from manashelper.modules.ui_flows.demo import demo_document
from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer, InvalidScreenError, validate_message
from ui_flows.domain.schema import FlowDocument
from ui_flows.domain.state import DialogState, ExecutionResult, RuntimeUser


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
@pytest.mark.parametrize("theme", ["basic", "halloween"])
def test_demo_templates_render_in_every_locale_and_theme(locale, theme):
    flow = demo_document()
    state = DialogState(
        uuid4(), 1, 1, flow.id, 1, "menu", "waiting_button", 0, {"submitted": False, "answer": "<b>private</b>"}
    )
    renderer = FlowRenderer()
    for node in flow.nodes:
        if node.kind not in {"menu", "input", "end"}:
            continue
        screen = renderer.render(
            flow,
            ExecutionResult(replace(state, node_id=node.id), node, "resumed"),
            RuntimeUser(1, 1, locale, theme),
            {},
        )
        assert "ui_flows." not in screen.text
        if node.id == "shown":
            assert "&lt;b&gt;private&lt;/b&gt;" in screen.text
        for index in range(sum(len(row) for row in screen.buttons)):
            assert len(UiFlowCallback(token="x" * 16, index=index).pack().encode()) <= 64


@pytest.mark.parametrize(
    "text",
    [
        "<script>alert(1)</script>",
        "<b>unclosed",
        '<a href="javascript:alert(1)">x</a>',
        "<!-- hidden -->text",
        "😀" * 2049,
    ],
)
def test_unsupported_html_and_oversize_messages_fail_before_delivery(text):
    with pytest.raises(InvalidScreenError):
        validate_message(text)


def test_ambiguous_reply_labels_cannot_be_sent():
    flow = demo_document().model_dump(mode="json")
    menu = flow["nodes"][1]
    menu["buttons"][1][0]["label"] = menu["buttons"][0][0]["label"]
    flow = FlowDocument.model_validate(flow)
    state = DialogState(uuid4(), 1, 1, flow.id, 1, "menu", "waiting_button", 0, {"submitted": False})
    with pytest.raises(InvalidScreenError, match="ambiguous"):
        FlowRenderer().render(flow, ExecutionResult(state, flow.nodes[1], "started"), RuntimeUser(1, 1), {})


def test_reply_labels_cannot_be_parsed_as_global_commands():
    flow = demo_document().model_dump(mode="json")
    flow["nodes"][1]["buttons"][0][0]["label"] = {"kind": "inline", "translations": {"en": "/other"}}
    document = FlowDocument.model_validate(flow)
    with pytest.raises(InvalidScreenError, match="commands"):
        FlowRenderer().validate_document(document, {})


def test_inline_text_uses_theme_and_english_fallback_without_foreign_locale_leakage():
    flow = FlowDocument.model_validate(
        {
            "schema_version": 1,
            "id": "fallback",
            "entry": "menu",
            "nodes": [
                {
                    "kind": "menu",
                    "id": "menu",
                    "keyboard": "reply",
                    "buttons": [],
                    "text": [
                        {
                            "kind": "inline",
                            "translations": {"en": "Base", "ru": "База"},
                            "themes": {"halloween": {"en": "Boo"}},
                        }
                    ],
                },
            ],
        }
    )
    state = DialogState(uuid4(), 1, 1, flow.id, 1, "menu", "waiting_button", 0, {})
    result = ExecutionResult(state, flow.nodes[0], "started")
    assert FlowRenderer().render(flow, result, RuntimeUser(1, 1, "ru", "halloween"), {}).text == "База"
    assert FlowRenderer().render(flow, result, RuntimeUser(1, 1, "zh", "halloween"), {}).text == "Boo"
    assert FlowRenderer().render(flow, result, RuntimeUser(1, 1, "en", "basic"), {}).text == "Base"
