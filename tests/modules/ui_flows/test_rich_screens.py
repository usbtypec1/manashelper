from uuid import uuid4

import pytest

from manashelper.modules.ui_flows.presentation.admin_contracts import PreviewRequest, PreviewUser
from manashelper.modules.ui_flows.presentation.preview import preview
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer, InvalidScreenError
from ui_flows.application.delegates import DelegateRegistry
from ui_flows.application.policy import FlowPolicy
from ui_flows.application.validation import validate_flow
from ui_flows.domain.schema import FlowDocument
from ui_flows.domain.state import DialogState, ExecutionResult, RuntimeUser


def rich_document(*, caption="Caption", chunks=None, messages=None):
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "rich_screen",
            "entry": "show",
            "fields": {
                "attachments": {
                    "type": "list",
                    "max_items": 10,
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "text"},
                            "file_id": {"type": "text"},
                            "caption": {"type": "text", "nullable": True},
                        },
                    },
                },
                "chunks": {"type": "list", "max_items": 19, "items": {"type": "text"}},
            },
            "initial_data": {
                "attachments": [{"type": "photo", "file_id": "cached-file", "caption": caption}],
                "chunks": chunks if chunks is not None else ["<script>escaped & exact</script>"],
            },
            "nodes": [
                {
                    "kind": "menu",
                    "id": "show",
                    "keyboard": "inline",
                    "text": [{"kind": "inline", "translations": {"en": "Primary"}}],
                    "buttons": [],
                    "media": {"kind": "ref", "scope": "data", "field": "attachments"},
                    "message_source": {"kind": "ref", "scope": "data", "field": "chunks"},
                    "messages": messages or [{"kind": "inline", "translations": {"en": "<b>Introduction</b>"}}],
                }
            ],
        }
    )


def render(document):
    node = document.nodes[0]
    state = DialogState(uuid4(), 1, 1, document.id, 1, node.id, "waiting_button", 0, document.initial_data)
    return FlowRenderer().render(document, ExecutionResult(state, node, "started"), RuntimeUser(1, 1), {})


def issues(document):
    return validate_flow(document, delegates=[], features=set(), catalog_keys=set(), capabilities={})


@pytest.mark.parametrize("caption", ["<" * 300, "😀" * 512])
def test_media_captions_use_decoded_utf16_length_and_escape_dynamic_content(caption):
    document = rich_document(caption=caption)
    assert issues(document) == []
    FlowRenderer().validate_document(document, {})
    screen = render(document)
    assert screen.messages == ["<b>Introduction</b>", "&lt;script&gt;escaped &amp; exact&lt;/script&gt;"]
    assert screen.media[0].caption == ("&lt;" * 300 if caption.startswith("<") else caption)


def test_media_caption_exceeding_rendered_limit_fails_before_telegram_io():
    with pytest.raises(InvalidScreenError):
        render(rich_document(caption="😀" * 513))


@pytest.mark.parametrize(
    "field,shape,code",
    [
        ("attachments", {"type": "text"}, "screen_media"),
        ("attachments", {"type": "list", "max_items": 11, "items": {"type": "text"}}, "screen_media"),
        ("chunks", {"type": "list", "max_items": 19, "items": {"type": "integer"}}, "message_source"),
        ("chunks", {"type": "list", "max_items": 20, "items": {"type": "text"}}, "screen_messages"),
    ],
)
def test_incompatible_rich_sources_are_rejected_by_publication_contract(field, shape, code):
    body = rich_document().model_dump(mode="json")
    body["fields"][field] = shape
    body["initial_data"].pop(field)
    assert code in {issue.code for issue in issues(FlowDocument.model_validate(body))}


@pytest.mark.parametrize("variant", ["translation", "theme"])
def test_authored_message_markup_is_validated_in_every_variant_before_publication(variant):
    text = {"kind": "inline", "translations": {"en": "Safe"}}
    if variant == "translation":
        text["translations"]["ru"] = "<script>bad</script>"
    else:
        text["themes"] = {"halloween": {"zh": "<script>bad</script>"}}
    with pytest.raises(InvalidScreenError):
        FlowRenderer().validate_document(rich_document(messages=[text]), {})


def test_rich_fields_require_v2_and_combined_runtime_chunks_remain_bounded():
    body = rich_document().model_dump(mode="json")
    body["schema_version"] = 1
    assert "v2_screen" in {issue.code for issue in issues(FlowDocument.model_validate(body))}
    with pytest.raises(InvalidScreenError):
        render(rich_document(chunks=["chunk"] * 20))


async def test_preview_exposes_rich_screen_without_telegram_or_file_fetches():
    result = await preview(
        PreviewRequest(
            document=rich_document(),
            user=PreviewUser(id=1, chat_id=1, locale="en", theme="basic"),
            eders_enabled=False,
        ),
        DelegateRegistry(),
        FlowPolicy(),
    )
    assert result.issues == []
    assert result.screen.messages == ["<b>Introduction</b>", "&lt;script&gt;escaped &amp; exact&lt;/script&gt;"]
    assert result.screen.media[0].kind == "photo" and result.screen.media[0].caption == "Caption"
