"""Transactional catalog persistence; published JSON snapshots are immutable."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import JSONPATH, insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.platform.i18n.orm import TextCatalogRelease, TextCatalogState
from ui_flows.application.texts import validate_text_document
from ui_flows.domain.schema import FlowDocument
from ui_flows.domain.texts import TextDocument, TextSnapshot
from ui_flows.errors import FlowConflictError, FlowNotFoundError, InvalidFlowError


@dataclass(frozen=True, slots=True)
class CatalogDraft:
    document: TextDocument
    revision: int
    current_release: int


@dataclass(frozen=True, slots=True)
class CatalogRelease:
    id: int
    draft_revision: int
    author_id: int | None
    published_at: datetime


def release_info(row: TextCatalogRelease) -> CatalogRelease:
    return CatalogRelease(row.id, row.draft_revision, row.author_id, row.published_at)


async def initialize_catalog(session: AsyncSession, document: TextDocument | None = None) -> None:
    """Explicit bootstrap/import only. Existing operator drafts/releases win."""
    if await session.get(TextCatalogState, 1) is not None:
        return
    if document is None:
        from manashelper.platform.i18n.seed import import_document

        document = import_document()
    issues = validate_text_document(document)
    if issues:
        raise InvalidFlowError(issues)
    payload = document.model_dump(mode="json")
    await session.execute(
        insert(TextCatalogRelease)
        .values(id=1, draft_revision=0, document=payload, author_id=None)
        .on_conflict_do_nothing(index_elements=[TextCatalogRelease.id])
    )
    await session.execute(
        insert(TextCatalogState)
        .values(id=1, revision=0, draft=payload, current_release=1)
        .on_conflict_do_nothing(index_elements=[TextCatalogState.id])
    )


class TextCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def draft(self, *, lock: bool = False) -> CatalogDraft:
        query = select(TextCatalogState).where(TextCatalogState.id == 1).execution_options(populate_existing=True)
        row = await self._session.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise FlowNotFoundError("Text catalog is not initialized; apply migrations")
        return CatalogDraft(TextDocument.model_validate(row.draft), row.revision, row.current_release)

    async def current(self) -> TextSnapshot:
        row = (
            await self._session.execute(
                select(TextCatalogRelease.id, TextCatalogRelease.document)
                .join(TextCatalogState, TextCatalogState.current_release == TextCatalogRelease.id)
                .where(TextCatalogState.id == 1)
            )
        ).one_or_none()
        if row is None:
            raise FlowNotFoundError("Text catalog has no published release")
        return TextSnapshot(row.id, TextDocument.model_validate(row.document))

    async def version(self, release_id: int) -> TextSnapshot:
        row = await self._session.get(TextCatalogRelease, release_id)
        if row is None:
            raise FlowNotFoundError("Text catalog release does not exist")
        return TextSnapshot(row.id, TextDocument.model_validate(row.document))

    async def save(self, document: TextDocument, revision: int) -> CatalogDraft:
        changed = await self._session.scalar(
            update(TextCatalogState)
            .where(TextCatalogState.id == 1, TextCatalogState.revision == revision)
            .values(draft=document.model_dump(mode="json"), revision=TextCatalogState.revision + 1)
            .returning(TextCatalogState.id)
        )
        if changed is None:
            raise FlowConflictError("Text catalog revision has changed")
        return await self.draft()

    async def publish(self, expected_revision: int, author_id: int) -> CatalogRelease:
        async with self._session.begin_nested():
            draft = await self.draft(lock=True)
            if draft.revision != expected_revision:
                raise FlowConflictError("Text catalog revision has changed")
            previous = await self._session.scalar(
                select(TextCatalogRelease).where(TextCatalogRelease.draft_revision == expected_revision)
            )
            if previous is not None:
                return release_info(previous)
            issues = validate_text_document(draft.document)
            if issues:
                raise InvalidFlowError(issues)
            latest = await self._session.scalar(select(func.max(TextCatalogRelease.id)))
            row = TextCatalogRelease(
                id=(latest or 0) + 1,
                draft_revision=draft.revision,
                document=draft.document.model_dump(mode="json"),
                author_id=author_id,
            )
            self._session.add(row)
            await self._session.flush()
            await self._session.execute(
                update(TextCatalogState).where(TextCatalogState.id == 1).values(current_release=row.id)
            )
            return release_info(row)

    async def activate(self, release_id: int, expected_current_release: int) -> CatalogDraft:
        async with self._session.begin_nested():
            draft = await self.draft(lock=True)
            if draft.current_release != expected_current_release:
                raise FlowConflictError("Current text release has changed")
            await self.version(release_id)
            await self._session.execute(
                update(TextCatalogState).where(TextCatalogState.id == 1).values(current_release=release_id)
            )
            return await self.draft()

    async def versions(self) -> list[CatalogRelease]:
        rows = await self._session.scalars(select(TextCatalogRelease).order_by(TextCatalogRelease.id.desc()))
        return [release_info(row) for row in rows]

    async def published_revision(self, revision: int) -> CatalogRelease | None:
        row = await self._session.scalar(
            select(TextCatalogRelease).where(TextCatalogRelease.draft_revision == revision)
        )
        return release_info(row) if row is not None else None

    async def published_flows(self) -> list[FlowDocument]:
        from manashelper.modules.ui_flows.infrastructure.orm import UiFlow, UiFlowVersion

        documents = await self._session.scalars(
            select(UiFlowVersion.document).join(
                UiFlow, (UiFlow.id == UiFlowVersion.flow_id) & (UiFlow.published_version == UiFlowVersion.version)
            )
        )
        return [FlowDocument.model_validate(document) for document in documents]

    async def historical_labels(self) -> dict[tuple[str, str], frozenset[str]]:
        # Reply labels are the only historical templates needed for legacy input.
        # Read immutable releases; never copy user/session data into this mapping.
        entries = await self._session.scalars(
            select(
                func.jsonb_path_query(
                    TextCatalogRelease.document, cast('$.entries[*] ? (@.content_type == "label")', JSONPATH)
                )
            )
        )
        labels: dict[tuple[str, str], set[str]] = {}
        for entry in entries:
            for variant in entry["variants"]:
                labels.setdefault((entry["key"], variant["locale"]), set()).add(variant["text"])
        return {key: frozenset(values) for key, values in labels.items()}

    async def trigger_reply_keys(self) -> frozenset[str]:
        from manashelper.modules.ui_flows.infrastructure.trigger_orm import UiTriggerRelease, UiTriggerState

        manifest = await self._session.scalar(
            select(UiTriggerRelease.manifest)
            .join(UiTriggerState, UiTriggerState.current_release == UiTriggerRelease.id)
            .where(UiTriggerState.id == 1)
        )
        if manifest is None:
            return frozenset()
        return frozenset(
            binding["matcher"]["key"]
            for binding in manifest["document"]["bindings"]
            if binding["matcher"]["kind"] == "reply_label"
        )
