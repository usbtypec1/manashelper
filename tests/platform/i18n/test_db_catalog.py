import asyncio
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, Message, User
from dishka.integrations.aiogram import CONTAINER_NAME
from sqlalchemy import func, select

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.platform.i18n.catalog import CatalogI18n, i18n
from manashelper.platform.i18n.orm import TextCatalogRelease
from manashelper.platform.i18n.repository import TextCatalogRepository, initialize_catalog
from manashelper.platform.i18n.service import TextCatalogService
from manashelper.platform.telegram.filters.translated_text import TranslatedText
from manashelper.platform.telegram.middlewares.i18n import LocaleMiddleware
from ui_flows.application.texts import validate_text_document
from ui_flows.domain.texts import TextDocument, TextSnapshot, plural_form
from ui_flows.errors import FlowConflictError, InvalidFlowError


def changed_entry(document, key="menu.food", *, text="Updated food", locale="en", theme="basic"):
    entry = next(item for item in document.entries if item.key == key)
    return entry.model_copy(
        update={
            "variants": tuple(
                variant.model_copy(update={"text": text})
                if variant.locale == locale and variant.theme == theme
                else variant
                for variant in entry.variants
            )
        }
    )


@pytest.mark.parametrize(
    "locale,counts,forms",
    [
        ("en", (-1, 0, 1, 2), ("other", "other", "one", "other")),
        ("ru", (1, 2, 5, 11, 21, 22, -1), ("one", "few", "many", "many", "one", "few", "many")),
        ("ky", (0, 1, 2), ("other", "one", "other")),
        ("tr", (0, 1, 2), ("other", "other", "other")),
        ("zh", (0, 1, 2), ("other", "other", "other")),
    ],
)
def test_plural_rules_are_fixed_and_preserve_signed_counts(locale, counts, forms):
    assert tuple(plural_form(locale, count) for count in counts) == forms


def test_import_is_complete_valid_immutable_and_keeps_theme_variants(baseline_texts):
    assert len(baseline_texts.document.entries) == 356
    assert validate_text_document(baseline_texts.document) == []
    assert baseline_texts.gettext("menu.food", "en", "halloween") != baseline_texts.gettext("menu.food", "en")
    assert baseline_texts.gettext("menu.food", "unsupported") == baseline_texts.gettext("menu.food", "en")
    assert TextDocument.model_validate(baseline_texts.document.model_dump(mode="json")) == baseline_texts.document
    with pytest.raises((FrozenInstanceError, AttributeError)):
        baseline_texts.release_id = 2
    with pytest.raises(TypeError):
        baseline_texts._entries["menu.food"] = None
    with pytest.raises(ValueError):
        baseline_texts.entry("menu.food").variants[0].text = "mutated"


@pytest.mark.parametrize(
    "text", ["<script>alert(1)</script>", "{count.__class__}", "{count!r}", "{count:1000000}", "<b>Unclosed"]
)
def test_invalid_templates_are_rejected_without_executing_content(baseline_texts, text):
    entry = changed_entry(baseline_texts.document, "obis.new_grade", text=text)
    document = baseline_texts.document.model_copy(
        update={"entries": tuple(entry if x.key == entry.key else x for x in baseline_texts.document.entries)}
    )
    assert validate_text_document(document)


def test_duplicate_variants_and_missing_locales_are_rejected(baseline_texts):
    entry = baseline_texts.document.entries[0]
    for variants in (entry.variants + (entry.variants[0],), tuple(v for v in entry.variants if v.locale != "zh")):
        document = baseline_texts.document.model_copy(
            update={"entries": (entry.model_copy(update={"variants": variants}),)}
        )
        assert validate_text_document(document)


def test_database_mode_formats_without_any_mo_files(tmp_path, baseline_texts):
    translations = CatalogI18n(path=tmp_path, default_locale="ru", database=True)
    with translations.use_catalog(baseline_texts):
        assert translations.gettext("common.welcome", locale="en") == "Welcome to Manashelper!"
        assert (
            translations.gettext("obis.skips_left.one", "obis.skips_left.many", 2, locale="en") == "{count} skips left"
        )


async def test_draft_publication_snapshot_rollback_and_idempotent_import(catalog_pool):
    async with catalog_pool.begin() as session:
        service = TextCatalogService(TextCatalogRepository(session))
        original = await service.current()
        draft = await service.draft()
        await service.save_entry("menu.food", changed_entry(draft.document), draft.revision)
        assert (await service.current()).gettext("menu.food") == original.gettext("menu.food")
        release = await service.publish(1, 123)
        assert release.id == 2
        assert (await service.publish(1, 123)).id == 2
        await initialize_catalog(session)
        assert (await service.draft()).revision == 1
    async with catalog_pool.begin() as session:
        service = TextCatalogService(TextCatalogRepository(session))
        assert (await service.current()).gettext("menu.food") == "Updated food"
        assert (await service.version(1)).gettext("menu.food") == original.gettext("menu.food")
        labels = await service.historical_labels()
        assert {original.gettext("menu.food"), "Updated food"} <= labels[("menu.food", "en")]
        await service.activate(1, 2)
        with pytest.raises(FlowConflictError):
            await service.activate(2, 2)
        assert (await service.publish(1, 123)).id == 2
        assert (await service.draft()).current_release == 1


async def test_concurrent_saves_have_one_winner_and_do_not_overwrite(catalog_pool):
    async with catalog_pool() as session:
        draft = await TextCatalogRepository(session).draft()

    async def save(text):
        try:
            async with catalog_pool.begin() as session:
                return await TextCatalogService(TextCatalogRepository(session)).save_entry(
                    "menu.food", changed_entry(draft.document, text=text), 0
                )
        except FlowConflictError:
            return None

    results = await asyncio.gather(save("First edit"), save("Second edit"))
    assert sum(result is not None for result in results) == 1
    async with catalog_pool() as session:
        saved = await TextCatalogRepository(session).draft()
        assert saved.revision == 1
        assert TextSnapshot(0, saved.document).gettext("menu.food") in {"First edit", "Second edit"}


async def test_failed_outer_transaction_does_not_publish_or_change_pointer(catalog_pool):
    with pytest.raises(RuntimeError):
        async with catalog_pool.begin() as session:
            service = TextCatalogService(TextCatalogRepository(session))
            draft = await service.draft()
            await service.save_entry("menu.food", changed_entry(draft.document), 0)
            await service.publish(1, 123)
            raise RuntimeError("rollback after publication")
    async with catalog_pool() as session:
        assert (await TextCatalogRepository(session).draft()).current_release == 1
        assert await session.scalar(select(func.count()).select_from(TextCatalogRelease)) == 1


async def test_plain_reply_label_conflicts_with_historical_actions_are_rejected(catalog_pool):
    async with catalog_pool.begin() as session:
        service = TextCatalogService(TextCatalogRepository(session))
        snapshot = await service.current()
        draft = await service.draft()
        await service.save_entry("menu.food", changed_entry(draft.document, text=snapshot.gettext("menu.settings")), 0)
        with pytest.raises(InvalidFlowError):
            await service.publish(1, 123)


async def test_middleware_matches_published_and_historical_reply_labels(catalog_pool):
    async with catalog_pool.begin() as session:
        service = TextCatalogService(TextCatalogRepository(session))
        old = (await service.current()).gettext("menu.food")
        draft = await service.draft()
        await service.save_entry("menu.food", changed_entry(draft.document), 0)
        await service.publish(1, 123)
    async with catalog_pool() as session:
        dependencies = {
            TextCatalogService: TextCatalogService(TextCatalogRepository(session)),
            LocaleService: AsyncMock(resolve=AsyncMock(return_value=Locale.EN)),
            ThemeService: AsyncMock(get_theme=AsyncMock(return_value=Theme.BASIC)),
        }
        user = User(id=123, is_bot=False, first_name="Student")
        message = Message(message_id=1, date=0, chat=Chat(id=123, type="private"), from_user=user)
        data = {
            CONTAINER_NAME: SimpleNamespace(get=AsyncMock(side_effect=dependencies.__getitem__)),
            "event_from_user": user,
        }

        async def handler(event, payload):
            assert i18n.gettext("menu.food") == "Updated food"
            for label in (old, "Updated food"):
                assert await TranslatedText("menu.food")(event.model_copy(update={"text": label}))

        await LocaleMiddleware()(handler, message, data)


async def test_bound_catalog_context_is_isolated_between_tasks(baseline_texts):
    entry = changed_entry(baseline_texts.document, text="Other task food")
    document = baseline_texts.document.model_copy(
        update={"entries": tuple(entry if x.key == entry.key else x for x in baseline_texts.document.entries)}
    )
    other = TextSnapshot(2, document)

    async def read(snapshot):
        with i18n.use_catalog(snapshot):
            await asyncio.sleep(0)
            return i18n.gettext("menu.food", locale="en")

    assert await asyncio.gather(read(baseline_texts), read(other)) == [
        baseline_texts.gettext("menu.food"),
        "Other task food",
    ]
