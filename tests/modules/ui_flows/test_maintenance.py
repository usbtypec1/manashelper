from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update

from manashelper.modules.ui_flows.infrastructure.effect_orm import UiExternalOperation, UiInputSecret
from manashelper.modules.ui_flows.infrastructure.effects import EffectRepository
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent, UiScreenDelivery
from manashelper.modules.users.infrastructure.user import User
from manashelper.platform.web.auth import AdminAuthService
from manashelper.platform.web.orm import AdminLoginTicket, AdminWebSession
from tests.modules.ui_flows.factories import button, publish_examples, runtime
from tests.modules.ui_flows.telegram_factory import container_for
from ui_flows.application.maintenance import FlowMaintenanceService
from ui_flows.domain.state import RuntimeUser


async def test_closed_payload_cleanup_keeps_active_state_business_answers_and_receipts(isolated_flow_pool):
    from manashelper.modules.student_questions.orm import StudentQuestionsResponse

    pool = isolated_flow_pool
    user = RuntimeUser(991402, 991402)
    old = datetime.now(UTC) - timedelta(days=8)
    async with pool.begin() as session:
        session.add(User(id=user.id, full_name="Retention test"))
        await session.flush()
        services = runtime(session)
        await publish_examples(services)
        result = await services.dialogs.start("student_questions", user, 10)
        result = await services.dialogs.handle(button(result.state, 11, "year_1"), user)
        result = await services.dialogs.handle(button(result.state, 12, "no"), user)
        result = await services.dialogs.handle(button(result.state, 13, "yes"), user)
        closed_id = result.state.id
        active = await services.dialogs.start("student_questions", user, 20)
        for state, update_id, token in ((result.state, 13, "closed-screen"), (active.state, 20, "active-screen")):
            session.add(
                UiScreenDelivery(
                    token=token,
                    session_id=state.id,
                    revision=state.revision,
                    update_id=update_id,
                    chat_id=user.id,
                    status="unknown",
                    screen={"text": "private screen", "keyboard": "none", "locale": "en", "theme": "basic"},
                    created_at=old,
                )
            )
        await session.execute(update(UiDialogSession).values(updated_at=old))
    async with container_for(pool) as container:
        async with container() as request:
            assert await (await request.get(FlowMaintenanceService)).purge() == (1, 1)
        async with container() as request:
            assert await (await request.get(FlowMaintenanceService)).purge() == (0, 0)
    async with pool() as session:
        assert (await session.get(UiDialogSession, closed_id)).data == {}
        assert (await session.get(UiDialogSession, active.state.id)).data == active.state.data
        assert (await session.get(StudentQuestionsResponse, user.id)).wants_beta
        assert await session.get(UiFlowEvent, 13) is not None
        assert [row.token for row in (await session.scalars(select(UiScreenDelivery))).all()] == ["active-screen"]


async def test_auth_cleanup_removes_only_expired_records(isolated_flow_pool):
    pool = isolated_flow_pool
    now = datetime.now(UTC)
    async with pool.begin() as session:
        session.add(User(id=991402, full_name="Auth retention"))
        await session.flush()
        for model in (AdminLoginTicket, AdminWebSession):
            for suffix, age in (("expired", -1), ("valid", 1)):
                session.add(
                    model(digest=model.__tablename__ + suffix, user_id=991402, expires_at=now + timedelta(hours=age))
                )
    async with container_for(pool) as container, container() as request:
        assert await (await request.get(AdminAuthService)).purge_expired() == 2
    async with pool() as session:
        for model in (AdminLoginTicket, AdminWebSession):
            rows = (await session.scalars(select(model))).all()
            assert len(rows) == 1 and rows[0].digest.endswith("valid")


async def test_closed_external_payload_retention_preserves_active_results_and_durable_receipts(isolated_flow_pool):
    pool = isolated_flow_pool
    user = RuntimeUser(991403, 991403)
    now = datetime.now(UTC)
    old = now - timedelta(days=8)
    statuses = ("pending", "unknown", "succeeded", "failed", "applied")
    old_operations = {}
    active_operation_id, recent_operation_id = uuid4(), uuid4()
    old_secret_id, active_secret_id, recent_secret_id = uuid4(), uuid4(), uuid4()
    async with pool.begin() as session:
        session.add(User(id=user.id, full_name="External payload retention"))
        await session.flush()
        services = runtime(session)
        await publish_examples(services)
        closed = (await services.dialogs.start("student_questions", user, 30)).state
        await services.dialogs.cancel_active(user, 31)
        active = (await services.dialogs.start("student_questions", user, 32)).state
        await session.execute(update(UiDialogSession).where(UiDialogSession.id == closed.id).values(updated_at=old))
        recent_id = uuid4()
        session.add(
            UiDialogSession(
                id=recent_id,
                user_id=user.id,
                chat_id=user.chat_id,
                flow_id=closed.flow_id,
                flow_version=closed.flow_version,
                node_id=closed.node_id,
                status="cancelled",
                revision=1,
                data={"private_recent": "retained"},
                frames=[],
                updated_at=now,
            )
        )
        await session.flush()
        for index, status in enumerate(statuses):
            operation_id = uuid4()
            old_operations[operation_id] = status
            session.add(
                UiExternalOperation(
                    id=operation_id,
                    session_id=closed.id,
                    user_id=user.id,
                    chat_id=user.chat_id,
                    revision=index,
                    flow_id=closed.flow_id,
                    flow_version=closed.flow_version,
                    node_id="fetch",
                    delegate_id="test.external",
                    contract_version=1,
                    arguments={"private_form": "old private input"},
                    result={"outcome": "success", "values": {"answer": "old private result"}},
                    status=status,
                    error_code="execution_failed" if status == "failed" else None,
                    created_at=old,
                )
            )
        for operation_id, state_id in ((active_operation_id, active.id), (recent_operation_id, recent_id)):
            session.add(
                UiExternalOperation(
                    id=operation_id,
                    session_id=state_id,
                    user_id=user.id,
                    chat_id=user.chat_id,
                    revision=0,
                    flow_id=closed.flow_id,
                    flow_version=closed.flow_version,
                    node_id="fetch",
                    delegate_id="test.external",
                    contract_version=1,
                    arguments={"private_form": "retained input"},
                    result={"outcome": "success", "values": {"answer": "retained result"}},
                    status="succeeded",
                    created_at=old,
                )
            )
        for secret_id, state_id in (
            (old_secret_id, closed.id),
            (active_secret_id, active.id),
            (recent_secret_id, recent_id),
        ):
            session.add(
                UiInputSecret(
                    id=secret_id,
                    session_id=state_id,
                    user_id=user.id,
                    chat_id=user.chat_id,
                    ciphertext="synthetic ciphertext",
                    expires_at=now + timedelta(hours=1),
                )
            )
        session.add(
            UiScreenDelivery(
                token="old-effect",
                session_id=closed.id,
                revision=closed.revision,
                update_id=31,
                chat_id=user.chat_id,
                status="unknown",
                created_at=old,
                screen={"text": "old private screen", "keyboard": "none", "locale": "en", "theme": "basic"},
            )
        )
    async with container_for(pool) as container:
        async with container() as request:
            assert await (await request.get(FlowMaintenanceService)).purge() == (1, 1)
        async with container() as request:
            assert await (await request.get(FlowMaintenanceService)).purge() == (0, 0)
    async with pool() as session:
        assert (await session.get(UiDialogSession, closed.id)).data == {}
        assert (await session.get(UiDialogSession, active.id)).data == active.data
        assert (await session.get(UiDialogSession, recent_id)).data == {"private_recent": "retained"}
        for operation_id, original_status in old_operations.items():
            saved = await session.get(UiExternalOperation, operation_id)
            assert saved is not None and saved.session_id == closed.id
            assert saved.arguments == {} and saved.result is None
            assert saved.status == {"pending": "failed", "succeeded": "applied"}.get(original_status, original_status)
            assert saved.error_code == {"pending": "cancelled", "failed": "execution_failed"}.get(original_status)
        for operation_id in (active_operation_id, recent_operation_id):
            saved = await session.get(UiExternalOperation, operation_id)
            assert saved.status == "succeeded" and saved.arguments == {"private_form": "retained input"}
            assert saved.result == {"outcome": "success", "values": {"answer": "retained result"}}
        assert await session.get(UiInputSecret, old_secret_id) is None
        assert await session.get(UiInputSecret, active_secret_id) is not None
        assert await session.get(UiInputSecret, recent_secret_id) is not None
        assert await session.get(UiScreenDelivery, "old-effect") is None
        assert await session.get(UiFlowEvent, 31) is not None
        assert set(await EffectRepository(session).pending()) == {active_operation_id, recent_operation_id}
