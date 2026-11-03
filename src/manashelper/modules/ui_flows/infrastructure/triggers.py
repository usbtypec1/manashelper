from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.trigger_orm import UiIngressReceipt, UiTriggerRelease, UiTriggerState
from manashelper.modules.ui_flows.triggers import trigger_document
from ui_flows.domain.ingress import (
    IncomingEvent,
    RouteDecision,
    TriggerDocument,
    TriggerDraft,
    TriggerManifest,
    TriggerRelease,
)
from ui_flows.errors import FlowConflictError, FlowNotFoundError, InvalidEventError


def release_info(row: UiTriggerRelease) -> TriggerRelease:
    return TriggerRelease(
        row.id, row.draft_revision, row.author_id, row.published_at, TriggerManifest.model_validate(row.manifest)
    )


class TriggerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def initialize(self, document: TriggerDocument | None = None) -> None:
        await self._session.execute(
            insert(UiTriggerState)
            .values(
                id=1, revision=0, draft=(document or trigger_document()).model_dump(mode="json"), current_release=None
            )
            .on_conflict_do_nothing(index_elements=[UiTriggerState.id])
        )

    async def draft(self, *, lock: bool = False) -> TriggerDraft:
        query = select(UiTriggerState).where(UiTriggerState.id == 1).execution_options(populate_existing=True)
        row = await self._session.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise FlowNotFoundError("Trigger registry is not initialized")
        return TriggerDraft(TriggerDocument.model_validate(row.draft), row.revision, row.current_release)

    async def save(self, document: TriggerDocument, expected_revision: int) -> TriggerDraft:
        changed = await self._session.scalar(
            update(UiTriggerState)
            .where(UiTriggerState.id == 1, UiTriggerState.revision == expected_revision)
            .values(draft=document.model_dump(mode="json"), revision=expected_revision + 1)
            .returning(UiTriggerState.id)
        )
        if changed is None:
            raise FlowConflictError("Trigger draft revision has changed")
        return await self.draft()

    async def version(self, release_id: int) -> TriggerRelease:
        row = await self._session.get(UiTriggerRelease, release_id)
        if row is None:
            raise FlowNotFoundError("Trigger release does not exist")
        return release_info(row)

    async def current(self) -> TriggerRelease:
        row = await self._session.scalar(
            select(UiTriggerRelease)
            .join(UiTriggerState, UiTriggerState.current_release == UiTriggerRelease.id)
            .where(UiTriggerState.id == 1)
        )
        if row is None:
            raise FlowNotFoundError("Trigger registry has no release; run application bootstrap")
        return release_info(row)

    async def published_revision(self, revision: int) -> TriggerRelease | None:
        row = await self._session.scalar(select(UiTriggerRelease).where(UiTriggerRelease.draft_revision == revision))
        return release_info(row) if row else None

    async def publish(self, manifest: TriggerManifest, revision: int, author_id: int) -> TriggerRelease:
        async with self._session.begin_nested():
            draft = await self.draft(lock=True)
            if draft.revision != revision:
                raise FlowConflictError("Trigger draft revision has changed")
            previous = await self.published_revision(revision)
            if previous is not None:
                return previous
            latest = await self._session.scalar(select(func.max(UiTriggerRelease.id)))
            row = UiTriggerRelease(
                id=(latest or 0) + 1,
                draft_revision=revision,
                manifest=manifest.model_dump(mode="json"),
                author_id=author_id,
            )
            self._session.add(row)
            await self._session.flush()
            await self._session.execute(
                update(UiTriggerState).where(UiTriggerState.id == 1).values(current_release=row.id)
            )
            return release_info(row)

    async def activate(self, release_id: int, expected_current_release: int) -> TriggerDraft:
        draft = await self.draft(lock=True)
        if draft.current_release != expected_current_release:
            raise FlowConflictError("Trigger release has changed")
        await self.version(release_id)
        await self._session.execute(
            update(UiTriggerState).where(UiTriggerState.id == 1).values(current_release=release_id)
        )
        return await self.draft()

    async def versions(self) -> list[TriggerRelease]:
        return [
            release_info(row)
            for row in await self._session.scalars(select(UiTriggerRelease).order_by(UiTriggerRelease.id.desc()))
        ]

    async def receipt(self, event: IncomingEvent) -> RouteDecision | None:
        row = await self._session.get(UiIngressReceipt, (event.bot_id, event.update_id))
        if row is None:
            return None
        if (row.actor_id, row.chat_id) != (event.actor_id, event.chat_id):
            raise InvalidEventError("Event identity does not match its receipt")
        return RouteDecision.model_validate(row.decision)

    async def runtime_processed(self, update_id: int) -> bool:
        from manashelper.modules.ui_flows.infrastructure.orm import UiFlowEvent

        return await self._session.get(UiFlowEvent, update_id) is not None

    async def record(self, event: IncomingEvent, decision: RouteDecision) -> bool:
        inserted = await self._session.scalar(
            insert(UiIngressReceipt)
            .values(
                bot_id=event.bot_id,
                update_id=event.update_id,
                actor_id=event.actor_id,
                chat_id=event.chat_id,
                release_id=decision.release_id,
                decision=decision.model_dump(mode="json"),
            )
            .on_conflict_do_nothing(index_elements=[UiIngressReceipt.bot_id, UiIngressReceipt.update_id])
            .returning(UiIngressReceipt.bot_id)
        )
        return inserted is not None
