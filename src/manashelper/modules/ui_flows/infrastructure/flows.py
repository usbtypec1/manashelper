from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.orm import UiFlow, UiFlowVersion
from ui_flows.domain.schema import FlowDocument
from ui_flows.domain.state import Draft, PublishedFlow
from ui_flows.errors import FlowConflictError, FlowNotFoundError


def _draft(row: UiFlow) -> Draft:
    return Draft(FlowDocument.model_validate(row.draft), row.draft_revision, row.published_version)


def _version(row: UiFlowVersion) -> PublishedFlow:
    return PublishedFlow(
        FlowDocument.model_validate(row.document), row.version, row.draft_revision, row.author_id, row.published_at
    )


class FlowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def atomic(self) -> AsyncIterator[None]:
        async with self._session.begin_nested():
            yield

    async def create(self, document: FlowDocument) -> Draft:
        created = await self._session.scalar(
            insert(UiFlow)
            .values(
                id=document.id,
                draft=document.model_dump(mode="json"),
                draft_revision=0,
            )
            .on_conflict_do_nothing(index_elements=[UiFlow.id])
            .returning(UiFlow.id)
        )
        if created is None:
            raise FlowConflictError("A scenario with this ID already exists")
        return Draft(document.model_copy(deep=True), 0, None)

    async def get(self, flow_id: str, *, lock: bool = False) -> Draft:
        statement = select(UiFlow).where(UiFlow.id == flow_id).execution_options(populate_existing=True)
        row = await self._session.scalar(statement.with_for_update() if lock else statement)
        if row is None:
            raise FlowNotFoundError("Scenario does not exist")
        return _draft(row)

    async def save_draft(self, document: FlowDocument, expected_revision: int) -> Draft:
        row = await self._session.scalar(
            update(UiFlow)
            .where(
                UiFlow.id == document.id,
                UiFlow.draft_revision == expected_revision,
            )
            .values(draft=document.model_dump(mode="json"), draft_revision=UiFlow.draft_revision + 1)
            .returning(UiFlow)
            .execution_options(populate_existing=True)
        )
        if row is None:
            await self.get(document.id)
            raise FlowConflictError("The draft revision has changed")
        return _draft(row)

    async def find_revision(self, flow_id: str, draft_revision: int) -> PublishedFlow | None:
        row = await self._session.scalar(
            select(UiFlowVersion).where(
                UiFlowVersion.flow_id == flow_id,
                UiFlowVersion.draft_revision == draft_revision,
            )
        )
        return None if row is None else _version(row)

    async def version(self, flow_id: str, version: int) -> PublishedFlow:
        row = await self._session.get(UiFlowVersion, (flow_id, version))
        if row is None:
            raise FlowNotFoundError("Scenario version does not exist")
        return _version(row)

    async def published(self, flow_id: str) -> PublishedFlow:
        row = await self._session.scalar(
            select(UiFlowVersion)
            .join(UiFlow, (UiFlow.id == UiFlowVersion.flow_id) & (UiFlow.published_version == UiFlowVersion.version))
            .where(UiFlow.id == flow_id)
        )
        if row is None:
            raise FlowNotFoundError("Scenario has no published version")
        return _version(row)

    async def add_version(self, draft: Draft, author_id: int) -> PublishedFlow:
        # The caller holds the parent flow row lock, including while allocating a version.
        latest = await self._session.scalar(
            select(func.max(UiFlowVersion.version)).where(UiFlowVersion.flow_id == draft.document.id)
        )
        row = UiFlowVersion(
            flow_id=draft.document.id,
            version=(latest or 0) + 1,
            draft_revision=draft.revision,
            document=draft.document.model_dump(mode="json"),
            author_id=author_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self.activate(row.flow_id, row.version)
        return _version(row)

    async def activate(self, flow_id: str, version: int) -> None:
        await self._session.execute(update(UiFlow).where(UiFlow.id == flow_id).values(published_version=version))
