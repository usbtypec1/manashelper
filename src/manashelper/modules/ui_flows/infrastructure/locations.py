from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiUserLocation, UiUserTransition
from ui_flows.domain.state import ACTIVE_STATUSES, DialogState


class LocationRepository:
    """Metadata only; neither FSM data nor user input belongs in these tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def runtime(
        self,
        state: DialogState,
        update_id: int | None,
        from_step: str | None,
        outcome: str,
        *,
        operation_id: UUID | None = None,
    ) -> None:
        values = dict(
            user_id=state.user_id,
            chat_id=state.chat_id,
            owner="runtime" if state.status in ACTIVE_STATUSES else "unknown",
            session_id=state.id,
            legacy_state=None,
            handler=None,
            update_id=update_id,
            operation_id=operation_id,
            updated_at=func.now(),
        )
        await self._session.execute(
            insert(UiUserLocation)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[UiUserLocation.user_id],
                set_=values,
            )
        )
        await self._session.execute(
            insert(UiUserTransition)
            .values(
                update_id=update_id,
                operation_id=operation_id,
                user_id=state.user_id,
                owner="runtime",
                flow_id=state.flow_id,
                flow_version=state.flow_version,
                from_step=from_step,
                to_step=state.node_id,
                outcome=outcome,
            )
            .on_conflict_do_nothing()
        )

    async def observe(self, user_id: int, chat_id: int, update_id: int, handler: str, state: str | None) -> None:
        await self._session.execute(select(func.pg_advisory_xact_lock(chat_id)))
        if (
            await self._session.scalar(
                select(UiDialogSession.id).where(
                    UiDialogSession.chat_id == chat_id,
                    UiDialogSession.status.in_(ACTIVE_STATUSES),
                )
            )
            is not None
        ):
            return
        previous = await self._session.get(UiUserLocation, user_id, populate_existing=True)
        # Update IDs may jump backwards after an idle week. Chat locks order fresh events;
        # receipts reject replays without mistaking a fresh smaller ID for an old event.
        seen = await self._session.scalar(select(UiUserTransition).where(UiUserTransition.update_id == update_id))
        if seen is not None and (
            seen.user_id != user_id or seen.owner != "runtime" or previous is None or previous.update_id != update_id
        ):
            return
        source = (previous.legacy_state or previous.handler) if previous is not None else None
        values = dict(
            user_id=user_id,
            chat_id=chat_id,
            owner="legacy",
            session_id=None,
            legacy_state=state,
            handler=handler,
            update_id=update_id,
            operation_id=None,
            updated_at=func.now(),
        )
        await self._session.execute(
            insert(UiUserLocation)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[UiUserLocation.user_id],
                set_=values,
            )
        )
        transition = insert(UiUserTransition).values(
            update_id=update_id,
            user_id=user_id,
            owner="legacy",
            flow_id=None,
            flow_version=None,
            from_step=source,
            to_step=state or handler,
            outcome="observed",
        )
        # A handoff is one Telegram update: preserve its source/version, record its final owner/step.
        await self._session.execute(
            transition.on_conflict_do_update(
                index_elements=[UiUserTransition.update_id],
                set_={"owner": "legacy", "to_step": state or handler, "outcome": "handed_off"},
            )
        )

    async def forget_legacy(self) -> None:
        # MemoryStorage is lost on a bot restart. Keep the timestamp and last observed metadata as history.
        await self._session.execute(
            update(UiUserLocation).where(UiUserLocation.owner == "legacy").values(owner="unknown")
        )
