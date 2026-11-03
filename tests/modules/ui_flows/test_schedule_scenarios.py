from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from manashelper.modules.schedule.application.lesson_search import LessonSearchService
from manashelper.modules.schedule.infrastructure.models.associations import user_courses
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.models.department import Department
from manashelper.modules.schedule.infrastructure.models.faculty import Faculty
from manashelper.modules.schedule.infrastructure.models.lesson import Lesson
from manashelper.modules.schedule.ui_scenarios import schedule_scenarios
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer
from manashelper.modules.users.infrastructure.user import User
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.i18n.service import TextCatalogService
from tests.modules.ui_flows.telegram_factory import container_for
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.contracts import ButtonEvent, InputEvent
from ui_flows.domain.schema import Position
from ui_flows.domain.state import ExecutionResult, RuntimeUser

USER = RuntimeUser(991_801, 991_801, "en", "basic")


async def seed(pool, *, faculty_count=1, courses=1, lessons=False):
    faculty_ids = [uuid4() for _ in range(faculty_count)]
    department = uuid4()
    async with pool.begin() as session:
        session.add(User(id=USER.id, full_name="Schedule scenario", locale="en"))
        session.add_all([Faculty(id=id, name=f"Faculty {index:02}") for index, id in enumerate(faculty_ids)])
        await session.flush()
        session.add(Department(id=department, name="Engineering", faculty_id=faculty_ids[0]))
        await session.flush()
        session.add_all([Course(id=100 + i, number=i + 1, department_id=department) for i in range(courses)])
        await session.flush()
        if lessons:
            session.add_all(
                [
                    Lesson(
                        id=uuid4(),
                        course_id=100 + i,
                        weekday=1,
                        time_range="09:00-09:50",
                        content=f"Calculus {i}",
                        normalized_content=f"calculus {i}",
                    )
                    for i in range(courses)
                ]
            )
    async with container_for(pool) as container, catalog_request(container) as request:
        flows = await request.get(FlowService)
        for doc in schedule_scenarios():
            await flows.create(doc)
            await flows.publish(doc.id, 0, USER.id)
    return faculty_ids, department


async def start(container, flow, update, user=USER):
    async with catalog_request(container) as request:
        return await (await request.get(DialogService)).start(flow, user, update)


async def press(container, state, update, button_id, user=USER):
    async with catalog_request(container) as request:
        flow = await (await request.get(FlowService)).version(state.flow_id, state.flow_version)
        node = next(n for n in flow.document.nodes if n.id == state.node_id)
        screen = FlowRenderer().render(flow.document, ExecutionResult(state, node, "resumed"), user, {})
        button = next(b for row in screen.buttons for b in row if b.id == button_id)
        event = ButtonEvent(
            kind="button",
            update_id=update,
            user_id=USER.id,
            chat_id=USER.chat_id,
            session_id=str(state.id),
            expected_revision=state.revision,
            button_id=button.id,
            snapshot=button.snapshot,
        )
        return await (await request.get(DialogService)).handle(event, user)


async def input_text(container, state, update, text):
    async with catalog_request(container) as request:
        event = InputEvent(
            kind="input",
            update_id=update,
            user_id=USER.id,
            chat_id=USER.chat_id,
            session_id=str(state.id),
            expected_revision=state.revision,
            text=text,
        )
        return await (await request.get(DialogService)).handle(event, USER)


async def test_course_selection_uses_persisted_frames_and_toggles_real_tracking(isolated_flow_pool):
    pool = isolated_flow_pool
    await seed(pool, courses=2)
    async with container_for(pool) as first:
        state = (await start(first, "course_tracking", 80100)).state
        assert (state.flow_id, state.node_id, len(state.frames)) == ("select_faculty", "choose", 1)
        state = (await press(first, state, 80101, "r0_0_0")).state
        assert (state.flow_id, state.node_id) == ("select_department", "choose")
        session_id = state.id
    async with container_for(pool) as restarted:
        async with catalog_request(restarted) as request:
            restored = await (await request.get(DialogService)).get(session_id, USER)
        assert restored == state
        state = (await press(restarted, restored, 80102, "r0_0_0")).state
        assert (state.flow_id, state.node_id) == ("course_tracking", "choose")
        state = (await press(restarted, state, 80103, "r0_0_0")).state
        assert state.node_id == "choose"
        async with pool() as observer:
            tracked = list(
                await observer.execute(select(user_courses.c.course_id).where(user_courses.c.user_id == USER.id))
            )
            assert tracked == [(100,)]
        state = (await press(restarted, state, 80104, "r0_0_0")).state
        async with pool() as observer:
            assert list(await observer.execute(select(user_courses).where(user_courses.c.user_id == USER.id))) == []


async def test_schedule_can_select_courses_and_switch_day_after_restart(isolated_flow_pool):
    pool = isolated_flow_pool
    await seed(pool, lessons=True)
    async with container_for(pool) as first:
        state = (await start(first, "my_schedule", 80500)).state
        assert state.node_id == "no_courses"
        state = (await press(first, state, 80501, "track")).state
        state = (await press(first, state, 80502, "r0_0_0")).state
        state = (await press(first, state, 80503, "r0_0_0")).state
        state = (await press(first, state, 80504, "r0_0_0")).state
        state = (await press(first, state, 80505, "done")).state
        assert (state.flow_id, state.node_id) == ("my_schedule", "day")
        previous_day = state.data["weekday"]
        next_day = state.data["days"][0]["id"]
    async with container_for(pool) as restarted:
        async with catalog_request(restarted) as request:
            restored = await (await request.get(DialogService)).get(state.id, USER)
        assert restored == state
        state = (await press(restarted, restored, 80506, "r0_0_0")).state
        assert state.node_id == "day" and state.data["weekday"] == next_day != previous_day
        assert state.data["chunks"]


async def test_faculty_pagination_preserves_snapshot_through_restart(isolated_flow_pool):
    pool = isolated_flow_pool
    faculty_ids, _ = await seed(pool, faculty_count=17)
    async with container_for(pool) as first:
        state = (await start(first, "course_tracking", 80200)).state
        assert len(state.data["visible"]) == 16 and state.data["has_following"] is True
        state = (await press(first, state, 80201, "following")).state
        assert state.data["page"] == 1 and len(state.data["visible"]) == 1
        saved_option = state.data["visible"][0]
    async with pool.begin() as session:
        await session.execute(delete(Faculty).where(Faculty.id == faculty_ids[-1]))
    async with container_for(pool) as restarted:
        async with catalog_request(restarted) as request:
            saved = await (await request.get(DialogService)).get(state.id, USER)
        assert saved == state and saved.data["visible"][0] == saved_option
        previous = (await press(restarted, saved, 80202, "previous")).state
        assert previous.data["page"] == 0 and len(previous.data["visible"]) == 16


async def test_search_pagination_uses_saved_snapshot_without_requery_after_restart(isolated_flow_pool, monkeypatch):
    pool = isolated_flow_pool
    await seed(pool, courses=9, lessons=True)
    calls = []
    original = LessonSearchService.search

    async def counted(self, query):
        calls.append(query)
        return await original(self, query)

    monkeypatch.setattr(LessonSearchService, "search", counted)
    async with container_for(pool) as first:
        state = (await start(first, "lesson_search", 80300)).state
        state = (await input_text(first, state, 80301, "calculus")).state
        assert state.node_id == "results" and state.data["has_following"] and len(state.data["snapshot"]) == 9
        snapshot = state.data["snapshot"]
    async with pool.begin() as session:
        await session.execute(delete(Lesson))
    async with container_for(pool) as restarted:
        async with catalog_request(restarted) as request:
            restored = await (await request.get(DialogService)).get(state.id, USER)
        state = (await press(restarted, restored, 80302, "following")).state
        assert state.data["page"] == 1 and state.data["snapshot"] == snapshot
        assert calls == ["calculus"]
        assert state.data["chunks"]


async def test_search_short_and_empty_queries_show_recoverable_screens(isolated_flow_pool):
    await seed(isolated_flow_pool)
    async with container_for(isolated_flow_pool) as container:
        state = (await start(container, "lesson_search", 80600)).state
        state = (await input_text(container, state, 80601, "a")).state
        assert state.node_id == "too_short"
        state = (await press(container, state, 80602, "search_again")).state
        state = (await input_text(container, state, 80603, "missing")).state
        assert state.node_id == "empty"


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
async def test_course_labels_use_the_current_user_locale(isolated_flow_pool, locale):
    await seed(isolated_flow_pool)
    user = RuntimeUser(USER.id, USER.chat_id, locale, "basic")
    async with container_for(isolated_flow_pool) as container:
        state = (await start(container, "course_tracking", 80400, user)).state
        state = (await press(container, state, 80401, "r0_0_0", user)).state
        state = (await press(container, state, 80402, "r0_0_0", user)).state
        async with catalog_request(container) as request:
            snapshot = await (await request.get(TextCatalogService)).current()
            expected = snapshot.gettext("schedule.course_year", locale, "basic").format(number=1)
        assert state.data["visible"][0]["label"] == expected


async def test_schedule_seed_publishes_dependencies_without_replacing_authored_drafts(isolated_flow_pool):
    pool = isolated_flow_pool
    async with pool.begin() as session:
        session.add(User(id=USER.id, full_name="Schedule seed", locale="en"))
    async with container_for(pool) as container:
        coordinator = await container.get(FlowTelegramCoordinator)
        await coordinator.install_defaults(USER.id)
        async with catalog_request(container) as request:
            flows = await request.get(FlowService)
            for document in schedule_scenarios():
                assert (await flows.get(document.id)).published_version == 1
            draft = await flows.get("select_faculty")
            draft.document.layout["choose"] = Position(x=123.0, y=456.0)
            saved = await flows.save(draft.document, draft.revision)
            assert saved.revision == 1
        await coordinator.install_defaults(USER.id)
        async with catalog_request(container) as request:
            draft = await (await request.get(FlowService)).get("select_faculty")
            assert draft.revision == 1 and draft.published_version == 1
            assert draft.document.layout["choose"].x == 123.0
