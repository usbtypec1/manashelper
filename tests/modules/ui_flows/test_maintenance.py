from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

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
