import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from manashelper.modules.ui_flows.infrastructure.effect_orm import UiExternalOperation, UiInputSecret
from manashelper.modules.ui_flows.infrastructure.effects import EffectRepository
from manashelper.modules.users.infrastructure.user import User
from tests.modules.ui_flows.factories import publish_examples, runtime
from ui_flows.domain.contracts import DelegateResult
from ui_flows.domain.effects import ExternalOperation
from ui_flows.domain.state import RuntimeUser
from ui_flows.errors import FlowConflictError


@pytest_asyncio.fixture
async def effect_session(isolated_flow_pool):
    user = RuntimeUser(991_751, 991_751)
    async with isolated_flow_pool.begin() as session:
        session.add(User(id=user.id, full_name="External operation test"))
        await session.flush()
        services = runtime(session)
        await publish_examples(services)
        state = (await services.dialogs.start("main_menu", user, 7010)).state
    return isolated_flow_pool, state


def operation(state, **changes):
    return replace(
        ExternalOperation(
            id=uuid4(),
            session_id=state.id,
            user_id=state.user_id,
            chat_id=state.chat_id,
            revision=state.revision,
            flow_id=state.flow_id,
            flow_version=state.flow_version,
            node_id="fetch",
            delegate_id="test.external",
            contract_version=1,
            arguments={"selection": [1, {"enabled": True, "note": None}]},
        ),
        **changes,
    )


async def test_preparation_race_is_idempotent_and_cannot_change_its_admitted_owner_or_arguments(effect_session):
    pool, state = effect_session
    first = operation(state)

    async def prepare(candidate):
        async with pool.begin() as session:
            return await EffectRepository(session).prepare(candidate)

    results = await asyncio.wait_for(asyncio.gather(prepare(first), prepare(replace(first, id=uuid4()))), 10)
    assert results[0].id == results[1].id
    for changed in (
        replace(first, id=uuid4(), arguments={"selection": [2]}),
        replace(first, id=uuid4(), user_id=state.user_id + 1),
        replace(first, id=uuid4(), chat_id=state.chat_id + 1),
    ):
        with pytest.raises(FlowConflictError):
            await prepare(changed)
    async with pool.begin() as session:
        repository = EffectRepository(session)
        with pytest.raises(RuntimeError, match="caught preparation failure"):
            async with repository.atomic():
                await repository.prepare(operation(state, revision=state.revision + 1))
                raise RuntimeError("caught preparation failure")
    async with pool() as session:
        assert await session.scalar(select(func.count()).select_from(UiExternalOperation)) == 1
        saved = await EffectRepository(session).get(results[0].id)
        assert saved.arguments == first.arguments and saved.status == "pending"


async def test_concurrent_claim_commits_unknown_before_external_work_and_never_reclaims_it(effect_session):
    pool, state = effect_session
    async with pool.begin() as session:
        prepared = await EffectRepository(session).prepare(operation(state))
    external_calls = []

    async def execute():
        async with pool.begin() as session:
            claimed = await EffectRepository(session).claim(prepared.id)
        if claimed is not None:
            # An independent connection models an external observer after the claim scope commits.
            async with pool() as observer:
                persisted = await EffectRepository(observer).get(claimed.id)
                assert persisted.status == "unknown"
                assert claimed.id not in await EffectRepository(observer).pending()
            external_calls.append(claimed.id)
        return claimed

    claims = await asyncio.wait_for(asyncio.gather(execute(), execute()), 10)
    assert sum(claim is not None for claim in claims) == 1
    assert external_calls == [prepared.id]
    # A fresh worker after a simulated crash cannot blindly repeat the uncertain external call.
    async with pool.begin() as session:
        assert await EffectRepository(session).claim(prepared.id) is None


@pytest.mark.parametrize("succeeds", [True, False])
async def test_only_claimed_operation_can_finish_and_terminal_result_cannot_be_overwritten(effect_session, succeeds):
    pool, state = effect_session
    result = DelegateResult("ok", {"items": [{"id": 7, "name": "preserved result"}]})
    async with pool.begin() as session:
        repository = EffectRepository(session)
        prepared = await repository.prepare(operation(state))
        assert not await repository.complete(prepared.id, result)
        assert not await repository.fail(prepared.id, "upstream_failed")
        assert not await repository.mark_applied(prepared.id)
        assert await repository.claim(prepared.id) is not None
    async with pool.begin() as session:
        repository = EffectRepository(session)
        if succeeds:
            assert await repository.complete(prepared.id, result)
            assert not await repository.complete(prepared.id, DelegateResult("other", {}))
            assert not await repository.fail(prepared.id, "late_failure")
            assert await repository.mark_applied(prepared.id)
            assert not await repository.mark_applied(prepared.id)
        else:
            assert await repository.fail(prepared.id, "upstream_failed")
            assert not await repository.fail(prepared.id, "late_failure")
            assert not await repository.complete(prepared.id, result)
            assert not await repository.mark_applied(prepared.id)
        assert await repository.claim(prepared.id) is None
    async with pool() as session:
        saved = await EffectRepository(session).get(prepared.id)
        assert saved.status == ("applied" if succeeds else "failed")
        assert saved.result == (result if succeeds else None)
        assert saved.error_code == (None if succeeds else "upstream_failed")


async def test_pending_work_is_bounded_and_excludes_claimed_operations(effect_session):
    pool, state = effect_session
    async with pool.begin() as session:
        repository = EffectRepository(session)
        for revision in range(102):
            await repository.prepare(operation(state, revision=revision))
    async with pool.begin() as session:
        repository = EffectRepository(session)
        batch = await repository.pending()
        assert len(batch) == len(set(batch)) == 100
        assert len(await repository.pending(5)) == 5
        await repository.claim(batch[0])
        assert batch[0] not in await repository.pending()
        for invalid in (0, -1, 101):
            with pytest.raises(ValueError):
                await repository.pending(invalid)


async def test_secret_handles_are_bound_to_owner_session_chat_and_strict_expiry(effect_session):
    pool, state = effect_session
    now = datetime.now(UTC)
    secret_id, expired_id = uuid4(), uuid4()
    ciphertext = "synthetic-encrypted-value"
    async with pool.begin() as session:
        repository = EffectRepository(session)
        await repository.put_secret(
            secret_id, state.id, state.user_id, state.chat_id, ciphertext, now + timedelta(minutes=5)
        )
        await repository.put_secret(expired_id, state.id, state.user_id, state.chat_id, "expired-ciphertext", now)
    async with pool.begin() as session:
        repository = EffectRepository(session)
        assert await repository.get_secret(secret_id, state.id, state.user_id, state.chat_id, now) == ciphertext
        for session_id, user_id, chat_id, checked_at in (
            (uuid4(), state.user_id, state.chat_id, now),
            (state.id, state.user_id + 1, state.chat_id, now),
            (state.id, state.user_id, state.chat_id + 1, now),
            (state.id, state.user_id, state.chat_id, now + timedelta(minutes=5)),
        ):
            assert await repository.get_secret(secret_id, session_id, user_id, chat_id, checked_at) is None
        assert await repository.get_secret(expired_id, state.id, state.user_id, state.chat_id, now) is None
        assert await repository.purge_expired(now) == 1
        assert await repository.get_secret(secret_id, state.id, state.user_id, state.chat_id, now) == ciphertext
    async with pool() as session:
        assert await session.scalar(select(func.count()).select_from(UiInputSecret)) == 1

    rolled_back_id = uuid4()
    async with pool.begin() as session:
        repository = EffectRepository(session)
        with pytest.raises(RuntimeError, match="secret scope failed"):
            async with repository.atomic():
                await repository.remove_secret(secret_id)
                await repository.put_secret(
                    rolled_back_id,
                    state.id,
                    state.user_id,
                    state.chat_id,
                    "rolled-back-ciphertext",
                    now + timedelta(minutes=5),
                )
                raise RuntimeError("secret scope failed")
        assert await repository.get_secret(rolled_back_id, state.id, state.user_id, state.chat_id, now) is None
        assert await repository.get_secret(secret_id, state.id, state.user_id, state.chat_id, now) == ciphertext
        await repository.remove_secret(secret_id)
    async with pool() as session:
        assert await session.scalar(select(func.count()).select_from(UiInputSecret)) == 0
