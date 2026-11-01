import json

import pytest
from pydantic import TypeAdapter, ValidationError

from ui_flows.domain.contracts import FlowEvent, InputEvent
from ui_flows.domain.schema import FlowDocument, InlineText, InputNode


def test_document_round_trip_preserves_interface_contract(main_menu_document):
    document = FlowDocument.model_validate(main_menu_document)
    restored = FlowDocument.model_validate_json(document.model_dump_json())
    assert restored == document
    assert [len(row) for row in restored.nodes[0].buttons] == [2, 1, 1]


@pytest.mark.parametrize("version", [True, "1", 1.0, 2])
def test_schema_version_is_explicit_and_not_coerced(main_menu_document, version):
    main_menu_document["schema_version"] = version
    with pytest.raises(ValidationError):
        FlowDocument.model_validate(main_menu_document)


@pytest.mark.parametrize("change", ["extra", "script", "missing_default", "invalid_identifier", "string_bool"])
def test_malformed_documents_are_rejected(survey_document, change):
    if change == "extra":
        survey_document["unexpected"] = True
    elif change == "script":
        survey_document["nodes"][0]["kind"] = "python"
    elif change == "missing_default":
        del survey_document["nodes"][1]["default"]
    elif change == "invalid_identifier":
        survey_document["nodes"][0]["id"] = "user.__class__"
    else:
        survey_document["fields"]["overwrite"]["nullable"] = "false"
    with pytest.raises(ValidationError):
        FlowDocument.model_validate(survey_document)


@pytest.mark.parametrize(
    "translations, parameters",
    [
        ({"ru": "Привет"}, {}),
        ({"en": "Hello {name}", "ru": "Привет {other}"}, {"name": {"kind": "literal", "value": "test"}}),
        ({"en": "{user.password}"}, {}),
        ({"en": "{value!r}"}, {}),
        ({"en": "{value:1000000}"}, {}),
        ({"en": "{0}"}, {}),
        ({"en": "{name}"}, {}),
    ],
)
def test_translations_require_fallback_and_safe_consistent_bindings(translations, parameters):
    with pytest.raises(ValidationError):
        InlineText(kind="inline", translations=translations, parameters=parameters)


def test_inline_themes_and_five_locales_share_parameters():
    text = InlineText.model_validate(
        {
            "kind": "inline",
            "translations": {locale: "Hello {name}" for locale in ("en", "ru", "ky", "tr", "zh")},
            "themes": {"halloween": {"ru": "Boo {name}"}},
            "parameters": {"name": {"kind": "ref", "scope": "data", "field": "name"}},
        }
    )
    assert text.translations["en"] == "Hello {name}"
    with pytest.raises(ValidationError):
        InlineText.model_validate({**text.model_dump(), "themes": {"halloween": {"ru": "Boo {other}"}}})


def test_input_limits_cannot_contradict_each_other(survey_document):
    node = next(node for node in survey_document["nodes"] if node["kind"] == "input")
    node.update(min_length=5, max_length=2)
    with pytest.raises(ValidationError):
        InputNode.model_validate(node)


def test_event_identity_is_separate_from_sensitive_input():
    payload = {
        "kind": "input",
        "update_id": 42,
        "user_id": 1,
        "chat_id": 1,
        "session_id": "session",
        "expected_revision": 3,
        "text": "private answer",
    }
    event = TypeAdapter(FlowEvent).validate_json(json.dumps(payload))
    assert isinstance(event, InputEvent)
    assert event.text == "private answer"
    assert "private answer" not in repr(event)
    with pytest.raises(ValidationError):
        TypeAdapter(FlowEvent).validate_python({**payload, "expected_revision": -1})
